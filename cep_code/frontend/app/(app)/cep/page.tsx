"use client";

import { useState } from "react";
import Link from "next/link";
import Validar from "../../components/validar/Validar";
import RelatorioViewer from "../../components/calibrar/RelatorioViewer";
import RelatoriosPeriodicos from "../../components/cep/RelatoriosPeriodicos";

type Aba = "calibrar" | "validar" | "periodicos";

export default function CepPage() {
  const [abaAtiva, setAbaAtiva] = useState<Aba>("calibrar");

  return (
    <>
      <section className="text-center pt-16 pb-10">
        <Link
          href="/"
          className="inline-flex items-center gap-1 text-lg text-fg-muted hover:text-fg transition-colors mb-6"
        >
          ← Menu
        </Link>
        <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-fg">
          Minhas Estatísticas
        </h1>
        <p className="mt-3 text-lg text-fg-muted font-normal tracking-tight">
          Controle e otimize sua evolução de forma simples e eficiente. Selecione uma ferramenta para receber seus relatórios ou validar seus dados.
        </p>
      </section>

      <nav
        role="tablist"
        aria-label="Ferramentas"
        className="flex justify-center gap-2 mb-10"
      >
        <TabButton
          ativa={abaAtiva === "calibrar"}
          onClick={() => setAbaAtiva("calibrar")}
        >
          Receber Relatório
        </TabButton>
        <TabButton
          ativa={abaAtiva === "validar"}
          onClick={() => setAbaAtiva("validar")}
        >
          Validar Dados
        </TabButton>
        <TabButton
          ativa={abaAtiva === "periodicos"}
          onClick={() => setAbaAtiva("periodicos")}
        >
          Diário / Mensal
        </TabButton>
      </nav>

      <div className="bg-surface border border-line rounded-3xl shadow-sm overflow-hidden">
        {abaAtiva === "calibrar" && (
          <div className="animate-in fade-in duration-300">
            <RelatorioViewer />
          </div>
        )}
        {abaAtiva === "validar" && (
          <div className="animate-in fade-in duration-300">
            <Validar />
          </div>
        )}
        {abaAtiva === "periodicos" && (
          <div className="animate-in fade-in duration-300">
            <RelatoriosPeriodicos />
          </div>
        )}
      </div>
    </>
  );
}

function TabButton({
  ativa,
  onClick,
  children,
}: {
  ativa: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      role="tab"
      aria-selected={ativa}
      onClick={onClick}
      className={`px-6 py-2.5 rounded-full text-[15px] font-medium tracking-tight transition-all ${
        ativa
          ? "bg-accent text-white shadow-sm"
          : "bg-surface-alt text-fg hover:bg-line/60"
      }`}
    >
      {children}
    </button>
  );
}
