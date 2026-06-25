"""Pipeline CEP em memória — sem dependência de filesystem.

Camada de adaptação sobre DataProcessor + Cartas para que o backend
possa processar amostras vindas do banco e devolver:
- `dados`    (JSON) por carta — para /results/cep/<chart>
- `respostas`(JSON) answer set completo Q1+Q2 — para /results/cep/<chart>
- `pdf`      (bytes) por carta — para /relatorio/<chart>

As classes originais ainda escrevem PDFs em disco, então isolamos o
efeito colateral por chart via tempdir + ENV var `CEP_RELATORIOS_DIR`.
"""
from __future__ import annotations

import json
import os
import tempfile
from contextlib import contextmanager
from typing import Iterable, Optional


@contextmanager
def _relatorios_dir(tmpdir: str):
    """Aponta Cartas.obter_caminhos para `tmpdir` durante o bloco."""
    anterior = os.environ.get("CEP_RELATORIOS_DIR")
    os.environ["CEP_RELATORIOS_DIR"] = tmpdir
    try:
        yield
    finally:
        if anterior is None:
            os.environ.pop("CEP_RELATORIOS_DIR", None)
        else:
            os.environ["CEP_RELATORIOS_DIR"] = anterior


def processar_para_usuario(amostras: Iterable[dict]) -> dict[str, dict]:
    """Recebe lista de payloads (formato do upload) e devolve
    `{chart: {dados: ..., respostas: ...}}`.

    O campo `respostas` contém o answer set completo do PDF (items a–g
    para cartas de variáveis; controle + deslocamento para atributos).
    """
    from CEP.amostras.data_processor import DataProcessor
    from CEP.respostas import calcular_answer_set

    processor = DataProcessor()
    processor.datasets = list(amostras)
    if not processor.datasets:
        return {}

    if not processor.processar_dados():
        return {}

    answer_set = calcular_answer_set(processor.dados_tratados)

    saida: dict[str, dict] = {}
    for dados in processor.dados_tratados:
        chart = (dados.get("chart") or "").upper()
        if not chart:
            continue
        saida[chart] = {
            "dados": dados,
            "respostas": answer_set.get(chart) or answer_set.get("atributos"),
        }

    # Inclui o bloco de atributos separado para que /results/cep/p e /u
    # também exponham as respostas Q2.
    if "atributos" in answer_set:
        for chart in ("P", "U"):
            if chart in saida:
                saida[chart]["respostas_q2"] = answer_set["atributos"]

    return saida


_CARTA_TO_PDF = {
    "XR":  "relatorio_XR.pdf",
    "P":   "relatorio_P.pdf",
    "U":   "relatorio_U.pdf",
    "IMR": "relatorio_IMR.pdf",
}


def gerar_pdf_para(chart: str, dados_tratados: Optional[dict]) -> bytes:
    """Gera o PDF da carta `chart` e retorna como bytes."""
    from CEP.cartas_controle.Cartas import Cartas

    chart = chart.upper()
    if chart not in _CARTA_TO_PDF:
        raise ValueError(f"chart inválida: {chart}")

    with tempfile.TemporaryDirectory(prefix="cep_") as tmpdir:
        with _relatorios_dir(tmpdir):
            if chart == "XR":
                Cartas.carta_xr(dados_tratados)
            elif chart == "P":
                Cartas.carta_p(dados_tratados)
            elif chart == "U":
                Cartas.carta_u(dados_tratados)
            elif chart == "IMR":
                Cartas.carta_imr(dados_tratados)

        caminho_pdf = os.path.join(tmpdir, _CARTA_TO_PDF[chart])
        if not os.path.exists(caminho_pdf):
            raise RuntimeError(
                f"Pipeline não gerou {caminho_pdf} para chart {chart}"
            )
        with open(caminho_pdf, "rb") as f:
            return f.read()


def normalizar_payload_upload(raw: bytes | str) -> list[dict]:
    """Lê o JSON do upload e devolve sempre uma lista de datasets canônicos."""
    from CEP.amostras.data_processor import normalizar_dataset

    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    obj = json.loads(raw)
    datasets = obj if isinstance(obj, list) else [obj]
    return [normalizar_dataset(ds) for ds in datasets]
