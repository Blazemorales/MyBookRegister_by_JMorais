// Rate limit de login.
//
// Se UPSTASH_REDIS_REST_URL e UPSTASH_REDIS_REST_TOKEN estiverem
// configurados, usa Upstash via REST (compartilhado entre instâncias
// serverless). Caso contrário, cai para um Map em memória — funciona
// localmente, mas em Fluid Compute cada instância tem o seu próprio.

const WINDOW_MS = 5 * 60 * 1000;
const MAX_ATTEMPTS = 5;
const MAX_ENTRIES = 5_000;
const WINDOW_SEC = Math.floor(WINDOW_MS / 1000);

type Entry = { count: number; resetAt: number };
const memory = new Map<string, Entry>();

function memoryCleanup(now: number) {
  if (memory.size < MAX_ENTRIES) return;
  for (const [key, entry] of memory) {
    if (entry.resetAt < now) memory.delete(key);
  }
}

function upstashConfig(): { url: string; token: string } | null {
  const url = process.env.UPSTASH_REDIS_REST_URL;
  const token = process.env.UPSTASH_REDIS_REST_TOKEN;
  if (!url || !token) return null;
  return { url, token };
}

async function upstashCommand(
  cfg: { url: string; token: string },
  command: (string | number)[],
): Promise<unknown> {
  const res = await fetch(cfg.url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${cfg.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(command),
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Upstash ${res.status}`);
  }
  const json = (await res.json()) as { result?: unknown; error?: string };
  if (json.error) throw new Error(json.error);
  return json.result;
}

export function getClientIp(request: Request): string {
  // Na Vercel, x-vercel-forwarded-for é definido pela plataforma e não
  // pode ser falsificado pelo cliente.
  const vercel = request.headers.get("x-vercel-forwarded-for");
  if (vercel) {
    const first = vercel.split(",")[0]?.trim();
    if (first) return first;
  }
  const fwd = request.headers.get("x-forwarded-for");
  if (fwd) {
    const first = fwd.split(",")[0]?.trim();
    if (first) return first;
  }
  return request.headers.get("x-real-ip") ?? "unknown";
}

export async function checkLoginRateLimit(ip: string): Promise<{
  allowed: boolean;
  retryAfterSec: number;
}> {
  const cfg = upstashConfig();
  if (cfg) {
    try {
      const key = `ratelimit:login:${ip}`;
      const result = (await upstashCommand(cfg, ["GET", key])) as
        | string
        | null;
      const count = result ? Number(result) : 0;
      if (count >= MAX_ATTEMPTS) {
        const ttl = (await upstashCommand(cfg, ["TTL", key])) as number;
        return {
          allowed: false,
          retryAfterSec: Math.max(1, ttl > 0 ? ttl : WINDOW_SEC),
        };
      }
      return { allowed: true, retryAfterSec: 0 };
    } catch {
      // cai para in-memory em caso de falha
    }
  }

  const now = Date.now();
  memoryCleanup(now);
  const entry = memory.get(ip);
  if (!entry || entry.resetAt < now) {
    return { allowed: true, retryAfterSec: 0 };
  }
  if (entry.count >= MAX_ATTEMPTS) {
    return {
      allowed: false,
      retryAfterSec: Math.max(1, Math.ceil((entry.resetAt - now) / 1000)),
    };
  }
  return { allowed: true, retryAfterSec: 0 };
}

export async function recordLoginFailure(ip: string): Promise<void> {
  const cfg = upstashConfig();
  if (cfg) {
    try {
      const key = `ratelimit:login:${ip}`;
      const count = (await upstashCommand(cfg, ["INCR", key])) as number;
      if (count === 1) {
        await upstashCommand(cfg, ["EXPIRE", key, WINDOW_SEC]);
      }
      return;
    } catch {
      // cai para in-memory
    }
  }

  const now = Date.now();
  const entry = memory.get(ip);
  if (!entry || entry.resetAt < now) {
    memory.set(ip, { count: 1, resetAt: now + WINDOW_MS });
    return;
  }
  entry.count += 1;
}

export async function resetLoginAttempts(ip: string): Promise<void> {
  const cfg = upstashConfig();
  if (cfg) {
    try {
      await upstashCommand(cfg, ["DEL", `ratelimit:login:${ip}`]);
      return;
    } catch {
      // cai para in-memory
    }
  }
  memory.delete(ip);
}
