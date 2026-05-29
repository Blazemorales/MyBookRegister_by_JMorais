// PDF do fluxo "Validador manual" — gera relatório a partir do que o usuário
// calculou na UI (parâmetros + resultados de cada seção).
//
// Para o PDF auto (a partir de /results/cep/<carta>) ver app/lib/pdfValidacao.ts.

import { resumir } from "@/app/lib/stats";
import { fmt, pct } from "./types";
import type {
  Parametros,
  ResultadoProb,
  ResultadoLimites,
  ResultadoARL,
} from "./types";

export interface ConteudoPdfManual {
  params: Parametros;
  resProb: ResultadoProb | null;
  resLimites: ResultadoLimites | null;
  resArl: ResultadoARL | null;
}

export async function gerarPdfManual(conteudo: ConteudoPdfManual): Promise<void> {
  const { params, resProb, resLimites, resArl } = conteudo;
  const { default: JsPDF } = await import("jspdf");

  const doc = new JsPDF("p", "mm", "a4");
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();
  let y = 20;

  const newPageIfNeeded = (delta = 8) => {
    if (y + delta > H - 18) {
      doc.addPage();
      y = 20;
    }
  };
  const titulo = (t: string, sz = 13) => {
    newPageIfNeeded(12);
    doc.setFont("helvetica", "bold");
    doc.setFontSize(sz);
    doc.text(t, 20, y);
    y += sz === 13 ? 8 : 7;
    doc.setFont("helvetica", "normal");
  };
  const linha = (t: string, sz = 10, x = 25) => {
    newPageIfNeeded(6);
    doc.setFontSize(sz);
    const partes = doc.splitTextToSize(t, W - x - 15);
    doc.text(partes, x, y);
    y += partes.length * (sz * 0.45 + 2);
  };

  // Cabeçalho
  doc.setFont("helvetica", "bold");
  doc.setFontSize(16);
  doc.text("Relatório de Validação Estatística", W / 2, y, { align: "center" });
  y += 7;
  doc.setFont("helvetica", "normal");
  doc.setFontSize(9);
  doc.text(
    "Montgomery — Probabilidade e Estatística Aplicada à Engenharia",
    W / 2,
    y,
    { align: "center" },
  );
  y += 5;
  doc.text(
    `Processo: ${params.nome}     Data: ${new Date().toLocaleString("pt-BR")}`,
    W / 2,
    y,
    { align: "center" },
  );
  y += 10;

  let secao = 0;
  const proxima = () => ++secao;

  // Parâmetros
  titulo(`${proxima()}. Parâmetros do processo`);
  linha(`μ (média) = ${fmt(params.mu)}     σ (desvio) = ${fmt(params.sigma)}`);
  linha(
    `LSC = ${fmt(params.lsc)}     LM = ${fmt(params.lm)}     LIC = ${fmt(params.lic)}`,
  );
  linha(`Tamanho do subgrupo n = ${params.n}`);
  if (params.pontos.length) {
    const s = resumir(params.pontos);
    linha(
      `Amostra observada: n=${s.n}, x̄=${fmt(s.media)}, s=${fmt(s.desvio)}, mín=${fmt(s.min)}, máx=${fmt(s.max)}`,
    );
  }
  y += 4;

  // Limites
  if (resLimites) {
    titulo(`${proxima()}. Análise pelos limites de controle (LIC/LSC)`);
    linha("Padronização: Z = (X − μ) / σ", 10);
    linha(`LIC = ${fmt(resLimites.lic)}     LSC = ${fmt(resLimites.lsc)}`, 10);
    linha(
      `z(LIC) = ${fmt(resLimites.z_lic)}     z(LSC) = ${fmt(resLimites.z_lsc)}`,
      10,
    );
    linha(`P(X < LIC) = ${pct(resLimites.pAbaixo)}`);
    linha(`P(LIC ≤ X ≤ LSC) = ${pct(resLimites.pDentro)}`);
    linha(`P(X > LSC) = ${pct(resLimites.pAcima)}`);
    const pFora = resLimites.pAbaixo + resLimites.pAcima;
    linha(`P(fora) = ${pct(pFora)}`);
    const arlEst = pFora > 0 ? 1 / pFora : Infinity;
    linha(`ARL ≈ 1/P(fora) = ${fmt(arlEst, 2)} amostras`, 10);
    const interp =
      resLimites.pDentro > 0.9973
        ? "Processo muito conservador: P(dentro) > 99,73%."
        : resLimites.pDentro > 0.9544
          ? "Processo dentro de tolerância clássica (≈ ±2σ a ±3σ)."
          : resLimites.pDentro > 0.6827
            ? "Cobertura limitada: ±1σ a ±2σ — risco de falsos alarmes."
            : "Limites muito estreitos: P(dentro) < ±1σ.";
    linha(`Interpretação: ${interp}`, 10);
    y += 4;
  }

  // Probabilidade
  if (resProb) {
    titulo(
      `${proxima()}. Análise de Probabilidade${resLimites ? " adicional" : ""} (Distribuição Normal)`,
    );
    linha("Padronização: Z = (X − μ) / σ", 10);
    linha(resProb.expressao, 10);
    linha(
      `z(a) = ${fmt(resProb.z_a)}` +
        (resProb.z_b !== undefined ? `   z(b) = ${fmt(resProb.z_b)}` : ""),
    );
    linha(`P calculada = ${pct(resProb.p)}`);
    linha(`P complementar = ${pct(resProb.p_complementar)}`);
    const interp =
      resProb.p > 0.9973
        ? "Massa de probabilidade alta — região muito provável."
        : resProb.p < 0.0027
          ? "Probabilidade muito baixa — evento raro (≈3σ)."
          : "Probabilidade típica de processo sob controle estatístico.";
    linha(`Interpretação: ${interp}`, 10);
    y += 4;
  }

  // ARL
  if (resArl) {
    const n = proxima();
    titulo(`${n}. Comprimento Médio de Corrida (CMC / ARL)`);
    linha(
      `Limites a ±${fmt(resArl.L, 2)}σ_x̄ com subgrupo n = ${resArl.n} e deslocamento k = ${fmt(resArl.k, 2)}σ`,
      10,
    );
    linha("β = Φ(L − k√n) − Φ(−L − k√n)     ARL = 1 / (1 − β)", 10);
    linha(`ARL₀ (em controle) = ${fmt(resArl.arl0, 2)} amostras`);
    linha(
      `ARL₁ (k=${fmt(resArl.k, 2)}σ) = ${fmt(resArl.arl1, 2)} amostras`,
    );
    linha(`P(dentro) = ${pct(resArl.probDentro)}`);
    linha(`P(fora) = ${pct(resArl.probFora)}`);

    if (resArl.corridas) {
      y += 2;
      titulo(`${n}.1 Corridas observadas`, 11);
      const c = resArl.corridas;
      linha(`Total: ${c.totalCorridas}`);
      linha(`Pontos dentro: ${c.pontosDentro}     fora: ${c.pontosFora}`);
      linha(
        `Maior corrida dentro: ${c.maiorCorridaDentro}     fora: ${c.maiorCorridaFora}`,
      );
      linha(`CMC observado = ${fmt(c.cmcObservado, 2)}`);
    }

    if (resArl.violacoes.length) {
      y += 2;
      titulo(`${n}.2 Violações de Western Electric`, 11);
      resArl.violacoes.slice(0, 30).forEach((v) => {
        linha(`• ${v.descricao}`, 9);
      });
      if (resArl.violacoes.length > 30) {
        linha(`… e mais ${resArl.violacoes.length - 30} violações`, 9);
      }
    } else if (params.pontos.length > 0) {
      linha("Nenhuma violação de regras de Western Electric detectada.", 10);
    }
  }

  // Rodapé
  const total = doc.getNumberOfPages();
  for (let i = 1; i <= total; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setTextColor(120);
    doc.text(`Página ${i} de ${total}`, W / 2, H - 8, { align: "center" });
    doc.setTextColor(0);
  }

  doc.save(`validacao-${params.nome.replace(/\s+/g, "_")}-${Date.now()}.pdf`);
}
