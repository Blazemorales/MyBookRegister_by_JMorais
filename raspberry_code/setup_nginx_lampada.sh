#!/usr/bin/env bash
# setup_nginx_lampada.sh — Instala e configura o nginx como proxy reverso
# único na Raspberry Pi (ESP32 + lampada_stats.py sob o mesmo hostname).
# Executar com: bash setup_nginx_lampada.sh <IP_da_ESP32>
set -euo pipefail

ESP32_IP="${1:?uso: bash setup_nginx_lampada.sh <IP_da_ESP32>}"
CONF_SRC="$(dirname "$0")/nginx-lampada.conf"
CONF_DST="/etc/nginx/sites-available/lampada"

echo "=== [1/5] Atualizando lista de pacotes ==="
sudo apt update -q

echo "=== [2/5] Instalando nginx ==="
sudo apt install -y nginx

echo "=== [3/5] Copiando config e ajustando IP da ESP32 ($ESP32_IP) ==="
sudo cp "$CONF_SRC" "$CONF_DST"
sudo sed -i "s/server 192\.168\.0\.42:80;/server ${ESP32_IP}:80;/" "$CONF_DST"

echo "=== [4/5] Habilitando o site e desabilitando o default ==="
sudo ln -sf "$CONF_DST" /etc/nginx/sites-enabled/lampada
sudo rm -f /etc/nginx/sites-enabled/default

echo "=== [5/5] Testando e recarregando o nginx ==="
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx

echo ""
echo "nginx ativo. Teste local:"
echo "  curl -I http://localhost/            # deve responder via ESP32 ($ESP32_IP)"
echo "  curl http://localhost/stats/hoje      # deve responder via lampada_stats.py"
echo ""
echo "Agora aponte o Public Hostname do Cloudflare Tunnel para:"
echo "  http://localhost:80   (em vez do IP da ESP32 direto)"
