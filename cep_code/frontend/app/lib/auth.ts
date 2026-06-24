import { createHmac, timingSafeEqual } from "node:crypto";

export const SESSION_COOKIE = "__Host-cep_session";
// Cookie httpOnly com o JWT que o backend devolve no /login. O proxy.ts
// NÃO valida esse cookie — só checa o SESSION_COOKIE (HMAC). Esse aqui
// é só transporte: as rotas /api/* leem para encaminhar ao backend.
export const BACKEND_JWT_COOKIE = "__Host-cep_backend_jwt";
export const SESSION_MAX_AGE_SECONDS = 60 * 30;
export const SESSION_WARNING_LEAD_SECONDS = 120;

export type AuthConfig = {
  secret: string;
};

export function readAuthConfig(): AuthConfig | null {
  const secret = process.env.AUTH_SECRET;
  if (!secret) return null;
  return { secret };
}

function safeEqualStrings(a: string, b: string): boolean {
  const aBuf = Buffer.from(a);
  const bBuf = Buffer.from(b);
  if (aBuf.length !== bBuf.length) return false;
  return timingSafeEqual(aBuf, bBuf);
}

function sign(payload: string, secret: string): string {
  return createHmac("sha256", secret).update(payload).digest("hex");
}

export function createSessionToken(username: string, secret: string): string {
  const issuedAt = Math.floor(Date.now() / 1000);
  // encodeURIComponent NÃO codifica ".", então usernames com ponto (ex.: "joao.silva")
  // gerariam tokens com partes extras ao dar split(".") na verificação. Forçamos %2E
  // para o "." continuar sendo separador inequívoco.
  const encodedUser = encodeURIComponent(username).replace(/\./g, "%2E");
  const payload = `${encodedUser}.${issuedAt}`;
  const signature = sign(payload, secret);
  return `${payload}.${signature}`;
}

export function verifySessionToken(
  token: string | undefined,
  secret: string,
): { username: string; issuedAt: number; expiresAt: number } | null {
  if (!token) return null;
  // Usa lastIndexOf em vez de split(".") para tolerar tokens antigos cujo encUser
  // ainda contém pontos não codificados (retrocompatível). issuedAt e a assinatura
  // hex nunca têm ponto, então os dois últimos "." delimitam o payload com segurança.
  const dotIndex = token.lastIndexOf(".");
  if (dotIndex === -1) return null;
  const sigDotIndex = token.lastIndexOf(".", dotIndex - 1);
  if (sigDotIndex === -1) return null;
  const encUser = token.slice(0, sigDotIndex);
  const issuedAtStr = token.slice(sigDotIndex + 1, dotIndex);
  const signature = token.slice(dotIndex + 1);

  const issuedAt = Number.parseInt(issuedAtStr, 10);
  if (!Number.isFinite(issuedAt)) return null;
  const now = Math.floor(Date.now() / 1000);
  if (now - issuedAt > SESSION_MAX_AGE_SECONDS) return null;

  const payload = `${encUser}.${issuedAtStr}`;
  const expected = sign(payload, secret);
  if (!safeEqualStrings(signature, expected)) return null;

  try {
    return {
      username: decodeURIComponent(encUser),
      issuedAt,
      expiresAt: issuedAt + SESSION_MAX_AGE_SECONDS,
    };
  } catch {
    return null;
  }
}
