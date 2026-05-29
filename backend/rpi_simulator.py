"""Simulador do Raspberry Pi — também serve de referência p/ o código real.

Conecta como cliente Socket.IO (role="rpi") e fica emitindo "rpi_data"
em intervalo. Útil para testar contra o backend local OU o de produção
enquanto você olha a aba "Receber relatório" no frontend.

Uso:
    SOCKET_URL=https://SEU-BACKEND.onrender.com \\
    RPI_DEVICE_TOKEN=seu-token \\
    ./venv/bin/python rpi_simulator.py

Defaults: SOCKET_URL=http://localhost:8000, intervalo de 2s.
No Raspberry Pi real, instale `python-socketio[asyncio_client]` e troque
o `random` por leituras de sensor.
"""
from __future__ import annotations

import asyncio
import os
import random

import socketio

SOCKET_URL = os.environ.get("SOCKET_URL", "http://localhost:8000")
TOKEN = os.environ.get("RPI_DEVICE_TOKEN", "")
INTERVALO = float(os.environ.get("INTERVALO", "2"))

sio = socketio.AsyncClient(
    reconnection=True,             # reconexão automática
    reconnection_attempts=0,       # 0 = tenta para sempre
    reconnection_delay=1,
    reconnection_delay_max=10,
)


@sio.event
async def connect():
    print(f"[rpi] conectado a {SOCKET_URL}")


@sio.event
async def disconnect():
    print("[rpi] desconectado — tentando reconectar...")


@sio.on("rpi_erro")
async def on_erro(data):
    print("[rpi] servidor rejeitou payload:", data)


async def main():
    if not TOKEN:
        raise SystemExit("defina RPI_DEVICE_TOKEN (mesmo valor do backend)")

    await sio.connect(
        SOCKET_URL,
        auth={"role": "rpi", "token": TOKEN},
        transports=["websocket"],
    )

    try:
        while True:
            # Substituir por leitura de sensor real no RPi.
            leitura = round(10 + random.uniform(-0.5, 0.5), 3)
            payload = {"chart": "xr", "valor": leitura, "unidade": "mm"}
            ack = await sio.call("rpi_data", payload, timeout=5)
            print(f"[rpi] enviado {payload} -> ack {ack}")
            await asyncio.sleep(INTERVALO)
    finally:
        await sio.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[rpi] encerrado")
