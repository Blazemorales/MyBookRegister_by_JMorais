"use client";

import { useRelatorioStream, type Medicao } from "@/hooks/useRelatorioStream";

export default function AoVivoPage() {
  // Pede 20 pontos de replay ao conectar para a página não começar vazia
  // se o dispositivo já estava emitindo antes do user abrir.
  const { status, erro, ultimo, buffer, limpar } = useRelatorioStream({
    replayN: 20,
  });

  return (
    <section className="pt-12 pb-20">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-fg">
            Receber em tempo real
          </h1>
          <p className="mt-1 text-[14px] text-fg-muted">
            Stream das medições enviadas pelo dispositivo.
          </p>
        </div>
        <StatusBadge status={status} />
      </header>

      {erro && (
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-[13px] text-red-400">
          {erro}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <Card label="Última leitura">
          <ValorPrincipal medicao={ultimo} />
        </Card>
        <Card label="Carta">
          <p className="text-2xl font-semibold text-fg">
            {ultimo?.chart?.toUpperCase() ?? "—"}
          </p>
        </Card>
        <Card label="Pontos no buffer">
          <p className="text-2xl font-semibold text-fg">{buffer.length}</p>
        </Card>
      </div>

      <div className="bg-surface border border-line rounded-3xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-line">
          <h2 className="text-[15px] font-semibold tracking-tight text-fg">
            Histórico recente
          </h2>
          <button
            type="button"
            onClick={limpar}
            className="text-[13px] text-fg-muted hover:text-fg transition-colors"
          >
            Limpar
          </button>
        </div>
        {buffer.length === 0 ? (
          <p className="px-6 py-10 text-center text-[13px] text-fg-muted">
            Sem leituras ainda. Esperando o dispositivo enviar dados…
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {[...buffer].reverse().map((m, i) => (
              <li
                key={`${m.received_at}-${i}`}
                className="grid grid-cols-[1fr_auto_auto] items-baseline gap-4 px-6 py-3 text-[13px]"
              >
                <span className="text-fg-muted">
                  {formatarHora(m.received_at)}
                  {m.canal ? ` · ${m.canal}` : ""}
                </span>
                <span className="text-fg-muted uppercase">
                  {m.chart ?? "—"}
                </span>
                <span className="font-mono text-fg">
                  {formatarValor(m)}
                  {m.unidade ? ` ${m.unidade}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

function ValorPrincipal({ medicao }: { medicao: Medicao | null }) {
  if (!medicao) {
    return <p className="text-2xl font-semibold text-fg-muted">—</p>;
  }
  return (
    <p className="text-2xl font-semibold text-fg">
      {formatarValor(medicao)}
      {medicao.unidade && (
        <span className="ml-1 text-[14px] text-fg-muted">
          {medicao.unidade}
        </span>
      )}
    </p>
  );
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

function Card({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-surface border border-line rounded-2xl p-5 shadow-sm">
      <p className="text-[12px] uppercase tracking-wide text-fg-muted">
        {label}
      </p>
      <div className="mt-2">{children}</div>
    </div>
  );
}

function formatarValor(m: Medicao): string {
  if (typeof m.valor === "number") return m.valor.toString();
  if (Array.isArray(m.valores)) return `${m.valores.length} valores`;
  return "—";
}

function formatarHora(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("pt-BR", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}
