"use client";

import { useState, useCallback, useRef } from "react";
import { useCepRelatorio } from "@/hooks/useCepRelatorio";
import type { TipoRelatorio } from "@/hooks/cepApi";

const TIPOS: { valor: TipoRelatorio; label: string; descricao: string }[] = [
  { valor: "xr", label: "Carta X̄-R", descricao: "Média e amplitude" },
  { valor: "p", label: "Carta P", descricao: "Proporção de defeituosos" },
  { valor: "u", label: "Carta U", descricao: "Defeitos por unidade" },
  { valor: "imr", label: "Carta I-MR", descricao: "Indivíduos e amplitude móvel" },
];

export default function RelatorioViewer() {
  const [tipo, setTipo] = useState<TipoRelatorio>("xr");
  const [aba, setAba] = useState<"padrao" | "json">("padrao");

  const [dragAtivo, setDragAtivo] = useState(false);
  const [nomeArquivo, setNomeArquivo] = useState<string | null>(null);
  const [jsonRecemEnviado, setJsonRecemEnviado] = useState(false);
  const [etapaAuto, setEtapaAuto] = useState<
    "idle" | "enviando" | "processando" | "pronto" | "erro"
  >("idle");

  const inputRef = useRef<HTMLInputElement>(null);

  const {
    carregando,
    erro,
    pdfUrl,
    processamento,
    processar,
    buscarRelatorio,
    baixar,
    limpar,
    enviarJson,
  } = useCepRelatorio();

  const handleProcessar = useCallback(async () => {
    setJsonRecemEnviado(false);
    setEtapaAuto("processando");
    const res = await processar();
    setEtapaAuto(res ? "pronto" : "erro");
  }, [processar]);

  const handleArquivo = useCallback(
    async (file: File) => {
      if (!file.name.endsWith(".json")) {
        alert("Envie apenas arquivos .json");
        return;
      }

      setNomeArquivo(file.name);
      setJsonRecemEnviado(false);
      setEtapaAuto("enviando");
      setAba("padrao");

      const ok = await enviarJson(file);

      if (!ok) {
        setEtapaAuto("erro");
        return;
      }

      setJsonRecemEnviado(true);
      setEtapaAuto("processando");

      const res = await processar();
      setEtapaAuto(res ? "pronto" : "erro");
    },
    [enviarJson, processar]
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      setDragAtivo(false);

      const file = e.dataTransfer.files?.[0];
      if (!file) return;

      handleArquivo(file);
    },
    [handleArquivo]
  );

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragAtivo(true);
  };

  const handleDragLeave = () => setDragAtivo(false);

  return (
    <div className="flex flex-col gap-8 p-8 max-w-4xl mx-auto font-sans">
      <h2 className="text-2xl font-semibold tracking-tight text-fg text-center">
        Calibrador de dados
      </h2>

      <div className="flex gap-2 justify-center">
        <SubTab ativo={aba === "padrao"} onClick={() => setAba("padrao")}>
          Fluxo padrão
        </SubTab>
        <SubTab ativo={aba === "json"} onClick={() => setAba("json")}>
          Upload JSON
        </SubTab>
      </div>

      {aba === "padrao" && (
        <>
          {etapaAuto !== "idle" && (
            <FluxoStepper
              etapa={etapaAuto}
              nomeArquivo={nomeArquivo}
              mensagem={processamento?.message}
            />
          )}

          <section className="flex flex-col items-center gap-3">
            <h3 className="text-[11px] font-semibold tracking-widest text-fg-muted uppercase">
              Passo 1 — Processar dados
            </h3>

            <button
              onClick={handleProcessar}
              disabled={carregando}
              className={`px-5 py-2.5 rounded-full font-medium tracking-tight transition-all ${
                jsonRecemEnviado && etapaAuto !== "pronto"
                  ? "bg-accent text-white hover:bg-accent-hover ring-4 ring-accent-soft animate-pulse"
                  : "bg-surface-alt text-fg hover:bg-line/60"
              }`}
            >
              {carregando
                ? etapaAuto === "enviando"
                  ? "Enviando JSON…"
                  : "Processando…"
                : "Processar Dados"}
            </button>

            {processamento && etapaAuto === "pronto" && (
              <span className="text-emerald-600 dark:text-emerald-400 text-sm">
                ✓ {processamento.message}
              </span>
            )}
          </section>

          <section className="flex flex-col items-center gap-4">
            <h3 className="text-[11px] font-semibold tracking-widest text-fg-muted uppercase">
              Passo 2 — Escolher carta
            </h3>

            <div className="flex flex-wrap justify-center gap-3">
              {TIPOS.map((t) => (
                <button
                  key={t.valor}
                  onClick={() => {
                    limpar();
                    setTipo(t.valor);
                  }}
                  className={`p-4 rounded-2xl border min-w-[140px] text-left transition-all ${
                    tipo === t.valor
                      ? "bg-accent border-accent text-white scale-[1.02]"
                      : "bg-surface border-line text-fg hover:border-fg-muted/40"
                  }`}
                >
                  <b className="text-[15px] font-semibold tracking-tight">
                    {t.label}
                  </b>
                  <div
                    className={`text-xs mt-0.5 ${
                      tipo === t.valor ? "text-white/80" : "text-fg-muted"
                    }`}
                  >
                    {t.descricao}
                  </div>
                </button>
              ))}
            </div>
          </section>

          <section className="flex justify-center gap-3 flex-wrap">
            <button
              onClick={() => buscarRelatorio(tipo)}
              disabled={carregando}
              className="px-6 py-2.5 bg-accent text-white rounded-full font-medium tracking-tight hover:bg-accent-hover disabled:opacity-60 transition-colors"
            >
              {carregando ? "Gerando…" : "Gerar Relatório"}
            </button>

            {pdfUrl && (
              <>
                <button
                  onClick={() => baixar(`relatorio-${tipo}.pdf`)}
                  className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-full font-medium tracking-tight transition-colors"
                >
                  Baixar PDF
                </button>

                <button
                  onClick={limpar}
                  className="px-5 py-2.5 bg-surface-alt text-fg rounded-full font-medium tracking-tight hover:bg-line/60 transition-colors"
                >
                  Limpar
                </button>
              </>
            )}
          </section>
        </>
      )}

      {aba === "json" && (
        <section className="flex flex-col items-center gap-4">
          <h3 className="text-[11px] font-semibold tracking-widest text-fg-muted uppercase">
            Enviar JSON
          </h3>

          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onClick={() => inputRef.current?.click()}
            className={`w-full max-w-md h-40 flex flex-col items-center justify-center border-2 border-dashed rounded-2xl cursor-pointer transition-all ${
              dragAtivo
                ? "border-accent bg-accent-soft"
                : "border-line bg-surface-alt hover:border-fg-muted/40"
            }`}
          >
            <p className="text-sm text-fg">Arraste seu JSON aqui</p>
            <p className="text-xs text-fg-muted mt-1">
              ou clique para selecionar
            </p>

            <input
              ref={inputRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleArquivo(file);
              }}
            />
          </div>

          {nomeArquivo && (
            <p className="text-xs text-emerald-600 dark:text-emerald-400">
              Arquivo: {nomeArquivo}
            </p>
          )}

          <button
            onClick={() => buscarRelatorio(tipo, false)}
            className="px-6 py-2.5 bg-accent text-white rounded-full font-medium tracking-tight hover:bg-accent-hover transition-colors"
          >
            Gerar Relatório
          </button>
        </section>
      )}

      {erro && (
        <div className="p-3 bg-danger-soft text-danger border border-danger/30 rounded-xl text-sm">
          {erro}
        </div>
      )}

      {pdfUrl && (
        <iframe
          src={pdfUrl}
          title={`Relatório CEP — carta ${tipo.toUpperCase()}`}
          className="w-full border border-line rounded-2xl bg-surface"
          style={{ height: "70vh" }}
        />
      )}
    </div>
  );
}

function SubTab({
  ativo,
  onClick,
  children,
}: {
  ativo: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 rounded-full text-[13px] font-medium tracking-tight transition-colors ${
        ativo
          ? "bg-accent text-white"
          : "bg-surface-alt text-fg hover:bg-line/60"
      }`}
    >
      {children}
    </button>
  );
}

type EtapaAuto = "idle" | "enviando" | "processando" | "pronto" | "erro";

function FluxoStepper({
  etapa,
  nomeArquivo,
  mensagem,
}: {
  etapa: EtapaAuto;
  nomeArquivo: string | null;
  mensagem?: string;
}) {
  const passos = [
    { id: "enviando", label: "Enviando JSON" },
    { id: "processando", label: "Processando dados" },
    { id: "pronto", label: "Pronto para gerar relatório" },
  ] as const;

  const ordem = (e: EtapaAuto) =>
    e === "enviando" ? 0 : e === "processando" ? 1 : e === "pronto" ? 2 : -1;

  const atual = ordem(etapa);

  return (
    <div className="w-full max-w-2xl mx-auto rounded-2xl border border-line bg-surface-alt p-4 animate-in fade-in duration-300">
      <ol className="flex items-center justify-between gap-2">
        {passos.map((p, i) => {
          const concluido = atual > i || etapa === "pronto";
          const ativo = atual === i && etapa !== "pronto" && etapa !== "erro";
          const falhou = etapa === "erro" && atual === -1 && i === 0;
          return (
            <li
              key={p.id}
              className="flex-1 flex flex-col items-center text-center"
            >
              <div
                className={`h-9 w-9 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-all ${
                  falhou
                    ? "border-danger bg-danger-soft text-danger"
                    : concluido
                      ? "border-emerald-500 bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                      : ativo
                        ? "border-accent bg-accent-soft text-accent animate-pulse"
                        : "border-line bg-surface text-fg-muted"
                }`}
              >
                {falhou ? "!" : concluido ? "✓" : ativo ? "…" : i + 1}
              </div>
              <span
                className={`mt-2 text-[11px] font-medium ${
                  ativo
                    ? "text-accent"
                    : concluido
                      ? "text-emerald-600 dark:text-emerald-400"
                      : "text-fg-muted"
                }`}
              >
                {p.label}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="mt-3 text-center text-sm">
        {etapa === "enviando" && (
          <p className="text-accent">
            Enviando <span className="font-mono">{nomeArquivo}</span> ao
            servidor…
          </p>
        )}
        {etapa === "processando" && (
          <p className="text-accent">
            Servidor processando os dados — aguarde…
          </p>
        )}
        {etapa === "pronto" && (
          <p className="text-emerald-600 dark:text-emerald-400">
            ✓{" "}
            {mensagem ??
              "Dados processados. Escolha a carta e gere o relatório."}
          </p>
        )}
        {etapa === "erro" && (
          <p className="text-danger">Clique em &ldquo;Processar Dados&rdquo;</p>
        )}
      </div>
    </div>
  );
}
