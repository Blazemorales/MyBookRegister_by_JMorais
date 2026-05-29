import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import {
  SESSION_COOKIE,
  SESSION_MAX_AGE_SECONDS,
  createSessionToken,
  readAuthConfig,
  verifySessionToken,
} from "../../lib/auth";

export async function POST() {
  const config = readAuthConfig();
  if (!config) {
    return NextResponse.json({ ok: false }, { status: 500 });
  }

  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  const session = verifySessionToken(token, config.secret);
  if (!session) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }

  const newToken = createSessionToken(session.username, config.secret);
  const expiresAt = (Math.floor(Date.now() / 1000) + SESSION_MAX_AGE_SECONDS) * 1000;
  const response = NextResponse.json({ ok: true, expiresAt });
  response.cookies.set(SESSION_COOKIE, newToken, {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: SESSION_MAX_AGE_SECONDS,
  });
  return response;
}
