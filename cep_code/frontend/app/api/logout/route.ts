import { NextResponse } from "next/server";
import { BACKEND_JWT_COOKIE, SESSION_COOKIE } from "../../lib/auth";

export async function POST() {
  const response = NextResponse.json({ ok: true });
  const opts = {
    httpOnly: true,
    secure: true,
    sameSite: "lax" as const,
    path: "/",
    maxAge: 0,
  };
  response.cookies.set(SESSION_COOKIE, "", opts);
  response.cookies.set(BACKEND_JWT_COOKIE, "", opts);
  return response;
}
