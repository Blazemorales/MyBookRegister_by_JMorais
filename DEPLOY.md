# Deploy (100% gratuito)

A stack tem três deploys independentes, todos em tier free sem cartão de crédito:

| Camada | Onde | Por quê |
|---|---|---|
| Front Next.js | **Vercel** | Caso de uso nativo, build automático em cada push |
| Backend FastAPI + Socket.IO | **Koyeb** | WebSocket nativo, sem hibernação, 1 web service free always-on |
| Postgres | **Neon** | 0.5GB free sem expiração, integra com asyncpg direto |

> O Render saiu por hibernar após 15min (mata Socket.IO). O Fly.io saiu porque o tier free de 256MB apertava — mas como o startup do backend agora consome só **67.6 MB** (lazy imports de scipy/matplotlib já existentes em `cep_pipeline.py`), Koyeb 256MB cabe folgadamente.

---

## 1. Postgres → Neon

1. Criar conta em https://neon.tech (login Google/GitHub, **sem cartão**).
2. **Create Project**: nome `tpe-postgres`, region mais perto do Koyeb (`AWS us-east-1` se for usar Koyeb Washington).
3. Copiar a **Connection string** que aparece no dashboard. Formato:
   ```
   postgresql://<user>:<pass>@ep-xxx-yyy.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
4. **Pegadinha:** Neon free **suspende** o compute após 5min inativo. Primeiro request após pausa leva ~2-3s pra subir. Pra `/ao-vivo` isso significa que o primeiro handshake do dia é lento; depois fica fluido enquanto houver tráfego.
5. O `ensure_schema()` do [backend/Login/async_model.py](backend/Login/async_model.py) cria todas as tabelas sozinho no primeiro startup do app — você **não** precisa rodar `schema.sql` manualmente.

---

## 2. Backend → Koyeb

### Via dashboard (mais fácil)

1. Login em https://app.koyeb.com (GitHub/Google, **sem cartão**).
2. **Create App → Deploy from GitHub**, autorize e selecione `backend_projeto_tpe`.
3. **Service settings:**
   - **Service type:** Web service
   - **Builder:** Dockerfile
   - **Work directory:** `backend`
   - **Dockerfile path:** `backend/Dockerfile` (relativo à raiz do repo)
   - **Branch:** `main`, auto-deploy ligado
4. **Instance:**
   - Type: **Free** (eco-2, 256MB, 0.1 vCPU, always-on)
   - Region: `was` (Washington) — mais perto do Neon US-East
5. **Ports:** `8000` → HTTP exposto
6. **Health check:** HTTP GET `/health`, intervalo 30s
7. **Environment variables** (Secrets para os sensíveis):
   ```
   DATABASE_URL       = <copiada do Neon, com sslmode=require>
   SECRET_KEY         = <gere com: python3 -c "import secrets; print(secrets.token_hex(32))">
   RPI_DEVICE_TOKEN   = <gere com: python3 -c "import secrets; print(secrets.token_hex(16))">
   ALLOWED_ORIGINS    = https://<seu-app>.vercel.app
   ACCESS_TOKEN_EXPIRE_MINUTES = 60
   RPI_RATE_LIMIT_HZ  = 20
   STREAM_REPLAY_MAX  = 200
   LOG_LEVEL          = INFO
   ```
8. **Deploy.** Acompanhe os logs até ver `Application startup complete.` (1-3 min na primeira vez).

### Via CLI (alternativa)

```bash
curl -fsSL https://raw.githubusercontent.com/koyeb/koyeb-cli/master/install.sh | bash
koyeb login

koyeb app create tpe-backend

koyeb service create backend \
  --app tpe-backend \
  --git github.com/Blazemorales/backend_projeto_tpe \
  --git-branch main \
  --git-builder docker \
  --git-docker-dockerfile backend/Dockerfile \
  --git-workdir backend \
  --instance-type free \
  --region was \
  --ports 8000:http \
  --routes /:8000 \
  --checks 8000:http:/health \
  --env DATABASE_URL=@<secret-id-neon> \
  --env SECRET_KEY=@<secret-id-key> \
  --env RPI_DEVICE_TOKEN=@<secret-id-rpi> \
  --env ALLOWED_ORIGINS=https://<seu-app>.vercel.app
```

### Verificar
```bash
curl -fsS https://<seu-app>.koyeb.app/health
# {"ok":true}
curl -fsS https://<seu-app>.koyeb.app/health/db
# {"ok":true}  (pode levar ~3s no primeiro request se o Neon estava suspenso)
```

---

## 3. Front → Vercel

1. **Dashboard Vercel → Add New → Project → importar `backend_projeto_tpe`**
2. **Configure Project:**
   - Framework: `Next.js` (auto-detectado)
   - **Root Directory: `front`** ← essencial num monorepo
3. **Environment Variables** (Production + Preview):
   ```
   CEP_API_URL              = https://<seu-app>.koyeb.app
   NEXT_PUBLIC_SOCKET_URL   = https://<seu-app>.koyeb.app
   AUTH_SECRET              = <gere com: python3 -c "import secrets; print(secrets.token_hex(32))">
   ```
4. **Deploy.** O Next inlinea `NEXT_PUBLIC_SOCKET_URL` no bundle e na CSP automaticamente.
5. **Primeiro usuário:**
   ```bash
   curl -X POST https://<seu-app>.koyeb.app/register \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"<senha-forte>"}'
   ```

---

## Variáveis (referência)

| Variável | Origem | Obrigatória |
|---|---|---|
| `DATABASE_URL` | Connection string do Neon | sim |
| `SECRET_KEY` | gerar localmente, secret no Koyeb | sim |
| `RPI_DEVICE_TOKEN` | gerar localmente, secret no Koyeb | sim |
| `ALLOWED_ORIGINS` | URL Vercel (CORS, separado por vírgula) | sim |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | default 60 | não |
| `RPI_RATE_LIMIT_HZ` | default 20 (msg/s por dispositivo) | não |
| `STREAM_REPLAY_MAX` | default 200 (limite duro do replay) | não |
| `LOG_LEVEL` | default INFO | não |

---

## Endpoints expostos

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET  | `/` | público | health/info |
| GET  | `/health` | público | liveness (sem DB) |
| GET  | `/health/db` | público | readiness (com DB) |
| POST | `/register` | público | cria usuário (hash pbkdf2) |
| POST | `/login` | público | devolve JWT |
| GET  | `/me` | Bearer JWT | retorna username |
| POST | `/upload` | Bearer JWT | envia JSON, grava em `amostras` |
| GET  | `/processar` | Bearer JWT | processa amostras (carrega scipy/numpy aqui) |
| GET  | `/relatorio/{xr,p,u,imr}` | Bearer JWT | PDF (carrega matplotlib/fpdf2 aqui) |
| GET  | `/results/cep/{xr,p,u,imr}` | Bearer JWT | JSON tratado |
| WS   | `/socket.io/` | JWT no handshake | stream `relatorio_data` + `subscribe_relatorio` com replay |

---

## Troubleshooting

- **OOM no Koyeb 256MB ao chamar `/processar` ou `/relatorio`:** scipy + matplotlib carregam ~150MB. Se estourar, ou (a) upgrade pra plano `eco-3` ($2/mês, 512MB), ou (b) mova esses endpoints pra um worker separado.
- **Primeiro request lento (~3s):** o compute do Neon estava suspenso. Comportamento esperado no free tier após 5min sem tráfego.
- **`asyncpg.exceptions.InvalidPasswordError` ou `CannotConnectNowError`:** confira se o `DATABASE_URL` tem `?sslmode=require` no final (obrigatório no Neon).
- **`statement cache mismatch` no asyncpg:** o `ASYNCPG_STATEMENT_CACHE_SIZE=0` já é default em [backend/Login/async_model.py:61](backend/Login/async_model.py#L61) — necessário quando o Neon roteia via pgbouncer.
- **Socket.IO desconectando:** o Koyeb não hiberna; se cair, é problema de proxy. Confira que `ALLOWED_ORIGINS` inclui o domínio Vercel exato (com protocolo, sem barra final).
- **CSP bloqueia WebSocket:** o `connect-src` é inlinado pelo Next no build a partir de `NEXT_PUBLIC_SOCKET_URL`. Se mudar o domínio do backend, refaça o build da Vercel.
- **Rate-limit "rate-limit excedido":** o default são 20 msg/s por conexão RPi. Ajuste com env var `RPI_RATE_LIMIT_HZ`.

---

## Local (Docker Compose)

Pra dev local, [docker-compose.yml](docker-compose.yml) sobe tudo:

```bash
cp .env.example .env.local-test
# preencha SECRET_KEY e AUTH_SECRET com 64 hex chars
sudo docker compose --env-file .env.local-test --profile sim up --build -d
# UI: http://localhost:3000  | API: http://localhost:8000
```
