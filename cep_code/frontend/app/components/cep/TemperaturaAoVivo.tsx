"use client";

import { useMemo } from "react";
import {
  CartesianGrid,
  Label,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useRelatorioStream } from "@/hooks/useRelatorioStream";

const CANAL_TEMPERATURA = "default";

// d2 pra n=2 (par usado na amplitude móvel) — mesma tabela de constantes
// de cep_code/backend/CEP/constantes.py, linha n=2: (A2, D3, D4, d2).
const D2_N2 = 1.128;
const MINIMO_PONTOS_LIMITES = 5;

interface LimitesIMR {
  mediaInd: number;
  lscInd: number;
  licInd: number;
}

/** Carta I (Individuals): sigma estimado pela amplitude móvel, LSC/LIC = média ± 3σ.
 * Mesma fórmula de processar_tipo_imr em cep_code/backend/CEP/amostras/data_processor.py. */
function calcularLimitesIMR(valores: number[]): LimitesIMR | null {
  if (valores.length < MINIMO_PONTOS_LIMITES) return null;
  const mediaInd = valores.reduce((a, b) => a + b, 0) / valores.length;
  const amplitudes = valores.slice(1).map((v, i) => Math.abs(v - valores[i]));
  const amBar = amplitudes.reduce((a, b) => a + b, 0) / amplitudes.length;
  const sigmaInd = amBar / D2_N2;
  return {
    mediaInd,
    lscInd: mediaInd + 3 * sigmaInd,
    licInd: mediaInd - 3 * sigmaInd,
  };
}

function formatHora(iso: string): string {
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

export default function TemperaturaAoVivo() {
  const { status, erro, buffer } = useRelatorioStream({
    canal: CANAL_TEMPERATURA,
    replayN: 60,
    bufferSize: 120,
  });

  const pontos = useMemo(
    () =>
      buffer
        .filter((m) => m.chart === "imr" && typeof m.valor === "number")
        .map((m) => ({
          hora: formatHora(m.received_at),
          valor: m.valor as number,
          received_at: m.received_at,
        })),
    [buffer],
  );

  const limites = useMemo(
    () => calcularLimitesIMR(pontos.map((p) => p.valor)),
    [pontos],
  );

  const ultimo = pontos.length > 0 ? pontos[pontos.length - 1] : null;
  const foraDeControle =
    limites && ultimo
      ? ultimo.valor > limites.lscInd || ultimo.valor < limites.licInd
      : false;

  return (
    <div className="bg-surface border border-line rounded-3xl shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-line flex items-center justify-between gap-4">
        <div>
          <h2 className="text-[15px] font-semibold tracking-tight text-fg">
            Temperatura ao vivo
          </h2>
          <p className="mt-0.5 text-[13px] text-fg-muted">
            Leituras do sensor DHT11 (ESP32 → Raspberry Pi → CEP)
          </p>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span
            className={`inline-block h-2 w-2 rounded-full ${
              status === "connected"
                ? "bg-emerald-500"
                : status === "error"
                  ? "bg-red-500"
                  : "bg-fg-muted"
            }`}
          />
          <span className="text-[12px] text-fg-muted">
            {status === "connected" ? "ao vivo" : status === "connecting" ? "conectando…" : status}
          </span>
        </div>
      </div>

      {erro && (
        <div className="mx-6 mt-4 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-[13px] text-red-400">
          {erro}
        </div>
      )}

      <div className="px-6 pt-5">
        <div className={`text-4xl font-semibold tracking-tight ${foraDeControle ? "text-red-400" : "text-fg"}`}>
          {ultimo ? `${ultimo.valor.toFixed(1)}°C` : "—"}
        </div>
        {ultimo && (
          <p className="mt-1 text-[13px] text-fg-muted">
            última leitura às {ultimo.hora}
            {foraDeControle && " — fora dos limites de controle (Carta I)"}
          </p>
        )}
        {limites && (
          <p className="mt-0.5 text-[12px] text-fg-muted font-mono">
            LC {limites.mediaInd.toFixed(2)}°C · LSC {limites.lscInd.toFixed(2)}°C · LIC {limites.licInd.toFixed(2)}°C
          </p>
        )}
      </div>

      <div className="px-2 pb-4 pt-2 h-64">
        {pontos.length === 0 ? (
          <p className="px-4 py-10 text-center text-[13px] text-fg-muted">
            Aguardando leituras… assim que a ESP32 publicar, os pontos aparecem aqui.
          </p>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={pontos} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
              <XAxis
                dataKey="hora"
                stroke="var(--fg-muted)"
                fontSize={11}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                stroke="var(--fg-muted)"
                fontSize={11}
                tickLine={false}
                domain={["auto", "auto"]}
                unit="°C"
                width={48}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--surface)",
                  border: "1px solid var(--line)",
                  borderRadius: 12,
                  fontSize: 12,
                  color: "var(--fg)",
                }}
                formatter={(value) => {
                  const n = typeof value === "number" ? value : Number(value);
                  return [`${Number.isFinite(n) ? n.toFixed(1) : value}°C`, "Temperatura"];
                }}
              />
              {limites && (
                <>
                  <ReferenceLine y={limites.mediaInd} stroke="var(--fg-muted)" strokeDasharray="2 2">
                    <Label value="LC" position="right" fill="var(--fg-muted)" fontSize={11} />
                  </ReferenceLine>
                  <ReferenceLine y={limites.lscInd} stroke="var(--danger)" strokeDasharray="4 4">
                    <Label value="LSC" position="right" fill="var(--danger)" fontSize={11} />
                  </ReferenceLine>
                  <ReferenceLine y={limites.licInd} stroke="var(--danger)" strokeDasharray="4 4">
                    <Label value="LIC" position="right" fill="var(--danger)" fontSize={11} />
                  </ReferenceLine>
                </>
              )}
              <Line
                type="monotone"
                dataKey="valor"
                stroke="var(--accent)"
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
