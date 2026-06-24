"use client";

import { useState, useCallback, useRef } from "react";
import type { TipoRelatorio, ProcessarResponse } from "@/hooks/cepApi";

interface Estado {
  carregando: boolean;
  erro: string | null;
  pdfUrl: string | null;
  processamento: ProcessarResponse | null;
}

interface UseCepRelatorioReturn extends Estado {
  processar: () => Promise<ProcessarResponse | null>;
  buscarRelatorio: (tipo: TipoRelatorio, chamarProcessar?: boolean) => Promise<void>;
  baixar: (nomeArquivo?: string) => void;
  limpar: () => void;

  enviarJson: (arquivo: File) => Promise<boolean>;
}

export function useCepRelatorio(): UseCepRelatorioReturn {
  const [estado, setEstado] = useState<Estado>({
    carregando: false,
    erro: null,
    pdfUrl: null,
    processamento: null,
  });

  const blobRef = useRef<Blob | null>(null);

  const limpar = useCallback(() => {
    if (estado.pdfUrl) URL.revokeObjectURL(estado.pdfUrl);
    blobRef.current = null;
    setEstado({
      carregando: false,
      erro: null,
      pdfUrl: null,
      processamento: null,
    });
  }, [estado.pdfUrl]);

  // 🔵 processar
  const processar = useCallback(async () => {
    setEstado((s) => ({ ...s, carregando: true, erro: null }));

    try {
      const res = await fetch("/api/processar", { cache: "no-store" });
      const json = await res.json();

      if (json.status === "erro") throw new Error(json.message);

      setEstado((s) => ({
        ...s,
        carregando: false,
        processamento: json,
      }));

      return json;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro";
      setEstado((s) => ({ ...s, carregando: false, erro: msg }));
      return null;
    }
  }, []);

  // 🟢 enviar JSON
  const enviarJson = useCallback(async (arquivo: File) => {
    setEstado((s) => ({ ...s, carregando: true, erro: null }));

    try {
      const formData = new FormData();
      formData.append("file", arquivo);

      const res = await fetch("/api/upload", {
        method: "POST",
        body: formData,
      });

      const json = await res.json();

      if (!res.ok || json.status === "erro") {
        throw new Error(json.message);
      }

      setEstado((s) => ({
        ...s,
        carregando: false,
        processamento: json,
      }));

      return true;
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro ao enviar JSON";
      setEstado((s) => ({ ...s, carregando: false, erro: msg }));
      return false;
    }
  }, []);

  // 🔵 relatório
  const buscarRelatorio = useCallback(async (tipo: TipoRelatorio, chamarProcessar = true) => {
    setEstado((s) => {
      if (s.pdfUrl) URL.revokeObjectURL(s.pdfUrl);
      return { ...s, pdfUrl: null, erro: null, carregando: true };
    });

    blobRef.current = null;

    try {
      if (chamarProcessar) {
        await fetch("/api/processar");
      }

      const res = await fetch(`/api/relatorio/${tipo}`, { cache: "no-store" });

      if (!res.ok) throw new Error("Erro ao gerar relatório");

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      blobRef.current = blob;

      setEstado((s) => ({
        ...s,
        carregando: false,
        pdfUrl: url,
      }));
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Erro";
      setEstado((s) => ({ ...s, carregando: false, erro: msg }));
    }
  }, []);

  const baixar = useCallback((nome = "relatorio.pdf") => {
    if (!blobRef.current) return;

    const url = URL.createObjectURL(blobRef.current);
    const a = document.createElement("a");
    a.href = url;
    a.download = nome;
    a.click();
    URL.revokeObjectURL(url);
  }, []);

  return {
    ...estado,
    processar,
    buscarRelatorio,
    baixar,
    limpar,
    enviarJson,
  };
}