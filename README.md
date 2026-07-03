# 💡 Lâmpada IoT — ESP32 + Raspberry Pi + Cloudflare Tunnel

Controle uma lâmpada **DC 12V** de qualquer lugar: a **ESP32** hospeda um
servidor web e aciona a lâmpada através de um **módulo relé**; a
**Raspberry Pi** roda o **Cloudflare Tunnel**, que expõe esse controle na
internet com HTTPS — sem abrir portas no roteador e sem IP fixo.

---

## 📋 Sumário

- [Visão geral](#-visão-geral)
- [Hardware necessário](#-hardware-necessário)
- [Configuração do ESP32](#-configuração-do-esp32)
- [Configuração da Raspberry Pi (Tunnel)](#-configuração-da-raspberry-pi-tunnel)
- [Estatísticas de uso (opcional)](#-estatísticas-de-uso-opcional)
- [Estrutura do projeto](#-estrutura-do-projeto)
- [Troubleshooting](#-troubleshooting)

---

## 🔭 Visão geral

O fluxo completo do projeto:

```
navegador (qualquer lugar)
        │  HTTPS
        ▼
Cloudflare Tunnel  ◄── cloudflared rodando na Raspberry Pi
        │  HTTP (rede local)
        ▼
ESP32 (servidor web embutido)
        │  GPIO4
        ▼
Módulo relé 5V (SRD-05VDC-SL-C)
        │  contatos COM/NO
        ▼
Lâmpada DC 12V  (fonte 12V própria, via jack P4)
```

**Como as placas trabalham juntas:**

- A **ESP32** conecta no Wi-Fi de casa e sobe uma página web com botões
  Ligar / Desligar / Alternar. Quando você aperta um botão, ela muda o nível do
  GPIO4, que aciona o relé — e o relé fecha o circuito da lâmpada.
- A **Raspberry Pi** não controla a lâmpada: o papel dela é rodar o
  `cloudflared`, criando um túnel de saída até a Cloudflare. Quem acessa a URL
  pública chega até a página da ESP32 sem que nenhuma porta do roteador seja
  aberta.
- A Pi também funciona como um **segundo cérebro**: a cada vez que a ESP32
  liga/desliga a lâmpada, ela manda um evento pra Pi (`RASPBERRY_URL` no
  `.ino`), que registra a duração de cada sessão e, uma vez por dia, fecha um
  JSON com as horas em que a lâmpada ficou acesa (veja
  [Estatísticas de uso](#-estatísticas-de-uso-opcional)).
- A carga (12V) fica **isolada** da parte lógica pelos contatos do relé.

---

## 🔩 Hardware necessário

| Item | Observação |
|------|------------|
| ESP32 (DevKit) | Testado com ESP32-S3-N16R8 e ESP32 WROOM-32 |
| Módulo relé 1 canal 5V | SONGLE SRD-05VDC-SL-C (tipo KY-019) |
| Lâmpada **DC 12V** + bocal | ⚠️ NÃO usar lâmpada de tomada (AC) |
| Fonte 12V DC com jack P4 | Corrente ≥ a da lâmpada, com folga |
| Raspberry Pi (3B ou melhor) | Com Raspberry Pi OS instalado |
| Fios | Rígido 22 AWG p/ sinais; flexível 18–20 AWG p/ a carga |

**Ligações do relé:**

```
ESP32           Módulo relé          Carga
─────           ───────────          ─────
GPIO4  ───────► S  (sinal)
5V/VIN ───────► +  (VCC)             +12V (fonte) ───► COM
GND    ───────► −  (GND)             NO ────────────► lâmpada (+)
                                     lâmpada (−) ───► GND da fonte 12V
```

> ⚠️ O **+** do módulo vai no pino **5V/VIN** da ESP32 — **nunca no 3V3**.
> A ordem S/+/− e NO/COM/NC varia por fabricante: siga a serigrafia do seu módulo.

---

## ⚙️ Configuração do ESP32

### 1. Instalar o Arduino IDE e o suporte à ESP32

1. Baixe o [Arduino IDE 2.x](https://www.arduino.cc/en/software).
2. Abra **File → Preferences** e, em *Additional Boards Manager URLs*, cole:
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Vá em **Tools → Board → Boards Manager**, busque **esp32** e instale o
   pacote **"esp32 by Espressif Systems"** (série 3.x).

### 2. Selecionar a placa

| Sua placa | Board no IDE | Ajustes |
|-----------|--------------|---------|
| ESP32 WROOM-32 | **ESP32 Dev Module** | Tudo no padrão |
| ESP32-S3-N16R8 | **ESP32S3 Dev Module** | PSRAM = `OPI PSRAM` · Flash Size = `16MB` · USB CDC On Boot = `Enabled` |

> ⚠️ Na S3-N16R8, errar o PSRAM (OPI) causa travamento/boot loop.

### 3. Bibliotecas

O firmware web usa só bibliotecas que **já vêm no core** (`WiFi.h`,
`WebServer.h`, `ESPmDNS.h`) — nada a instalar.
(Somente a variante MQTT exige a **PubSubClient**, via Library Manager.)

### 4. Configurar e carregar o sketch

1. Abra `esp32s3_web_lampada.ino`.
2. Edite o topo do arquivo:
   ```cpp
   const char* WIFI_SSID     = "SUA_REDE";
   const char* WIFI_PASSWORD = "SUA_SENHA";
   ```
3. Conecte a placa por USB e selecione a porta em **Tools → Port**
   (Linux: `/dev/ttyACM0` ou `/dev/ttyUSB0`; Windows: `COMx`).
4. Clique em **Upload** (→).
   - Se travar em `Connecting...`: segure **BOOT**, toque **RESET**, solte.
5. Abra o **Serial Monitor** a `115200` e anote o IP:
   ```
   [WiFi] OK!  Acesse:  http://192.168.0.42   ou   http://lampada.local
   ```

> 💡 Depois de gravado, o sketch fica salvo na flash: a ESP32 roda sozinha em
> qualquer fonte USB 5V, sem PC. Recomenda-se criar uma **reserva de DHCP** no
> roteador para o IP dela nunca mudar (o túnel aponta para esse IP).

> 🐧 Linux: se a porta não aparecer, rode
> `sudo usermod -a -G dialout $USER` e faça logout/login.

### 5. Testar na rede local

No celular/PC (mesmo Wi-Fi), abra `http://<IP_da_ESP32>` — a página com os
botões deve aparecer e o relé deve "clicar" ao comandar.

---

## 🌐 Configuração da Raspberry Pi (Tunnel)

Pré-requisito: um **domínio gerenciado pela Cloudflare** (o plano Free serve).

### 1. Instalar o cloudflared

```bash
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | \
  sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared bookworm main" | \
  sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install -y cloudflared
```

### 2. Criar o túnel (pelo dashboard)

1. Acesse [one.dash.cloudflare.com](https://one.dash.cloudflare.com) →
   **Networks → Tunnels → Create a tunnel** → tipo **Cloudflared**.
2. Dê um nome (ex.: `lampada`) e copie o comando com o **token**.
3. Na Pi, rode (instala como serviço e sobe no boot):
   ```bash
   sudo cloudflared service install <SEU_TOKEN>
   ```

### 3. Apontar o túnel para a ESP32

No dashboard do túnel, aba **Public Hostname**:

| Campo | Valor |
|-------|-------|
| Subdomain | `lampada` (exemplo) |
| Domain | seu domínio |
| Service | **HTTP** → `http://<IP_da_ESP32>:80` |

Pronto: `https://lampada.seudominio.com` abre a página da ESP32 de qualquer lugar.

### 4. Controlar remotamente (linha de comando)

Com o hostname configurado, esses comandos funcionam de **qualquer rede** —
4G, outra cidade, outro país:

```bash
curl https://lampada.seudominio.com/on       # liga
curl https://lampada.seudominio.com/off      # desliga
curl https://lampada.seudominio.com/toggle   # alterna
curl https://lampada.seudominio.com/state    # {"aceso":true,"ligadoHa":123}
```

Pelo navegador, `https://lampada.seudominio.com/` abre a mesma página com os
três botões que aparece na rede local.

### 5. Proteger o acesso (importante!)

Sem proteção, **qualquer pessoa com a URL controla sua lâmpada**. No Zero Trust:
**Access → Applications → Add application** → selecione o hostname → crie uma
política exigindo login (Google ou e-mail com código OTP).

Depois de criar a política, chamadas automatizadas (script, atalho no
celular) que não passam por login de navegador precisam de um **Service
Token** (Access → Service Auth → Create Service Token):

```bash
curl https://lampada.seudominio.com/on \
  -H "CF-Access-Client-Id: <ID>" \
  -H "CF-Access-Client-Secret: <SECRET>"
```

### 6. Verificar se o túnel está funcionando

```bash
systemctl status cloudflared --no-pager   # deve estar "active (running)"
journalctl -u cloudflared -n 30           # logs recentes
curl -I http://<IP_da_ESP32>              # a Pi enxerga a ESP32? (HTTP 200)
```
No dashboard, o túnel deve aparecer como **HEALTHY**. Teste a URL pública
fora do Wi-Fi de casa (4G/5G).

> 💡 Teste rápido sem domínio:
> `cloudflared tunnel --url http://<IP_da_ESP32>:80`
> gera uma URL `*.trycloudflare.com` temporária (some ao fechar o comando).

---

## 📊 Estatísticas de uso (opcional)

Além do túnel, a Pi pode virar um **segundo cérebro**: ela recebe um evento
da ESP32 a cada vez que a lâmpada liga/desliga e, uma vez por dia, fecha um
JSON com o total de horas em que a lâmpada ficou acesa.

```
ESP32 ──POST /lampada──► lampada_stats.py (Flask, :5000, na Pi)
                              │ grava eventos.jsonl / estado.json
                              ▼
              gerar_relatorio_lampada.py (systemd timer, 23:59 BRT)
                              │
                              ▼
              dados_lampada/relatorio_<data>.json
```

### 1. Apontar a ESP32 pra Pi

No `esp32s3_web_lampada.ino`, edite (junto com `WIFI_SSID`/`WIFI_PASSWORD`):

```cpp
const char* RASPBERRY_URL = "http://<IP_da_Pi>:5000/lampada";
```

Use o mesmo cuidado do IP da ESP32: reserve o IP da Pi no DHCP do roteador
pra ele nunca mudar.

### 2. Subir o receptor de eventos na Pi

```bash
cd /home/pi/MyBookRegister_by_JMorais/raspberry_code
python3 -m venv /home/pi/MyBookRegister_by_JMorais/venv_lampada
/home/pi/MyBookRegister_by_JMorais/venv_lampada/bin/pip install -r requirements.txt

sudo cp lampada-stats.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lampada-stats
sudo systemctl status lampada-stats --no-pager
```

Teste manual: ligue/desligue a lâmpada pela página da ESP32 e confira

```bash
curl http://localhost:5000/lampada/hoje
```

### 3. Agendar o relatório diário

```bash
sudo cp lampada-relatorio.service lampada-relatorio.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lampada-relatorio.timer
systemctl list-timers lampada-relatorio.timer --no-pager
```

O relatório do dia fica em `raspberry_code/dados_lampada/relatorio_<data>.json`,
por exemplo:

```json
{
  "data": "2026-07-02",
  "segundos_ligada": 5400.0,
  "horas_ligada": 1.5,
  "ciclos_liga_desliga": 3
}
```

Pra fechar um dia específico na mão (ex.: recuperar um dia perdido):
`gerar_relatorio_lampada.py 2026-07-01`.

> 💡 A duração de cada sessão é calculada pelo relógio da própria Pi (não pelo
> `ligadoHa` da ESP32), então sobrevive a reboots da placa. Se a Pi ficar
> desligada na hora do timer (23:59), `Persistent=true` faz ele rodar assim
> que ela voltar.

---

## 📁 Estrutura do projeto

```
.
├── esp32_code/
│   ├── code_web/esp32s3_web_lampada/esp32s3_web_lampada.ino   # Firmware principal (web + túnel)
│   └── code_bluetooth/esp32_ble_lampada/esp32_ble_lampada.ino # Variante Bluetooth (BLE, controle local)
├── raspberry_code/
│   ├── control_led.py             # (Só p/ variante MQTT) API Flask na Pi
│   ├── led-api.service            # (Só p/ variante MQTT) serviço systemd
│   ├── lampada_stats.py           # Receptor de eventos da ESP32 (POST /lampada)
│   ├── lampada-stats.service      # Serviço systemd do receptor
│   ├── gerar_relatorio_lampada.py # Fecha o JSON diário de horas ligada
│   ├── lampada-relatorio.service  # Job (oneshot) do relatório diário
│   ├── lampada-relatorio.timer    # Agenda o job diário (23:59 BRT)
│   ├── dados_lampada/             # eventos.jsonl, estado.json, relatorio_<data>.json (gerados em runtime)
│   └── README_raspberry.md        # Guia do lado da Pi (variante MQTT)
├── esquematico_svg/           # Desenho das ligações (relé + ESP32 + lâmpada)
└── README.md                  # Este arquivo
```

**Qual firmware usar?**
- `esp32s3_web_lampada.ino` — o principal (web + túnel). Comece por ele.
- `esp32s3_mqtt_led.ino` — se quiser integrar com automação/Home Assistant.
- `esp32_ble_lampada.ino` — controle local pelo celular via Bluetooth (sem Wi-Fi).

---

## 🔧 Troubleshooting

### ESP32

| Problema | Solução |
|----------|---------|
| Porta não aparece no IDE | Cabo USB de **dados** (não só carga); no Linux, `sudo usermod -a -G dialout $USER` + logout |
| Upload trava em `Connecting...` | Segure **BOOT**, toque **RESET**, solte BOOT durante a gravação |
| S3 reinicia em loop após gravar | PSRAM errado — na S3-N16R8 use **OPI PSRAM** e Flash 16MB |
| Serial Monitor vazio (S3) | Ative **USB CDC On Boot = Enabled** e regrave |
| Não conecta no Wi-Fi | SSID/senha corretos? Rede é **2.4 GHz**? (ESP32 não usa 5 GHz) |
| Relé aciona invertido (liga quando devia desligar) | Módulo ativo-baixo: troque `LED_ATIVO_ALTO`/`RELE_ATIVO_ALTO` para `false` |
| Relé não aciona com 3,3V | Alguns módulos pedem 5V no sinal: alimente o **+** com 5V; persiste → use módulo com optoacoplador ou transistor no sinal |
| Lâmpada não acende, relé clica | Confira a carga: +12V→COM, NO→lâmpada(+), lâmpada(−)→GND da fonte; teste a fonte com multímetro |
| `http://lampada.local` não abre no Android | Alguns Androids não resolvem mDNS: use o IP direto (faça reserva de DHCP) |

### Raspberry Pi / Tunnel

| Problema | Solução |
|----------|---------|
| `cloudflared` não inicia | `journalctl -u cloudflared -n 50` para ver o erro; token colado errado é a causa mais comum |
| Túnel "DOWN" no dashboard | Pi com internet? `ping 1.1.1.1`; reinicie: `sudo systemctl restart cloudflared` |
| URL pública abre em branco / 502 | A Pi não alcança a ESP32: `curl -I http://<IP_da_ESP32>` na Pi; confira se o IP da ESP32 mudou (→ reserva de DHCP) |
| URL funciona em casa, mas não no 4G | DNS ainda propagando (aguarde alguns minutos) ou política de Access bloqueando seu login |
| Página pública pede login que não chega | No Access, confira o método (e-mail OTP: veja spam; Google: use a conta cadastrada na política) |
| `curl` retorna HTML de login em vez do JSON | A política de Access está bloqueando a chamada; use um **Service Token** (`CF-Access-Client-Id`/`CF-Access-Client-Secret`) para automação |
| Quero MQTT de fora de casa | O Tunnel não expõe TCP cru (porta 1883). Use MQTT sobre **WebSockets** (listener 9001 no mosquitto) ou a API Flask em `raspberry_code/` |

### Estatísticas de uso

| Problema | Solução |
|----------|---------|
| `lampada-stats` não sobe | `journalctl -u lampada-stats -n 50`; confira se o venv em `venv_lampada` existe e tem `flask`/`gunicorn` |
| `/lampada/hoje` sempre retorna 0 | A ESP32 está postando pro IP certo? Confira `RASPBERRY_URL` no `.ino` e teste `curl -X POST http://localhost:5000/lampada -d '{"aceso":true}' -H 'Content-Type: application/json'` direto na Pi |
| Relatório do dia não foi gerado | `systemctl list-timers lampada-relatorio.timer`; rode na mão com `gerar_relatorio_lampada.py` para ver o erro |
| Quero reprocessar um dia antigo | `venv_lampada/bin/python gerar_relatorio_lampada.py AAAA-MM-DD` (os eventos brutos ficam em `dados_lampada/eventos.jsonl`) |

---

## 📄 Licença

Projeto de estudo — use, modifique e compartilhe à vontade.
