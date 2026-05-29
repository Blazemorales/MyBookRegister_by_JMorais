import { NextResponse } from "next/server";
import { backendAuthHeader, backendBaseUrl } from "@/app/lib/backend";

export const dynamic = "force-dynamic";

export async function GET() {
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
    const auth = await backendAuthHeader();
    const res = await fetch(`${base}/processar`, {
      method: "GET",
      headers: { ...auth },
      cache: "no-store",
    });
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
    const msg = e instanceof Error ? e.message : "Falha ao acessar backend";
    return NextResponse.json({ status: "erro", message: msg }, { status: 502 });
  }
}
