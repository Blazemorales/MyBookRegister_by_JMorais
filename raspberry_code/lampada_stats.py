#!/usr/bin/env python3
"""
============================================================================
 lampada_stats.py — Receptor de eventos da lâmpada, rodando na Raspberry Pi
============================================================================
 Papel: receber o POST que a ESP32 (variante web, RASPBERRY_URL no .ino)
 manda a cada troca de estado, e registrar quanto tempo a lâmpada ficou
 acesa. gerar_relatorio_lampada.py depois fecha o JSON do dia com esses
 dados.

 - POST /lampada       {"aceso": bool, "ligadoHa": int}  — evento da ESP32
 - GET  /lampada/hoje                                     — total acumulado hoje

 A duração de cada sessão é calculada pelo relógio da própria Pi, não pelo
 `ligadoHa` da ESP32 (que zera a cada boot da placa e vem sempre 0 no
 evento de desligar, já que o estado interno já virou "apagada" antes do
 POST ser montado).

 Cada sessão fechada também é publicada no broker MQTT local
 (tópico MQTT_TOPICO_LAMPADA), de onde o cep_agent/ingest.py a recolhe e
 encaminha como ponto da carta I-MR no canal "lampada" — mesmo pipeline
 de autenticação/armazenamento/relatório já usado pelo CEP genérico.

 Dependências:  pip install flask gunicorn paho-mqtt
============================================================================
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

logger = logging.getLogger(__name__)

TZ = ZoneInfo("America/Sao_Paulo")
DADOS_DIR = Path(__file__).parent / "dados_lampada"
DADOS_DIR.mkdir(exist_ok=True)
ARQUIVO_ESTADO = DADOS_DIR / "estado.json"
ARQUIVO_EVENTOS = DADOS_DIR / "eventos.jsonl"

MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPICO_LAMPADA = os.environ.get("MQTT_TOPICO_LAMPADA", "jmorais/lampada/sessao")
MQTT_TOPICO_STATUS_LAMPADA = os.environ.get(
    "MQTT_TOPICO_STATUS_LAMPADA", "jmorais/lampada/status"
)

app = Flask(__name__)


def _publicar_mqtt(topico: str, payload: dict) -> None:
    """Publica no broker MQTT local, de onde o cep_agent/ingest.py recolhe.

    Best-effort: se o broker estiver fora do ar, o estado local (arquivos
    em dados_lampada/) continua sendo a fonte de verdade normalmente."""
    try:
        import paho.mqtt.publish as mqtt_publish
        mqtt_publish.single(
            topico,
            payload=json.dumps(payload),
            hostname=MQTT_BROKER,
            port=MQTT_PORT,
        )
    except Exception:
        logger.exception("[lampada] falha ao publicar no MQTT (%s)", topico)


def _agora() -> datetime:
    return datetime.now(TZ)


def _ler_estado() -> dict:
    if ARQUIVO_ESTADO.exists():
        return json.loads(ARQUIVO_ESTADO.read_text())
    return {"ligada_desde": None}


def _salvar_estado(estado: dict) -> None:
    ARQUIVO_ESTADO.write_text(json.dumps(estado))


def _registrar_sessao(inicio: datetime, fim: datetime) -> None:
    duracao_s = round((fim - inicio).total_seconds(), 1)
    evento = {
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "duracao_s": duracao_s,
    }
    with ARQUIVO_EVENTOS.open("a") as f:
        f.write(json.dumps(evento) + "\n")
    _publicar_mqtt(MQTT_TOPICO_LAMPADA, {"valor": duracao_s})


@app.post("/lampada")
def receber_evento():
    corpo = request.get_json(silent=True) or {}
    aceso = bool(corpo.get("aceso"))
    agora = _agora()
    estado = _ler_estado()

    if aceso and not estado["ligada_desde"]:
        estado["ligada_desde"] = agora.isoformat()
        _salvar_estado(estado)
        _publicar_mqtt(MQTT_TOPICO_STATUS_LAMPADA, {"aceso": True})
    elif not aceso and estado["ligada_desde"]:
        inicio = datetime.fromisoformat(estado["ligada_desde"])
        _registrar_sessao(inicio, agora)
        estado["ligada_desde"] = None
        _salvar_estado(estado)
        _publicar_mqtt(MQTT_TOPICO_STATUS_LAMPADA, {"aceso": False})

    return jsonify(ok=True)


@app.get("/lampada/hoje")
def hoje():
    from gerar_relatorio_lampada import calcular_totais_do_dia
    return jsonify(calcular_totais_do_dia(_agora().date()))


if __name__ == "__main__":
    # modo de teste; em produção use o gunicorn (ver README)
    app.run(host="0.0.0.0", port=5000)
