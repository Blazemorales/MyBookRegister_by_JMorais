"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

const WARNING_LEAD_MS = 2 * 60 * 1000;

export default function SessionWatcher() {
  const router = useRouter();
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());
  const [extending, setExtending] = useState(false);
  const loggedOutRef = useRef(false);

  const goToLogin = useCallback(async () => {
    if (loggedOutRef.current) return;
    loggedOutRef.current = true;
    try {
      await fetch("/api/logout", { method: "POST" });
    } catch {}
    router.replace("/login");
    router.refresh();
  }, [router]);

  const fetchSession = useCallback(async () => {
    try {
      const r = await fetch("/api/me", { cache: "no-store" });
      const data = (await r.json()) as { user: string | null; expiresAt: number | null };
      if (!data.user || !data.expiresAt) {
        await goToLogin();
        return;
      }
      setExpiresAt(data.expiresAt);
    } catch {}
  }, [goToLogin]);

  useEffect(() => {
    // Data fetching de mount — não há equivalente RSC porque o
    // componente precisa ser client (controla modal de expiração).
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchSession();
  }, [fetchSession]);

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") fetchSession();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [fetchSession]);

  useEffect(() => {
    if (!expiresAt) return;
    let interval: ReturnType<typeof setInterval> | null = null;
    const startTick = () => {
      interval = setInterval(() => setNow(Date.now()), 1000);
    };

    const msUntilWarning = expiresAt - Date.now() - WARNING_LEAD_MS;
    if (msUntilWarning <= 0) {
      startTick();
      return () => {
        if (interval) clearInterval(interval);
      };
    }

    const timeout = setTimeout(() => {
      setNow(Date.now());
      startTick();
    }, msUntilWarning);

    return () => {
      clearTimeout(timeout);
      if (interval) clearInterval(interval);
    };
  }, [expiresAt]);

  useEffect(() => {
    if (!expiresAt) return;
    if (now >= expiresAt) {
      goToLogin();
    }
  }, [now, expiresAt, goToLogin]);

  async function handleExtend() {
    setExtending(true);
    try {
      const r = await fetch("/api/refresh", { method: "POST" });
      if (!r.ok) {
        await goToLogin();
        return;
      }
      const data = (await r.json()) as { expiresAt: number };
      setExpiresAt(data.expiresAt);
    } catch {
      await goToLogin();
    } finally {
      setExtending(false);
    }
  }

  if (!expiresAt) return null;
  const remaining = expiresAt - now;
  if (remaining > WARNING_LEAD_MS) return null;
  if (remaining <= 0) return null;

  const totalSec = Math.max(0, Math.ceil(remaining / 1000));
  const mm = Math.floor(totalSec / 60);
  const ss = totalSec % 60;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="session-warning-title"
        className="w-full max-w-sm rounded-2xl bg-surface border border-line shadow-xl p-6 text-center"
      >
        <h2
          id="session-warning-title"
          className="text-[17px] font-semibold tracking-tight text-fg"
        >
          Sua sessão vai expirar
        </h2>
        <p className="mt-2 text-[14px] text-fg-muted">
          Por segurança, você será desconectado em
        </p>
        <p className="mt-3 text-4xl font-semibold tracking-tight tabular-nums text-fg">
          {mm}:{ss.toString().padStart(2, "0")}
        </p>
        <div className="mt-6 flex gap-2">
          <button
            onClick={() => goToLogin()}
            className="flex-1 px-4 py-2.5 rounded-full bg-surface-alt text-fg hover:bg-line/60 text-[15px] font-medium transition-colors"
          >
            Sair agora
          </button>
          <button
            onClick={handleExtend}
            disabled={extending}
            className="flex-1 px-4 py-2.5 rounded-full bg-accent text-white hover:opacity-90 disabled:opacity-50 text-[15px] font-medium transition-colors"
          >
            {extending ? "Estendendo…" : "Estender sessão"}
          </button>
        </div>
      </div>
    </div>
  );
}
