import { NextResponse } from "next/server";
import { backendAuthHeader, backendBaseUrl } from "@/app/lib/backend";

export const dynamic = "force-dynamic";

export async function POST(req: Request) {
  const start = Date.now();

  let base: string;
  try {
    base = backendBaseUrl();
  } catch (e) {
    return NextResponse.json(
      { status: "erro", message: (e as Error).message },
      { status: 500 },
    );
  }

  try {
    const incoming = await req.formData();
    const file = incoming.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json(
        { status: "erro", message: "Arquivo ausente no campo 'file'" },
        { status: 400 },
      );
    }

    const fwd = new FormData();
    fwd.append("file", file, file.name);

    const auth = await backendAuthHeader();
    const res = await fetch(`${base}/upload`, {
      method: "POST",
      headers: { ...auth },
      body: fwd,
      cache: "no-store",
    });

    if (res.ok) {
      const cache = (
        globalThis as unknown as { __RELATORIO_CACHE?: Map<string, unknown> }
      ).__RELATORIO_CACHE;
      cache?.clear();
    }

    const duration = Date.now() - start;
    const contentType = res.headers.get("content-type") ?? "application/json";
    const text = await res.text().catch(() => "");

    return new NextResponse(text, {
      status: res.status,
      headers: {
        "Content-Type": contentType,
        "X-Upstream-Duration-Ms": String(duration),
      },
    });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Falha ao enviar arquivo";
    return NextResponse.json({ status: "erro", message: msg }, { status: 502 });
  }
}
