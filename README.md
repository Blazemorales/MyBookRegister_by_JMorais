# MyBookRegister — CEP + Lâmpada IoT (ESP32 · Raspberry Pi · Render · Vercel)

Projeto de **Controle Estatístico de Processo (CEP)** que usa uma lâmpada
12V DC controlada por ESP32 como "processo" de exemplo: a placa mede
temperatura/umidade (DHT11) e o tempo de uso da lâmpada, envia tudo em
tempo real para um backend estatístico, e um frontend web mostra cartas
de controle (X̄-R, P, U, I-MR), relatórios periódicos e permite controlar
a lâmpada remotamente — de qualquer lugar do mundo, sem VPN e sem porta
aberta no roteador.

O repositório é um **monorepo** com quatro partes que rodam em lugares
diferentes:

| Parte | Onde roda | Papel |
|---|---|---|
| `esp32_code/` | Microcontrolador ESP32 | Sensor + servidor web de controle da lâmpada |
| `raspberry_code/` | Raspberry Pi (em casa) | Broker MQTT, ponte MQTT→nuvem, proxy/túnel público |
| `cep_code/backend/` | Render (nuvem) | API + motor estatístico CEP + tempo real (Socket.IO) |
| `cep_code/frontend/` | Vercel (nuvem) | Dashboard web (Next.js) |

---

## Sumário

- [Visão geral e fluxo de dados](#visão-geral-e-fluxo-de-dados)
- [`esp32_code/` — firmware](#esp32_code--firmware)
- [`raspberry_code/` — Raspberry Pi](#raspberry_code--raspberry-pi)
  - [`cep_agent/` (papel principal atual)](#cep_agent-papel-principal-atual)
  - [nginx + Cloudflare Tunnel](#nginx--cloudflare-tunnel)
  - [Scripts legados (lâmpada via HTTP/MQTT direto)](#scripts-legados-lâmpada-via-httpmqtt-direto)
- [`cep_code/backend/` — API + motor CEP](#cep_codebackend--api--motor-cep)
- [`cep_code/frontend/` — dashboard web](#cep_codefrontend--dashboard-web)
- [Deploy e ambientes](#deploy-e-ambientes)
- [Rodando localmente (docker-compose)](#rodando-localmente-docker-compose)
- [Variáveis de ambiente — referência completa](#variáveis-de-ambiente--referência-completa)
- [Notas de manutenção / dívidas técnicas conhecidas](#notas-de-manutenção--dívidas-técnicas-conhecidas)
- [Troubleshooting](#troubleshooting)

---

## Visão geral e fluxo de dados

```
┌──────────┐  MQTT (LAN)   ┌──────────────┐  MQTT (localhost) ┌──────────────┐
│  ESP32   │──────────────►│  Mosquitto   │───────────────────►│  cep_agent   │
│ (DHT11 + │               │ (Raspberry   │                    │  (ingest.py, │
│  relé)   │◄──HTTP (nginx)│      Pi)     │                    │  na mesma Pi)│
└────┬─────┘   /on /off    └──────────────┘                    └──────┬───────┘
     │                                                                 │ Socket.IO
     │ servidor web próprio (porta 80)                                 │ (role=rpi)
     │                                                                 ▼
     │                                                        ┌─────────────────┐
     │                                                        │  Backend FastAPI │
     │                                                        │  + Socket.IO      │
     │                                                        │  (Render)          │
     │                                                        └────────┬────────┘
     │                                                                 │ Postgres
     │                                                                 │ + Socket.IO
┌────┴─────────────────────────────────────┐                          ▼
│  nginx (Pi) + Cloudflare Tunnel            │                ┌─────────────────┐
│  raspberry.mbrlamp.com.br  ───────────────►│                │  Frontend Next.js │
│  (proxy único: ESP32, stats, cep-agent)    │                │  (Vercel)          │
└─────────────────────────────────────────────┘                └─────────────────┘
```

Dois circuitos independentes, que se cruzam na Raspberry Pi:

1. **Controle da lâmpada (HTTP, síncrono)** — o navegador acessa
   `https://raspberry.mbrlamp.com.br`, o Cloudflare Tunnel entrega pro
   nginx da Pi, que repassa direto pra ESP32 (`/`, `/on`, `/off`,
   `/api/status`). Esse caminho **não depende do backend na nuvem** — a
   lâmpada liga/desliga mesmo se o Render/Vercel estiverem fora do ar.
   O frontend também expõe esses mesmos botões dentro da própria UI
   (`/dispositivos`), fazendo proxy server-side pra essa mesma URL.

2. **Telemetria CEP (MQTT → Socket.IO, assíncrono)** — a ESP32 publica
   temperatura/umidade e estado da lâmpada via MQTT no broker local
   (Mosquitto, na Pi). O `cep_agent` (rodando na mesma Pi) assina esses
   tópicos e retransmite cada leitura para o backend no Render via
   **Socket.IO**, que persiste no Postgres e faz broadcast em tempo real
   pro frontend. Uma vez por dia (ou sob demanda, pelo botão "Gerar
   relatório agora"), o `cep_agent` roda o motor estatístico (o mesmo
   código Python do backend, compartilhado) e publica um relatório
   consolidado (JSON + gráficos + PDF) de volta no backend.

**Por que a ESP32 fala MQTT com o IP local da Pi, e não com o domínio
público:** o Cloudflare Tunnel gratuito só repassa HTTP/HTTPS, não TCP
cru — então MQTT (porta 1883) só funciona com a ESP32 e a Pi na mesma
rede de casa. O domínio público só é usado para o controle HTTP da
lâmpada (item 1 acima), que continua funcionando de qualquer lugar do
mundo normalmente.

---

## `esp32_code/` — firmware

```
esp32_code/code_web/esp32s3_web_lampada_residencial/esp32_wroom_lampada_residencial/codigo_esp/
├── codigo_esp.ino          # firmware ativo
├── credenciais.h.example   # modelo de credenciais Wi-Fi (copiar para credenciais.h)
└── credenciais.h           # credenciais reais — git-ignored, nunca commitado
```

Sketch Arduino/C++ para ESP32 (testado em WROOM-32 e S3-N16R8). Bibliotecas:
`WiFi.h`/`WebServer.h`/`esp_wpa2.h` (core, nada a instalar), `PubSubClient`
(MQTT) e `DHT sensor library` (Adafruit).

**O que o firmware faz:**

- **Wi-Fi com fallback automático**: escaneia as redes visíveis e tenta
  conectar primeiro na rede UnB Wireless (WPA2-Enterprise), depois numa
  rede residencial (WPA2-Personal) — o que estiver no ar. Reconecta
  sozinho se a conexão cair (checado a cada iteração do `loop()`).
- **Servidor web embutido** (`WebServer`, porta 80): `GET /` (página HTML
  com botões Ligar/Desligar, cronômetro da sessão atual, temperatura e
  umidade — tudo client-side em JS puro, sem framework), `GET /on`,
  `GET /off` (acionam o relé via GPIO4 e respondem `text/plain "ok"`),
  `GET /api/status` (JSON com estado, tempo de sessão/total, umidade,
  temperatura — consultado pela própria página a cada 4s e pelo
  frontend indiretamente).
- **Relé** (GPIO4, módulo SRD-05VDC-SL-C, ativo-baixo): `relayOn()`/
  `relayOff()` também controlam a contagem de tempo de sessão
  (persistida em NVS via `Preferences`, sobrevive a reboots).
- **Cliente MQTT** (`PubSubClient`, broker = **IP local** da Raspberry
  Pi, porta 1883, sem TLS/autenticação — rede de confiança): publica
  `mbrlamp/lampada/estado` (ON/OFF, retained), `mbrlamp/lampada/
  tempo_sessao_s`/`tempo_total_s` (a cada 5s enquanto ligada),
  `mbrlamp/ambiente/temperatura`/`umidade` (a cada leitura do DHT11) e
  `jmorais/esp32s3/sensor/leitura` (`{"valor": <temperatura>}` — tópico
  dedicado que o `cep_agent` assina para alimentar o CEP). Também assina
  `mbrlamp/lampada/comando` (ON/OFF) para permitir acionamento via MQTT,
  além do HTTP.
- **DHT11**: leitura a cada 30s (`INTERVALO_DHT_MS`), publica
  temperatura/umidade mesmo com a lâmpada apagada.
- **Controle via Serial**: comandos `on`/`off` digitados no Monitor
  Serial (115200 baud) também acionam o relé — útil para testar sem
  rede.

**Hardware** (ver `esquematico_svg/`): ESP32 → GPIO4 → sinal do relé;
5V/VIN da ESP32 → VCC do relé (**nunca 3.3V** — a bobina do SRD-05VDC
precisa de ~5V pra engatar, mesmo que o LED de sinal acenda com 3.3V);
GND comum; contatos COM/NO do relé chaveiam a fonte 12V DC da lâmpada,
isolada eletricamente da lógica.

---

## `raspberry_code/` — Raspberry Pi

A Pi tem três papéis simultâneos hoje: broker MQTT local, ponte
MQTT→nuvem (`cep_agent`), e proxy/túnel público (nginx + `cloudflared`).

### `cep_agent/` (papel principal atual)

Serviço Python (FastAPI + APScheduler), roda como `cep-agent.service`
(systemd) direto na Pi, escutando em `:8080` (não exposto publicamente,
exceto a sub-rota `/run/diario` via nginx — ver abaixo).

```
raspberry_code/cep_agent/
├── app.py          # FastAPI: /health, /run/diario, /run/mensal, /reports/*/latest
├── config.py       # carrega .env, expõe todas as configs (tópicos MQTT, canal, etc.)
├── ingest.py       # ponte MQTT → Socket.IO (o coração do serviço)
├── scheduler.py    # APScheduler: diário 03:00 BRT, mensal dia 1 03:05 BRT
├── jobs/
│   ├── diario.py   # busca pontos do dia, roda o CEP, gera PDF, publica no backend
│   └── mensal.py   # agrega os relatórios diários do mês anterior
├── run_job.py       # dispara um job uma vez e sai (usado por Render Cron/GitHub Actions)
├── requirements.txt
└── Dockerfile        # permite rodar este serviço também no Render (ver raspberry_code/render*.yaml)
```

- **`ingest.py`**: mantém duas conexões simultâneas — cliente MQTT
  (Mosquitto local) e cliente Socket.IO assíncrono (`role=rpi`, backend
  no Render). Assina os tópicos que a ESP32 publica de verdade
  (`jmorais/esp32s3/sensor/leitura`, `mbrlamp/lampada/estado`,
  `mbrlamp/lampada/tempo_sessao_s`) e, para cada leitura de temperatura,
  agrupa em subgrupos de `XR_SUBGRUPO_N` pontos (carta X̄-R) além de
  emitir cada leitura individual (carta I-MR). Na transição ON→OFF da
  lâmpada, fecha a sessão como 1 ponto na carta I-MR do canal `lampada`
  (duração calculada a partir do último `tempo_sessao_s` publicado pela
  própria ESP32) e emite o estado ao vivo (`device_status`, no
  frontend) a cada mudança.
- **`jobs/diario.py`**: às 03:00 BRT (ou sob demanda via
  `POST /run/diario`), troca o `RPI_DEVICE_TOKEN` por um JWT de serviço
  (`POST /device/token` no backend), busca todos os pontos do dia
  (`GET /stream/diario`), reconstrói os datasets por carta, roda o
  **mesmo motor estatístico do backend** (`cep_code/backend/CEP/`,
  copiado pro container/checkout da Pi), gera os gráficos (matplotlib)
  e um PDF (fpdf2), e publica tudo em `POST /relatorios/diario` — dados
  + gráficos + PDF em base64, num único POST JSON. Também guarda uma
  cópia local em SQLite (`relatorios_locais.db`) para resiliência
  offline.
- **`app.py`**: `POST /run/diario`/`POST /run/mensal` (disparo manual,
  **exige header `X-RPI-Token`** igual ao `RPI_DEVICE_TOKEN` — esses
  endpoints são alcançáveis publicamente via nginx, então precisam de
  autenticação própria, independente do JWT usado nas chamadas REST ao
  backend).

Duas formas de rodar o agendamento (`SCHEDULER_ENABLED`/
`INGEST_ENABLED` em `config.py`): **tudo na Pi** (padrão — scheduler
interno via APScheduler + ingest com acesso ao broker local), ou
**scheduler no Render** (`render-free.yaml`, `run_job.py` disparado por
GitHub Actions cron — `INGEST_ENABLED=false`, já que essa instância não
alcança o broker MQTT da LAN; usada apenas para não depender da Pi
ficar ligada 24/7 para gerar os relatórios).

### nginx + Cloudflare Tunnel

`nginx-lampada.conf` (instalado via `setup_nginx_lampada.sh`) coloca a
Pi como **proxy reverso único** na frente de tudo que precisa ser
público, e o `cloudflared` aponta um único hostname
(`raspberry.mbrlamp.com.br`) pra `http://localhost:80`:

| Rota pública | Proxy pra | Propósito |
|---|---|---|
| `/`, `/on`, `/off`, `/api/status` | ESP32 (IP local, porta 80) | Controle e status da lâmpada |
| `/stats/hoje` | `lampada_stats.py` (`:5001`) | Estatística legada (ver abaixo) |
| `/cep-agent/*` | `cep_agent` (`:8080`) | Disparo manual de relatório (`/cep-agent/run/diario`) |

`POST /lampada` (ingestão de eventos do pipeline legado) **não** é
exposta publicamente — não tem autenticação própria.

### Scripts legados (lâmpada via HTTP/MQTT direto)

Estes arquivos existem no repositório mas **não fazem parte do fluxo
ativo hoje** — o firmware atual não os invoca. Mantidos por
compatibilidade/histórico; considerar remover ou revalidar (ver
[Notas de manutenção](#notas-de-manutenção--dívidas-técnicas-conhecidas)):

- **`control_led.py`** + `led-api.service` — API Flask alternativa
  (`/led/on|off|toggle|state`) que traduz HTTP em comandos MQTT pra uma
  variante do firmware que não hospeda página própria. Hoje ocupa a
  porta **5000** na Pi sem ser referenciada pelo nginx atual.
- **`lampada_stats.py`** + `lampada-stats.service` — recebia
  `POST /lampada {"aceso": bool}` da ESP32 (via um `RASPBERRY_URL` que
  o firmware atual não tem mais) e calculava duração de sessões,
  publicando em MQTT (`jmorais/lampada/sessao`, `jmorais/lampada/
  status`) para o `cep_agent` antigo consumir. Roda na porta **5001**.
  `GET /lampada/hoje` (exposto via `/stats/hoje` no nginx) ainda
  funciona para consultar o acumulado do dia, mas os dados só chegam
  aqui se algo voltar a POSTar pra ele.
- **`gerar_relatorio_lampada.py`** + `lampada-relatorio.{service,timer}`
  — fechava um JSON diário de horas de uso a partir dos eventos que
  `lampada_stats.py` registrava em `dados_lampada/eventos.jsonl`.
- **`mqtt_test.py`**, **`setup_mosquitto.sh`**, **`local.conf`** —
  utilitário de teste MQTT e instalação/config do broker Mosquitto
  (esse último **ainda é usado** — é o broker real que `ingest.py` e a
  ESP32 usam).
- **`esp32-watchdog.sh`** + `.service` — loga no journal quando a ESP32
  fica online/offline, observando o LWT/disponibilidade MQTT (recurso
  do firmware MQTT antigo, não presente no `codigo_esp.ino` atual).

---

## `cep_code/backend/` — API + motor CEP

Serviço FastAPI + Socket.IO num único processo ASGI, deployado no
Render como `tpe-backend` (Docker, `render.yaml` na raiz do repo,
`healthCheckPath: /health`, `autoDeployTrigger: commit`).

```
cep_code/backend/
├── backend_api.py       # entrypoint: monta FastAPI + Socket.IO, CORS, /login /register /me
├── auth.py               # JWT (HS256): create_access_token, get_current_user, decode_token
├── realtime.py           # servidor Socket.IO: rooms, rate-limit, validação, persistência
├── cep_routes.py         # /upload /processar /results/cep/{chart} /relatorio/{chart}
├── periodicos_routes.py  # /device/token /stream/* /relatorios/*
├── cep_pipeline.py       # adapta amostras do banco para os módulos CEP/*, em memória
├── cep_alertas.py        # análise CEP em streaming (Nelson + Kalman), usado por realtime.py
├── schema.sql             # tabelas Postgres
├── Login/
│   └── async_model.py    # AsyncDBUserManager — pool asyncpg, todo o acesso a dados
└── CEP/
    ├── parametros_enunciado.py   # fonte única dos parâmetros fixos (PPM, margem-alvo, etc.)
    ├── constantes.py             # tabela A2/D3/D4/d2 por tamanho de subgrupo
    ├── analise.py                # fórmulas de capacidade/ppm/binomial (scipy)
    ├── respostas.py              # monta o "answer set" (Q1 variáveis + Q2 atributos)
    ├── amostras/data_processor.py # DataProcessor: XR, P, U, I-MR a partir de dados brutos
    └── cartas_controle/Cartas.py  # gera gráficos (matplotlib) + PDF (fpdf2) por carta
```

**Autenticação**: usuário/senha (`pbkdf2_sha256` via `passlib`) em
`users`, JWT HS256 (`SECRET_KEY`, expira em `ACCESS_TOKEN_EXPIRE_MINUTES`,
default 60min). A Raspberry Pi usa um mecanismo **separado**: troca um
`RPI_DEVICE_TOKEN` (segredo compartilhado, fixo) por um JWT de serviço
de 24h via `POST /device/token` — esse JWT não corresponde a nenhum
usuário real no banco (`_get_rpi_or_user` trata os dois casos).

**Tempo real (`realtime.py`)**: Socket.IO com dois papéis de conexão —
`role=frontend` (JWT de usuário, entra na room `receber_relatorio`,
pode pedir replay do histórico) e `role=rpi` (token de dispositivo,
fail-closed se não configurado). Evento `rpi_data` (ou alias `report`)
é validado, redistribuído (`relatorio_data`), persistido em background
(`medicoes_stream`, tabela append-only) e passa por análise incremental
(`cep_alertas.py` — regras de Nelson + filtro de Kalman 1D) que pode
emitir `alerta_cep`. Evento `rpi_status` é mais simples: só repassa
`device_status` pro frontend, sem persistir (é um flag efêmero de
"ligado/desligado").

**Cartas de controle implementadas**: X̄-R (médias/amplitudes por
subgrupo), P (proporção de defeituosos), U (defeitos por unidade),
I-MR (individuais + amplitude móvel — é a usada pela lâmpada/CEP deste
projeto). Fórmulas seguem Montgomery, *Introduction to Statistical
Quality Control* (comentários no código citam os números das equações).

**Banco de dados**: Postgres (Neon/Supabase/Render Postgres — qualquer
um compatível com `asyncpg`). Tabelas: `users`, `amostras` (upload
bruto), `resultados` (saída do pipeline + PDF cacheado), `medicoes_stream`
(stream bruto do Socket.IO, alimenta replay), `relatorios_periodicos`
(relatórios diário/mensal da Pi, com PDF). Ver `schema.sql`.

**Rotas HTTP principais** (lista completa no código, resumo aqui):
`POST /login|/register`, `GET /me`, `POST /token/refresh`, `POST /upload`,
`GET /processar`, `GET /results/cep/{chart}`, `GET /relatorio/{chart}`
(PDF), `POST /device/token`, `GET /stream/diario|periodo`,
`POST /relatorios/{tipo}`, `GET /relatorios/{tipo}/latest|{periodo}|/pdf|/list`,
`GET /health`, `GET /health/db`.

---

## `cep_code/frontend/` — dashboard web

Next.js 16 (App Router) + React 19 + Tailwind v4, deployado no Vercel.
Todas as chamadas ao backend passam por rotas `app/api/*` (Route
Handlers) que rodam **server-side** — o JWT do backend nunca é exposto
ao browser, exceto via `/api/socket-token` (necessário só para o
handshake do Socket.IO, que roda no cliente).

```
cep_code/frontend/
├── app/
│   ├── (app)/                 # rotas autenticadas
│   │   ├── page.tsx            # menu principal
│   │   ├── cep/page.tsx        # "Minhas Estatísticas": Calibrador, Validador, Relatórios
│   │   ├── dispositivos/page.tsx # "Meus dispositivos": lâmpada, temperatura ao vivo, sessões
│   │   └── ao-vivo/page.tsx    # stream bruto de qualquer canal (debug/demo)
│   ├── login/page.tsx           # login/registro
│   ├── api/                    # proxies server-side pro backend e pra Raspberry Pi
│   ├── components/
│   │   ├── calibrar/            # fluxo "Calibrador" (PDF gerado no backend)
│   │   ├── validar/              # fluxo "Validador" (PDF gerado no cliente via jsPDF)
│   │   └── cep/                 # RespostasViewer, RelatoriosPeriodicos, TemperaturaAoVivo
│   ├── lib/                     # auth (HMAC), backend (URLs/headers), rate limit, estatística
│   └── manifest.ts               # PWA
├── hooks/                        # useRelatorioStream (Socket.IO), useRelatoriosPeriodicos, ...
└── proxy.ts                       # middleware de autenticação (Next 16: não é middleware.ts)
```

### Autenticação e sessão

Dois cookies httpOnly separados: `__Host-cep_session` (sessão do
frontend, assinada com HMAC-SHA256 usando `AUTH_SECRET`, 30 min) e
`__Host-cep_backend_jwt` (o JWT bruto devolvido pelo backend no login,
usado só server-side). `proxy.ts` (middleware) bloqueia rotas sem
sessão válida, redireciona pra `/login`, e cai em `/acesso-negado` se
`AUTH_SECRET` não estiver configurada. `SessionWatcher` avisa 2 minutos
antes da sessão expirar, com opção de estender (`POST /api/refresh`).
Rate limit de 5 tentativas/5min por IP em login/registro (Upstash Redis
se configurado, senão em memória por instância).

### `/cep` — Calibrador e Validador

- **Calibrador** (`RelatorioViewer` + `useCepRelatorio`): duas
  sub-abas — processar dados já enviados por dispositivos (botão
  "Processar Dados" → `/api/processar`) ou fazer upload de um `.json`
  de medições (`/api/upload`). Depois, "Gerar Relatório" busca o PDF
  pronto do backend (`/api/relatorio/{tipo}`, matplotlib server-side) e
  mostra num `<iframe>`, junto com as respostas estruturadas
  (`RespostasViewer` → `/api/respostas/{tipo}`).
- **Validador** (`Validar` + `app/lib/stats.ts`): calculadora
  estatística independente — probabilidades pela Normal, ARL/CMC
  (fórmula de Shewhart), regras de Western Electric. Dois modos de
  gerar PDF, **ambos no cliente** via `jsPDF`: manual (a partir de
  parâmetros digitados na tela) ou automático (carrega parâmetros
  direto de um resultado do backend via `/api/results/{chart}` e
  recalcula tudo com um motor de PDF mais completo,
  `app/lib/pdfValidacao.ts`).
- **Relatórios periódicos** (`RelatoriosPeriodicos` +
  `useRelatoriosPeriodicos`): abas Diário/Mensal, lê
  `/api/relatorios-periodicos/{tipo}` (proxy pro backend).

### `/dispositivos` — lâmpada + temperatura ao vivo

- **Card de status da lâmpada**: liga/desliga por botões nativos
  (`POST /api/lampada/on|off` → proxy server-side pra
  `https://raspberry.mbrlamp.com.br/{on,off}` — o browser nunca vê o
  domínio da Pi), com estado otimista até a confirmação real chegar via
  Socket.IO (`device_status`).
- **`TemperaturaAoVivo`**: gráfico Recharts em tempo real (canal
  `default`, via `useRelatorioStream`), com **Carta I de verdade** —
  calcula LC/LSC/LIC no cliente com a mesma fórmula do backend
  (`sigma = amplitude_móvel_média / 1.128`, `LSC/LIC = média ± 3σ`) e
  destaca em vermelho quando a última leitura sai de controle.
- **Últimas Sessões**: lista as sessões (liga→desliga) da lâmpada,
  reconstruídas pelo `cep_agent` a partir dos tópicos MQTT que a ESP32
  já publica.
- **Botão "Gerar relatório agora"**: `POST /api/lampada-relatorio` →
  proxy pra `https://raspberry.mbrlamp.com.br/cep-agent/run/diario`
  (autenticado com `RASPBERRY_CEP_AGENT_TOKEN`) — dispara o job diário
  do `cep_agent` sob demanda, sem esperar o agendamento das 03:00 BRT.

### PWA

`manifest.ts` + `public/sw.js` (service worker mínimo — só existe para
o Android reconhecer o app como instalável, sem cache offline real).

---

## Deploy e ambientes

| Ambiente | Onde | Config |
|---|---|---|
| Backend (`tpe-backend`) | Render, Docker | `render.yaml` (raiz) |
| Frontend | Vercel | `cep_code/frontend/` (build Next.js nativo) |
| `cep_agent` (produção) | Raspberry Pi, systemd (`cep-agent.service`) | `raspberry_code/cep_agent/.env` |
| `cep_agent` (alternativa sem Pi 24/7) | Render, Docker, `run_job.py` + GitHub Actions cron | `raspberry_code/render-free.yaml` |
| Broker MQTT | Raspberry Pi (Mosquitto) | `raspberry_code/local.conf` |
| Túnel público | Raspberry Pi (`cloudflared`) → `raspberry.mbrlamp.com.br` | painel Cloudflare Zero Trust |
| Banco de dados | Postgres externo (Neon/Supabase/Render Postgres) | `DATABASE_URL` no backend |

O deploy do backend e do frontend é automático por commit (push na
`main` → Render e Vercel redesployam sozinhos). Mudanças em
`raspberry_code/cep_agent/` e `raspberry_code/nginx-lampada.conf`
**não** são automáticas — exigem `git pull` na Pi e reiniciar o serviço
correspondente (`systemctl restart cep-agent`, ou `nginx -t && systemctl
reload nginx`) manualmente.

---

## Rodando localmente (docker-compose)

```bash
cp .env.example .env   # preencher SECRET_KEY e AUTH_SECRET (gerar com
                        # python -c "import secrets; print(secrets.token_hex(32))")
docker compose up
```

Sobe Postgres + backend (`:8000`) + frontend (`:3000`). Health checks
garantem a ordem de subida (frontend espera o backend responder
`/health`). Para simular a Raspberry Pi sem hardware real:

```bash
docker compose --profile sim up
```

Isso sobe também o `rpi-sim` (`cep_code/backend/rpi_simulator.py`),
que conecta via Socket.IO como `role=rpi` e emite leituras aleatórias
periodicamente — útil para testar o pipeline de tempo real sem ESP32.

---

## Variáveis de ambiente — referência completa

### Backend (Render / docker-compose)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `SECRET_KEY` | sim | Assinatura dos JWT (gerada automaticamente no Render) |
| `DATABASE_URL` | sim | Postgres (`postgresql://...`, incluir `?sslmode=require` no Neon/Supabase) |
| `RPI_DEVICE_TOKEN` | sim | Segredo compartilhado com a Raspberry Pi |
| `ALLOWED_ORIGINS` | sim | CORS + Socket.IO, separado por vírgula (URL do frontend) |
| `REDIS_URL` | não | `AsyncRedisManager` do Socket.IO p/ múltiplas instâncias |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | não | default 60 |
| `RPI_RATE_LIMIT_HZ` | não | limite de mensagens/s por conexão RPi (default 20) |
| `STREAM_REPLAY_MAX` | não | máximo de pontos no replay (default 200) |
| `CEP_JANELA_MIN`/`MAX` | não | janela do CEP em streaming (default 20/200) |
| `KALMAN_Q`/`KALMAN_R` | não | filtro de Kalman 1D (ruído processo/medida) |
| `DESLOCAMENTO_PCT` | não | limiar de alerta de deslocamento via Kalman |

### Frontend (Vercel)

| Variável | Obrigatória | Descrição |
|---|---|---|
| `AUTH_SECRET` | sim | HMAC da sessão do frontend |
| `CEP_API_URL` | sim | URL do backend (Render) — **nunca** o domínio da Pi |
| `NEXT_PUBLIC_SOCKET_URL` | sim | Mesma URL do backend, usada pelo browser no Socket.IO (sem ela, tempo real quebra em produção) |
| `RASPBERRY_LAMPADA_URL` | não | default `https://raspberry.mbrlamp.com.br` |
| `RASPBERRY_CEP_AGENT_TOKEN` | sim (p/ botão de relatório) | mesmo valor do `RPI_DEVICE_TOKEN` da Pi |
| `UPSTASH_REDIS_REST_URL`/`_TOKEN` | não | rate limit de login distribuído |
| `RELATORIO_CACHE_TTL_MS` | não | cache em memória dos PDFs do Calibrador (default 60000) |

### `cep_agent` (Raspberry Pi / Render alternativo)

Ver `raspberry_code/cep_agent/.env.example` — inclui `BACKEND_URL`,
`RPI_DEVICE_TOKEN`, `MQTT_BROKER`/`PORT`, `CANAL`/`CANAL_LAMPADA`,
`XR_SUBGRUPO_N`, `SCHEDULER_ENABLED`, `INGEST_ENABLED`.

---

## Notas de manutenção / dívidas técnicas conhecidas

Registrado aqui para quem for mexer no código depois:

- **`cep_code/backend/Login/auth.py`** é uma cópia antiga de
  `cep_code/backend/auth.py`, não importada por nenhum módulo — código
  morto, candidato a remoção.
- **`cep_code/backend/CEP/cep_alertas.py`** é idêntico a
  `cep_code/backend/cep_alertas.py` (raiz) — só a cópia da raiz é
  importada por `realtime.py`; a de dentro de `CEP/` é redundante.
- **`app/acesso-negado/page.tsx`** (frontend) menciona uma variável
  `USERS` que não existe mais no código (a autenticação migrou pra
  `/login`/`/register` no backend) — texto desatualizado.
- **`NEXT_PUBLIC_API_BASE`** e **`RELATORIO_CACHE_TTL_MS`** (frontend)
  são lidas no código mas não estavam documentadas — corrigido nesta
  versão do README.
- **Pipeline legado da lâmpada** (`lampada_stats.py`, `control_led.py`
  e os serviços/timers associados) está desconectado do firmware atual
  — ver [seção correspondente](#scripts-legados-lâmpada-via-httpmqtt-direto).
  Os dados reais de sessão/status hoje vêm do `cep_agent` lendo os
  tópicos MQTT nativos da ESP32, não desse pipeline antigo.
- **Domínio da Cloudflare Tunnel gratuito não expõe TCP cru** — por
  isso o MQTT da ESP32 aponta pro IP local da Pi, não pro domínio
  público. Se a ESP32 algum dia precisar operar fora da rede de casa,
  isso vai quebrar e precisa de outra solução (ex.: MQTT sobre
  WebSockets, ou Cloudflare Spectrum).

---

## Troubleshooting

### ESP32

| Problema | Solução |
|----------|---------|
| Porta não aparece no IDE | Cabo USB de dados (não só carga); Linux: `sudo usermod -a -G dialout $USER` + logout |
| Upload trava em `Connecting...` | Segure BOOT, toque RESET, solte BOOT durante a gravação |
| Não conecta em nenhuma rede | `credenciais.h` existe e preenchido? Rede é 2.4GHz (ESP32 não usa 5GHz)? |
| Relé clica mas lâmpada não acende | Fiação do lado 12V: +12V→COM, NO→lâmpada(+), lâmpada(−)→GND da fonte |
| Relé não clica, LED de sinal acende | VCC do módulo relé no pino errado (3.3V) — precisa de 5V/VIN |

### Raspberry Pi / túnel

| Problema | Solução |
|----------|---------|
| `cloudflared` não inicia | `journalctl -u cloudflared -n 50`; token colado errado é a causa mais comum |
| URL pública abre em branco/502 | A Pi não alcança a ESP32: `curl -I http://<IP_da_ESP32>` na Pi; IP mudou? (reservar no DHCP) |
| `/cep-agent/run/diario` dá 401 | Header `X-RPI-Token` errado ou ausente |
| CEP não recebe dado nenhum | `journalctl -u cep-agent -f`; confira `MQTT conectado`/`Socket.IO conectado` nos logs |

### Backend / frontend

| Problema | Solução |
|----------|---------|
| Login falha com "Falha ao contatar o serviço de autenticação" | Cold-start do Render free tier (10s de timeout no frontend); tente de novo em ~30s |
| "Temperatura ao vivo" trava em "conectando"/timeout | Confira `NEXT_PUBLIC_SOCKET_URL` no Vercel; o WebSocket pode falhar no Render, mas o socket.io-client deve cair pro polling automaticamente (não force `transports:["websocket"]`) |
| Relatório sempre "não disponível" | Confira `CEP_API_URL` no Vercel (não pode ser o domínio da Pi) e se o `cep_agent` já publicou algum relatório (`journalctl -u cep-agent`) |

---

## Licença

Projeto de estudo (TPE) — use, modifique e compartilhe à vontade.
