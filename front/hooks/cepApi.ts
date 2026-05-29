// Tipos e utilitários de UI para o fluxo CEP.
// As chamadas ao backend passam pelas rotas /api/* do Next (ver useCepRelatorio).

export type TipoRelatorio = "xr" | "p" | "u" | "imr";

export interface ProcessarResponse {
  status: "sucesso" | "erro";
  message: string;
}

export function blobParaObjectURL(blob: Blob): string {
  return URL.createObjectURL(blob);
}

export function baixarPDF(blob: Blob, nomeArquivo = "relatorio-cep.pdf"): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nomeArquivo;
  a.click();
  URL.revokeObjectURL(url);
}
