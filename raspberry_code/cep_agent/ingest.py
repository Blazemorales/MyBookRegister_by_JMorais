"""Ponte ESP32 → JSON → mybookregister (Socket.IO).

Assina o tópico MQTT da ESP32, agrupa as leituras nos formatos necessários
para cada carta CEP e emite `rpi_data` para o backend local via Socket.IO.

Decisão de subgrupo (FASE 0.5):
  - X̄-R : agrupa XR_SUBGRUPO_N leituras consecutivas → 1 ponto na carta X̄-R.
  - I-MR : cada leitura individual → 1 ponto (n=1).
  - P    : se P_CRITERIO_DEFEITO configurado, conta defeituosos no buffer e
           emite quando o buffer atingir XR_SUBGRUPO_N itens.
  - U    : mesmo critério de P, mas normalizado por unidade (defeitos/n).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections import deque
from typing import Any, Optional

import paho.mqtt.client as mqtt
import socketio

from config import (
    BACKEND_URL,
    CANAL,
    MQTT_BROKER,
    MQTT_PORT,
    MQTT_TOPICO_SENSOR,
    P_CRITERIO_DEFEITO,
    RPI_DEVICE_TOKEN,
    XR_SUBGRUPO_N,
)

logger = logging.getLogger(__name__)

# ── Análise do critério de defeito ────────────────────────────────────

_OPS = {"<": float.__lt__, "<=": float.__le__, ">": float.__gt__,
        ">=": float.__ge__, "==": float.__eq__, "!=": float.__ne__}


def _compilar_criterio(expr: Optional[str]):
    if not expr:
        return None
    m = re.search(r"([<>!=]=|[<>])\s*(-?\d+(?:[.,]\d+)?)", expr)
    if not m:
        return None
    op = _OPS.get(m.group(1))
    limite = float(m.group(2).replace(",", "."))
    return lambda x: op(float(x), limite)


_pred = _compilar_criterio(P_CRITERIO_DEFEITO)


# ── Buffer de leituras ────────────────────────────────────────────────

_buf: deque[float] = deque(maxlen=XR_SUBGRUPO_N * 20)


def _parse_leitura(payload_bytes: bytes) -> Optional[float]:
    """Extrai um float do payload MQTT (número puro ou JSON {"valor": ...})."""
    texto = payload_bytes.decode("utf-8", errors="ignore").strip()
    try:
        return float(texto)
    except ValueError:
        pass
    try:
        obj = json.loads(texto)
        if isinstance(obj, dict):
            v = obj.get("valor") or obj.get("value")
            return float(v) if v is not None else None
        return float(obj)
    except Exception:
        return None


# ── Socket.IO client (async) ──────────────────────────────────────────

_sio = socketio.AsyncClient(
    reconnection=True,
    reconnection_attempts=0,
    reconnection_delay=1,
    reconnection_delay_max=10,
)

_conectado = asyncio.Event()


@_sio.event
async def connect():
    logger.info("[ingest] Socket.IO conectado a %s", BACKEND_URL)
    _conectado.set()


@_sio.event
async def disconnect():
    logger.warning("[ingest] Socket.IO desconectado — reconectando…")
    _conectado.clear()


@_sio.on("rpi_erro")
async def on_erro(data):
    logger.warning("[ingest] backend rejeitou payload: %s", data)


async def _conectar_sio():
    await _sio.connect(
        BACKEND_URL,
        auth={"role": "rpi", "token": RPI_DEVICE_TOKEN},
        transports=["websocket"],
    )


async def _emitir(payload: dict):
    if not _conectado.is_set():
        logger.debug("[ingest] aguardando conexão Socket.IO…")
        await asyncio.wait_for(_conectado.wait(), timeout=15.0)
    try:
        ack = await _sio.call("rpi_data", payload, timeout=5)
        logger.debug("[ingest] rpi_data ack: %s", ack)
    except Exception as exc:
        logger.warning("[ingest] falha ao emitir rpi_data: %s", exc)


# ── Processamento de leituras ─────────────────────────────────────────

_loop: Optional[asyncio.AbstractEventLoop] = None


def _processar_leitura(valor: float):
    """Agrega a leitura e emite payloads para cada carta configurada."""
    _buf.append(valor)

    # I-MR: sempre, ponto a ponto
    payload_imr = {
        "chart": "imr",
        "valor": valor,
        "canal": CANAL,
        "unidade": "leitura",
    }
    asyncio.run_coroutine_threadsafe(_emitir(payload_imr), _loop)

    # X̄-R: a cada XR_SUBGRUPO_N leituras, emite o subgrupo como lista
    if len(_buf) >= XR_SUBGRUPO_N:
        subgrupo = list(_buf)[-XR_SUBGRUPO_N:]
        payload_xr: dict[str, Any] = {
            "chart": "xr",
            "valores": subgrupo,
            "subgrupo": len(subgrupo),
            "canal": CANAL,
        }
        asyncio.run_coroutine_threadsafe(_emitir(payload_xr), _loop)

    # P / U: se critério configurado
    if _pred is not None and len(_buf) >= XR_SUBGRUPO_N:
        bloco = list(_buf)[-XR_SUBGRUPO_N:]
        n_defeituosos = sum(1 for x in bloco if _pred(x))

        payload_p: dict[str, Any] = {
            "chart": "p",
            "valor": n_defeituosos,
            "dados": {"n_total": XR_SUBGRUPO_N, "n_defeituosos": n_defeituosos},
            "canal": CANAL,
        }
        asyncio.run_coroutine_threadsafe(_emitir(payload_p), _loop)

        payload_u: dict[str, Any] = {
            "chart": "u",
            "valor": n_defeituosos / XR_SUBGRUPO_N,
            "dados": {"defeitos": n_defeituosos, "n_unidades": XR_SUBGRUPO_N},
            "canal": CANAL,
        }
        asyncio.run_coroutine_threadsafe(_emitir(payload_u), _loop)


# ── Cliente MQTT ──────────────────────────────────────────────────────

def _on_connect_mqtt(client, userdata, flags, rc, props=None):
    if rc == 0:
        logger.info("[ingest] MQTT conectado a %s:%s", MQTT_BROKER, MQTT_PORT)
        client.subscribe(MQTT_TOPICO_SENSOR, qos=1)
        logger.info("[ingest] assinando tópico: %s", MQTT_TOPICO_SENSOR)
    else:
        logger.error("[ingest] MQTT falhou rc=%s", rc)


def _on_message_mqtt(client, userdata, msg):
    valor = _parse_leitura(msg.payload)
    if valor is None:
        logger.debug("[ingest] payload MQTT não numérico ignorado: %s", msg.payload[:80])
        return
    logger.debug("[ingest] leitura MQTT: %s = %s", msg.topic, valor)
    _processar_leitura(valor)


def _criar_cliente_mqtt() -> mqtt.Client:
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="cep-agent-ingest")
    c.on_connect = _on_connect_mqtt
    c.on_message = _on_message_mqtt
    c.reconnect_delay_set(min_delay=1, max_delay=30)
    return c


# ── Entry point ───────────────────────────────────────────────────────

async def run():
    """Inicia o loop de ingestão. Chamar no lifespan do FastAPI."""
    global _loop
    _loop = asyncio.get_running_loop()

    await _conectar_sio()

    mqtt_client = _criar_cliente_mqtt()
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as exc:
        logger.error("[ingest] não conseguiu conectar ao MQTT: %s", exc)
        logger.warning("[ingest] prosseguindo sem MQTT — reconexão automática ativa")

    mqtt_client.loop_start()
    logger.info("[ingest] ponte ESP32→Socket.IO ativa")

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        await _sio.disconnect()
