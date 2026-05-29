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
