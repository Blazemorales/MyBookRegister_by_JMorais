"use client";

import { useEffect, useState } from "react";
import type { TipoRelatorio } from "@/hooks/cepApi";

interface RespostasQ1 {
  chart: string;
  mu: number;
  sigma: number;
  lic: number;
  lsc: number;
  lie: number;
  lse: number;
  fator_lie: number;
  fator_lse: number;
  curto_prazo: { sob_controle: boolean; pontos_fora: { indice: number; valor: number }[] };
  longo_prazo: { ppm_obtido: number; ppm_requerido: number; atende: boolean };
  x_para_margem_alvo: { margem_alvo: number; x_percentil: number; x_intervalo_inferior: number; x_intervalo_superior: number };
  capacidade: { cp: number | null; cpk: number | null };
  margem_atual: number;
  margem_com_deslocamento: { deslocamento_sigmas: number; margem: number };
  binomial: { k: number; n: number; p_usada: number; exata: number; ao_menos: number; ate: number };
}

interface RespostasAtributos {
  carta_p?: {
    P_bar: number;
    lic_P: number;
    lsc_P: number;
    curto_prazo: { sob_controle: boolean; pontos_fora: { indice: number; valor: number }[] };
    deslocamento_kalman: string;
  };
  carta_u?: {
    U_bar: number;
    lic_u: number;
    lsc_u: number;
    curto_prazo: { sob_controle: boolean; pontos_fora: { indice: number; valor: number }[] };
    deslocamento_kalman: string;
  };
}

interface RespostasResponse {
  respostas: RespostasQ1 | RespostasAtributos | null;
  respostas_q2: RespostasAtributos | null;
}

function pct(v: number) {
  return (v * 100).toFixed(4) + "%";
}

function fmt(v: number, d = 4) {
  return v.toFixed(d);
}

function BoolBadge({ ok, sim, nao }: { ok: boolean; sim: string; nao: string }) {
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-full text-xs font-semibold ${
        ok
          ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
          : "bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300"
      }`}
    >
      {ok ? sim : nao}
    </span>
  );
}

function SecaoVariaveis({ r }: { r: RespostasQ1 }) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 font-mono text-xs text-fg-muted bg-surface-alt rounded-xl p-3">
        <span>μ = {fmt(r.mu)}</span>
        <span>σ = {fmt(r.sigma)}</span>
        <span>LIC = {fmt(r.lic)}</span>
        <span>LSC = {fmt(r.lsc)}</span>
        <span>LIE = {r.fator_lie}×LIC = {fmt(r.lie)}</span>
        <span>LSE = {r.fator_lse}×LSC = {fmt(r.lse)}</span>
      </div>

      <Linha letra="a" titulo="Curto prazo (±3σ)">
        <BoolBadge ok={r.curto_prazo.sob_controle} sim="SOB CONTROLE" nao="FORA DE CONTROLE" />
        {!r.curto_prazo.sob_controle && (
          <span className="ml-2 text-xs text-fg-muted">
            {r.curto_prazo.pontos_fora.length} ponto(s) fora
          </span>
        )}
      </Linha>

      <Linha letra="b" titulo="Longo prazo (ppm)">
        <BoolBadge ok={r.longo_prazo.atende} sim="ATENDE" nao="NÃO ATENDE" />
        <span className="ml-2 text-xs text-fg-muted">
          ppm obtido = {fmt(r.longo_prazo.ppm_obtido, 2)} vs requerido = {r.longo_prazo.ppm_requerido}
        </span>
      </Linha>

      <Linha letra="c" titulo={`Valor de X para ${(r.x_para_margem_alvo.margem_alvo * 100).toFixed(0)}% de sucesso`}>
        <span className="font-mono font-semibold">{fmt(r.x_para_margem_alvo.x_percentil)}</span>
        <span className="ml-2 text-xs text-fg-muted">
          intervalo central: [{fmt(r.x_para_margem_alvo.x_intervalo_inferior)}, {fmt(r.x_para_margem_alvo.x_intervalo_superior)}]
        </span>
      </Linha>

      <Linha letra="d" titulo="Capacidade (Cp / Cpk centralizado)">
        <span className="font-mono">
          Cp = {r.capacidade.cp != null ? fmt(r.capacidade.cp) : "N/A"}
          {" | "}
          Cpk = {r.capacidade.cpk != null ? fmt(r.capacidade.cpk) : "N/A"}
        </span>
      </Linha>

      <Linha letra="e" titulo="Margem de sucesso atual">
        <span className="font-mono font-semibold">{pct(r.margem_atual)}</span>
      </Linha>

      <Linha letra="f" titulo={`Margem com +${r.margem_com_deslocamento.deslocamento_sigmas}σ de deslocamento`}>
        <span className="font-mono font-semibold">{pct(r.margem_com_deslocamento.margem)}</span>
      </Linha>

      <Linha letra="g" titulo={`Binomial P(X=${r.binomial.k} em ${r.binomial.n} | p=${fmt(r.binomial.p_usada)})`}>
        <span className="font-mono text-xs">
          exata = {r.binomial.exata.toExponential(4)}
          {" | "}
          P(≥{r.binomial.k}) = {r.binomial.ao_menos.toExponential(4)}
        </span>
      </Linha>
    </div>
  );
}

function SecaoAtributos({ r, prefix }: { r: RespostasAtributos; prefix: string }) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      {r.carta_p && (
        <div>
          <p className="text-xs font-semibold text-fg-muted uppercase tracking-widest mb-2">Carta P</p>
          <div className="grid grid-cols-3 gap-x-4 font-mono text-xs bg-surface-alt rounded-xl p-3 mb-2">
            <span>P̄ = {fmt(r.carta_p.P_bar, 6)}</span>
            <span>LIC = {fmt(r.carta_p.lic_P, 6)}</span>
            <span>LSC = {fmt(r.carta_p.lsc_P, 6)}</span>
          </div>
          <Linha letra={`${prefix}h`} titulo="Curto prazo">
            <BoolBadge ok={r.carta_p.curto_prazo.sob_controle} sim="SOB CONTROLE" nao="FORA DE CONTROLE" />
          </Linha>
          <Linha letra={`${prefix}i`} titulo="Deslocamento (Kalman)">
            <span className="text-xs">{r.carta_p.deslocamento_kalman}</span>
          </Linha>
        </div>
      )}
      {r.carta_u && (
        <div className="mt-2">
          <p className="text-xs font-semibold text-fg-muted uppercase tracking-widest mb-2">Carta U</p>
          <div className="grid grid-cols-3 gap-x-4 font-mono text-xs bg-surface-alt rounded-xl p-3 mb-2">
            <span>Ū = {fmt(r.carta_u.U_bar, 6)}</span>
            <span>LIC = {fmt(r.carta_u.lic_u, 6)}</span>
            <span>LSC = {fmt(r.carta_u.lsc_u, 6)}</span>
          </div>
          <Linha letra={`${prefix}j`} titulo="Curto prazo">
            <BoolBadge ok={r.carta_u.curto_prazo.sob_controle} sim="SOB CONTROLE" nao="FORA DE CONTROLE" />
          </Linha>
          <Linha letra={`${prefix}k`} titulo="Deslocamento (Kalman)">
            <span className="text-xs">{r.carta_u.deslocamento_kalman}</span>
          </Linha>
        </div>
      )}
    </div>
  );
}

function Linha({
  letra,
  titulo,
  children,
}: {
  letra: string;
  titulo: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start gap-2">
      <span className="shrink-0 w-6 h-6 flex items-center justify-center rounded-full bg-accent/10 text-accent text-[11px] font-bold">
        {letra}
      </span>
      <div>
        <p className="text-xs text-fg-muted">{titulo}</p>
        <div className="mt-0.5">{children}</div>
      </div>
    </div>
  );
}

export default function RespostasViewer({ tipo }: { tipo: TipoRelatorio }) {
  const [dados, setDados] = useState<RespostasResponse | null>(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    let cancelado = false;
    setCarregando(true);
    setErro(null);
    setDados(null);

    fetch(`/api/respostas/${tipo}`, { cache: "no-store" })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((json) => {
        if (!cancelado) {
          setDados(json as RespostasResponse);
          setCarregando(false);
        }
      })
      .catch((e) => {
        if (!cancelado) {
          setErro(e instanceof Error ? e.message : "Erro ao carregar respostas");
          setCarregando(false);
        }
      });

    return () => {
      cancelado = true;
    };
  }, [tipo]);

  if (carregando) {
    return (
      <div className="flex items-center gap-2 text-sm text-fg-muted p-4">
        <span className="animate-spin">⟳</span> Carregando respostas…
      </div>
    );
  }

  if (erro) {
    return (
      <div className="p-3 bg-danger-soft text-danger border border-danger/30 rounded-xl text-sm">
        {erro}
        {erro.includes("404") || erro.includes("não encontrado") ? (
          <p className="mt-1 text-xs text-fg-muted">Execute /processar primeiro.</p>
        ) : null}
      </div>
    );
  }

  if (!dados || !dados.respostas) {
    return (
      <p className="text-sm text-fg-muted p-4">Nenhuma resposta disponível. Processe os dados primeiro.</p>
    );
  }

  const isVariaveis = tipo === "xr" || tipo === "imr";

  return (
    <div className="border border-line rounded-2xl bg-surface p-4 flex flex-col gap-4">
      <h3 className="text-xs font-semibold tracking-widest text-fg-muted uppercase">
        Respostas do PDF — Carta {tipo.toUpperCase()}
      </h3>

      {isVariaveis && dados.respostas && (
        <SecaoVariaveis r={dados.respostas as RespostasQ1} />
      )}

      {(tipo === "p" || tipo === "u") && dados.respostas_q2 && (
        <>
          <p className="text-xs font-semibold text-fg-muted uppercase tracking-widest">
            Questão 2 — Cartas de Atributos
          </p>
          <SecaoAtributos r={dados.respostas_q2 as RespostasAtributos} prefix="" />
        </>
      )}
    </div>
  );
}
