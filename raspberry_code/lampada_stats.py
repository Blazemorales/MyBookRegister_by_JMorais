#!/usr/bin/env python3
"""
============================================================================
 lampada_stats.py — Receptor de eventos da lâmpada, rodando na Raspberry Pi
============================================================================
 Papel: receber o POST que a ESP32 (variante web, RASPBERRY_URL no .ino)
 manda a cada troca de estado, e registrar quanto tempo a lâmpada ficou
 acesa. gerar_relatorio_lampada.py depois fecha o JSON do dia com esses
 dados.

 - POST /lampada       {"aceso": bool, "ligadoHa": int}  — evento da ESP32
 - GET  /lampada/hoje                                     — total acumulado hoje

 A duração de cada sessão é calculada pelo relógio da própria Pi, não pelo
 `ligadoHa` da ESP32 (que zera a cada boot da placa e vem sempre 0 no
 evento de desligar, já que o estado interno já virou "apagada" antes do
 POST ser montado).

 Dependências:  pip install flask gunicorn
============================================================================
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, request

TZ = ZoneInfo("America/Sao_Paulo")
DADOS_DIR = Path(__file__).parent / "dados_lampada"
DADOS_DIR.mkdir(exist_ok=True)
ARQUIVO_ESTADO = DADOS_DIR / "estado.json"
ARQUIVO_EVENTOS = DADOS_DIR / "eventos.jsonl"

app = Flask(__name__)


def _agora() -> datetime:
    return datetime.now(TZ)


def _ler_estado() -> dict:
    if ARQUIVO_ESTADO.exists():
        return json.loads(ARQUIVO_ESTADO.read_text())
    return {"ligada_desde": None}


def _salvar_estado(estado: dict) -> None:
    ARQUIVO_ESTADO.write_text(json.dumps(estado))


def _registrar_sessao(inicio: datetime, fim: datetime) -> None:
    evento = {
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "duracao_s": round((fim - inicio).total_seconds(), 1),
    }
    with ARQUIVO_EVENTOS.open("a") as f:
        f.write(json.dumps(evento) + "\n")


@app.post("/lampada")
def receber_evento():
    corpo = request.get_json(silent=True) or {}
    aceso = bool(corpo.get("aceso"))
    agora = _agora()
    estado = _ler_estado()

    if aceso and not estado["ligada_desde"]:
        estado["ligada_desde"] = agora.isoformat()
        _salvar_estado(estado)
    elif not aceso and estado["ligada_desde"]:
        inicio = datetime.fromisoformat(estado["ligada_desde"])
        _registrar_sessao(inicio, agora)
        estado["ligada_desde"] = None
        _salvar_estado(estado)

    return jsonify(ok=True)


@app.get("/lampada/hoje")
def hoje():
    from gerar_relatorio_lampada import calcular_totais_do_dia
    return jsonify(calcular_totais_do_dia(_agora().date()))


if __name__ == "__main__":
    # modo de teste; em produção use o gunicorn (ver README)
    app.run(host="0.0.0.0", port=5000)
