import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import {
  SESSION_COOKIE,
  readAuthConfig,
  verifySessionToken,
} from "./app/lib/auth";

const PUBLIC_PATHS = new Set<string>([
  "/login",
  "/api/login",
  "/api/register",
  "/acesso-negado",
]);

export function proxy(request: NextRequest) {
  const config = readAuthConfig();
  if (!config) {
    if (request.nextUrl.pathname === "/acesso-negado") {
      return NextResponse.next();
    }
    const deniedUrl = request.nextUrl.clone();
    deniedUrl.pathname = "/acesso-negado";
    deniedUrl.search = "";
    return NextResponse.rewrite(deniedUrl);
  }

  const { pathname } = request.nextUrl;
  const isApi = pathname.startsWith("/api/");
  const isPublic = PUBLIC_PATHS.has(pathname);

  const token = request.cookies.get(SESSION_COOKIE)?.value;
  const session = verifySessionToken(token, config.secret);

  if (session) {
    if (pathname === "/login") {
      const homeUrl = request.nextUrl.clone();
      homeUrl.pathname = "/";
      homeUrl.search = "";
      return NextResponse.redirect(homeUrl);
    }
    return NextResponse.next();
  }

  if (isPublic) {
    return NextResponse.next();
  }

  if (isApi) {
    return new NextResponse("Unauthorized", { status: 401 });
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  loginUrl.search = "";
  const next = `${pathname}${request.nextUrl.search}`;
  if (next && next !== "/" && next.startsWith("/") && !next.startsWith("//")) {
    loginUrl.searchParams.set("next", next);
  }
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/((?!\\.well-known|_next/static|_next/image|manifest.webmanifest|sw.js|icon-192.png|icon-512.png|favicon.ico|placa-mae.png).*)",
  ],
};
