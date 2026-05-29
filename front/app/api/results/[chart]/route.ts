import { NextResponse } from "next/server";
import { backendAuthHeader, backendBaseUrl } from "@/app/lib/backend";

export const dynamic = "force-dynamic";

const VALIDOS = new Set(["xr", "p", "u", "imr"]);

export async function GET(
  _req: Request,
  context: { params: Promise<{ chart: string }> },
) {
  const start = Date.now();
  const { chart } = await context.params;

  let base: string;
  try {
    base = backendBaseUrl();
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }

  const c = chart?.toLowerCase();
  if (!c || !VALIDOS.has(c)) {
    return NextResponse.json(
      { error: "Carta inválida (esperado: xr, p, u ou imr)" },
      { status: 400 },
    );
  }

  try {
    const auth = await backendAuthHeader();
    const res = await fetch(`${base}/results/cep/${c}`, {
      method: "GET",
      headers: { ...auth },
      cache: "no-store",
    });
    const text = await res.text();
    const contentType = res.headers.get("content-type") ?? "application/json";
    const duration = Date.now() - start;
    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": contentType,
        "X-Upstream-Duration-Ms": String(duration),
      },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao acessar backend";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
