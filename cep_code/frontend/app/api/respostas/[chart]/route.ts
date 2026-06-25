import { NextResponse } from "next/server";
import { backendAuthHeader, backendBaseUrl } from "@/app/lib/backend";

export const dynamic = "force-dynamic";

const VALIDOS = new Set(["xr", "p", "u", "imr"]);

export async function GET(
  _req: Request,
  context: { params: Promise<{ chart: string }> },
) {
  const { chart } = await context.params;
  const c = chart?.toLowerCase();
  if (!c || !VALIDOS.has(c)) {
    return NextResponse.json({ error: "Carta inválida" }, { status: 400 });
  }

  let base: string;
  try {
    base = backendBaseUrl();
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }

  try {
    const auth = await backendAuthHeader();
    const res = await fetch(`${base}/results/cep/${c}`, {
      method: "GET",
      headers: { ...auth },
      cache: "no-store",
    });
    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      return new NextResponse(text, {
        status: res.status,
        headers: { "Content-Type": res.headers.get("content-type") ?? "application/json" },
      });
    }
    const json = await res.json();
    // Retorna apenas o bloco de respostas (Q1+Q2) se existir no novo formato
    const respostas = json.respostas ?? json;
    const respostasQ2 = json.respostas_q2 ?? null;
    return NextResponse.json({ respostas, respostas_q2: respostasQ2 });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao acessar backend";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
