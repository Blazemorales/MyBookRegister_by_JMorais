import type { NextConfig } from "next";

// Origem pública do backend (HTTP + WS). Lida em tempo de build — o Next
// inlinea NEXT_PUBLIC_*. Em Docker, vem como build arg.
const SOCKET_ORIGIN = process.env.NEXT_PUBLIC_SOCKET_URL ?? "";
const WS_ORIGIN = SOCKET_ORIGIN.replace(/^http/, "ws");
const connectSrc = ["'self'", SOCKET_ORIGIN, WS_ORIGIN]
  .filter(Boolean)
  .join(" ");

// Política de Segurança de Conteúdo — restritiva, mas compatível com
// Next.js (precisa de 'unsafe-inline' para estilos e scripts inline
// gerados pelo framework).
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "img-src 'self' data: blob:",
  "font-src 'self' data: https://fonts.gstatic.com",
  `connect-src ${connectSrc}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
  "upgrade-insecure-requests",
].join("; ");

const nextConfig: NextConfig = {
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Content-Security-Policy", value: CSP },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
          },
        ],
      },
      {
        source: "/sw.js",
        headers: [
          {
            key: "Content-Type",
            value: "application/javascript; charset=utf-8",
          },
          {
            key: "Cache-Control",
            value: "no-cache, no-store, must-revalidate",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
