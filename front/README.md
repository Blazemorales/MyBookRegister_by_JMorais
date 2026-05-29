# MyBookRegister — Frontend CEP/TPE

Frontend Next.js 16 (App Router, React 19) para a ferramenta de
**Controle Estatístico de Processo** que conversa com o backend
FastAPI hospedado no Render.

## Funcionalidades

- **Calibrador** — envia JSON de medições, dispara `/processar` no
  backend e exibe o PDF do relatório (cartas X̄-R, P, U, I-MR).
- **Validador estatístico** — calcula probabilidades pela Normal,
  ARL/CMC, regras de Western Electric e gera PDF próprio
  (Montgomery, *Probabilidade e Estatística Aplicada à Engenharia*).
- **Autenticação** — cookie HMAC-SHA256 (sessão de 30 min, com
  diálogo de extensão antes da expiração).
- **PWA** — `manifest.ts` + service worker mínimo (instalável).

## Setup

```bash
npm install
cp .env.example .env.local   # preencher AUTH_SECRET e CEP_API_URL
npm run dev
```

Acesse <http://localhost:3000>.

## Variáveis de ambiente

| Nome | Onde | Para que |
|------|------|----------|
| `CEP_API_URL` | server-side | URL do backend (rotas `/api/*` fazem proxy). |
| `NEXT_PUBLIC_CEP_API_URL` | client (legado) | Mantido apenas para tipos/helpers. |
| `AUTH_SECRET` | server-side | Segredo HMAC para assinar a sessão. Gere com `openssl rand -hex 32`. |
| `UPSTASH_REDIS_REST_URL` | server-side (opcional) | Habilita rate limit distribuído de login. |
| `UPSTASH_REDIS_REST_TOKEN` | server-side (opcional) | Token do Upstash. |

Sem `AUTH_SECRET` o app redireciona tudo para `/acesso-negado`.
Sem `UPSTASH_REDIS_*` o rate limit cai para in-memory (por instância).

## Estrutura

```
app/
  (app)/            # rotas autenticadas (layout + Sair)
  api/              # rotas-proxy ao backend + auth
  components/       # UI (validar, calibrar, SessionWatcher, PwaRegister)
  lib/              # auth.ts, rateLimit.ts, stats.ts, pdfValidacao.ts
hooks/              # useCepRelatorio, tipos compartilhados
proxy.ts            # middleware: redireciona não-logados / verifica HMAC
```

## Scripts

```bash
npm run dev     # servidor de desenvolvimento
npm run build   # build de produção
npm run start   # servir build
npm run lint    # eslint
```

## Deploy

Vercel, branch `main` direto em produção. Backend FastAPI no Render.
