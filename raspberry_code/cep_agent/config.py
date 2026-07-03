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
MQTT_TOPICO_LAMPADA = os.environ.get("MQTT_TOPICO_LAMPADA", "jmorais/lampada/sessao")
MQTT_TOPICO_STATUS_LAMPADA = os.environ.get(
    "MQTT_TOPICO_STATUS_LAMPADA", "jmorais/lampada/status"
)

# Credenciais/TLS — obrigatório quando o agente roda fora da LAN da Pi
# (ex.: Render) e o broker precisa ficar exposto na internet.
MQTT_USERNAME      = os.environ.get("MQTT_USERNAME") or None
MQTT_PASSWORD      = os.environ.get("MQTT_PASSWORD") or None
MQTT_TLS           = os.environ.get("MQTT_TLS", "false").strip().lower() in ("1", "true", "yes")

CANAL              = os.environ.get("CANAL", "default")
CANAL_LAMPADA      = os.environ.get("CANAL_LAMPADA", "lampada")
XR_SUBGRUPO_N      = int(os.environ.get("XR_SUBGRUPO_N", "5"))
P_CRITERIO_DEFEITO = os.environ.get("P_CRITERIO_DEFEITO", "").strip() or None

AGENT_PORT         = int(os.environ.get("AGENT_PORT", "8080"))
TZ                 = os.environ.get("TZ", "America/Sao_Paulo")

# Desative quando o disparo diário/mensal for feito por outro agendador
# (ex.: Render Cron Job — ver raspberry_code/render-free.yaml) para não
# gerar o mesmo relatório duas vezes.
SCHEDULER_ENABLED  = os.environ.get("SCHEDULER_ENABLED", "true").strip().lower() in ("1", "true", "yes")
