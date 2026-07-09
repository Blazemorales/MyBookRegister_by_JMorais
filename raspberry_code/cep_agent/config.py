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
# Tópicos publicados diretamente pelo firmware atual da ESP32
# (codigo_esp.ino) — plain "ON"/"OFF" (retained) e segundos da sessão
# atual. Uso preferencial: MQTT_TOPICO_STATUS_LAMPADA/MQTT_TOPICO_LAMPADA
# acima só têm dado se o lampada_stats.py (pipeline legado via POST
# /lampada) estiver recebendo eventos, o que o firmware atual não faz.
MQTT_TOPICO_ESTADO_ESP32 = os.environ.get(
    "MQTT_TOPICO_ESTADO_ESP32", "mbrlamp/lampada/estado"
)
MQTT_TOPICO_TEMPO_SESSAO_ESP32 = os.environ.get(
    "MQTT_TOPICO_TEMPO_SESSAO_ESP32", "mbrlamp/lampada/tempo_sessao_s"
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
# (ex.: GitHub Actions — ver raspberry_code/render-free.yaml) para não
# gerar o mesmo relatório duas vezes.
SCHEDULER_ENABLED  = os.environ.get("SCHEDULER_ENABLED", "true").strip().lower() in ("1", "true", "yes")

# Desative quando esta instância não tem acesso ao broker MQTT da Pi
# (ex.: rodando no Render free — o broker só existe na LAN da Pi). O
# ingest.py continua rodando normalmente na própria Pi via cep-agent.service.
INGEST_ENABLED     = os.environ.get("INGEST_ENABLED", "true").strip().lower() in ("1", "true", "yes")
