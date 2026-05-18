# Deploy no Render — passo a passo

O repositório tem um `render.yaml` que provisiona **um Web Service** (FastAPI) e **um Postgres gerenciado** já conectados.

## 1. Commit e push

```bash
git add render.yaml Procfile runtime.txt backend_api.py cep_routes.py Login/ requirements.txt
git commit -m "Backend FastAPI unificado + auth com Postgres"
git push origin main
```

## 2. Criar Blueprint no Render

1. Acesse https://dashboard.render.com → **New** → **Blueprint**.
2. Conecte o repositório `Blazemorales/backend_projeto_tpe`.
3. O Render lê o `render.yaml` automaticamente e mostra dois recursos:
   - **Web Service**: `backend-projeto-tpe`
   - **Database**: `tpe-postgres`
4. Clique **Apply** — ele cria o Postgres primeiro, depois o web service. O Render injeta sozinho:
   - `DATABASE_URL` (do Postgres)
   - `SECRET_KEY` (gerado aleatório)
   - `ACCESS_TOKEN_EXPIRE_MINUTES=60`

## 3. Aguardar o primeiro build

- Build (`pip install -r requirements.txt`) leva 2–4 min.
- Start (`uvicorn backend_api:app`) chama o `lifespan`, que executa `CREATE TABLE IF NOT EXISTS users (...)` automaticamente.
- Health check em `/` deve retornar 200.

## 4. Criar o primeiro usuário

Depois que o serviço subir:

```bash
curl -X POST https://<seu-service>.onrender.com/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<senha-forte>"}'
```

Ou, com o frontend já apontando pra essa URL, use a aba "Criar conta" na tela de login.

## 5. Apontar o frontend pra produção

No projeto `frontend_tpe` (Vercel), garanta as env vars:

| Variável | Valor |
|---|---|
| `CEP_API_URL` | `https://<seu-service>.onrender.com` |
| `NEXT_PUBLIC_CEP_API_URL` | `https://<seu-service>.onrender.com` |
| `AUTH_SECRET` | `openssl rand -hex 32` |

## Variáveis do backend (referência)

| Variável | Origem | Obrigatória |
|---|---|---|
| `DATABASE_URL` | Postgres do Render (auto) | sim |
| `SECRET_KEY` | gerada pelo Render (auto) | sim |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | render.yaml | não (default 60) |
| `PORT` | injetada pelo Render | sim (uvicorn já usa) |
| `PYTHON_VERSION` | render.yaml (`3.12.0`) | não |

## Endpoints expostos

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET  | `/` | público | health/info |
| POST | `/register` | público | cria usuário (hash pbkdf2) |
| POST | `/login` | público | devolve JWT |
| GET  | `/me` | Bearer JWT | retorna username |
| GET  | `/processar` | público | roda pipeline CEP |
| GET  | `/relatorio/{xr,p,u,imr}` | público | PDF |
| GET  | `/results/cep/{xr,p,u,imr}` | público | JSON tratado |
| GET  | `/validarprocesso` | público | valida pipeline |

> Hoje as rotas CEP são públicas (mesmo comportamento do Flask anterior). Se quiser exigir login, adicione `Depends(get_current_username)` em cada uma.

## Troubleshooting

- **Build falha por `psycopg2`**: requirements já tem `psycopg2-binary` (não exige libpq-dev).
- **`SECRET_KEY` aviso "insecure default"**: significa que a env var não chegou no runtime — confira no dashboard se foi gerada.
- **`asyncpg.exceptions.InvalidPasswordError` ou `CannotConnectNowError`**: o Postgres ainda está iniciando; aguarde e o lifespan reconecta no próximo deploy/restart.
- **Cold start lento (plano free)**: primeira request após 15 min de ociosidade demora ~30s.
