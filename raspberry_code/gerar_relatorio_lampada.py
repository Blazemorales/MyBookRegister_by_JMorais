#!/usr/bin/env python3
"""
============================================================================
 gerar_relatorio_lampada.py — Fecha o relatório diário de uso da lâmpada
============================================================================
 Roda 1x/dia (systemd timer: lampada-relatorio.timer, 23:59 BRT) e
 consolida os eventos que lampada_stats.py registrou em
 dados_lampada/eventos.jsonl, gerando dados_lampada/relatorio_<data>.json.

 Se a lâmpada estiver acesa no momento em que o job roda, a sessão em
 aberto entra no total como parcial (até o instante da execução) — assim
 o relatório do dia não perde o pedaço final de uso.
============================================================================
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Sao_Paulo")
DADOS_DIR = Path(__file__).parent / "dados_lampada"
ARQUIVO_ESTADO = DADOS_DIR / "estado.json"
ARQUIVO_EVENTOS = DADOS_DIR / "eventos.jsonl"


def calcular_totais_do_dia(dia: date) -> dict:
    segundos = 0.0
    ciclos = 0

    if ARQUIVO_EVENTOS.exists():
        for linha in ARQUIVO_EVENTOS.read_text().splitlines():
            if not linha.strip():
                continue
            evento = json.loads(linha)
            fim = datetime.fromisoformat(evento["fim"])
            if fim.date() == dia:
                segundos += evento["duracao_s"]
                ciclos += 1

    if ARQUIVO_ESTADO.exists():
        estado = json.loads(ARQUIVO_ESTADO.read_text())
        inicio_aberto = estado.get("ligada_desde")
        if inicio_aberto:
            inicio = datetime.fromisoformat(inicio_aberto)
            if inicio.date() == dia:
                segundos += (datetime.now(TZ) - inicio).total_seconds()

    return {
        "data": dia.isoformat(),
        "segundos_ligada": round(segundos, 1),
        "horas_ligada": round(segundos / 3600, 2),
        "ciclos_liga_desliga": ciclos,
    }


def gerar_relatorio(dia: date | None = None) -> Path:
    dia = dia or datetime.now(TZ).date()
    totais = calcular_totais_do_dia(dia)
    destino = DADOS_DIR / f"relatorio_{dia.isoformat()}.json"
    destino.write_text(json.dumps(totais, indent=2, ensure_ascii=False))
    return destino


if __name__ == "__main__":
    dia_alvo = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else None
    caminho = gerar_relatorio(dia_alvo)
    print(f"[relatorio] salvo em {caminho}")
