"use client";

import { Suspense, useState } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";

type Mode = "login" | "register";

// Aceita apenas paths locais — evita open redirect via ?next=https://…
function safeNext(next: string | null): string {
  if (!next) return "/";
  if (!next.startsWith("/") || next.startsWith("//")) return "/";
  return next;
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const next = safeNext(searchParams.get("next"));
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const isRegister = mode === "register";

  function switchMode(novoModo: Mode) {
    setMode(novoModo);
    setError(null);
    setInfo(null);
    setConfirmPassword("");
  }

  async function doLogin(user: string, pass: string): Promise<boolean> {
    const res = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pass }),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setError(data?.error ?? "Falha ao entrar.");
      return false;
    }
    return true;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setInfo(null);

    if (isRegister && password !== confirmPassword) {
      setError("As senhas não coincidem.");
      return;
    }

    setLoading(true);
    try {
      if (isRegister) {
        const res = await fetch("/api/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(data?.error ?? "Falha ao criar conta.");
          return;
        }
        setInfo("Conta criada. Entrando…");
      }

      const ok = await doLogin(username, password);
      if (!ok) return;
      router.replace(next);
      router.refresh();
    } catch {
      setError("Erro de rede. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-canvas text-fg flex items-center justify-center p-6">
      <div className="w-full max-w-sm bg-surface border border-line rounded-3xl shadow-sm p-10 space-y-8">
        <header className="text-center space-y-3 flex flex-col items-center">
          <Image
            src="/placa-mae.png"
            alt="Logo do CEP"
            width={72}
            height={72}
            priority
            className="dark:invert"
          />
          <h1 className="text-3xl font-semibold tracking-tight">MyBookRegister by J.Morais</h1>
          <p className="text-[15px] text-fg-muted">
            {isRegister ? "Crie sua conta para começar." : "Entre para continuar."}
          </p>
        </header>

        <div
          role="tablist"
          aria-label="Modo de autenticação"
          className="grid grid-cols-2 gap-1 rounded-full bg-surface-alt p-1 text-[13px] font-medium"
        >
          <button
            type="button"
            role="tab"
            aria-selected={!isRegister}
            onClick={() => switchMode("login")}
            className={`py-2 rounded-full transition-colors ${
              !isRegister
                ? "bg-surface text-fg shadow-sm"
                : "text-fg-muted hover:text-fg"
            }`}
          >
            Entrar
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isRegister}
            onClick={() => switchMode("register")}
            className={`py-2 rounded-full transition-colors ${
              isRegister
                ? "bg-surface text-fg shadow-sm"
                : "text-fg-muted hover:text-fg"
            }`}
          >
            Criar conta
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label
              htmlFor="username"
              className="text-[13px] font-medium text-fg-muted"
            >
              Usuário
            </label>
            <input
              id="username"
              name="username"
              type="text"
              autoComplete="username"
              autoCapitalize="none"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-surface-alt border border-line text-fg placeholder:text-fg-muted focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent-soft transition-all"
            />
          </div>

          <div className="space-y-1.5">
            <label
              htmlFor="password"
              className="text-[13px] font-medium text-fg-muted"
            >
              Senha
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={isRegister ? "new-password" : "current-password"}
              required
              minLength={isRegister ? 6 : undefined}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2.5 rounded-xl bg-surface-alt border border-line text-fg placeholder:text-fg-muted focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent-soft transition-all"
            />
            {isRegister && (
              <p className="text-[12px] text-fg-muted">Mínimo de 6 caracteres.</p>
            )}
          </div>

          {isRegister && (
            <div className="space-y-1.5">
              <label
                htmlFor="confirmPassword"
                className="text-[13px] font-medium text-fg-muted"
              >
                Confirmar senha
              </label>
              <input
                id="confirmPassword"
                name="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                minLength={6}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full px-4 py-2.5 rounded-xl bg-surface-alt border border-line text-fg placeholder:text-fg-muted focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent-soft transition-all"
              />
            </div>
          )}

          {error && (
            <p className="text-[13px] text-danger bg-danger-soft border border-danger/30 rounded-xl px-3 py-2">
              {error}
            </p>
          )}

          {info && !error && (
            <p className="text-[13px] text-fg-muted bg-surface-alt border border-line rounded-xl px-3 py-2">
              {info}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-accent hover:bg-accent-hover disabled:opacity-60 disabled:cursor-not-allowed text-white font-medium tracking-tight rounded-full py-2.5 transition-colors"
          >
            {loading
              ? isRegister
                ? "Criando…"
                : "Entrando…"
              : isRegister
                ? "Criar conta"
                : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
