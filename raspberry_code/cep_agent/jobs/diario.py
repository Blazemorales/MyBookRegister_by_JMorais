"""Job diário: consolida os dados de ontem e publica no backend.

Executado às 03:00 BRT pelo APScheduler (ver scheduler.py).

Cadeia:
  1. Obtém JWT de serviço (/device/token).
  2. Busca pontos de medicoes_stream de ontem (/stream/diario).
  3. Reconstrói datasets por carta e roda o núcleo CEP.
  4. Gera PNGs das cartas (matplotlib Agg, headless) e PDF consolidado.
  5. Publica no backend (/relatorios/diario).
  6. Salva cópia local em SQLite (resilience offline).
"""
from __future__ import annotations

import base64
import io
import json
import logging
import sqlite3
import tempfile
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use("Agg")

from config import BACKEND_URL, CANAL, RPI_DEVICE_TOKEN

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "relatorios_locais.db"

# ── Importa o núcleo CEP (relativo ao repositório) ────────────────────
# A Raspberry hospeda o repositório completo. O núcleo fica em
# cep_code/backend/CEP/ (dois níveis acima de raspberry_code/cep_agent/).
import sys as _sys
_REPO = Path(__file__).resolve().parents[3]
_BACKEND = _REPO / "cep_code" / "backend"
if str(_BACKEND) not in _sys.path:
    _sys.path.insert(0, str(_BACKEND))

from CEP.respostas import calcular_answer_set


# ── Auth helper ───────────────────────────────────────────────────────

async def _obter_jwt(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{BACKEND_URL}/device/token",
        json={"token": RPI_DEVICE_TOKEN},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


# ── Busca de pontos ───────────────────────────────────────────────────

async def _buscar_pontos_dia(client: httpx.AsyncClient, jwt: str, data: str) -> list[dict]:
    r = await client.get(
        f"{BACKEND_URL}/stream/diario",
        params={"data": data, "canal": CANAL},
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json().get("pontos", [])


# ── Reconstrói datasets por carta ────────────────────────────────────

def _pontos_para_datasets(pontos: list[dict]) -> list[dict]:
    """Reconstrói datasets compatíveis com DataProcessor a partir dos pontos do stream."""
    por_chart: dict[str, list] = defaultdict(list)
    for p in pontos:
        payload = p.get("payload", {})
        chart = (payload.get("chart") or "xr").lower()
        valor = payload.get("valor")
        valores = payload.get("valores")
        if valor is not None:
            por_chart[chart].append(float(valor))
        elif isinstance(valores, list):
            por_chart[chart].extend(float(v) for v in valores)

    datasets = []
    if "imr" in por_chart and len(por_chart["imr"]) >= 2:
        meds: dict[str, list] = {str(i): [v] for i, v in enumerate(por_chart["imr"])}
        datasets.append({"chart": "IMR", "measurements": meds})
    if "xr" in por_chart and len(por_chart["xr"]) >= 2:
        n = 5
        grupos: dict[str, list] = {}
        vals = por_chart["xr"]
        for idx in range(0, len(vals) - n + 1, n):
            grupos[str(idx // n)] = vals[idx: idx + n]
        if grupos:
            datasets.append({"chart": "XR", "measurements": grupos})
    return datasets


# ── Geração de PNG em base64 para cada carta ─────────────────────────

def _gerar_charts_b64(dados_tratados: list[dict]) -> dict[str, str]:
    charts: dict[str, str] = {}
    for d in dados_tratados:
        chart = d.get("chart", "").upper()
        try:
            if chart == "XR":
                fig = _plot_xr(d)
            elif chart == "IMR":
                fig = _plot_imr(d)
            else:
                continue
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            plt.close(fig)
            charts[chart] = base64.b64encode(buf.getvalue()).decode()
        except Exception:
            logger.exception("falha ao gerar PNG para carta %s", chart)
    return charts


def _plot_xr(d: dict) -> plt.Figure:
    medias = [s["media"] for s in d.get("estatisticas_por_amostra", [])]
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(medias, "o-", lw=1)
    ax.axhline(d["x_double_bar"], color="green", label=f"LC={d['x_double_bar']:.4f}")
    ax.axhline(d["lsc_x"], color="red", ls="--", label=f"LSC={d['lsc_x']:.4f}")
    ax.axhline(d["lic_x"], color="red", ls="--", label=f"LIC={d['lic_x']:.4f}")
    ax.set_title("Carta X̄")
    ax.legend(fontsize=7)
    return fig


def _plot_imr(d: dict) -> plt.Figure:
    vals = d.get("valores_individuais", [])
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.plot(vals, "o-", lw=1)
    ax.axhline(d["media_ind"], color="green", label=f"LC={d['media_ind']:.4f}")
    ax.axhline(d["lsc_ind"], color="red", ls="--", label=f"LSC={d['lsc_ind']:.4f}")
    ax.axhline(d["lic_ind"], color="red", ls="--", label=f"LIC={d['lic_ind']:.4f}")
    ax.set_title("Carta I")
    ax.legend(fontsize=7)
    return fig


# ── PDF do dia ────────────────────────────────────────────────────────

# fpdf2 com fonte core (Arial/Helvetica) só suporta latin-1. Textos vindos
# de JSON/answer_set podem trazer tipografia "smart" (em/en dash, aspas
# curvas, reticências) que quebra o encode — normaliza pro equivalente
# ASCII antes de qualquer pdf.cell/multi_cell.
_PDF_UNSUPPORTED = str.maketrans({
    "—": "-",   # —
    "–": "-",   # –
    "‘": "'",   # '
    "’": "'",   # '
    "“": '"',   # "
    "”": '"',   # "
    "…": "...", # …
    "•": "-",   # •
})


def _pdf_safe(texto: str) -> str:
    texto = texto.translate(_PDF_UNSUPPORTED)
    return texto.encode("latin-1", errors="replace").decode("latin-1")


def _gerar_pdf(data: str, answer_set: dict, charts_b64: dict[str, str]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(190, 10, _pdf_safe(f"Relatorio CEP Diario - {data}"), ln=True, align="C")
    pdf.ln(4)

    for chart, resp in answer_set.items():
        if chart == "atributos":
            continue
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 8, _pdf_safe(f"Carta {chart}"), ln=True)
        pdf.set_font("Arial", "", 9)
        texto = json.dumps(resp, indent=2, ensure_ascii=False)
        pdf.multi_cell(190, 4, _pdf_safe(texto[:1000]))  # trunca para caber
        pdf.ln(3)
        if chart in charts_b64:
            img_bytes = base64.b64decode(charts_b64[chart])
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            pdf.image(tmp_path, x=10, w=180)
            Path(tmp_path).unlink(missing_ok=True)

    return bytes(pdf.output())


# ── Publicação no backend ─────────────────────────────────────────────

async def _publicar(client: httpx.AsyncClient, jwt: str, data: str,
                    dados: dict, charts: dict, pdf: bytes) -> None:
    headers = {"Authorization": f"Bearer {jwt}"}
    r = await client.post(
        f"{BACKEND_URL}/relatorios/diario",
        json={"periodo": data, "canal": CANAL, "dados": dados, "charts": charts},
        headers=headers,
        timeout=30.0,
    )
    r.raise_for_status()
    logger.info("[diario] publicado no backend: %s", r.json())


# ── Cache local SQLite ────────────────────────────────────────────────

def _salvar_local(data: str, dados: dict, pdf: bytes) -> None:
    con = sqlite3.connect(_DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS relatorios_diarios
           (periodo TEXT PRIMARY KEY, dados TEXT, pdf BLOB, gerado_em TEXT)"""
    )
    from datetime import datetime, timezone
    con.execute(
        "INSERT OR REPLACE INTO relatorios_diarios VALUES (?,?,?,?)",
        (data, json.dumps(dados), pdf, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()
    con.close()


# ── Entry point ───────────────────────────────────────────────────────

async def run_diario(data_brt: Optional[str] = None) -> bool:
    """Gera e publica o relatório do dia `data_brt` (YYYY-MM-DD).

    Se `data_brt` for None, usa ontem (em BRT).
    Retorna True em caso de sucesso.
    """
    if data_brt is None:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Sao_Paulo")
        from datetime import datetime
        ontem = (datetime.now(tz) - timedelta(days=1)).date()
        data_brt = ontem.isoformat()

    logger.info("[diario] iniciando job para %s", data_brt)

    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            jwt = await _obter_jwt(client)
        except Exception as exc:
            logger.error("[diario] falha ao obter JWT: %s", exc)
            return False

        try:
            pontos = await _buscar_pontos_dia(client, jwt, data_brt)
        except Exception as exc:
            logger.error("[diario] falha ao buscar pontos: %s", exc)
            return False

    logger.info("[diario] %d ponto(s) recebidos para %s", len(pontos), data_brt)

    if not pontos:
        logger.warning("[diario] nenhum ponto para %s — relatório vazio", data_brt)
        dados_vazio = {"aviso": "sem dados no período", "periodo": data_brt}
        _salvar_local(data_brt, dados_vazio, b"")
        return True

    datasets = _pontos_para_datasets(pontos)
    if not datasets:
        logger.warning("[diario] pontos sem formato reconhecível para CEP")
        return False

    # Processa via núcleo CEP
    from CEP.amostras.data_processor import DataProcessor
    processor = DataProcessor()
    processor.datasets = datasets
    processor.processar_dados()

    answer_set = calcular_answer_set(processor.dados_tratados)
    charts_b64 = _gerar_charts_b64(processor.dados_tratados)
    pdf_bytes = _gerar_pdf(data_brt, answer_set, charts_b64)

    _salvar_local(data_brt, answer_set, pdf_bytes)

    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            jwt = await _obter_jwt(client)
            await _publicar(client, jwt, data_brt, answer_set, charts_b64, pdf_bytes)
            logger.info("[diario] relatório %s publicado com sucesso", data_brt)
            return True
        except Exception as exc:
            logger.error("[diario] falha ao publicar: %s", exc)
            return False
