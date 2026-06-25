"use client";

import { useState, useCallback } from "react";

export type TipoPeriodico = "diario" | "mensal";

export interface RelatorioPeriodico {
  id: number;
  tipo: string;
  periodo: string;
  canal: string;
  gerado_em: string;
  dados?: Record<string, unknown>;
  charts?: Record<string, string>;
}

interface Estado {
  carregando: boolean;
  erro: string | null;
  relatorio: RelatorioPeriodico | null;
}

export function useRelatoriosPeriodicos(canal = "default") {
  const [estado, setEstado] = useState<Estado>({
    carregando: false,
    erro: null,
    relatorio: null,
  });

  const buscar = useCallback(
    async (tipo: TipoPeriodico, periodo?: string) => {
      setEstado((s) => ({ ...s, carregando: true, erro: null }));
      try {
        const url =
          `/api/relatorios-periodicos/${tipo}` +
          (periodo ? `?periodo=${periodo}&canal=${canal}` : `?canal=${canal}`);
        const res = await fetch(url, { cache: "no-store" });
        if (res.status === 404) {
          setEstado((s) => ({
            ...s,
            carregando: false,
            relatorio: null,
            erro: `Nenhum relatório ${tipo} disponível ainda.`,
          }));
          return null;
        }
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const json = (await res.json()) as RelatorioPeriodico;
        setEstado({ carregando: false, erro: null, relatorio: json });
        return json;
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Erro ao buscar relatório";
        setEstado((s) => ({ ...s, carregando: false, erro: msg }));
        return null;
      }
    },
    [canal],
  );

  return { ...estado, buscar };
}
