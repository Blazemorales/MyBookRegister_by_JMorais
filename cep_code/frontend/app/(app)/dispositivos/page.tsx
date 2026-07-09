"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRelatorioStream, type Medicao } from "@/hooks/useRelatorioStream";
import RelatoriosPeriodicos from "@/app/components/cep/RelatoriosPeriodicos";
import TemperaturaAoVivo from "@/app/components/cep/TemperaturaAoVivo";

const CANAL_LAMPADA = "lampada";

export default function DispositivosPage() {
  const { status, erro, buffer, deviceStatus } = useRelatorioStream({
    canal: CANAL_LAMPADA,
    replayN: 20,
  });
  const [refreshRelatorios, setRefreshRelatorios] = useState(0);

  const sessoes = [...buffer]
    .filter((m) => m.chart === "imr" && m.canal === CANAL_LAMPADA)
    .reverse();

  return (
    <section className="pt-12 pb-20">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-[13px] text-fg-muted hover:text-fg transition-colors mb-6"
      >
        ← Menu
      </Link>

      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-fg">
            Meus dispositivos
          </h1>
          <p className="mt-1 text-[14px] text-fg-muted">
            Lâmpada monitorada pela ESP32 — estado ao vivo, sessões recentes e relatórios de CEP.
          </p>
        </div>
        <StatusBadge status={status} />
      </header>

      {erro && (
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-[13px] text-red-400">
          {erro}
        </div>
      )}

      <div className="mb-8">
        <LampadaStatusCard aceso={deviceStatus?.aceso ?? null} desde={deviceStatus?.received_at ?? null} />
      </div>

      <div className="mb-8">
        <TemperaturaAoVivo />
      </div>

      <div className="bg-surface border border-line rounded-3xl shadow-sm overflow-hidden mb-8">
        <div className="px-6 py-4 border-b border-line">
          <h2 className="text-[15px] font-semibold tracking-tight text-fg">
            Últimas Sessões
          </h2>
        </div>
        {sessoes.length === 0 ? (
          <p className="px-6 py-10 text-center text-[13px] text-fg-muted">
            Nenhuma sessão registrada ainda. Assim que a lâmpada ligar e desligar, ela aparece aqui.
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {sessoes.map((m, i) => (
              <SessaoItem key={`${m.received_at}-${i}`} medicao={m} />
            ))}
          </ul>
        )}
      </div>

      <div className="bg-surface border border-line rounded-3xl shadow-sm overflow-hidden">
        <div className="px-6 py-4 border-b border-line flex items-center justify-between gap-4">
          <h2 className="text-[15px] font-semibold tracking-tight text-fg">
            Relatórios
          </h2>
          <GerarRelatorioButton
            canal={CANAL_LAMPADA}
            onGerado={() => setRefreshRelatorios((n) => n + 1)}
          />
        </div>
        <RelatoriosPeriodicos canal={CANAL_LAMPADA} refreshSignal={refreshRelatorios} />
      </div>
    </section>
  );
}

function LampadaStatusCard({
  aceso,
  desde,
}: {
  aceso: boolean | null;
  desde: string | null;
}) {
  const [agora, setAgora] = useState(() => Date.now());
  const [pendente, setPendente] = useState<"on" | "off" | null>(null);
  const [erroControle, setErroControle] = useState<string | null>(null);

  // Estado otimista: o clique já muda o botão/badge na hora (aceso + desde),
  // mas quem confirma de verdade é o próximo `device_status` via Socket.IO —
  // quando ele chegar, os dois efeitos abaixo descartam o otimista e passam
  // a refletir o estado real.
  const [acesoOtimista, setAcesoOtimista] = useState<boolean | null>(null);
  const [desdeOtimista, setDesdeOtimista] = useState<string | null>(null);
  useEffect(() => setAcesoOtimista(null), [aceso]);
  useEffect(() => setDesdeOtimista(null), [desde]);
  const acesoExibido = acesoOtimista ?? aceso;
  const desdeExibido = desdeOtimista ?? desde;

  useEffect(() => {
    if (!acesoExibido) return;
    const id = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(id);
  }, [acesoExibido]);

  const elapsed =
    acesoExibido && desdeExibido
      ? Math.max(0, Math.floor((agora - new Date(desdeExibido).getTime()) / 1000))
      : null;

  async function acionar(acao: "on" | "off") {
    setPendente(acao);
    setErroControle(null);
    try {
      const res = await fetch(`/api/lampada/${acao}`, { method: "POST" });
      if (!res.ok) {
        const corpo = await res.json().catch(() => ({}) as { error?: string });
        throw new Error(corpo.error ?? `HTTP ${res.status}`);
      }
      setAcesoOtimista(acao === "on");
      setDesdeOtimista(new Date().toISOString());
    } catch (e) {
      setErroControle(e instanceof Error ? e.message : "falha ao acionar a lâmpada");
    } finally {
      setPendente(null);
    }
  }

  return (
    <div className="bg-surface border border-line rounded-3xl shadow-sm p-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-4">
          <span
            className={`h-3 w-3 rounded-full ${
              acesoExibido === null
                ? "bg-zinc-400"
                : acesoExibido
                  ? "bg-emerald-500 animate-pulse"
                  : "bg-zinc-400"
            }`}
          />
          <div>
            <p className="text-[13px] uppercase tracking-wide text-fg-muted">Lâmpada</p>
            <p className="text-xl font-semibold text-fg">
              {acesoExibido === null
                ? "Estado desconhecido — aguardando o dispositivo"
                : acesoExibido
                  ? `Ligada há ${formatarDuracao(elapsed ?? 0)}`
                  : "Apagada"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => acionar("on")}
            disabled={pendente !== null}
            className="rounded-full bg-accent text-white px-4 py-2 text-[13px] font-medium disabled:opacity-50 hover:bg-accent-hover transition-colors"
          >
            {pendente === "on" ? "Ligando…" : "Ligar"}
          </button>
          <button
            onClick={() => acionar("off")}
            disabled={pendente !== null}
            className="rounded-full border border-line px-4 py-2 text-[13px] font-medium text-fg disabled:opacity-50 hover:bg-surface-alt transition-colors"
          >
            {pendente === "off" ? "Desligando…" : "Desligar"}
          </button>
        </div>
      </div>

      {erroControle && (
        <p className="mt-3 text-[13px] text-red-400">{erroControle}</p>
      )}
    </div>
  );
}

function GerarRelatorioButton({
  canal,
  onGerado,
}: {
  canal: string;
  onGerado: () => void;
}) {
  const [estado, setEstado] = useState<"idle" | "gerando" | "ok" | "erro">("idle");
  const [mensagem, setMensagem] = useState<string | null>(null);

  async function gerar() {
    setEstado("gerando");
    setMensagem(null);
    try {
      const res = await fetch("/api/lampada-relatorio", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ canal }),
      });
      const corpo = await res.json().catch(() => ({}) as { error?: string; detail?: string });
      if (!res.ok) {
        throw new Error(corpo.error ?? corpo.detail ?? `HTTP ${res.status}`);
      }
      setEstado("ok");
      setMensagem("Relatório gerado.");
      onGerado();
    } catch (e) {
      setEstado("erro");
      setMensagem(e instanceof Error ? e.message : "falha ao gerar relatório");
    }
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        onClick={gerar}
        disabled={estado === "gerando"}
        className="rounded-full border border-line px-4 py-1.5 text-[12px] font-medium text-fg disabled:opacity-50 hover:bg-surface-alt transition-colors whitespace-nowrap"
      >
        {estado === "gerando" ? "Gerando…" : "Gerar relatório agora"}
      </button>
      {mensagem && (
        <span className={`text-[12px] ${estado === "erro" ? "text-red-400" : "text-fg-muted"}`}>
          {mensagem}
        </span>
      )}
    </div>
  );
}

function SessaoItem({ medicao }: { medicao: Medicao }) {
  const duracaoS = typeof medicao.valor === "number" ? medicao.valor : 0;
  const fim = new Date(medicao.received_at);
  const inicio = new Date(fim.getTime() - duracaoS * 1000);

  return (
    <li className="grid grid-cols-[1fr_auto] items-baseline gap-4 px-6 py-3 text-[13px]">
      <span className="text-fg-muted font-mono">
        {formatarHora(inicio)} → {formatarHora(fim)}
      </span>
      <span className="font-mono text-fg">{formatarDuracao(duracaoS)}</span>
    </li>
  );
}

function formatarDuracao(segundos: number): string {
  const s = Math.round(segundos);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const rs = s % 60;
  if (h > 0) return `${h}h ${m}m ${rs}s`;
  if (m > 0) return `${m}m ${rs}s`;
  return `${rs}s`;
}

function formatarHora(d: Date): string {
  try {
    return d.toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZone: "America/Sao_Paulo",
    });
  } catch {
    return d.toISOString();
  }
}

function StatusBadge({ status }: { status: string }) {
  const cores: Record<string, string> = {
    idle: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
    connecting: "bg-yellow-500/15 text-yellow-300 border-yellow-500/30",
    connected: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    disconnected: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
    error: "bg-red-500/15 text-red-300 border-red-500/30",
  };
  const rotulos: Record<string, string> = {
    idle: "aguardando",
    connecting: "conectando",
    connected: "ao vivo",
    disconnected: "desconectado",
    error: "erro",
  };
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[12px] font-medium ${
        cores[status] ?? cores.idle
      }`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {rotulos[status] ?? status}
    </span>
  );
}
