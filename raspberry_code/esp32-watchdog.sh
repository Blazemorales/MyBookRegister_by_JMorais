#!/usr/bin/env bash
# esp32-watchdog.sh — Monitora disponibilidade da ESP32 via MQTT LWT
# Loga quando a placa cai (offline) ou volta (online)
# Instalação: veja esp32-watchdog.service

BROKER="${MQTT_BROKER:-localhost}"
TOPICO="jmorais/esp32s3/led/disponibilidade"

echo "[watchdog] Monitorando $TOPICO em $BROKER"

mosquitto_sub -h "$BROKER" -t "$TOPICO" -v --retained-only -C 1 &
pid_retained=$!
sleep 2
kill "$pid_retained" 2>/dev/null || true

mosquitto_sub -h "$BROKER" -t "$TOPICO" -v | while read -r linha; do
    ts=$(date '+%Y-%m-%d %H:%M:%S')
    status=$(echo "$linha" | awk '{print $NF}')
    case "$status" in
        online)  echo "[$ts] [INFO] ESP32 ONLINE"  ;;
        offline) echo "[$ts] [ALERTA] ESP32 OFFLINE — verifique WiFi ou alimentação USB" ;;
        *)       echo "[$ts] [?] Mensagem inesperada: $linha" ;;
    esac
done
