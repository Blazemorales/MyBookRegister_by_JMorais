import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  BACKEND_JWT_COOKIE,
  SESSION_COOKIE,
  SESSION_MAX_AGE_SECONDS,
  createSessionToken,
  readAuthConfig,
  verifySessionToken,
} from "../../lib/auth";

export async function POST() {
  const config = readAuthConfig();
  if (!config) {
    return NextResponse.json({ ok: false }, { status: 500 });
  }

  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  const session = verifySessionToken(token, config.secret);
  if (!session) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  const newToken = createSessionToken(session.username, config.secret);
  const expiresAt = (Math.floor(Date.now() / 1000) + SESSION_MAX_AGE_SECONDS) * 1000;
  const response = NextResponse.json({ ok: true, expiresAt });

  const cookieOpts = {
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  };
  response.cookies.set(SESSION_COOKIE, newToken, cookieOpts);

  // Renova proativamente o JWT do backend para evitar que expire enquanto a
  // sessão está ativa. Falha silenciosa: a sessão é estendida de qualquer modo;
  // chamadas ao backend começarão a falhar (401) somente se o JWT já tiver
  // expirado, levando o usuário a refazer o login.
  const backendUrl = process.env.CEP_API_URL;
  const currentJwt = store.get(BACKEND_JWT_COOKIE)?.value;
  if (backendUrl && currentJwt) {
    try {
      const jwtRes = await fetch(new URL("/token/refresh", backendUrl), {
        method: "POST",
        headers: { Authorization: `Bearer ${currentJwt}` },
        cache: "no-store",
        signal: AbortSignal.timeout(5_000),
      });
      if (jwtRes.ok) {
        const body = (await jwtRes.json()) as { access_token?: string };
        if (body.access_token) {
          response.cookies.set(BACKEND_JWT_COOKIE, body.access_token, cookieOpts);
        }
      }
    } catch {
      // ignora — JWT antigo continua válido até expirar
    }
  }

  return response;
}
