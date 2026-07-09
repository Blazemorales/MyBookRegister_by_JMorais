import { NextRequest, NextResponse } from "next/server";
import { backendAuthHeader, raspberryBaseUrl, raspberryCepAgentToken } from "@/app/lib/backend";

export const dynamic = "force-dynamic";

function hojeBRT(): string {
  // YYYY-MM-DD no fuso de São Paulo, sem depender de libs extras.
  const partes = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const get = (t: string) => partes.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export async function POST(req: NextRequest) {
  const auth = await backendAuthHeader();
  if (!("Authorization" in auth)) {
    return NextResponse.json({ error: "sessão expirada — faça login novamente" }, { status: 401 });
  }

  let token: string;
  try {
    token = raspberryCepAgentToken();
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }

  const body = await req.json().catch(() => ({}) as { data?: string });
  const data = body.data ?? hojeBRT();

  try {
    const res = await fetch(
      `${raspberryBaseUrl()}/cep-agent/run/diario?data=${encodeURIComponent(data)}`,
      {
        method: "POST",
        headers: { "X-RPI-Token": token },
        cache: "no-store",
        signal: AbortSignal.timeout(90_000),
      },
    );
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao acessar o cep-agent na Raspberry Pi";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
