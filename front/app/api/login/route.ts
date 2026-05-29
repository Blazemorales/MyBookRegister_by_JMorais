import { NextResponse } from "next/server";
import {
  BACKEND_JWT_COOKIE,
  SESSION_COOKIE,
  SESSION_MAX_AGE_SECONDS,
  createSessionToken,
  readAuthConfig,
} from "../../lib/auth";
import {
  checkLoginRateLimit,
  getClientIp,
  recordLoginFailure,
  resetLoginAttempts,
} from "../../lib/rateLimit";

const BACKEND_TIMEOUT_MS = 10_000;
const MAX_USERNAME_LENGTH = 64;
const MAX_PASSWORD_LENGTH = 128;

export async function POST(request: Request) {
  const config = readAuthConfig();
  if (!config) {
    return NextResponse.json(
      { error: "Servidor sem AUTH_SECRET configurado." },
      { status: 500 },
    );
  }

  const backendUrl = process.env.CEP_API_URL;
  if (!backendUrl) {
    return NextResponse.json(
      { error: "Servidor sem CEP_API_URL configurado." },
      { status: 500 },
    );
  }

  const ip = getClientIp(request);
  const rate = await checkLoginRateLimit(ip);
  if (!rate.allowed) {
    return NextResponse.json(
      { error: "Muitas tentativas. Tente novamente em alguns minutos." },
      {
        status: 429,
        headers: { "Retry-After": String(rate.retryAfterSec) },
      },
    );
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Corpo inválido." }, { status: 400 });
  }

  const { username, password } =
    (body as { username?: unknown; password?: unknown }) ?? {};
  if (typeof username !== "string" || typeof password !== "string") {
    return NextResponse.json(
      { error: "Usuário e senha são obrigatórios." },
      { status: 400 },
    );
  }

  const trimmedUser = username.trim();
  if (
    trimmedUser.length === 0 ||
    trimmedUser.length > MAX_USERNAME_LENGTH ||
    password.length === 0 ||
    password.length > MAX_PASSWORD_LENGTH
  ) {
    return NextResponse.json(
      { error: "Usuário ou senha inválidos." },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
  let backendRes: Response;
  try {
    backendRes = await fetch(new URL("/login", backendUrl), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: trimmedUser, password }),
      signal: controller.signal,
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: "Falha ao contatar o serviço de autenticação." },
      { status: 502 },
    );
  } finally {
    clearTimeout(timeout);
  }

  if (backendRes.status === 401) {
    await recordLoginFailure(ip);
    return NextResponse.json(
      { error: "Usuário ou senha inválidos." },
      { status: 401 },
    );
  }

  if (!backendRes.ok) {
    return NextResponse.json(
      { error: "Serviço de autenticação indisponível." },
      { status: 502 },
    );
  }

  let backendToken: string | null = null;
  try {
    const body = (await backendRes.json()) as { access_token?: string };
    backendToken = body.access_token ?? null;
  } catch {
    backendToken = null;
  }
  if (!backendToken) {
    return NextResponse.json(
      { error: "Backend não devolveu access_token." },
      { status: 502 },
    );
  }

  await resetLoginAttempts(ip);
  const token = createSessionToken(trimmedUser, config.secret);
  const response = NextResponse.json({ ok: true, username: trimmedUser });
  response.cookies.set(SESSION_COOKIE, token, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  response.cookies.set(BACKEND_JWT_COOKIE, backendToken, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  return response;
}
