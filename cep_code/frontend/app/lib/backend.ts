// Helpers para chamadas server-side ao backend autenticado.
// Lê o JWT do cookie __Host-cep_backend_jwt e devolve um Authorization
// header pronto para uso.

import { cookies } from "next/headers";
import { BACKEND_JWT_COOKIE } from "./auth";

export async function backendAuthHeader(): Promise<HeadersInit> {
  const store = await cookies();
  const token = store.get(BACKEND_JWT_COOKIE)?.value;
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export function backendBaseUrl(): string {
  const url = process.env.CEP_API_URL;
  if (!url) throw new Error("CEP_API_URL não definida");
  return url;
}

// URL pública da Raspberry Pi (nginx + Cloudflare Tunnel) — serve a página
// de controle da ESP32 (/on, /off) e, sob /cep-agent/, o cep-agent local.
export function raspberryBaseUrl(): string {
  return process.env.RASPBERRY_LAMPADA_URL ?? "https://raspberry.mbrlamp.com.br";
}

// Mesmo valor do RPI_DEVICE_TOKEN configurado no cep-agent da Pi — exigido
// pelo endpoint /cep-agent/run/diario (ver raspberry_code/cep_agent/app.py).
export function raspberryCepAgentToken(): string {
  const token = process.env.RASPBERRY_CEP_AGENT_TOKEN;
  if (!token) throw new Error("RASPBERRY_CEP_AGENT_TOKEN não definida");
  return token;
}
