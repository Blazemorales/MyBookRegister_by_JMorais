// Distribuição Normal e Comprimento Médio de Corrida (CMC / ARL)
// Referência: Montgomery, "Probabilidade e Estatística Aplicada à Engenharia"
// (formulas e capítulos sobre cartas de controle de Shewhart).

// ─── Função erro (Abramowitz & Stegun 7.1.26, |err| < 1.5e-7) ─────────────
export function erf(x: number): number {
  const sign = x < 0 ? -1 : 1;
  const ax = Math.abs(x);

  const a1 = 0.254829592;
  const a2 = -0.284496736;
  const a3 = 1.421413741;
  const a4 = -1.453152027;
  const a5 = 1.061405429;
  const p = 0.3275911;

  const t = 1.0 / (1.0 + p * ax);
  const y =
    1.0 -
    ((((a5 * t + a4) * t + a3) * t + a2) * t + a1) * t * Math.exp(-ax * ax);

  return sign * y;
}

// ─── Φ(z): CDF da Normal padrão ───────────────────────────────────────────
export function normCDF(z: number): number {
  return 0.5 * (1 + erf(z / Math.SQRT2));
}

// ─── φ(z): PDF da Normal padrão ───────────────────────────────────────────
export function normPDF(z: number): number {
  return Math.exp(-0.5 * z * z) / Math.sqrt(2 * Math.PI);
}

// ─── Φ⁻¹(p): inversa da CDF — algoritmo de Acklam ─────────────────────────
export function normInverse(p: number): number {
  if (p <= 0 || p >= 1) {
    if (p === 0) return -Infinity;
    if (p === 1) return Infinity;
    return NaN;
  }

  const a = [
    -3.969683028665376e1, 2.209460984245205e2, -2.759285104469687e2,
    1.38357751867269e2, -3.066479806614716e1, 2.506628277459239,
  ];
  const b = [
    -5.447609879822406e1, 1.615858368580409e2, -1.556989798598866e2,
    6.680131188771972e1, -1.328068155288572e1,
  ];
  const c = [
    -7.784894002430293e-3, -3.223964580411365e-1, -2.400758277161838,
    -2.549732539343734, 4.374664141464968, 2.938163982698783,
  ];
  const d = [
    7.784695709041462e-3, 3.224671290700398e-1, 2.445134137142996,
    3.754408661907416,
  ];

  const pLow = 0.02425;
  const pHigh = 1 - pLow;
  let q: number, r: number;

  if (p < pLow) {
    q = Math.sqrt(-2 * Math.log(p));
    return (
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }

  if (p <= pHigh) {
    q = p - 0.5;
    r = q * q;
    return (
      ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) *
        q) /
      (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
    );
  }

  q = Math.sqrt(-2 * Math.log(1 - p));
  return (
    -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
    ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
  );
}

// ─── Probabilidades em torno de uma N(μ, σ²) ──────────────────────────────
export function zScore(x: number, mu: number, sigma: number): number {
  if (sigma === 0) return 0;
  return (x - mu) / sigma;
}

export function probLess(x: number, mu: number, sigma: number): number {
  return normCDF(zScore(x, mu, sigma));
}

export function probGreater(x: number, mu: number, sigma: number): number {
  return 1 - normCDF(zScore(x, mu, sigma));
}

export function probBetween(
  a: number,
  b: number,
  mu: number,
  sigma: number
): number {
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  return normCDF(zScore(hi, mu, sigma)) - normCDF(zScore(lo, mu, sigma));
}

// ─── Comprimento Médio de Corrida (ARL) — Shewhart ────────────────────────
//
// ARL = 1 / p, onde p é a probabilidade de um ponto cair fora dos limites
// de controle. Para limites simétricos a ±L·σ_x̄ com deslocamento de k·σ
// na média e tamanho de subgrupo n, σ_x̄ = σ/√n e:
//
//   β  = Φ(L − k√n) − Φ(−L − k√n)        (ponto dentro dos limites)
//   p  = 1 − β
//   ARL = 1 / p
//
// k = 0 ⇒ ARL₀ (em controle)              [Montgomery, Cap. cartas X̄-R]
// k > 0 ⇒ ARL₁ (fora de controle)
export function arl(L: number, k: number = 0, n: number = 1): number {
  const sqrtN = Math.sqrt(n);
  const beta = normCDF(L - k * sqrtN) - normCDF(-L - k * sqrtN);
  const p = 1 - beta;
  return p > 0 ? 1 / p : Infinity;
}

// ARL para limites assimétricos (ex.: cartas P, U, I-MR), via probabilidade
// de "estar dentro" calculada externamente.
export function arlFromInsideProb(probInside: number): number {
  const p = 1 - probInside;
  return p > 0 ? 1 / p : Infinity;
}

// ─── Análise de corridas observadas ───────────────────────────────────────
export interface Corrida {
  tipo: "dentro" | "fora-superior" | "fora-inferior";
  inicio: number;
  comprimento: number;
}

export interface AnaliseCorridas {
  corridas: Corrida[];
  totalCorridas: number;
  pontosDentro: number;
  pontosFora: number;
  maiorCorridaDentro: number;
  maiorCorridaFora: number;
  cmcObservado: number; // comprimento médio das corridas "dentro"
}

export function analisarCorridas(
  pontos: number[],
  lic: number,
  lsc: number
): AnaliseCorridas {
  const corridas: Corrida[] = [];
  if (pontos.length === 0) {
    return {
      corridas: [],
      totalCorridas: 0,
      pontosDentro: 0,
      pontosFora: 0,
      maiorCorridaDentro: 0,
      maiorCorridaFora: 0,
      cmcObservado: 0,
    };
  }

  const classificar = (v: number): Corrida["tipo"] =>
    v > lsc ? "fora-superior" : v < lic ? "fora-inferior" : "dentro";

  let atual: Corrida = {
    tipo: classificar(pontos[0]),
    inicio: 0,
    comprimento: 1,
  };

  for (let i = 1; i < pontos.length; i++) {
    const t = classificar(pontos[i]);
    if (t === atual.tipo) {
      atual.comprimento++;
    } else {
      corridas.push(atual);
      atual = { tipo: t, inicio: i, comprimento: 1 };
    }
  }
  corridas.push(atual);

  const dentro = corridas.filter((c) => c.tipo === "dentro");
  const fora = corridas.filter((c) => c.tipo !== "dentro");

  const pontosDentro = dentro.reduce((s, c) => s + c.comprimento, 0);
  const pontosFora = fora.reduce((s, c) => s + c.comprimento, 0);
  const maiorDentro = dentro.reduce((m, c) => Math.max(m, c.comprimento), 0);
  const maiorFora = fora.reduce((m, c) => Math.max(m, c.comprimento), 0);
  const cmcObservado =
    dentro.length > 0 ? pontosDentro / dentro.length : pontos.length;

  return {
    corridas,
    totalCorridas: corridas.length,
    pontosDentro,
    pontosFora,
    maiorCorridaDentro: maiorDentro,
    maiorCorridaFora: maiorFora,
    cmcObservado,
  };
}

// ─── Regras de Western Electric (Montgomery, Cap. 5) ──────────────────────
// 1) Um ponto além de ±3σ
// 2) 2 de 3 consecutivos além de ±2σ no mesmo lado
// 3) 4 de 5 consecutivos além de ±1σ no mesmo lado
// 4) 8 consecutivos no mesmo lado da linha média
export interface ViolacaoWE {
  regra: 1 | 2 | 3 | 4;
  indice: number;
  descricao: string;
}

export function regrasWesternElectric(
  pontos: number[],
  mu: number,
  sigma: number
): ViolacaoWE[] {
  const violacoes: ViolacaoWE[] = [];
  if (sigma <= 0) return violacoes;

  const sinal = (v: number) => Math.sign(v - mu);

  pontos.forEach((v, i) => {
    const z = (v - mu) / sigma;
    if (Math.abs(z) > 3) {
      violacoes.push({
        regra: 1,
        indice: i,
        descricao: `Ponto ${i + 1}: |z| = ${Math.abs(z).toFixed(2)} > 3 (além ±3σ)`,
      });
    }
  });

  for (let i = 2; i < pontos.length; i++) {
    const janela = [pontos[i - 2], pontos[i - 1], pontos[i]];
    const lados = janela.map(sinal);
    const mesmoLado = lados.every((s) => s === lados[0]) && lados[0] !== 0;
    if (!mesmoLado) continue;
    const acima2sigma = janela.filter((v) => Math.abs((v - mu) / sigma) > 2)
      .length;
    if (acima2sigma >= 2) {
      violacoes.push({
        regra: 2,
        indice: i,
        descricao: `Pontos ${i - 1}-${i + 1}: 2 de 3 além de ±2σ no mesmo lado`,
      });
    }
  }

  for (let i = 4; i < pontos.length; i++) {
    const janela = pontos.slice(i - 4, i + 1);
    const lados = janela.map(sinal);
    const mesmoLado = lados.every((s) => s === lados[0]) && lados[0] !== 0;
    if (!mesmoLado) continue;
    const acima1sigma = janela.filter((v) => Math.abs((v - mu) / sigma) > 1)
      .length;
    if (acima1sigma >= 4) {
      violacoes.push({
        regra: 3,
        indice: i,
        descricao: `Pontos ${i - 3}-${i + 1}: 4 de 5 além de ±1σ no mesmo lado`,
      });
    }
  }

  for (let i = 7; i < pontos.length; i++) {
    const janela = pontos.slice(i - 7, i + 1);
    const lados = janela.map(sinal);
    const mesmoLado = lados.every((s) => s === lados[0]) && lados[0] !== 0;
    if (mesmoLado) {
      violacoes.push({
        regra: 4,
        indice: i,
        descricao: `Pontos ${i - 6}-${i + 1}: 8 consecutivos do mesmo lado da linha média`,
      });
    }
  }

  return violacoes;
}

// ─── Estatísticas básicas de uma amostra ──────────────────────────────────
export interface Resumo {
  n: number;
  media: number;
  desvio: number;
  variancia: number;
  min: number;
  max: number;
}

export function resumir(amostra: number[]): Resumo {
  const n = amostra.length;
  if (n === 0) {
    return { n: 0, media: 0, desvio: 0, variancia: 0, min: 0, max: 0 };
  }
  const media = amostra.reduce((s, v) => s + v, 0) / n;
  const variancia =
    n > 1
      ? amostra.reduce((s, v) => s + (v - media) ** 2, 0) / (n - 1)
      : 0;
  return {
    n,
    media,
    desvio: Math.sqrt(variancia),
    variancia,
    min: Math.min(...amostra),
    max: Math.max(...amostra),
  };
}
