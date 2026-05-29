// Geração do relatório de Validação Estatística (auto) a partir do JSON
// exposto pelo backend em /results/cep/<chart>. Cobre todas as etapas da
// página "Validar Processo":
//
//   1. Parâmetros do processo
//   2. Análise pelos limites de controle (LIC/LSC)
//   3. Probabilidade — Distribuição Normal (faixas clássicas)
//   4. ARL / CMC + corridas + Western Electric
//   5. Seção específica por carta (R, MR, P binomial, U Poisson)
//
// Importante: o PDF é gerado em ASCII-safe — jsPDF com Helvetica padrão usa
// WinAnsi e NÃO renderiza Greek (μ σ Φ), combinações com macron (x̄), nem
// símbolos matemáticos (≤ ≥ ≈ ² ³ √). Por isso usamos "mu", "sigma", "Phi",
// "X-barra", "<=", ">=", "~", "^2", "sqrt", etc.

import type jsPDF from "jspdf";
import {
  probLess,
  probGreater,
  probBetween,
  zScore,
  arl,
  analisarCorridas,
  regrasWesternElectric,
  resumir,
} from "./stats";

// ─── Tipos de payload do backend ─────────────────────────────────────────
export type TipoCarta = "xr" | "p" | "u" | "imr";

export interface AmostraXR {
  amostra: string;
  media: number;
  dp: number;
  amplitude: number;
  n: number;
  valores: number[];
}

export interface DadosXR {
  chart: "XR";
  lse: number;
  lie: number;
  x_double_bar: number;
  r_bar: number;
  sigma: number;
  lsc_x: number;
  lic_x: number;
  lsc_r: number;
  lic_r: number;
  n_amostra: number;
  estatisticas_por_amostra: AmostraXR[];
}

export interface DadosP {
  chart: "P";
  P: number;
  P_bar: number;
  total_defeitos: number;
  N: number;
  desvio_padrao_p: number;
  lsc_P: number;
  lic_P: number;
  proporcoes: number[];
}

export interface DadosU {
  chart: "U";
  U: number;
  U_bar: number;
  total_defeitos: number;
  n: number;
  desvio_padrao_u: number;
  lsc_u: number;
  lic_u: number;
  u_valores: number[];
}

export interface DadosIMR {
  chart: "IMR";
  media_ind: number;
  sigma_ind: number;
  am_bar: number;
  lsc_ind: number;
  lic_ind: number;
  lsc_mr: number;
  lic_mr: number;
  valores_individuais: number[];
  mr_values: number[];
}

export type DadosCarta = DadosXR | DadosP | DadosU | DadosIMR;

// ─── Normaliza resposta do backend (objeto único ou array) ───────────────
export function normalizarResposta(
  payload: unknown,
  tipo: TipoCarta
): DadosCarta | null {
  const alvo = tipo.toUpperCase();
  if (Array.isArray(payload)) {
    const achado = (payload as Array<{ chart?: string }>).find(
      (p) => String(p?.chart ?? "").toUpperCase() === alvo
    );
    return (achado as DadosCarta) ?? null;
  }
  if (
    payload &&
    typeof payload === "object" &&
    String((payload as { chart?: string }).chart ?? "").toUpperCase() === alvo
  ) {
    return payload as DadosCarta;
  }
  return null;
}

// ─── Parâmetros normalizados ─────────────────────────────────────────────
export interface ParamsCarta {
  nome: string;
  mu: number;
  sigma: number;
  lsc: number;
  lic: number;
  lm: number;
  n: number;
  pontos: number[];
}

export function extrairParams(
  dados: DadosCarta,
  tipo: TipoCarta
): ParamsCarta {
  switch (tipo) {
    case "xr": {
      const d = dados as DadosXR;
      return {
        nome: "Carta X-R",
        mu: d.x_double_bar,
        sigma: d.sigma,
        lsc: d.lsc_x,
        lic: d.lic_x,
        lm: d.x_double_bar,
        n: d.n_amostra,
        pontos: d.estatisticas_por_amostra.map((s) => s.media),
      };
    }
    case "p": {
      const d = dados as DadosP;
      return {
        nome: "Carta P (proporcao de defeituosos)",
        mu: d.P_bar,
        sigma: d.desvio_padrao_p,
        lsc: d.lsc_P,
        lic: d.lic_P,
        lm: d.P_bar,
        n: d.N,
        pontos: d.proporcoes,
      };
    }
    case "u": {
      const d = dados as DadosU;
      return {
        nome: "Carta U (defeitos por unidade)",
        mu: d.U_bar,
        sigma: d.desvio_padrao_u,
        lsc: d.lsc_u,
        lic: d.lic_u,
        lm: d.U_bar,
        n: d.n,
        pontos: d.u_valores,
      };
    }
    case "imr": {
      const d = dados as DadosIMR;
      return {
        nome: "Carta I-MR (individuos)",
        mu: d.media_ind,
        sigma: d.sigma_ind,
        lsc: d.lsc_ind,
        lic: d.lic_ind,
        lm: d.media_ind,
        n: 1,
        pontos: d.valores_individuais,
      };
    }
  }
}

// ─── Formatação ──────────────────────────────────────────────────────────
const fmt = (v: number, casas = 4) =>
  Number.isFinite(v) ? v.toFixed(casas) : "inf";
const pct = (v: number, casas = 4) =>
  Number.isFinite(v) ? (v * 100).toFixed(casas) + " %" : "-";

// ─── Paleta de cores ─────────────────────────────────────────────────────
type RGB = [number, number, number];
const COR_PRIMARIA: RGB = [37, 99, 235];      // azul
const COR_SECUNDARIA: RGB = [16, 185, 129];   // verde
const COR_ALERTA: RGB = [245, 158, 11];       // ambar
const COR_NEUTRA: RGB = [71, 85, 105];        // cinza escuro
const COR_FUNDO_INFO: RGB = [239, 246, 255];  // azul claro
const COR_FUNDO_OK: RGB = [236, 253, 245];    // verde claro
const COR_FUNDO_AVISO: RGB = [254, 243, 199]; // ambar claro
const COR_BORDA: RGB = [203, 213, 225];       // cinza
const COR_TEXTO: RGB = [15, 23, 42];          // quase preto
const COR_TEXTO_FRACO: RGB = [100, 116, 139]; // cinza médio

// ─── Renderer com helpers de layout ──────────────────────────────────────
class Render {
  doc: jsPDF;
  W: number;
  H: number;
  margem = 18;
  y = 0;

  constructor(doc: jsPDF) {
    this.doc = doc;
    this.W = this.doc.internal.pageSize.getWidth();
    this.H = this.doc.internal.pageSize.getHeight();
    this.y = this.margem;
  }

  private contW() {
    return this.W - 2 * this.margem;
  }

  espacoNecessario(altura: number) {
    if (this.y + altura > this.H - this.margem - 8) {
      this.doc.addPage();
      this.y = this.margem;
      return true;
    }
    return false;
  }

  private setCorTexto(c: RGB) {
    this.doc.setTextColor(c[0], c[1], c[2]);
  }

  private setCorFill(c: RGB) {
    this.doc.setFillColor(c[0], c[1], c[2]);
  }

  private setCorDraw(c: RGB) {
    this.doc.setDrawColor(c[0], c[1], c[2]);
  }

  // ── Capa / cabecalho ──────────────────────────────────────────────────
  capa(nomeCarta: string) {
    this.setCorFill(COR_PRIMARIA);
    this.doc.rect(0, 0, this.W, 38, "F");

    this.setCorTexto([255, 255, 255]);
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(20);
    this.doc.text("Relatorio de Validacao Estatistica", this.margem, 18);

    this.doc.setFont("helvetica", "normal");
    this.doc.setFontSize(10);
    this.doc.text(
      "Distribuicao Normal | CMC (ARL) | Western Electric | Montgomery",
      this.margem,
      26
    );

    this.doc.setFontSize(9);
    const data = new Date().toLocaleString("pt-BR");
    this.doc.text(`${nomeCarta}    |    ${data}`, this.margem, 33);

    this.setCorTexto(COR_TEXTO);
    this.y = 48;
  }

  // ── Barra de capítulo (sessao numerada) ───────────────────────────────
  capitulo(numero: number, titulo: string, cor: RGB = COR_PRIMARIA) {
    this.espacoNecessario(16);
    this.setCorFill(cor);
    this.doc.rect(this.margem, this.y, this.contW(), 8, "F");
    this.setCorTexto([255, 255, 255]);
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(11);
    this.doc.text(`${numero}.  ${titulo}`, this.margem + 3, this.y + 5.7);
    this.setCorTexto(COR_TEXTO);
    this.y += 11;
  }

  // ── Subtitulo (negrito menor) ─────────────────────────────────────────
  subtitulo(texto: string) {
    this.espacoNecessario(8);
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(10);
    this.setCorTexto(COR_PRIMARIA);
    this.doc.text(texto, this.margem, this.y);
    this.setCorTexto(COR_TEXTO);
    this.y += 5;
  }

  // ── Paragrafo de prosa ────────────────────────────────────────────────
  prosa(texto: string, sz = 9.5) {
    this.doc.setFont("helvetica", "normal");
    this.doc.setFontSize(sz);
    const partes = this.doc.splitTextToSize(texto, this.contW());
    for (const linha of partes) {
      this.espacoNecessario(sz * 0.45 + 1.5);
      this.doc.text(linha, this.margem, this.y);
      this.y += sz * 0.45 + 1.5;
    }
  }

  // ── Linha em fonte monoespacada (fórmula) ─────────────────────────────
  formula(texto: string) {
    this.espacoNecessario(7);
    this.doc.setFont("courier", "normal");
    this.doc.setFontSize(9);
    this.setCorTexto(COR_NEUTRA);
    this.doc.text(texto, this.margem + 3, this.y);
    this.setCorTexto(COR_TEXTO);
    this.doc.setFont("helvetica", "normal");
    this.y += 5;
  }

  // ── Grade 2 colunas (chave/valor) ─────────────────────────────────────
  grade(itens: Array<[string, string]>, colunas = 2) {
    const linhas = Math.ceil(itens.length / colunas);
    const altura = linhas * 6 + 2;
    this.espacoNecessario(altura);

    const larg = this.contW() / colunas;
    for (let i = 0; i < itens.length; i++) {
      const col = i % colunas;
      const lin = Math.floor(i / colunas);
      const x = this.margem + col * larg;
      const yy = this.y + lin * 6 + 4;

      this.doc.setFont("helvetica", "bold");
      this.doc.setFontSize(8.5);
      this.setCorTexto(COR_TEXTO_FRACO);
      this.doc.text(itens[i][0], x, yy);

      this.doc.setFont("courier", "normal");
      this.doc.setFontSize(10);
      this.setCorTexto(COR_TEXTO);
      this.doc.text(itens[i][1], x + 38, yy);
    }
    this.setCorTexto(COR_TEXTO);
    this.y += altura;
  }

  // ── Caixa informativa colorida (texto centralizado por linhas) ────────
  caixa(linhas: string[], variante: "info" | "ok" | "aviso" = "info") {
    const bg =
      variante === "ok"
        ? COR_FUNDO_OK
        : variante === "aviso"
          ? COR_FUNDO_AVISO
          : COR_FUNDO_INFO;
    const borda =
      variante === "ok"
        ? COR_SECUNDARIA
        : variante === "aviso"
          ? COR_ALERTA
          : COR_PRIMARIA;

    const padding = 3;
    const altLinha = 4.5;

    // Quebra de linhas considerando largura disponivel
    const todasPartes: string[] = [];
    this.doc.setFont("helvetica", "normal");
    this.doc.setFontSize(9.5);
    for (const linha of linhas) {
      const partes = this.doc.splitTextToSize(linha, this.contW() - 2 * padding - 4);
      todasPartes.push(...partes);
    }

    const altura = todasPartes.length * altLinha + 2 * padding;
    this.espacoNecessario(altura + 2);

    this.setCorFill(bg);
    this.setCorDraw(borda);
    this.doc.setLineWidth(0.4);
    this.doc.roundedRect(this.margem, this.y, this.contW(), altura, 2, 2, "FD");
    this.doc.setLineWidth(0.2);
    // Faixa lateral colorida
    this.setCorFill(borda);
    this.doc.rect(this.margem, this.y, 1.5, altura, "F");

    this.setCorTexto(COR_TEXTO);
    let yy = this.y + padding + 3;
    for (const linha of todasPartes) {
      this.doc.text(linha, this.margem + padding + 3, yy);
      yy += altLinha;
    }
    this.y += altura + 3;
  }

  // ── Tabela simples ────────────────────────────────────────────────────
  tabela(cabecalhos: string[], linhas: string[][], larguras: number[]) {
    const altLinha = 6;
    const altCab = 7;
    const totalLin = linhas.length * altLinha + altCab;
    this.espacoNecessario(totalLin + 2);

    let x = this.margem;
    // Cabeçalho
    this.setCorFill(COR_PRIMARIA);
    this.doc.rect(this.margem, this.y, this.contW(), altCab, "F");
    this.setCorTexto([255, 255, 255]);
    this.doc.setFont("helvetica", "bold");
    this.doc.setFontSize(9);
    for (let i = 0; i < cabecalhos.length; i++) {
      this.doc.text(cabecalhos[i], x + 2, this.y + altCab - 2.2);
      x += larguras[i];
    }
    this.y += altCab;

    // Linhas
    this.doc.setFont("helvetica", "normal");
    this.setCorTexto(COR_TEXTO);
    for (let r = 0; r < linhas.length; r++) {
      if (r % 2 === 0) {
        this.setCorFill([248, 250, 252]);
        this.doc.rect(this.margem, this.y, this.contW(), altLinha, "F");
      }
      x = this.margem;
      for (let c = 0; c < linhas[r].length; c++) {
        this.doc.setFont(c === 0 ? "helvetica" : "courier", "normal");
        this.doc.setFontSize(9);
        this.doc.text(linhas[r][c], x + 2, this.y + altLinha - 1.8);
        x += larguras[c];
      }
      this.y += altLinha;
    }
    this.setCorDraw(COR_BORDA);
    this.doc.setLineWidth(0.2);
    this.doc.rect(this.margem, this.y - totalLin + altCab, this.contW(), totalLin - altCab);
    this.y += 2;
  }

  // ── Linha horizontal divisória ────────────────────────────────────────
  divisor() {
    this.setCorDraw(COR_BORDA);
    this.doc.setLineWidth(0.2);
    this.doc.line(this.margem, this.y, this.W - this.margem, this.y);
    this.y += 4;
  }

  // ── Pequeno espaco ────────────────────────────────────────────────────
  vspace(n = 3) {
    this.y += n;
  }

  // ── Rodape em todas as paginas ────────────────────────────────────────
  rodape() {
    const total = this.doc.getNumberOfPages();
    for (let i = 1; i <= total; i++) {
      this.doc.setPage(i);
      this.doc.setFont("helvetica", "normal");
      this.doc.setFontSize(8);
      this.setCorTexto(COR_TEXTO_FRACO);
      this.doc.text(
        `Pagina ${i} de ${total}`,
        this.W / 2,
        this.H - 7,
        { align: "center" }
      );
      this.doc.text(
        "Gerado automaticamente a partir de /results/cep/<carta>",
        this.margem,
        this.H - 7
      );
    }
  }
}

// ─── Geração do PDF ──────────────────────────────────────────────────────
export async function gerarPdfValidacao(
  dados: DadosCarta,
  tipo: TipoCarta
): Promise<jsPDF> {
  const { default: JsPDF } = await import("jspdf");
  const params = extrairParams(dados, tipo);
  const r = new Render(new JsPDF("p", "mm", "a4"));

  // ── Capa ──────────────────────────────────────────────────────────────
  r.capa(params.nome);

  // ── 1. Parâmetros do processo ─────────────────────────────────────────
  r.capitulo(1, "Parametros do processo");
  r.grade(
    [
      ["Media (mu)", fmt(params.mu, 4)],
      ["LSC", fmt(params.lsc, 4)],
      ["Desvio (sigma)", fmt(params.sigma, 4)],
      ["LM", fmt(params.lm, 4)],
      ["Tamanho n", String(params.n)],
      ["LIC", fmt(params.lic, 4)],
    ],
    2
  );

  if (params.pontos.length > 0) {
    r.vspace(1);
    r.subtitulo("Resumo da amostra observada");
    const s = resumir(params.pontos);
    r.grade(
      [
        ["n", String(s.n)],
        ["media", fmt(s.media, 4)],
        ["desvio (s)", fmt(s.desvio, 4)],
        ["variancia", fmt(s.variancia, 4)],
        ["minimo", fmt(s.min, 4)],
        ["maximo", fmt(s.max, 4)],
      ],
      3
    );
  }
  r.vspace(2);

  // ── 2. Limites de controle ────────────────────────────────────────────
  r.capitulo(2, "Analise pelos limites de controle (LIC/LSC)", COR_SECUNDARIA);
  if (params.sigma > 0 && params.lsc > params.lic) {
    const pAbaixo = probLess(params.lic, params.mu, params.sigma);
    const pAcima = probGreater(params.lsc, params.mu, params.sigma);
    const pDentro = probBetween(params.lic, params.lsc, params.mu, params.sigma);
    const zLic = zScore(params.lic, params.mu, params.sigma);
    const zLsc = zScore(params.lsc, params.mu, params.sigma);

    r.prosa(
      "Padronizacao Z = (X - mu) / sigma. Z segue uma N(0, 1) e suas probabilidades sao obtidas pela CDF Phi(z)."
    );
    r.formula("z(LIC) = " + fmt(zLic, 4) + "        z(LSC) = " + fmt(zLsc, 4));
    r.vspace(1);
    r.tabela(
      ["Regiao", "Formula", "Probabilidade"],
      [
        ["X < LIC", "Phi(z_LIC)", pct(pAbaixo, 4)],
        ["LIC <= X <= LSC", "Phi(z_LSC) - Phi(z_LIC)", pct(pDentro, 4)],
        ["X > LSC", "1 - Phi(z_LSC)", pct(pAcima, 4)],
      ],
      [50, 65, 60]
    );

    const pFora = pAbaixo + pAcima;
    const arlEst = pFora > 0 ? 1 / pFora : Infinity;
    r.vspace(1);
    r.caixa(
      [
        "P(fora) = P(X<LIC) + P(X>LSC) = " + pct(pFora, 4),
        "ARL estimado pelos limites = 1 / P(fora) ~ " +
          fmt(arlEst, 2) +
          " amostras",
        "Verificacao: soma das tres regioes = " +
          pct(pAbaixo + pDentro + pAcima, 4),
      ],
      "info"
    );

    const interp =
      pDentro > 0.9973
        ? "Processo muito conservador: P(dentro) > 99,73 % (>= +-3 sigma)."
        : pDentro > 0.9544
          ? "Processo dentro de tolerancia classica (~ +-2 sigma a +-3 sigma)."
          : pDentro > 0.6827
            ? "Cobertura limitada: P(dentro) na faixa +-1 a +-2 sigma — risco de falsos alarmes elevado."
            : "Limites muito estreitos: P(dentro) abaixo de +-1 sigma.";
    r.caixa(
      ["Interpretacao: " + interp],
      pDentro > 0.9544 ? "ok" : "aviso"
    );
  } else {
    r.caixa(
      ["Nao foi possivel calcular: sigma <= 0 ou LSC <= LIC."],
      "aviso"
    );
  }
  r.vspace(2);

  // ── 3. Probabilidade — Distribuição Normal (faixas) ───────────────────
  r.capitulo(3, "Probabilidade - Distribuicao Normal", COR_PRIMARIA);
  if (params.sigma > 0) {
    r.prosa(
      "Aplicacao livre da N(mu, sigma^2) em faixas classicas (regra empirica)."
    );
    const linhasFaixas: string[][] = [];
    for (const k of [1, 2, 3]) {
      const lo = params.mu - k * params.sigma;
      const hi = params.mu + k * params.sigma;
      const p = probBetween(lo, hi, params.mu, params.sigma);
      linhasFaixas.push([
        "+-" + k + " sigma",
        "[" + fmt(lo, 3) + " ; " + fmt(hi, 3) + "]",
        pct(p, 4),
      ]);
    }
    r.tabela(
      ["Faixa", "Intervalo [lo ; hi]", "P(mu-k.s <= X <= mu+k.s)"],
      linhasFaixas,
      [30, 80, 65]
    );
    r.vspace(1);
    const pLic = probLess(params.lic, params.mu, params.sigma);
    const pLsc = probGreater(params.lsc, params.mu, params.sigma);
    r.caixa(
      [
        "P(X < LIC) = " + pct(pLic, 4),
        "P(X > LSC) = " + pct(pLsc, 4),
        "Valores esperados (regra empirica): +-1s ~ 68,27 %, +-2s ~ 95,45 %, +-3s ~ 99,73 %.",
      ],
      "info"
    );
  } else {
    r.caixa(["sigma <= 0 - analise normal nao aplicavel."], "aviso");
  }
  r.vspace(2);

  // ── 4. ARL / CMC + corridas + Western Electric ────────────────────────
  r.capitulo(4, "Comprimento Medio de Corrida (CMC / ARL)", COR_PRIMARIA);

  if (tipo === "xr" || tipo === "imr") {
    const L = 3;
    const k = 1;
    const arl0 = arl(L, 0, params.n);
    const arl1 = arl(L, k, params.n);
    r.prosa(
      `Fluxo de Shewhart com limites a +-${L}.sigma_xbar, subgrupo n = ${params.n}, deslocamento k = ${k}.sigma.`
    );
    r.formula("Beta = Phi(L - k.sqrt(n)) - Phi(-L - k.sqrt(n))");
    r.formula("ARL = 1 / (1 - Beta)");
    r.vspace(1);
    r.grade(
      [
        ["ARL_0 (em controle)", fmt(arl0, 2) + " amostras"],
        ["ARL_1 (k=" + k + ".s)", fmt(arl1, 2) + " amostras"],
      ],
      2
    );
  } else {
    r.prosa(
      tipo === "p"
        ? "Carta P (atributos): ARL baseado em P(p_chapeu fora de [LIC, LSC]) sob aproximacao normal."
        : "Carta U (atributos): ARL baseado em P(u_chapeu fora de [LIC, LSC]) sob aproximacao normal."
    );
  }

  if (params.sigma > 0 && params.lsc > params.lic) {
    const pDentro = probBetween(
      params.lic,
      params.lsc,
      params.mu,
      params.sigma
    );
    const pFora = 1 - pDentro;
    const arlGeral = pFora > 0 ? 1 / pFora : Infinity;
    r.vspace(1);
    r.caixa(
      [
        "P(dentro) = " + pct(pDentro, 4) + "    P(fora) = " + pct(pFora, 4),
        "ARL geral = 1 / P(fora) ~ " + fmt(arlGeral, 2) + " amostras",
      ],
      "ok"
    );
  }

  // Corridas observadas
  if (params.pontos.length > 0) {
    r.vspace(2);
    r.subtitulo("Analise de corridas observadas");
    const c = analisarCorridas(params.pontos, params.lic, params.lsc);
    r.grade(
      [
        ["Total de corridas", String(c.totalCorridas)],
        ["CMC observado", fmt(c.cmcObservado, 2)],
        ["Pontos dentro", String(c.pontosDentro)],
        ["Pontos fora", String(c.pontosFora)],
        ["Maior corrida dentro", String(c.maiorCorridaDentro)],
        ["Maior corrida fora", String(c.maiorCorridaFora)],
      ],
      2
    );
  }

  // Western Electric
  if (params.pontos.length > 0 && params.sigma > 0) {
    r.vspace(2);
    r.subtitulo("Regras de Western Electric");
    const violacoes = regrasWesternElectric(
      params.pontos,
      params.mu,
      params.sigma
    );
    if (tipo === "p" || tipo === "u") {
      r.caixa(
        [
          "Atencao: Western Electric foi desenhado para cartas de variaveis. Aplicado aqui sob aproximacao normal - interprete com cuidado.",
        ],
        "aviso"
      );
    }
    if (violacoes.length === 0) {
      r.caixa(["Nenhuma violacao detectada."], "ok");
    } else {
      const linhas = violacoes
        .slice(0, 30)
        .map((v) => ["Regra " + v.regra, v.descricao]);
      r.tabela(["Regra", "Descricao"], linhas, [25, 150]);
      if (violacoes.length > 30) {
        r.prosa("... e mais " + (violacoes.length - 30) + " violacoes.", 9);
      }
    }
  }
  r.vspace(2);

  // ── 5. Seção específica por carta ─────────────────────────────────────
  if (tipo === "xr") {
    const d = dados as DadosXR;
    r.capitulo(5, "Analise especifica - Carta R (amplitude)", COR_NEUTRA);
    r.grade(
      [
        ["R_barra", fmt(d.r_bar, 4)],
        ["LSC_R", fmt(d.lsc_r, 4)],
        ["LIC_R", fmt(d.lic_r, 4)],
      ],
      3
    );

    const amplitudes = d.estatisticas_por_amostra.map((s) => s.amplitude);
    const foraR = amplitudes.filter((a) => a > d.lsc_r || a < d.lic_r).length;
    r.vspace(1);
    r.subtitulo(`Amplitudes dos ${amplitudes.length} subgrupos`);
    const linhasAmp: string[][] = d.estatisticas_por_amostra.map((s) => [
      "Subgrupo " + s.amostra,
      fmt(s.media, 3),
      fmt(s.amplitude, 3),
      fmt(s.dp, 3),
    ]);
    r.tabela(
      ["Subgrupo", "Media", "Amplitude", "Desvio s"],
      linhasAmp,
      [40, 45, 45, 45]
    );
    r.caixa(
      [
        "Pontos fora da carta R: " + foraR + " de " + amplitudes.length,
      ],
      foraR > 0 ? "aviso" : "ok"
    );

    r.vspace(2);
    r.subtitulo("Limites de especificacao (LSE / LIE)");
    r.grade(
      [
        ["LSE", fmt(d.lse, 4)],
        ["LIE", fmt(d.lie, 4)],
        ["Amplitude (LSE-LIE)", fmt(d.lse - d.lie, 4)],
      ],
      3
    );
    if (params.sigma > 0) {
      const pSpec = probBetween(d.lie, d.lse, params.mu, params.sigma);
      const cp = (d.lse - d.lie) / (6 * params.sigma);
      const cpk = Math.min(
        (d.lse - params.mu) / (3 * params.sigma),
        (params.mu - d.lie) / (3 * params.sigma)
      );
      r.vspace(1);
      r.formula("Cp  = (LSE - LIE) / (6 . sigma) = " + fmt(cp, 3));
      r.formula(
        "Cpk = min( (LSE-mu)/3s , (mu-LIE)/3s ) = " + fmt(cpk, 3)
      );
      r.caixa(
        ["P(LIE <= X <= LSE) = " + pct(pSpec, 4) + "   (capabilidade aprox.)"],
        "info"
      );
      const interp =
        cpk >= 1.33
          ? "Cpk >= 1,33 - processo capaz com folga."
          : cpk >= 1.0
            ? "1,0 <= Cpk < 1,33 - processo marginalmente capaz."
            : "Cpk < 1,0 - processo NAO capaz (alta probabilidade fora de especificacao).";
      r.caixa(["Interpretacao: " + interp], cpk >= 1.0 ? "ok" : "aviso");
    }
  } else if (tipo === "imr") {
    const d = dados as DadosIMR;
    r.capitulo(5, "Analise especifica - Carta MR (amplitude movel)", COR_NEUTRA);
    r.grade(
      [
        ["MR_barra", fmt(d.am_bar, 4)],
        ["LSC_MR", fmt(d.lsc_mr, 4)],
        ["LIC_MR", fmt(d.lic_mr, 4)],
      ],
      3
    );
    const foraMr = d.mr_values.filter(
      (a) => a > d.lsc_mr || a < d.lic_mr
    ).length;
    r.vspace(1);
    r.subtitulo(`Amplitudes moveis (${d.mr_values.length} pontos)`);
    const linhasMR: string[][] = d.mr_values.map((v, i) => [
      String(i + 1),
      fmt(v, 4),
    ]);
    r.tabela(["#", "MR"], linhasMR, [30, 60]);
    r.caixa(
      ["Pontos fora da carta MR: " + foraMr + " de " + d.mr_values.length],
      foraMr > 0 ? "aviso" : "ok"
    );

    r.vspace(2);
    r.subtitulo("Estimativa de sigma a partir de MR_barra");
    r.formula("sigma_chapeu = MR_barra / d2     (d2 = 1,128 para n=2)");
    const sigmaEst = d.am_bar / 1.128;
    r.caixa(
      [
        "sigma_chapeu = " +
          fmt(d.am_bar, 4) +
          " / 1.128 = " +
          fmt(sigmaEst, 4),
        "sigma informado pelo backend = " + fmt(d.sigma_ind, 4),
      ],
      "info"
    );
  } else if (tipo === "p") {
    const d = dados as DadosP;
    r.capitulo(5, "Analise especifica - Carta P (binomial)", COR_NEUTRA);
    r.grade(
      [
        ["p_barra", fmt(d.P_bar, 6)],
        ["N (tamanho)", String(d.N)],
        ["sigma_p", fmt(d.desvio_padrao_p, 6)],
        ["Total defeitos", String(d.total_defeitos)],
        ["LSC", fmt(d.lsc_P, 6)],
        ["LIC", fmt(d.lic_P, 6)],
      ],
      2
    );

    r.vspace(1);
    r.subtitulo("Aproximacao normal para a binomial");
    r.formula("sigma_p = sqrt( p_barra . (1 - p_barra) / N )");
    r.formula("LSC = p_barra + 3 . sigma_p");
    r.formula("LIC = max( 0 , p_barra - 3 . sigma_p )");

    const np = d.N * d.P_bar;
    const nq = d.N * (1 - d.P_bar);
    const adequada = np >= 5 && nq >= 5;
    r.vspace(1);
    r.caixa(
      [
        "N . p_barra = " + fmt(np, 2) + "    N . (1-p_barra) = " + fmt(nq, 2),
        "Aproximacao normal e " +
          (adequada ? "ADEQUADA" : "FRACA") +
          " (precisa N.p >= 5 e N.q >= 5).",
      ],
      adequada ? "ok" : "aviso"
    );

    const foraP = d.proporcoes.filter(
      (p) => p > d.lsc_P || p < d.lic_P
    ).length;
    r.vspace(1);
    r.subtitulo(`Proporcoes observadas (${d.proporcoes.length})`);
    const linhasP: string[][] = d.proporcoes.map((p, i) => [
      String(i + 1),
      fmt(p, 4),
      p > d.lsc_P || p < d.lic_P ? "fora" : "ok",
    ]);
    r.tabela(["#", "p_chapeu", "Status"], linhasP, [30, 65, 40]);
    r.caixa(
      ["Pontos fora dos limites: " + foraP + " de " + d.proporcoes.length],
      foraP > 0 ? "aviso" : "ok"
    );
  } else if (tipo === "u") {
    const d = dados as DadosU;
    r.capitulo(5, "Analise especifica - Carta U (Poisson)", COR_NEUTRA);
    r.grade(
      [
        ["u_barra", fmt(d.U_bar, 6)],
        ["n (unidade)", String(d.n)],
        ["sigma_u", fmt(d.desvio_padrao_u, 6)],
        ["Total defeitos", String(d.total_defeitos)],
        ["LSC", fmt(d.lsc_u, 6)],
        ["LIC", fmt(d.lic_u, 6)],
      ],
      2
    );

    r.vspace(1);
    r.subtitulo("Aproximacao normal para Poisson");
    r.formula("sigma_u = sqrt( u_barra / n )");
    r.formula("LSC = u_barra + 3 . sigma_u");
    r.formula("LIC = max( 0 , u_barra - 3 . sigma_u )");

    const nu = d.n * d.U_bar;
    r.vspace(1);
    r.caixa(
      [
        "n . u_barra = " + fmt(nu, 2),
        "Aproximacao normal e " +
          (nu >= 5 ? "ADEQUADA" : "FRACA") +
          " (melhora quando n.u_barra >= 5).",
      ],
      nu >= 5 ? "ok" : "aviso"
    );

    const foraU = d.u_valores.filter(
      (u) => u > d.lsc_u || u < d.lic_u
    ).length;
    r.vspace(1);
    r.subtitulo(`Valores observados (${d.u_valores.length})`);
    const linhasU: string[][] = d.u_valores.map((u, i) => [
      String(i + 1),
      fmt(u, 4),
      u > d.lsc_u || u < d.lic_u ? "fora" : "ok",
    ]);
    r.tabela(["#", "u_chapeu", "Status"], linhasU, [30, 65, 40]);
    r.caixa(
      ["Pontos fora dos limites: " + foraU + " de " + d.u_valores.length],
      foraU > 0 ? "aviso" : "ok"
    );
  }

  r.rodape();
  return r.doc;
}

// ─── Conveniência: nome de arquivo padronizado ───────────────────────────
export function nomeArquivoPdf(tipo: TipoCarta): string {
  return `validacao-${tipo}-${Date.now()}.pdf`;
}
