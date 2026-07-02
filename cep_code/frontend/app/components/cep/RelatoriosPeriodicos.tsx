"use client";

import { useEffect, useState } from "react";
import { useRelatoriosPeriodicos, type TipoPeriodico } from "@/hooks/useRelatoriosPeriodicos";

function FmtData({ iso }: { iso: string }) {
  try {
    const d = new Date(iso);
    return (
      <time dateTime={iso} title={iso}>
        {d.toLocaleString("pt-BR", {
          day: "2-digit",
          month: "2-digit",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
          timeZone: "America/Sao_Paulo",
        })}
      </time>
    );
  } catch {
    return <span>{iso}</span>;
  }
}

function IndicadoresBloco({ dados }: { dados: Record<string, unknown> }) {
  // Mostra os indicadores principais do answer set de forma compacta
  const charts = ["XR", "IMR"] as const;
  const atributos = dados["atributos"] as Record<string, unknown> | undefined;

  return (
    <div className="flex flex-col gap-4 text-sm">
      {charts.map((chart) => {
        const d = dados[chart] as Record<string, unknown> | undefined;
        if (!d) return null;
        return (
          <div key={chart} className="bg-surface-alt rounded-xl p-3">
            <p className="text-xs font-semibold text-fg-muted uppercase tracking-widest mb-2">
              Carta {chart}
            </p>
            <div className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-xs">
              {(d.longo_prazo as Record<string, unknown> | undefined) && (
                <>
                  <span>ppm = {((d.longo_prazo as Record<string, number>).ppm_obtido).toFixed(2)}</span>
                  <span className={(d.longo_prazo as Record<string, unknown>).atende ? "text-emerald-600" : "text-red-500"}>
                    {(d.longo_prazo as Record<string, unknown>).atende ? "ATENDE" : "NÃO ATENDE"}
                  </span>
                </>
              )}
              {d.margem_atual != null && (
                <span>margem = {((d.margem_atual as number) * 100).toFixed(4)}%</span>
              )}
              {(d.capacidade as Record<string, unknown> | undefined) && (
                <span>
                  Cpk = {((d.capacidade as Record<string, number | null>).cpk ?? 0)?.toFixed(4) ?? "N/A"}
                </span>
              )}
            </div>
          </div>
        );
      })}

      {atributos && (
        <div className="bg-surface-alt rounded-xl p-3">
          <p className="text-xs font-semibold text-fg-muted uppercase tracking-widest mb-2">
            Atributos (P / U)
          </p>
          {(atributos.carta_p as Record<string, unknown> | undefined) && (
            <p className="text-xs font-mono">
              P̄ = {((atributos.carta_p as Record<string, number>).P_bar).toFixed(6)}
              {" — "}
              {((atributos.carta_p as Record<string, Record<string, boolean>>).curto_prazo?.sob_controle) ? "Sob controle" : "Fora de controle"}
            </p>
          )}
          {(atributos.carta_u as Record<string, unknown> | undefined) && (
            <p className="text-xs font-mono">
              Ū = {((atributos.carta_u as Record<string, number>).U_bar).toFixed(6)}
              {" — "}
              {((atributos.carta_u as Record<string, Record<string, boolean>>).curto_prazo?.sob_controle) ? "Sob controle" : "Fora de controle"}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function PainelRelatorio({ tipo }: { tipo: TipoPeriodico }) {
  const { carregando, erro, relatorio, buscar } = useRelatoriosPeriodicos();

  useEffect(() => {
    buscar(tipo);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tipo]);

  const titulo = tipo === "diario" ? "Relatório Diário" : "Relatório Mensal";
  const descricao =
    tipo === "diario"
      ? "Gerado às 03:00 BRT com os dados do dia anterior."
      : "Gerado no dia 1 às 03:05 BRT com os dados do mês anterior.";

  return (
    <div className="flex flex-col gap-4 max-w-2xl mx-auto">
      <div className="text-center">
        <h3 className="text-lg font-semibold tracking-tight text-fg">{titulo}</h3>
        <p className="text-xs text-fg-muted mt-1">{descricao}</p>
      </div>

      {carregando && (
        <div className="flex items-center justify-center gap-2 text-sm text-fg-muted p-8">
          <span className="animate-spin">⟳</span> Carregando…
        </div>
      )}

      {erro && (
        <div className="p-3 bg-surface-alt text-fg-muted border border-line rounded-xl text-sm text-center">
          {erro}
        </div>
      )}

      {relatorio && !carregando && (
        <div className="border border-line rounded-2xl bg-surface p-4 flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-fg-muted">Período</p>
              <p className="font-mono font-semibold">{relatorio.periodo}</p>
            </div>
            <div className="text-right">
              <p className="text-xs text-fg-muted">Gerado em</p>
              <p className="text-xs font-mono">
                <FmtData iso={relatorio.gerado_em} />
              </p>
            </div>
          </div>

          {relatorio.dados && (
            <IndicadoresBloco dados={relatorio.dados} />
          )}

          <div className="flex gap-3 justify-center flex-wrap">
            <button
              onClick={() => buscar(tipo)}
              className="px-4 py-2 bg-surface-alt text-fg rounded-full text-sm font-medium hover:bg-line/60 transition-colors"
            >
              Atualizar
            </button>
            <a
              href={`${process.env.NEXT_PUBLIC_API_BASE ?? ""}/api/relatorios-periodicos/${tipo}?periodo=${relatorio.periodo}`}
              className="px-4 py-2 bg-accent text-white rounded-full text-sm font-medium hover:bg-accent-hover transition-colors"
            >
              Ver JSON
            </a>
          </div>
        </div>
      )}
    </div>
  );
}

export default function RelatoriosPeriodicos() {
  const [tipo, setTipo] = useState<TipoPeriodico>("diario");

  return (
    <div className="flex flex-col gap-6 p-8">
      <div className="flex gap-2 justify-center">
        {(["diario", "mensal"] as TipoPeriodico[]).map((t) => (
          <button
            key={t}
            onClick={() => setTipo(t)}
            className={`px-5 py-2 rounded-full text-[13px] font-medium tracking-tight transition-colors ${
              tipo === t
                ? "bg-accent text-white"
                : "bg-surface-alt text-fg hover:bg-line/60"
            }`}
          >
            {t === "diario" ? "Diário" : "Mensal"}
          </button>
        ))}
      </div>

      <PainelRelatorio key={tipo} tipo={tipo} />
    </div>
  );
}
