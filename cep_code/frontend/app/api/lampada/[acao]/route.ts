import { NextRequest, NextResponse } from "next/server";
import { backendAuthHeader, raspberryBaseUrl } from "@/app/lib/backend";

export const dynamic = "force-dynamic";

const ACOES_VALIDAS = new Set(["on", "off"]);

export async function POST(
  req: NextRequest,
  context: { params: Promise<{ acao: string }> },
) {
  const { acao } = await context.params;
  if (!acao || !ACOES_VALIDAS.has(acao)) {
    return NextResponse.json({ error: "ação inválida (on|off)" }, { status: 400 });
  }

  const auth = await backendAuthHeader();
  if (!("Authorization" in auth)) {
    return NextResponse.json({ error: "sessão expirada — faça login novamente" }, { status: 401 });
  }

  try {
    const res = await fetch(`${raspberryBaseUrl()}/${acao}`, {
      method: "GET",
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "text/plain" },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao acessar a Raspberry Pi";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
