#!/usr/bin/env python3
"""
mqtt_test.py — Teste de fumaça do caminho completo ESP32 ↔ broker ↔ lâmpada
Instalar dependência: pip install paho-mqtt

Uso:
  python3 mqtt_test.py                    # usa localhost
  python3 mqtt_test.py 192.168.0.42       # usa IP externo
"""

import sys
import time
import threading
import paho.mqtt.client as mqtt

BROKER     = sys.argv[1] if len(sys.argv) > 1 else "localhost"
PORT       = 1883
TOPICO_CMD    = "jmorais/esp32s3/led/comando"
TOPICO_ESTADO = "jmorais/esp32s3/led/estado"
TOPICO_LWT    = "jmorais/esp32s3/led/disponibilidade"

CICLOS   = 3       # quantas vezes liga/desliga
DELAY    = 2.0     # segundos entre comandos
TIMEOUT  = 5.0     # máximo para receber confirmação de estado

# ─────────────────────────────────────────────────────────────────────────────
estado_recebido = threading.Event()
ultimo_estado   = {"valor": None}
erros           = []

def on_connect(client, userdata, flags, rc, props=None):
    if rc == 0:
        print(f"[broker] Conectado a {BROKER}:{PORT}")
        client.subscribe([(TOPICO_ESTADO, 1), (TOPICO_LWT, 1)])
    else:
        print(f"[broker] Falha de conexão rc={rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode().strip()
    print(f"  ← {msg.topic}: {payload}")
    if msg.topic == TOPICO_LWT:
        if payload != "online":
            erros.append(f"ESP32 está {payload!r} — verifique a conexão WiFi/MQTT da placa")
    if msg.topic == TOPICO_ESTADO:
        ultimo_estado["valor"] = payload
        estado_recebido.set()

def publicar_e_confirmar(client, comando: str, esperado: str) -> bool:
    estado_recebido.clear()
    ultimo_estado["valor"] = None
    client.publish(TOPICO_CMD, comando, qos=1)
    print(f"  → {TOPICO_CMD}: {comando}")

    if not estado_recebido.wait(timeout=TIMEOUT):
        msg = f"Timeout: sem resposta de estado após '{comando}'"
        print(f"  [ERRO] {msg}")
        erros.append(msg)
        return False

    recebido = ultimo_estado["valor"]
    ok = recebido == esperado
    status = "OK" if ok else f"ERRO (esperado {esperado!r}, recebido {recebido!r})"
    print(f"  [estado] {status}")
    if not ok:
        erros.append(f"Comando '{comando}': esperado '{esperado}', recebido '{recebido}'")
    return ok

# ─────────────────────────────────────────────────────────────────────────────
def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mqtt-test-pi")
    client.on_connect = on_connect
    client.on_message = on_message

    client.connect(BROKER, PORT, keepalive=10)
    client.loop_start()

    # Aguarda conexão e mensagem de disponibilidade retida
    time.sleep(1.5)

    print(f"\n=== Teste de fumaça — {CICLOS} ciclos ON/OFF ===\n")

    for i in range(1, CICLOS + 1):
        print(f"--- Ciclo {i}/{CICLOS} ---")
        publicar_e_confirmar(client, "ON",  "ON")
        time.sleep(DELAY)
        publicar_e_confirmar(client, "OFF", "OFF")
        time.sleep(DELAY)

    # Testa TOGGLE
    print("--- Teste TOGGLE ---")
    estado_antes = ultimo_estado["valor"]
    estado_recebido.clear()
    client.publish(TOPICO_CMD, "TOGGLE", qos=1)
    print(f"  → {TOPICO_CMD}: TOGGLE  (estado anterior: {estado_antes})")
    if estado_recebido.wait(timeout=TIMEOUT):
        print(f"  [estado] {ultimo_estado['valor']}  (OK)")
    else:
        erros.append("Timeout no TOGGLE")

    # Deixa desligado ao final
    time.sleep(DELAY)
    publicar_e_confirmar(client, "OFF", "OFF")

    client.loop_stop()
    client.disconnect()

    print("\n=== Resultado ===")
    if erros:
        print(f"FALHOU — {len(erros)} erro(s):")
        for e in erros:
            print(f"  • {e}")
        sys.exit(1)
    else:
        print("PASSOU — todos os ciclos confirmados com sucesso.")

if __name__ == "__main__":
    main()
