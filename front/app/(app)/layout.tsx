"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import SessionWatcher from "../components/SessionWatcher";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [user, setUser] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  useEffect(() => {
    fetch("/api/me", { cache: "no-store" })
      .then((r) => r.json())
      .then((data) => setUser(data?.user ?? null))
      .catch(() => setUser(null));
  }, []);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      await fetch("/api/logout", { method: "POST" });
      router.replace("/login");
      router.refresh();
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="min-h-screen bg-canvas text-fg">
      <SessionWatcher />
      <header className="sticky top-0 z-40 bg-nav-bg backdrop-blur-xl supports-[backdrop-filter]:bg-nav-bg border-b border-line/60">
        <div className="max-w-5xl mx-auto px-6 h-12 flex items-center justify-between">
          <Link
            href="/"
            className="flex items-center gap-2 text-[15px] font-semibold tracking-tight hover:opacity-80 transition-opacity"
          >
            <Image
              src="/placa-mae.png"
              alt="CEP TPE"
              width={24}
              height={24}
              priority
              className="rounded-md dark:invert"
            />
            MyBookRegister by JMorais
          </Link>
          <div className="flex items-center gap-3 text-[13px]">
            {user && (
              <span className="text-fg-muted">
                Olá, <span className="text-fg font-medium">{user}</span>
              </span>
            )}
            <button
              onClick={handleLogout}
              disabled={loggingOut}
              className="px-3 py-1 rounded-full text-fg-muted hover:text-fg hover:bg-surface-alt disabled:opacity-50 transition-colors"
            >
              {loggingOut ? "Saindo…" : "Sair"}
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-5xl mx-auto px-6 pb-24">{children}</main>
    </div>
  );
}
