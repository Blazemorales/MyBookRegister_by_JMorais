#!/usr/bin/env bash
# setup_mosquitto.sh — Instala e configura o broker MQTT na Raspberry Pi
# Executar com: bash setup_mosquitto.sh
set -euo pipefail

CONF_FILE="/etc/mosquitto/conf.d/local.conf"

echo "=== [1/4] Atualizando lista de pacotes ==="
sudo apt update -q

echo "=== [2/4] Instalando mosquitto e clientes ==="
sudo apt install -y mosquitto mosquitto-clients

echo "=== [3/4] Criando configuração para rede local ==="
sudo tee "$CONF_FILE" > /dev/null <<'EOF'
# Aceita conexões de qualquer IP na porta 1883
listener 1883 0.0.0.0

# AVISO: allow_anonymous só é seguro em rede local confiável.
# Para produção, use: mosquitto_passwd /etc/mosquitto/passwd <usuário>
# e substitua esta linha por: password_file /etc/mosquitto/passwd
allow_anonymous true
EOF

echo "=== [4/4] Habilitando e reiniciando o serviço ==="
sudo systemctl enable --now mosquitto
sudo systemctl restart mosquitto
sleep 1
sudo systemctl status mosquitto --no-pager

echo ""
echo "IP desta Raspberry Pi:"
hostname -I
echo ""
echo "Coloque o IP acima em MQTT_BROKER no firmware da ESP32."
echo "Teste rápido:"
echo "  Terminal A: mosquitto_sub -h localhost -t 'jmorais/esp32s3/led/#' -v"
echo "  Terminal B: mosquitto_pub -h localhost -t 'jmorais/esp32s3/led/comando' -m 'ON'"
