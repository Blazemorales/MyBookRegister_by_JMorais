#!/usr/bin/env python3
"""
============================================================================
 control_led.py  —  API de controle da lâmpada, rodando na Raspberry Pi
============================================================================
 Papel: receber requisições HTTP (/led/on, /led/off, /led/toggle, /led/state)
 e publicar comandos MQTT no broker mosquitto local, que a ESP32 assina.

 - Publica comandos no tópico de comando.
 - Um cliente MQTT em segundo plano assina os tópicos de ESTADO (retido) e de
   DISPONIBILIDADE (LWT), então /led/state responde o estado real da lâmpada e
   se a ESP32 está online — sem precisar consultar a placa a cada request.

 Dependências:  pip install flask paho-mqtt gunicorn
============================================================================
"""
import threading
from flask import Flask, jsonify

import paho.mqtt.client as mqtt

# ---- Configuração ----
BROKER = "localhost"
PORT   = 1883

TOPIC_COMANDO        = "jmorais/esp32s3/led/comando"
TOPIC_ESTADO         = "jmorais/esp32s3/led/estado"
TOPIC_DISPONIBILIDADE = "jmorais/esp32s3/led/disponibilidade"

# ---- Estado em cache (atualizado pelo cliente MQTT em segundo plano) ----
estado = {"aceso": None, "online": False}

# ============================================================================
#  Cliente MQTT (assinante + publicador)
# ============================================================================
cliente = mqtt.Client(client_id="pi-led-api")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        client.subscribe(TOPIC_ESTADO)
        client.subscribe(TOPIC_DISPONIBILIDADE)
        print("[MQTT] conectado ao broker e assinando estado/disponibilidade")
    else:
        print(f"[MQTT] falha na conexão, rc={rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode(errors="ignore").strip().upper()
    if msg.topic == TOPIC_ESTADO:
        estado["aceso"] = (payload == "ON")
    elif msg.topic == TOPIC_DISPONIBILIDADE:
        estado["online"] = (payload == "ONLINE")

cliente.on_connect = on_connect
cliente.on_message = on_message

def iniciar_mqtt():
    while True:
        try:
            cliente.connect(BROKER, PORT, keepalive=30)
            cliente.loop_forever()          # reconecta sozinho em quedas
        except Exception as e:
            print(f"[MQTT] erro: {e}; tentando de novo em 5s")
            import time; time.sleep(5)

# sobe o cliente MQTT numa thread separada do servidor web
threading.Thread(target=iniciar_mqtt, daemon=True).start()

# ============================================================================
#  API HTTP
# ============================================================================
app = Flask(__name__)

def publicar(cmd):
    cliente.publish(TOPIC_COMANDO, cmd)

@app.get("/led/on")
def on():     publicar("ON");     return jsonify(ok=True, comando="ON")
@app.get("/led/off")
def off():    publicar("OFF");    return jsonify(ok=True, comando="OFF")
@app.get("/led/toggle")
def toggle(): publicar("TOGGLE"); return jsonify(ok=True, comando="TOGGLE")

@app.get("/led/state")
def state():
    return jsonify(aceso=estado["aceso"], online=estado["online"])

# página mínima pra controlar pelo navegador (opcional)
PAGINA = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lâmpada</title><style>body{font-family:sans-serif;text-align:center;
background:#0b1120;color:#e2e8f0;padding-top:60px}button{font-size:1rem;padding:14px 22px;
margin:6px;border:none;border-radius:10px;cursor:pointer;background:#38bdf8;color:#0b1120}
#s{font-size:1.2rem;margin:18px}</style></head><body>
<h2>Controle da Lâmpada</h2><div id="s">—</div>
<button onclick="a('on')">Ligar</button><button onclick="a('off')">Desligar</button>
<button onclick="a('toggle')">Alternar</button>
<script>async function u(){let r=await fetch('/led/state');let j=await r.json();
document.getElementById('s').textContent=(j.online?'':'(ESP32 offline) ')+
(j.aceso===null?'—':(j.aceso?'ACESA':'APAGADA'));}
async function a(c){await fetch('/led/'+c);setTimeout(u,300);}
u();setInterval(u,2000);</script></body></html>"""

@app.get("/")
def root():
    return PAGINA

if __name__ == "__main__":
    # modo de teste; em produção use o gunicorn (ver README)
    app.run(host="127.0.0.1", port=5000)
