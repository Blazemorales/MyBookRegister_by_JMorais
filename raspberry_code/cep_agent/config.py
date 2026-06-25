"""Configurações centralizadas do agente CEP na Raspberry Pi."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_AQUI = Path(__file__).parent
load_dotenv(_AQUI / ".env", override=False)

BACKEND_URL        = os.environ["BACKEND_URL"].rstrip("/")
RPI_DEVICE_TOKEN   = os.environ["RPI_DEVICE_TOKEN"]

MQTT_BROKER        = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT          = int(os.environ.get("MQTT_PORT", "1883"))
MQTT_TOPICO_SENSOR = os.environ.get("MQTT_TOPICO_SENSOR", "jmorais/esp32s3/sensor/leitura")

CANAL              = os.environ.get("CANAL", "default")
XR_SUBGRUPO_N      = int(os.environ.get("XR_SUBGRUPO_N", "5"))
P_CRITERIO_DEFEITO = os.environ.get("P_CRITERIO_DEFEITO", "").strip() or None

AGENT_PORT         = int(os.environ.get("AGENT_PORT", "8080"))
TZ                 = os.environ.get("TZ", "America/Sao_Paulo")
