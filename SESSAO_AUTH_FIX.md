# Diagnóstico e Correção — Falha de Autenticação PostgreSQL

**Branch de trabalho:** `claude/session-2ytfl3`
**Data:** 2026-06-10
**Problema reportado:** Login falha mesmo com credenciais corretas — sistema retorna "erro de autenticação" e "falha de conexão com o servidor"

---

## Arquitetura do Projeto

| Camada | Tecnologia | Onde roda |
|--------|-----------|-----------|
| Frontend | Next.js 16 | Vercel |
| Backend | FastAPI + Socket.IO (Python) | Koyeb |
| Banco de dados | PostgreSQL | Neon (free tier) |

### Fluxo de autenticação

```
Usuário → /login (Next.js, Vercel)
        → POST /api/login  (Next.js API Route)
            → verifica AUTH_SECRET (env var)
            → verifica CEP_API_URL (env var)
            → fetch POST /login (FastAPI, Koyeb)
                → mgr.authenticate(username, password)
                    → SELECT password FROM users WHERE username = $1  (Neon PostgreSQL)
                    → pwd_context.verify(password, hash)  (PBKDF2-SHA256)
                → cria JWT (HS256, SECRET_KEY)
            → cria cookie de sessão HMAC-SHA256 (__Host-cep_session)
            → cria cookie JWT backend (__Host-cep_backend_jwt)
        → redireciona para /
```

---

## Bugs Encontrados

### Bug 1 — CRÍTICO: `proxy.ts` não é reconhecido como middleware pelo Next.js

**Arquivo afetado:** `front/proxy.ts` (removido) → `front/middleware.ts` (criado)

**Problema:**
O Next.js exige que o arquivo de middleware seja **exatamente** nomeado `middleware.ts` e exporte uma função chamada `middleware`. O projeto tinha o arquivo nomeado `proxy.ts` exportando `proxy(...)`. O framework simplesmente ignorava o arquivo — o middleware nunca rodava.

**Consequências:**
- Proteção de rotas completamente desativada (qualquer usuário acessava páginas protegidas sem login)
- A verificação de `AUTH_SECRET` no middleware nunca era executada
- Usuários não autenticados poderiam navegar livremente pelo app

**Antes (errado):**
```typescript
// front/proxy.ts
export function proxy(request: NextRequest) {   // ← nome errado
  ...
}
export const config = { matcher: [...] };
```

**Depois (correto):**
```typescript
// front/middleware.ts
export function middleware(request: NextRequest) {  // ← nome correto, arquivo correto
  ...
}
export const config = { matcher: [...] };
```

---

### Bug 2 — MODERADO: Token de sessão quebrado para usernames com ponto

**Arquivo afetado:** `front/app/lib/auth.ts`

**Problema:**
`createSessionToken` gerava tokens com `.` como separador:
```
formato: <encodedUsername>.<timestamp>.<signature-hex>
```

`encodeURIComponent` **não** codifica o caractere ponto (`.`). Então para o username `"john.doe"`:
```
token gerado: "john.doe.1718000000.a3f9b2..."
split("."): ["john", "doe", "1718000000", "a3f9b2..."]  ← 4 partes!
```

`verifySessionToken` fazia `token.split(".")` e checava `parts.length !== 3` → retornava `null` → **qualquer usuário com ponto no nome nunca conseguia manter a sessão ativa**, mesmo depois de um login bem-sucedido.

**Correção aplicada em `createSessionToken`:**
```typescript
// Antes
const payload = `${encodeURIComponent(username)}.${issuedAt}`;

// Depois — força codificação do ponto para %2E
const encodedUser = encodeURIComponent(username).replace(/\./g, "%2E");
const payload = `${encodedUser}.${issuedAt}`;
```

**Correção aplicada em `verifySessionToken`:**
```typescript
// Antes — quebrava com usernames que tinham ponto
const parts = token.split(".");
if (parts.length !== 3) return null;
const [encUser, issuedAtStr, signature] = parts;

// Depois — usa lastIndexOf, funciona para tokens antigos e novos
const dotIndex = token.lastIndexOf(".");
if (dotIndex === -1) return null;
const sigDotIndex = token.lastIndexOf(".", dotIndex - 1);
if (sigDotIndex === -1) return null;
const encUser = token.slice(0, sigDotIndex);
const issuedAtStr = token.slice(sigDotIndex + 1, dotIndex);
const signature = token.slice(dotIndex + 1);
```

> A correção em `verifySessionToken` é retrocompatível: lê corretamente tanto tokens antigos (username com ponto não codificado) quanto tokens novos (com `%2E`).

---

### Bug 3 — CONFIGURAÇÃO: Variáveis de ambiente ausentes/incorretas

Estas não são bugs de código, mas são a **causa direta** de "falha de conexão" que o usuário vê. O código retorna mensagens de erro específicas conforme a variável ausente.

#### Vercel (frontend Next.js)

| Variável | Obrigatória | Sintoma se ausente |
|----------|------------|-------------------|
| `AUTH_SECRET` | Sim | `POST /api/login` → 500 "Servidor sem AUTH_SECRET configurado." |
| `CEP_API_URL` | Sim | `POST /api/login` → 500 "Servidor sem CEP_API_URL configurado." |
| `NEXT_PUBLIC_SOCKET_URL` | Sim (build) | WebSocket e CSP quebrados |

**Como gerar e configurar:**
```bash
# Gerar AUTH_SECRET
python3 -c "import secrets; print(secrets.token_hex(32))"

# Valor de CEP_API_URL — URL do serviço Koyeb
# Exemplo: https://tpe-backend-xxxxx.koyeb.app
```

#### Koyeb (backend FastAPI)

| Variável | Obrigatória | Sintoma se ausente |
|----------|------------|-------------------|
| `DATABASE_URL` | Sim | Backend não sobe (RuntimeError na inicialização) |
| `SECRET_KEY` | Sim | Backend não sobe (RuntimeError na inicialização) |
| `RPI_DEVICE_TOKEN` | Sim | Dispositivos RPi não conseguem conectar via Socket.IO |
| `ALLOWED_ORIGINS` | Sim | CORS bloqueia requisições do browser |

**Formato obrigatório do `DATABASE_URL` (Neon):**
```
postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
                                                                ^^^^^^^^^^^^^^
                                                                OBRIGATÓRIO no Neon
```

> Sem `?sslmode=require`, o asyncpg lança `InvalidPasswordError` ou `CannotConnectNowError` ao tentar conectar ao Neon.

---

## Como validar que as correções funcionam

### 1. Verificar se o backend Koyeb está acessível

```bash
# Health check sem banco
curl https://<seu-app>.koyeb.app/health
# Esperado: {"ok":true}

# Health check com banco
curl https://<seu-app>.koyeb.app/health/db
# Esperado: {"ok":true}  (pode demorar ~3s se o Neon estava suspenso)
```

### 2. Criar o primeiro usuário (se ainda não existir)

```bash
curl -X POST https://<seu-app>.koyeb.app/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"senha-forte-aqui"}'
# Esperado: {"ok":true}
```

### 3. Testar autenticação direto no backend (sem frontend)

```bash
curl -X POST https://<seu-app>.koyeb.app/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"senha-forte-aqui"}'
# Esperado: {"access_token":"eyJ...","token_type":"bearer"}
```

### 4. Testar autenticação pelo frontend (Vercel)

```bash
curl -X POST https://backend-projeto-tpe.vercel.app/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"senha-forte-aqui"}'
# Esperado: {"ok":true,"username":"admin"}
# Com cookies Set-Cookie: __Host-cep_session e __Host-cep_backend_jwt
```

### 5. Testar com username contendo ponto (bug 2)

```bash
# Registrar
curl -X POST https://<seu-app>.koyeb.app/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"joao.silva","password":"teste123"}'

# Login — antes do fix isso falharia silenciosamente após o redirect
curl -X POST https://backend-projeto-tpe.vercel.app/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"joao.silva","password":"teste123"}'
# Esperado: {"ok":true,"username":"joao.silva"}
```

---

## Arquivos modificados

```
front/
  proxy.ts          ← REMOVIDO
  middleware.ts     ← CRIADO (renomear + corrigir export)
  app/
    lib/
      auth.ts       ← MODIFICADO (bug do ponto no token de sessão)
```

### Diff resumido — `front/app/lib/auth.ts`

```diff
+ // Force-encode dots so the "." separator stays unambiguous when splitting.
+ const encodedUser = encodeURIComponent(username).replace(/\./g, "%2E");
- const payload = `${encodeURIComponent(username)}.${issuedAt}`;
+ const payload = `${encodedUser}.${issuedAt}`;

- const parts = token.split(".");
- if (parts.length !== 3) return null;
- const [encUser, issuedAtStr, signature] = parts;
+ const dotIndex = token.lastIndexOf(".");
+ if (dotIndex === -1) return null;
+ const sigDotIndex = token.lastIndexOf(".", dotIndex - 1);
+ if (sigDotIndex === -1) return null;
+ const encUser = token.slice(0, sigDotIndex);
+ const issuedAtStr = token.slice(sigDotIndex + 1, dotIndex);
+ const signature = token.slice(dotIndex + 1);
```

---

## Checklist de deploy após aplicar as correções

- [ ] Fazer merge ou cherry-pick do branch `claude/session-2ytfl3` para `main`
- [ ] Confirmar que `AUTH_SECRET` está configurada na Vercel (Secrets)
- [ ] Confirmar que `CEP_API_URL` aponta para a URL correta do Koyeb
- [ ] Confirmar que `NEXT_PUBLIC_SOCKET_URL` aponta para a URL correta do Koyeb
- [ ] Confirmar que `DATABASE_URL` no Koyeb contém `?sslmode=require`
- [ ] Confirmar que `SECRET_KEY` está configurada no Koyeb
- [ ] Confirmar que `ALLOWED_ORIGINS` no Koyeb inclui `https://backend-projeto-tpe.vercel.app`
- [ ] Fazer redeploy na Vercel (para pegar o novo `middleware.ts`)
- [ ] Testar `curl` no `/health` e `/health/db` do Koyeb
- [ ] Testar login pelo site `https://backend-projeto-tpe.vercel.app/login`
