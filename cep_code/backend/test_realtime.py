"""Teste end-to-end do Socket.IO: RPi -> servidor -> frontend.

Sobe o servidor ASGI num processo separado e roda dois clientes:

  • um simulando o Raspberry Pi (role="rpi"), que emite "rpi_data";
  • um simulando a aba "Receber relatório" (role="frontend"), que
    deve receber o evento "relatorio_data".

Uso:
    ./venv/bin/python test_realtime.py

Sai com código 0 se o dado fez o caminho todo; !=0 caso contrário.
Não precisa de banco real — o pool só conecta no lifespan, e mockamos
o suficiente para o servidor subir. Requer aiohttp (cliente Socket.IO).
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta, timezone

# Env mínimo para o servidor importar/subir sem banco real.
os.environ.setdefault("SECRET_KEY", "test-secret-para-e2e")
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/db")
os.environ.setdefault("RPI_DEVICE_TOKEN", "token-rpi-de-teste")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")

import jwt  # noqa: E402
import socketio  # noqa: E402
import uvicorn  # noqa: E402

HOST, PORT = "127.0.0.1", 8123
URL = f"http://{HOST}:{PORT}"


def gerar_jwt_frontend(username: str = "tester") -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    return jwt.encode(payload, os.environ["SECRET_KEY"], algorithm="HS256")


class ServerThread:
    """Roda o uvicorn num thread, sem lifespan (não toca no banco)."""

    def __init__(self):
        import code.backend.backend_api as backend_api

        # Desliga o lifespan p/ não exigir Postgres no teste.
        backend_api.app.router.lifespan_context = _noop_lifespan
        self.config = uvicorn.Config(
            backend_api.asgi, host=HOST, port=PORT, log_level="warning"
        )
        self.server = uvicorn.Server(self.config)

    def start(self):
        import threading

        self._t = threading.Thread(target=self.server.run, daemon=True)
        self._t.start()
        # espera ficar de pé
        for _ in range(100):
            if self.server.started:
                return
            time.sleep(0.1)
        raise RuntimeError("servidor não subiu a tempo")

    def stop(self):
        self.server.should_exit = True
        self._t.join(timeout=5)


from contextlib import asynccontextmanager  # noqa: E402


@asynccontextmanager
async def _noop_lifespan(app):
    yield


async def cenario() -> bool:
    recebidos: list[dict] = []
    frontend_pronto = asyncio.Event()

    frontend = socketio.AsyncClient(reconnection=True)
    rpi = socketio.AsyncClient(reconnection=True)

    @frontend.on("conectado")
    async def _conectado(data):
        print("  [frontend] conectado:", data)
        frontend_pronto.set()

    @frontend.on("relatorio_data")
    async def _relatorio(data):
        print("  [frontend] RECEBEU relatorio_data:", data)
        recebidos.append(data)

    # 1) frontend conecta com JWT válido
    await frontend.connect(
        URL,
        auth={"role": "frontend", "token": gerar_jwt_frontend()},
        transports=["websocket"],
    )
    await asyncio.wait_for(frontend_pronto.wait(), timeout=5)

    # 2) RPi conecta com o device token
    await rpi.connect(
        URL,
        auth={"role": "rpi", "token": os.environ["RPI_DEVICE_TOKEN"]},
        transports=["websocket"],
    )
    print("  [rpi] conectado")

    # 3) RPi emite um dado válido e espera o ack
    ack = await rpi.call(
        "rpi_data",
        {"chart": "xr", "valores": [10.1, 9.8, 10.0], "unidade": "mm"},
        timeout=5,
    )
    print("  [rpi] ack do servidor:", ack)
    assert ack.get("ok") is True, f"ack negativo: {ack}"

    # 4) RPi emite um dado INVÁLIDO -> não deve chegar no frontend
    ack_ruim = await rpi.call("rpi_data", {"foo": "bar"}, timeout=5)
    print("  [rpi] ack (payload inválido):", ack_ruim)
    assert ack_ruim.get("ok") is False, "payload inválido deveria ser rejeitado"

    # dá um tempinho pro broadcast chegar
    await asyncio.sleep(0.5)

    await rpi.disconnect()
    await frontend.disconnect()

    # 5) Frontend deve ter recebido exatamente 1 evento (o válido)
    ok = len(recebidos) == 1 and recebidos[0].get("chart") == "xr"
    print(f"  -> eventos recebidos pelo frontend: {len(recebidos)} (esperado 1)")
    return ok


def main() -> int:
    print("Subindo servidor...")
    srv = ServerThread()
    srv.start()
    print(f"Servidor no ar em {URL}")
    try:
        ok = asyncio.run(cenario())
    finally:
        srv.stop()

    if ok:
        print("\n✅ PASSOU: dado do RPi chegou na aba 'Receber relatório'.")
        return 0
    print("\n❌ FALHOU: dado não fez o caminho esperado.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
