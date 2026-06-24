import { NextResponse } from "next/server";
import { cookies } from "next/headers";
import { SESSION_COOKIE, readAuthConfig, verifySessionToken } from "../../lib/auth";

export async function GET() {
  const config = readAuthConfig();
  const res = (body: unknown) =>
    NextResponse.json(body, {
      headers: { "Cache-Control": "no-store" },
    });

  if (!config) return res({ user: null, expiresAt: null });

  const store = await cookies();
  const token = store.get(SESSION_COOKIE)?.value;
  const session = verifySessionToken(token, config.secret);
  if (!session) return res({ user: null, expiresAt: null });

  return res({ user: session.username, expiresAt: session.expiresAt * 1000 });
}
