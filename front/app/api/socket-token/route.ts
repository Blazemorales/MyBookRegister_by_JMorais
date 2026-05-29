// Entrega o JWT do backend (cookie httpOnly) para o browser, que precisa
// dele para o handshake autenticado do Socket.IO. As demais rotas /api/*
// não fazem isso porque o JWT viaja só server-side via Authorization.

import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { BACKEND_JWT_COOKIE } from "@/app/lib/auth";

export const dynamic = "force-dynamic";

export async function GET() {
  const store = await cookies();
  const token = store.get(BACKEND_JWT_COOKIE)?.value;
  if (!token) {
    return NextResponse.json(
      { error: "unauthorized" },
      { status: 401, headers: { "Cache-Control": "no-store" } },
    );
  }
  return NextResponse.json(
    { token },
    { headers: { "Cache-Control": "no-store" } },
  );
}
