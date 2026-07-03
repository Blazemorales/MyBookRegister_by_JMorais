"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRelatorioStream, type Medicao } from "@/hooks/useRelatorioStream";
import RelatoriosPeriodicos from "@/app/components/cep/RelatoriosPeriodicos";

const CANAL_LAMPADA = "lampada";

export default function DispositivosPage() {
  const { status, erro, buffer, deviceStatus } = useRelatorioStream({
    canal: CANAL_LAMPADA,
    replayN: 20,
  });

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
        <div className="px-6 py-4 border-b border-line">
          <h2 className="text-[15px] font-semibold tracking-tight text-fg">
            Relatórios
          </h2>
        </div>
        <RelatoriosPeriodicos canal={CANAL_LAMPADA} />
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

  useEffect(() => {
    if (!aceso) return;
    const id = setInterval(() => setAgora(Date.now()), 1000);
    return () => clearInterval(id);
  }, [aceso]);

  const elapsed =
    aceso && desde ? Math.max(0, Math.floor((agora - new Date(desde).getTime()) / 1000)) : null;

  return (
    <div className="bg-surface border border-line rounded-3xl shadow-sm p-6 flex items-center gap-4">
      <span
        className={`h-3 w-3 rounded-full ${
          aceso === null
            ? "bg-zinc-400"
            : aceso
              ? "bg-emerald-500 animate-pulse"
              : "bg-zinc-400"
        }`}
      />
      <div>
        <p className="text-[13px] uppercase tracking-wide text-fg-muted">Lâmpada</p>
        <p className="text-xl font-semibold text-fg">
          {aceso === null
            ? "Estado desconhecido — aguardando o dispositivo"
            : aceso
              ? `Ligada há ${formatarDuracao(elapsed ?? 0)}`
              : "Apagada"}
        </p>
      </div>
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
