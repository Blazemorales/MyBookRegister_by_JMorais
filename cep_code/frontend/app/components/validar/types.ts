import type { AnaliseCorridas, ViolacaoWE } from "@/app/lib/stats";

export type ModoProb = "menor" | "maior" | "intervalo";

export interface Parametros {
  nome: string;
  mu: number;
  sigma: number;
  lsc: number;
  lm: number;
  lic: number;
  n: number;
  pontos: number[];
}

export interface ResultadoProb {
  modo: ModoProb;
  a: number;
  b?: number;
  z_a: number;
  z_b?: number;
  p: number;
  p_complementar: number;
  expressao: string;
}

export interface ResultadoLimites {
  lic: number;
  lsc: number;
  z_lic: number;
  z_lsc: number;
  pAbaixo: number;
  pDentro: number;
  pAcima: number;
}

export interface ResultadoARL {
  L: number;
  n: number;
  k: number;
  arl0: number;
  arl1: number;
  probDentro: number;
  probFora: number;
  corridas: AnaliseCorridas | null;
  violacoes: ViolacaoWE[];
}

export const PARAMS_VAZIO: Parametros = {
  nome: "Processo",
  mu: 0,
  sigma: 1,
  lsc: 3,
  lm: 0,
  lic: -3,
  n: 1,
  pontos: [],
};

export const fmt = (v: number, casas = 4) =>
  Number.isFinite(v) ? v.toFixed(casas) : "∞";

export const pct = (v: number, casas = 4) =>
  Number.isFinite(v) ? (v * 100).toFixed(casas) + "%" : "—";
