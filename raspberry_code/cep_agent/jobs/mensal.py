"""Job mensal: agrega os relatórios diários do mês anterior.

Executado no dia 1 às 03:05 BRT pelo APScheduler (ver scheduler.py).

Cadeia:
  1. Obtém JWT de serviço.
  2. Busca pontos do mês anterior em /stream/periodo.
  3. Agrega indicadores de todos os dias (médias ponderadas, ppm consolidado,
     contagem de pontos fora, deslocamentos detectados).
  4. Publica em /relatorios/mensal.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

import httpx

from config import BACKEND_URL, CANAL, RPI_DEVICE_TOKEN

logger = logging.getLogger(__name__)

import sys as _sys
from pathlib import Path
_REPO = Path(__file__).resolve().parents[3]
_BACKEND = _REPO / "cep_code" / "backend"
if str(_BACKEND) not in _sys.path:
    _sys.path.insert(0, str(_BACKEND))


async def _obter_jwt(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{BACKEND_URL}/device/token",
        json={"token": RPI_DEVICE_TOKEN},
        timeout=15.0,
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def _buscar_pontos_periodo(
    client: httpx.AsyncClient, jwt: str, inicio: str, fim: str
) -> list[dict]:
    r = await client.get(
        f"{BACKEND_URL}/stream/periodo",
        params={"inicio": inicio, "fim": fim, "canal": CANAL},
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=60.0,
    )
    r.raise_for_status()
    return r.json().get("pontos", [])


def _agregar_pontos(pontos: list[dict]) -> dict:
    """Calcula indicadores mensais a partir dos pontos brutos do stream."""
    from collections import defaultdict
    import numpy as np
    from CEP.respostas import calcular_answer_set
    from jobs.diario import _pontos_para_datasets
    from CEP.amostras.data_processor import DataProcessor

    por_chart: dict[str, list] = defaultdict(list)
    for p in pontos:
        payload = p.get("payload", {})
        chart = (payload.get("chart") or "xr").lower()
        valor = payload.get("valor")
        if valor is not None:
            por_chart[chart].append(float(valor))

    datasets = _pontos_para_datasets(pontos)
    if not datasets:
        return {"aviso": "pontos insuficientes para CEP mensal", "n_pontos": len(pontos)}

    processor = DataProcessor()
    processor.datasets = datasets
    processor.processar_dados()
    answer_set = calcular_answer_set(processor.dados_tratados)

    # Adiciona contagem de pontos por carta
    for chart in ("xr", "imr", "p", "u"):
        if chart in por_chart:
            answer_set[f"n_pontos_{chart}"] = len(por_chart[chart])

    answer_set["n_pontos_total"] = len(pontos)
    return answer_set


async def run_mensal(mes_brt: Optional[str] = None) -> bool:
    """Gera e publica o relatório do mês `mes_brt` (YYYY-MM).

    Se None, usa o mês anterior.
    """
    if mes_brt is None:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        tz = ZoneInfo("America/Sao_Paulo")
        hoje = datetime.now(tz).date()
        primeiro_do_mes = hoje.replace(day=1)
        mes_anterior = (primeiro_do_mes - __import__("datetime").timedelta(days=1)).replace(day=1)
        mes_brt = mes_anterior.strftime("%Y-%m")

    ano, mes = mes_brt.split("-")
    inicio = f"{ano}-{mes}-01"
    import calendar
    ultimo_dia = calendar.monthrange(int(ano), int(mes))[1]
    fim = f"{ano}-{mes}-{ultimo_dia:02d}"

    logger.info("[mensal] iniciando job para %s (%s → %s)", mes_brt, inicio, fim)

    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            jwt = await _obter_jwt(client)
            pontos = await _buscar_pontos_periodo(client, jwt, inicio, fim)
        except Exception as exc:
            logger.error("[mensal] falha ao buscar pontos: %s", exc)
            return False

    logger.info("[mensal] %d ponto(s) recebidos para %s", len(pontos), mes_brt)

    if not pontos:
        logger.warning("[mensal] nenhum ponto para %s", mes_brt)
        return True

    try:
        dados = _agregar_pontos(pontos)
    except Exception as exc:
        logger.exception("[mensal] falha ao agregar pontos")
        return False

    transport = httpx.AsyncHTTPTransport(retries=3)
    async with httpx.AsyncClient(transport=transport) as client:
        try:
            jwt = await _obter_jwt(client)
            r = await client.post(
                f"{BACKEND_URL}/relatorios/mensal",
                json={"periodo": mes_brt, "canal": CANAL, "dados": dados},
                headers={"Authorization": f"Bearer {jwt}"},
                timeout=30.0,
            )
            r.raise_for_status()
            logger.info("[mensal] relatório %s publicado: %s", mes_brt, r.json())
            return True
        except Exception as exc:
            logger.error("[mensal] falha ao publicar: %s", exc)
            return False
