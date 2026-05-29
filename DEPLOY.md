# Deploy

A stack tem dois deploys independentes:

| Camada | Onde | Por quê |
|---|---|---|
| Front Next.js | Vercel | Caso de uso nativo; build automático em cada push |
| Backend FastAPI + Socket.IO | Fly.io | Suporta WebSocket persistente sem hibernação |
| Postgres | Fly Postgres (via `fly postgres create`) | Same-region, baixa latência, gerenciado |

> O Render saiu da equação porque o free tier hiberna após 15min — derruba conexões Socket.IO em andamento.

---

## Backend → Fly.io

### Pré-requisitos
```bash
curl -L https://fly.io/install.sh | sh
fly auth login
```

### Primeiro deploy

```bash
cd backend
# Adota o fly.toml já versionado no repo. Troque o `app = "..."` antes
# se o nome estiver tomado no Fly.
fly launch --copy-config --no-deploy

# Cria Postgres gerenciado e injeta DATABASE_URL como secret automaticamente.
fly postgres create --name tpe-postgres --region gru
fly postgres attach tpe-postgres

# Segredos restantes (NÃO commite estes valores).
fly secrets set \
  SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))') \
  RPI_DEVICE_TOKEN=$(python3 -c 'import secrets; print(secrets.token_hex(16))') \
  ALLOWED_ORIGINS=https://<seu-app>.vercel.app

fly deploy
```

O `ensure_schema()` do [Login/async_model.py](backend/Login/async_model.py) cria/migra o schema sozinho no primeiro startup.

### Atualizações
```bash
cd backend
fly deploy
```

### Verificar
```bash
curl -fsS https://<seu-app>.fly.dev/health
# {"ok":true}
curl -fsS https://<seu-app>.fly.dev/health/db
# {"ok":true}
fly logs
```

### Variáveis (referência)

| Variável | Origem | Obrigatória |
|---|---|---|
| `DATABASE_URL` | `fly postgres attach` (auto) | sim |
| `SECRET_KEY` | `fly secrets set` | sim |
| `RPI_DEVICE_TOKEN` | `fly secrets set` | sim |
| `ALLOWED_ORIGINS` | `fly secrets set` (CORS — lista por vírgula) | sim |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `[env]` no fly.toml | não (default 60) |
| `RPI_RATE_LIMIT_HZ` | `[env]` no fly.toml | não (default 20) |
| `LOG_LEVEL` | `[env]` no fly.toml | não (default INFO) |

---

## Front → Vercel

1. **Dashboard Vercel → Add New → Project → importar `backend_projeto_tpe`**
2. **Configure Project:**
   - Framework: `Next.js` (auto)
   - **Root Directory: `front`** (essencial — é um monorepo)
3. **Environment Variables** (Production + Preview):
   ```
   CEP_API_URL=https://<seu-backend>.fly.dev
   NEXT_PUBLIC_SOCKET_URL=https://<seu-backend>.fly.dev
   AUTH_SECRET=<gere com: python3 -c "import secrets; print(secrets.token_hex(32))">
   ```
4. **Deploy.** O Vercel detecta o `next.config.ts` e inlinear `NEXT_PUBLIC_SOCKET_URL` no bundle do browser e na CSP.
5. **Primeiro usuário:**
   ```bash
   curl -X POST https://<seu-backend>.fly.dev/register \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"<senha-forte>"}'
   ```

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
| GET  | `/processar` | Bearer JWT | processa amostras, salva em `resultados` |
| GET  | `/relatorio/{xr,p,u,imr}` | Bearer JWT | PDF (gera on-demand se faltar) |
| GET  | `/results/cep/{xr,p,u,imr}` | Bearer JWT | JSON tratado |
| WS   | `/socket.io/` | JWT no handshake | stream `relatorio_data` em tempo real |

Multi-tenant: `amostras` e `resultados` têm `user_id` indexadas por `(user_id, chart)`.

---

## Troubleshooting

- **Fly free out-of-memory** (matplotlib/scipy/numpy estouram 256MB): o `fly.toml` já vem com `memory = "512mb"`. Custa ~$2/mês acima do free tier.
- **Socket.IO desconectando frequente:** confira se `auto_stop_machines = "off"` no `fly.toml` — auto-stop derruba conexões ativas.
- **CSP bloqueia WebSocket no front:** o `connect-src` é parametrizado por `NEXT_PUBLIC_SOCKET_URL`. Se mudar de domínio, refaça o build na Vercel pra inlinar o valor novo.
- **Rate-limit RPi disparando "rate-limit excedido"**: o default são 20 msg/s por conexão. Ajuste com `fly secrets set RPI_RATE_LIMIT_HZ=50` (ou outra var de ambiente conforme a plataforma).
- **`__Host-` cookies em localhost via Chrome**: funciona (Chrome trata localhost como secure context). Em Safari/Firefox, pode rejeitar.
- **`asyncpg.exceptions.CannotConnectNowError`:** Postgres ainda iniciando; espere ~30s no primeiro deploy e o lifespan reconecta.

## Local (Docker Compose)

Pra desenvolvimento, [docker-compose.yml](docker-compose.yml) sobe tudo:

```bash
cp .env.example .env.local-test
# preencha SECRET_KEY e AUTH_SECRET com 64 hex chars
sudo docker compose --env-file .env.local-test --profile sim up --build -d
# UI: http://localhost:3000  | API: http://localhost:8000
```
