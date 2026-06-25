import { NextRequest, NextResponse } from "next/server";
import { backendAuthHeader, backendBaseUrl } from "@/app/lib/backend";

export const dynamic = "force-dynamic";

const TIPOS_VALIDOS = new Set(["diario", "mensal"]);

export async function GET(
  req: NextRequest,
  context: { params: Promise<{ tipo: string }> },
) {
  const { tipo } = await context.params;
  const t = tipo?.toLowerCase();
  if (!t || !TIPOS_VALIDOS.has(t)) {
    return NextResponse.json({ error: "tipo inválido (diario|mensal)" }, { status: 400 });
  }

  let base: string;
  try {
    base = backendBaseUrl();
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }

  const { searchParams } = req.nextUrl;
  const periodo = searchParams.get("periodo");
  const canal = searchParams.get("canal") ?? "default";

  const path = periodo
    ? `/relatorios/${t}/${encodeURIComponent(periodo)}?canal=${canal}`
    : `/relatorios/${t}/latest?canal=${canal}`;

  try {
    const auth = await backendAuthHeader();
    const res = await fetch(`${base}${path}`, {
      method: "GET",
      headers: { ...auth },
      cache: "no-store",
    });
    const text = await res.text();
    return new NextResponse(text, {
      status: res.status,
      headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao acessar backend";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
