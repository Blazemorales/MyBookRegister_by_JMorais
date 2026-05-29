import { NextResponse } from "next/server";
import {
  checkLoginRateLimit,
  getClientIp,
  recordLoginFailure,
  resetLoginAttempts,
} from "../../lib/rateLimit";

const BACKEND_TIMEOUT_MS = 10_000;
const MIN_PASSWORD_LENGTH = 6;
const MAX_PASSWORD_LENGTH = 128;
const MAX_USERNAME_LENGTH = 64;

export async function POST(request: Request) {
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
  if (trimmedUser.length === 0 || trimmedUser.length > MAX_USERNAME_LENGTH) {
    return NextResponse.json(
      { error: `Usuário deve ter entre 1 e ${MAX_USERNAME_LENGTH} caracteres.` },
      { status: 400 },
    );
  }
  if (password.length < MIN_PASSWORD_LENGTH || password.length > MAX_PASSWORD_LENGTH) {
    return NextResponse.json(
      {
        error: `Senha deve ter entre ${MIN_PASSWORD_LENGTH} e ${MAX_PASSWORD_LENGTH} caracteres.`,
      },
      { status: 400 },
    );
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);
  let backendRes: Response;
  try {
    backendRes = await fetch(new URL("/register", backendUrl), {
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

  if (backendRes.status === 400) {
    await recordLoginFailure(ip);
    const data = (await backendRes.json().catch(() => ({}))) as {
      detail?: string;
    };
    return NextResponse.json(
      { error: data.detail ?? "Usuário já existe." },
      { status: 409 },
    );
  }

  if (!backendRes.ok) {
    return NextResponse.json(
      { error: "Serviço de autenticação indisponível." },
      { status: 502 },
    );
  }

  await resetLoginAttempts(ip);
  return NextResponse.json({ ok: true, username: trimmedUser });
}
