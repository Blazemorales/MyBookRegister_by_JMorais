import { NextResponse } from "next/server";
import { backendAuthHeader, backendBaseUrl } from "@/app/lib/backend";

export const dynamic = "force-dynamic";
// Gerar o PDF leva ~5-7s quente; com cold start do backend (Render free) ou a
// 1ª renderização do matplotlib pode passar dos 10s padrão da Vercel. 60s é o
// teto do plano Hobby e dá folga para não estourar o timeout da função.
export const maxDuration = 60;

const ROTAS: Record<string, string> = {
  xr: "/relatorio/xr",
  p: "/relatorio/p",
  u: "/relatorio/u",
  imr: "/relatorio/imr",
};

type CacheEntry = {
  buf: ArrayBuffer;
  contentType: string;
  status: number;
  ts: number;
};

const CACHE_TTL = Number(process.env.RELATORIO_CACHE_TTL_MS) || 60_000;
const cache: Map<string, CacheEntry> =
  ((globalThis as unknown as { __RELATORIO_CACHE?: Map<string, CacheEntry> })
    .__RELATORIO_CACHE ??= new Map());

export async function GET(
  _req: Request,
  context: { params: Promise<{ tipo: string }> },
) {
  const start = Date.now();
  const { tipo } = await context.params;

  let base: string;
  try {
    base = backendBaseUrl();
  } catch (e) {
    return NextResponse.json({ error: (e as Error).message }, { status: 500 });
  }

  if (!tipo || !ROTAS[tipo]) {
    return NextResponse.json(
      { error: "Tipo de relatório inválido" },
      { status: 400 },
    );
  }

  const now = Date.now();
  const cached = cache.get(tipo);
  if (cached && now - cached.ts < CACHE_TTL) {
    const duration = Date.now() - start;
    return new NextResponse(cached.buf, {
      status: cached.status,
      headers: {
        "Content-Type": cached.contentType,
        "X-Cache": "HIT",
        "X-Upstream-Duration-Ms": String(duration),
        "Cache-Control": `private, max-age=${Math.floor(CACHE_TTL / 1000)}`,
      },
    });
  }

  try {
    const auth = await backendAuthHeader();
    const res = await fetch(`${base}${ROTAS[tipo]}`, {
      method: "GET",
      headers: { ...auth },
      cache: "no-store",
    });

    if (!res.ok) {
      const text = await res.text().catch(() => res.statusText);
      const contentType = res.headers.get("content-type") ?? "application/json";
      const duration = Date.now() - start;
      return new NextResponse(text, {
        status: res.status,
        headers: {
          "Content-Type": contentType,
          "X-Upstream-Duration-Ms": String(duration),
        },
      });
    }

    const buf = await res.arrayBuffer();
    const contentType = res.headers.get("content-type") ?? "application/pdf";

    cache.set(tipo, { buf, contentType, status: res.status, ts: Date.now() });

    const duration = Date.now() - start;
    return new NextResponse(buf, {
      status: res.status,
      headers: {
        "Content-Type": contentType,
        "X-Cache": "MISS",
        "X-Upstream-Duration-Ms": String(duration),
        "Cache-Control": `private, max-age=${Math.floor(CACHE_TTL / 1000)}`,
      },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao acessar backend";
    return NextResponse.json({ error: msg }, { status: 502 });
  }
}
