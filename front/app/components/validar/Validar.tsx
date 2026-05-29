"use client";

import { useState, useMemo, useRef } from "react";
import {
  probLess,
  probGreater,
  probBetween,
  zScore,
  arl,
  analisarCorridas,
  regrasWesternElectric,
  resumir,
} from "@/app/lib/stats";
import {
  gerarPdfValidacao,
  normalizarResposta,
  extrairParams,
  nomeArquivoPdf,
  type TipoCarta,
  type DadosCarta,
} from "@/app/lib/pdfValidacao";
import { Campo, Stat } from "./Campos";
import { gerarPdfManual } from "./pdfManual";
import {
  PARAMS_VAZIO,
  fmt,
  pct,
  type ModoProb,
  type Parametros,
  type ResultadoProb,
  type ResultadoLimites,
  type ResultadoARL,
} from "./types";

export default function Validar() {
  const [params, setParams] = useState<Parametros>(PARAMS_VAZIO);
  const [erro, setErro] = useState("");

  const [modo, setModo] = useState<ModoProb>("intervalo");
  const [valorA, setValorA] = useState<string>("-1");
  const [valorB, setValorB] = useState<string>("1");

  const [L, setL] = useState<string>("3");
  const [k, setK] = useState<string>("1");

  const [resProb, setResProb] = useState<ResultadoProb | null>(null);
  const [resArl, setResArl] = useState<ResultadoARL | null>(null);
  const [resLimites, setResLimites] = useState<ResultadoLimites | null>(null);

  const [pontosTexto, setPontosTexto] = useState("");

  // Auto-validação a partir do backend
  const [tipoCarta, setTipoCarta] = useState<TipoCarta>("xr");
  const [autoLoading, setAutoLoading] = useState(false);
  const [autoStatus, setAutoStatus] = useState<string>("");
  const [dadosCarregados, setDadosCarregados] = useState<DadosCarta | null>(
    null,
  );

  const inputJsonRef = useRef<HTMLInputElement>(null);

  const atualizar = (campo: keyof Parametros, valor: string) => {
    if (campo === "nome") {
      setParams((p) => ({ ...p, nome: valor }));
      return;
    }
    if (campo === "pontos") return;
    const num = Number(valor);
    if (!Number.isFinite(num)) return;
    setParams((p) => ({ ...p, [campo]: num }));
  };

  const aplicarPontos = () => {
    const lista = pontosTexto
      .split(/[\s,;\n\t]+/)
      .map((s) => s.trim())
      .filter(Boolean)
      .map(Number)
      .filter(Number.isFinite);
    setParams((p) => ({ ...p, pontos: lista }));
    setErro(
      lista.length === 0 && pontosTexto.trim()
        ? "Nenhum número válido reconhecido"
        : "",
    );
  };

  const handleJson = async (file: File) => {
    setErro("");
    try {
      const txt = await file.text();
      const obj = JSON.parse(txt);
      const fonte = obj.parametros ?? obj;
      const novo: Parametros = {
        nome: obj.nome ?? fonte.nome ?? file.name.replace(/\.json$/i, ""),
        mu: Number(fonte.mu ?? fonte.media ?? PARAMS_VAZIO.mu),
        sigma: Number(fonte.sigma ?? fonte.desvio ?? PARAMS_VAZIO.sigma),
        lsc: Number(fonte.lsc ?? fonte.LSC ?? PARAMS_VAZIO.lsc),
        lm: Number(fonte.lm ?? fonte.LM ?? fonte.media ?? PARAMS_VAZIO.lm),
        lic: Number(fonte.lic ?? fonte.LIC ?? PARAMS_VAZIO.lic),
        n: Number(fonte.n ?? fonte.subgrupo ?? PARAMS_VAZIO.n),
        pontos:
          (Array.isArray(obj.pontos) && obj.pontos.map(Number)) ||
          (Array.isArray(fonte.pontos) && fonte.pontos.map(Number)) ||
          [],
      };
      setParams(novo);
      if (novo.pontos.length) setPontosTexto(novo.pontos.join(", "));
    } catch (e) {
      setErro("JSON inválido: " + (e as Error).message);
    }
  };

  const carregarJson = async (): Promise<DadosCarta | null> => {
    setErro("");
    setAutoStatus("Buscando dados do backend…");
    setAutoLoading(true);
    try {
      const r = await fetch(`/api/results/${tipoCarta}`, { cache: "no-store" });
      if (!r.ok) {
        const txt = await r.text().catch(() => r.statusText);
        throw new Error(`Backend retornou ${r.status}: ${txt}`);
      }
      const payload = await r.json();
      const dados = normalizarResposta(payload, tipoCarta);
      if (!dados) {
        throw new Error(
          `Resposta não contém objeto da carta ${tipoCarta.toUpperCase()}`,
        );
      }

      const p = extrairParams(dados, tipoCarta);
      setParams({
        nome: p.nome,
        mu: p.mu,
        sigma: p.sigma,
        lsc: p.lsc,
        lm: p.lm,
        lic: p.lic,
        n: p.n,
        pontos: p.pontos,
      });
      setPontosTexto(p.pontos.join(", "));

      if (p.sigma > 0 && p.lsc > p.lic) {
        const pAbaixo = probLess(p.lic, p.mu, p.sigma);
        const pAcima = probGreater(p.lsc, p.mu, p.sigma);
        const pDentro = probBetween(p.lic, p.lsc, p.mu, p.sigma);
        setResLimites({
          lic: p.lic,
          lsc: p.lsc,
          z_lic: zScore(p.lic, p.mu, p.sigma),
          z_lsc: zScore(p.lsc, p.mu, p.sigma),
          pAbaixo,
          pDentro,
          pAcima,
        });
        setResProb({
          modo: "intervalo",
          a: p.lic,
          b: p.lsc,
          z_a: zScore(p.lic, p.mu, p.sigma),
          z_b: zScore(p.lsc, p.mu, p.sigma),
          p: pDentro,
          p_complementar: 1 - pDentro,
          expressao: `P(LIC ≤ X ≤ LSC) = Φ(z_LSC) − Φ(z_LIC)`,
        });
        setResArl({
          L: 3,
          n: p.n,
          k: 1,
          arl0: arl(3, 0, p.n),
          arl1: arl(3, 1, p.n),
          probDentro: pDentro,
          probFora: 1 - pDentro,
          corridas:
            p.pontos.length > 0
              ? analisarCorridas(p.pontos, p.lic, p.lsc)
              : null,
          violacoes:
            p.pontos.length > 0
              ? regrasWesternElectric(p.pontos, p.mu, p.sigma)
              : [],
        });
      }

      setDadosCarregados(dados);
      setAutoStatus(
        `✓ JSON da carta ${tipoCarta.toUpperCase()} carregado — ${p.pontos.length} pontos.`,
      );
      return dados;
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao carregar JSON");
      setAutoStatus("");
      setDadosCarregados(null);
      return null;
    } finally {
      setAutoLoading(false);
    }
  };

  const validarAuto = async () => {
    const dados = dadosCarregados ?? (await carregarJson());
    if (!dados) return;
    setAutoStatus("Gerando PDF…");
    try {
      const doc = await gerarPdfValidacao(dados, tipoCarta);
      doc.save(nomeArquivoPdf(tipoCarta));
      setAutoStatus("✓ PDF gerado e baixado.");
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Falha ao gerar PDF");
      setAutoStatus("");
    }
  };

  const importarDoFluxo = async () => {
    setErro("");
    try {
      const r = await fetch("/api/processar", { cache: "no-store" });
      const j = await r.json();
      if (j.status === "erro") throw new Error(j.message);
      setErro(
        "Dados processados no servidor. Preencha μ, σ e limites manualmente ou faça upload do JSON gerado pelo Calibrador.",
      );
    } catch (e) {
      setErro("Falha ao processar: " + (e as Error).message);
    }
  };

  const resumoPontos = useMemo(
    () => (params.pontos.length ? resumir(params.pontos) : null),
    [params.pontos],
  );

  const calcularProb = () => {
    setErro("");
    const a = Number(valorA);
    if (!Number.isFinite(a)) {
      setErro("Valor 'a' inválido");
      return;
    }
    if (params.sigma <= 0) {
      setErro("σ deve ser positivo");
      return;
    }

    let p = 0;
    let z_b: number | undefined;
    let b: number | undefined;
    let expressao = "";

    if (modo === "menor") {
      p = probLess(a, params.mu, params.sigma);
      expressao = `P(X < ${fmt(a, 4)}) = Φ((${fmt(a, 4)} − μ)/σ)`;
    } else if (modo === "maior") {
      p = probGreater(a, params.mu, params.sigma);
      expressao = `P(X > ${fmt(a, 4)}) = 1 − Φ((${fmt(a, 4)} − μ)/σ)`;
    } else {
      const bb = Number(valorB);
      if (!Number.isFinite(bb)) {
        setErro("Valor 'b' inválido");
        return;
      }
      b = bb;
      p = probBetween(a, bb, params.mu, params.sigma);
      z_b = zScore(bb, params.mu, params.sigma);
      expressao = `P(${fmt(Math.min(a, bb), 4)} ≤ X ≤ ${fmt(Math.max(a, bb), 4)}) = Φ(z₂) − Φ(z₁)`;
    }

    setResProb({
      modo,
      a,
      b,
      z_a: zScore(a, params.mu, params.sigma),
      z_b,
      p,
      p_complementar: 1 - p,
      expressao,
    });
  };

  const calcularPorLimite = (tipo: "menor" | "maior" | "dentro") => {
    setErro("");
    if (params.sigma <= 0) {
      setErro("σ deve ser positivo");
      return;
    }
    if (tipo === "menor") {
      setModo("menor");
      setValorA(String(params.lic));
      const p = probLess(params.lic, params.mu, params.sigma);
      setResProb({
        modo: "menor",
        a: params.lic,
        z_a: zScore(params.lic, params.mu, params.sigma),
        p,
        p_complementar: 1 - p,
        expressao: `P(X < LIC) = P(X < ${fmt(params.lic, 4)}) = Φ((LIC − μ)/σ)`,
      });
    } else if (tipo === "maior") {
      setModo("maior");
      setValorA(String(params.lsc));
      const p = probGreater(params.lsc, params.mu, params.sigma);
      setResProb({
        modo: "maior",
        a: params.lsc,
        z_a: zScore(params.lsc, params.mu, params.sigma),
        p,
        p_complementar: 1 - p,
        expressao: `P(X > LSC) = P(X > ${fmt(params.lsc, 4)}) = 1 − Φ((LSC − μ)/σ)`,
      });
    } else {
      setModo("intervalo");
      setValorA(String(params.lic));
      setValorB(String(params.lsc));
      const p = probBetween(params.lic, params.lsc, params.mu, params.sigma);
      setResProb({
        modo: "intervalo",
        a: params.lic,
        b: params.lsc,
        z_a: zScore(params.lic, params.mu, params.sigma),
        z_b: zScore(params.lsc, params.mu, params.sigma),
        p,
        p_complementar: 1 - p,
        expressao: `P(LIC ≤ X ≤ LSC) = Φ(z_LSC) − Φ(z_LIC)`,
      });
    }
  };

  const calcularTudoLimites = () => {
    setErro("");
    if (params.sigma <= 0) {
      setErro("σ deve ser positivo");
      return;
    }
    if (params.lsc <= params.lic) {
      setErro("LSC deve ser maior que LIC");
      return;
    }
    const pAbaixo = probLess(params.lic, params.mu, params.sigma);
    const pAcima = probGreater(params.lsc, params.mu, params.sigma);
    const pDentro = probBetween(
      params.lic,
      params.lsc,
      params.mu,
      params.sigma,
    );
    setResLimites({
      lic: params.lic,
      lsc: params.lsc,
      z_lic: zScore(params.lic, params.mu, params.sigma),
      z_lsc: zScore(params.lsc, params.mu, params.sigma),
      pAbaixo,
      pDentro,
      pAcima,
    });
  };

  const calcularArl = () => {
    setErro("");
    const Lnum = Number(L);
    const knum = Number(k);
    if (!Number.isFinite(Lnum) || Lnum <= 0) {
      setErro("L (largura dos limites em σ) deve ser > 0");
      return;
    }
    if (!Number.isFinite(knum) || knum < 0) {
      setErro("k (deslocamento em σ) deve ser ≥ 0");
      return;
    }
    if (params.sigma <= 0) {
      setErro("σ deve ser positivo");
      return;
    }

    const probDentro = probBetween(
      params.lic,
      params.lsc,
      params.mu,
      params.sigma,
    );

    setResArl({
      L: Lnum,
      n: params.n,
      k: knum,
      arl0: arl(Lnum, 0, params.n),
      arl1: arl(Lnum, knum, params.n),
      probDentro,
      probFora: 1 - probDentro,
      corridas:
        params.pontos.length > 0
          ? analisarCorridas(params.pontos, params.lic, params.lsc)
          : null,
      violacoes:
        params.pontos.length > 0
          ? regrasWesternElectric(params.pontos, params.mu, params.sigma)
          : [],
    });
  };

  const gerarPDF = async () => {
    if (!resProb && !resArl && !resLimites) {
      setErro("Calcule probabilidade, limites ou CMC antes de exportar o PDF");
      return;
    }
    await gerarPdfManual({ params, resProb, resLimites, resArl });
  };

  return (
    <div className="text-left">
      <div className="max-w-6xl mx-auto p-2">
        <h2 className="text-2xl font-semibold tracking-tight text-fg mb-1">
          Validador Estatístico
        </h2>
        <p className="text-fg-muted mb-6 text-sm">
          Distribuição normal · CMC (ARL) · Western Electric · PDF — segundo Montgomery
        </p>

        {erro && (
          <div className="mb-4 p-3 rounded-xl bg-danger-soft border border-danger/30 text-danger text-sm">
            {erro}
          </div>
        )}

        {/* Auto-validação a partir do backend */}
        <section className="bg-surface-alt border border-line rounded-2xl p-5 mb-5">
          <h3 className="text-lg font-semibold tracking-tight text-fg mb-1">
            Validação automática a partir do backend
          </h3>
          <p className="text-xs text-fg-muted mb-3">
            Lê o JSON em <span className="font-mono">/results/cep/&lt;carta&gt;</span>,
            mapeia μ, σ, LSC/LIC e gera o PDF.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-3 items-end">
            <div>
              <label className="block text-[11px] font-semibold tracking-widest text-fg-muted uppercase mb-1.5">
                Tipo de carta
              </label>
              <select
                value={tipoCarta}
                onChange={(e) => {
                  setTipoCarta(e.target.value as TipoCarta);
                  setDadosCarregados(null);
                  setAutoStatus("");
                }}
                disabled={autoLoading}
                className="w-full p-2 rounded-xl bg-surface border border-line text-fg font-mono text-sm focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent-soft transition"
              >
                <option value="xr">X̄-R — média e amplitude</option>
                <option value="imr">I-MR — indivíduos e amplitude móvel</option>
                <option value="p">P — proporção de defeituosos</option>
                <option value="u">U — defeitos por unidade</option>
              </select>
            </div>
            <button
              onClick={carregarJson}
              disabled={autoLoading}
              aria-label="Carregar JSON do backend"
              className="px-5 py-2 bg-surface hover:bg-line/60 border border-line disabled:opacity-50 rounded-full text-fg font-medium tracking-tight"
            >
              {autoLoading ? "Carregando…" : "Carregar JSON"}
            </button>
            <button
              onClick={validarAuto}
              disabled={autoLoading}
              aria-label="Gerar PDF automático"
              className="px-5 py-2 bg-accent hover:bg-accent-hover disabled:opacity-50 rounded-full text-white font-medium tracking-tight"
            >
              {autoLoading ? "Processando…" : "Gerar PDF"}
            </button>
          </div>

          {autoStatus && (
            <p
              className={`mt-3 text-sm ${
                autoStatus.startsWith("✓")
                  ? "text-emerald-600 dark:text-emerald-400"
                  : "text-fg-muted"
              }`}
            >
              {autoStatus}
            </p>
          )}
        </section>

        {/* Parâmetros */}
        <section className="bg-surface-alt border border-line rounded-2xl p-5 mb-5">
          <div className="flex justify-between items-center mb-3">
            <h3 className="text-lg font-semibold tracking-tight text-fg">
              Parâmetros do processo
            </h3>
            <div className="flex gap-2 text-sm">
              <button
                onClick={() => inputJsonRef.current?.click()}
                aria-label="Carregar parâmetros de um arquivo JSON"
                className="px-3 py-1.5 bg-accent hover:bg-accent-hover rounded-full text-white font-medium tracking-tight"
              >
                Upload JSON
              </button>
              <input
                ref={inputJsonRef}
                type="file"
                accept=".json"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) handleJson(f);
                }}
              />
              <button
                onClick={importarDoFluxo}
                aria-label="Disparar /processar no backend"
                className="px-3 py-1.5 bg-surface hover:bg-line/60 border border-line rounded-full text-fg font-medium tracking-tight"
              >
                Processar dados
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <Campo label="Nome" value={params.nome} onChange={(v) => atualizar("nome", v)} tipo="text" />
            <Campo label="μ (média)" value={String(params.mu)} onChange={(v) => atualizar("mu", v)} />
            <Campo label="σ (desvio)" value={String(params.sigma)} onChange={(v) => atualizar("sigma", v)} />
            <Campo label="n (subgrupo)" value={String(params.n)} onChange={(v) => atualizar("n", v)} />
            <Campo label="LSC" value={String(params.lsc)} onChange={(v) => atualizar("lsc", v)} />
            <Campo label="LM" value={String(params.lm)} onChange={(v) => atualizar("lm", v)} />
            <Campo label="LIC" value={String(params.lic)} onChange={(v) => atualizar("lic", v)} />
          </div>

          <div className="mt-4">
            <label className="block text-[11px] font-semibold tracking-widest text-fg-muted uppercase mb-1.5">
              Pontos observados (opcional, separados por espaço/vírgula)
            </label>
            <textarea
              value={pontosTexto}
              onChange={(e) => setPontosTexto(e.target.value)}
              onBlur={aplicarPontos}
              rows={3}
              placeholder="ex: 9.8, 10.1, 10.05, 9.92, 10.3 …"
              className="w-full p-2 rounded-xl bg-surface border border-line text-fg font-mono text-xs focus:border-accent focus:outline-none focus:ring-4 focus:ring-accent-soft transition"
            />
            {resumoPontos && (
              <p className="text-xs text-fg-muted mt-1">
                n={resumoPontos.n} · x̄={fmt(resumoPontos.media)} · s={fmt(resumoPontos.desvio)} · mín={fmt(resumoPontos.min)} · máx={fmt(resumoPontos.max)}
              </p>
            )}
          </div>
        </section>

        {/* Análise pelos limites de controle */}
        <section className="bg-surface-alt border border-line rounded-2xl p-5 mb-5">
          <h3 className="text-lg font-semibold tracking-tight text-fg mb-1">
            Análise pelos limites de controle (LIC/LSC)
          </h3>
          <p className="text-xs text-fg-muted mb-3">
            Calcula a probabilidade de um ponto cair fora ou dentro dos limites
            informados, usando a distribuição normal N(μ, σ²).
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-3">
            <button
              onClick={() => calcularPorLimite("menor")}
              className="px-3 py-2 bg-rose-600 hover:bg-rose-500 rounded-full text-white text-sm font-medium tracking-tight"
            >
              P(X &lt; LIC) — abaixo
            </button>
            <button
              onClick={() => calcularPorLimite("dentro")}
              className="px-3 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-full text-white text-sm font-medium tracking-tight"
            >
              P(LIC ≤ X ≤ LSC) — dentro
            </button>
            <button
              onClick={() => calcularPorLimite("maior")}
              className="px-3 py-2 bg-amber-600 hover:bg-amber-500 rounded-full text-white text-sm font-medium tracking-tight"
            >
              P(X &gt; LSC) — acima
            </button>
          </div>

          <button
            onClick={calcularTudoLimites}
            className="w-full md:w-auto px-4 py-2 bg-indigo-600 hover:bg-indigo-500 rounded-full text-white text-sm font-medium tracking-tight"
          >
            Calcular as três regiões e consolidar no relatório
          </button>

          {resLimites && (
            <div className="mt-4 p-3 bg-indigo-500/10 border-l-4 border-indigo-500 rounded-xl text-sm text-fg">
              <p className="font-mono text-xs text-fg-muted mb-2">
                LIC = {fmt(resLimites.lic)} · LSC = {fmt(resLimites.lsc)} · z(LIC) = {fmt(resLimites.z_lic)} · z(LSC) = {fmt(resLimites.z_lsc)}
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Stat label="P(X < LIC)" valor={pct(resLimites.pAbaixo)} dest />
                <Stat label="P(dentro)" valor={pct(resLimites.pDentro)} dest />
                <Stat label="P(X > LSC)" valor={pct(resLimites.pAcima)} dest />
              </div>
              <p className="text-xs text-fg-muted mt-2">
                P(fora) = {pct(resLimites.pAbaixo + resLimites.pAcima)} · ARL ≈ {fmt(1 / (resLimites.pAbaixo + resLimites.pAcima || Infinity), 2)} amostras
              </p>
            </div>
          )}
        </section>

        {/* Probabilidade */}
        <section className="bg-surface-alt border border-line rounded-2xl p-5 mb-5">
          <h3 className="text-lg font-semibold tracking-tight text-fg mb-3">
            Probabilidade — Distribuição Normal (livre)
          </h3>
          <div className="flex flex-wrap gap-2 mb-3">
            {(["menor", "maior", "intervalo"] as ModoProb[]).map((m) => (
              <button
                key={m}
                onClick={() => setModo(m)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium tracking-tight transition-colors ${
                  modo === m
                    ? "bg-violet-600 text-white"
                    : "bg-surface text-fg border border-line hover:bg-surface-alt"
                }`}
              >
                {m === "menor" ? "P(X < a)" : m === "maior" ? "P(X > a)" : "P(a ≤ X ≤ b)"}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm items-end">
            <Campo label="a" value={valorA} onChange={setValorA} />
            {modo === "intervalo" && <Campo label="b" value={valorB} onChange={setValorB} />}
            <button
              onClick={calcularProb}
              className="col-span-2 md:col-span-1 px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-full text-white font-medium tracking-tight"
            >
              Calcular probabilidade
            </button>
          </div>

          {resProb && (
            <div className="mt-4 p-3 bg-violet-500/10 border-l-4 border-violet-500 rounded-xl text-sm text-fg">
              <p className="font-mono text-xs text-fg-muted">{resProb.expressao}</p>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-2">
                <Stat label="z(a)" valor={fmt(resProb.z_a)} />
                {resProb.z_b !== undefined && <Stat label="z(b)" valor={fmt(resProb.z_b)} />}
                <Stat label="P calculada" valor={pct(resProb.p)} dest />
                <Stat label="Complementar" valor={pct(resProb.p_complementar)} />
              </div>
            </div>
          )}
        </section>

        {/* ARL / CMC */}
        <section className="bg-surface-alt border border-line rounded-2xl p-5 mb-5">
          <h3 className="text-lg font-semibold tracking-tight text-fg mb-3">
            Comprimento Médio de Corrida (CMC / ARL)
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm items-end">
            <Campo label="L (largura ±L·σ)" value={L} onChange={setL} />
            <Campo label="k (deslocamento em σ)" value={k} onChange={setK} />
            <button
              onClick={calcularArl}
              className="col-span-2 md:col-span-1 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-full text-white font-medium tracking-tight"
            >
              Calcular CMC
            </button>
          </div>

          {resArl && (
            <div className="mt-4 p-3 bg-emerald-500/10 border-l-4 border-emerald-500 rounded-xl text-sm text-fg">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="ARL₀ (em controle)" valor={fmt(resArl.arl0, 2)} dest />
                <Stat label={`ARL₁ (k=${fmt(resArl.k, 2)}σ)`} valor={fmt(resArl.arl1, 2)} dest />
                <Stat label="P(dentro)" valor={pct(resArl.probDentro)} />
                <Stat label="P(fora)" valor={pct(resArl.probFora)} />
              </div>

              {resArl.corridas && (
                <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                  <Stat label="Corridas" valor={String(resArl.corridas.totalCorridas)} />
                  <Stat label="Maior dentro" valor={String(resArl.corridas.maiorCorridaDentro)} />
                  <Stat label="Maior fora" valor={String(resArl.corridas.maiorCorridaFora)} />
                  <Stat label="CMC obs." valor={fmt(resArl.corridas.cmcObservado, 2)} />
                </div>
              )}

              {resArl.violacoes.length > 0 && (
                <div className="mt-3">
                  <p className="text-amber-600 dark:text-amber-400 text-xs font-semibold mb-1">
                    Western Electric — {resArl.violacoes.length} violação(ões)
                  </p>
                  <ul className="text-xs text-amber-600 dark:text-amber-400 list-disc list-inside max-h-32 overflow-auto">
                    {resArl.violacoes.slice(0, 10).map((v, i) => (
                      <li key={i}>{v.descricao}</li>
                    ))}
                    {resArl.violacoes.length > 10 && (
                      <li>… e mais {resArl.violacoes.length - 10}</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
          )}
        </section>

        {/* PDF */}
        <section className="bg-surface-alt border border-line rounded-2xl p-5">
          <h3 className="text-lg font-semibold tracking-tight text-fg mb-2">
            Relatório PDF
          </h3>
          <p className="text-xs text-fg-muted mb-3">
            Gera um PDF com parâmetros, fórmulas, probabilidades, ARL e
            corridas observadas.
          </p>
          <button
            onClick={gerarPDF}
            disabled={!resProb && !resArl && !resLimites}
            aria-label="Gerar PDF manual"
            className="w-full md:w-auto px-5 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 rounded-full text-white font-medium tracking-tight"
          >
            Gerar PDF
          </button>
        </section>
      </div>
    </div>
  );
}
