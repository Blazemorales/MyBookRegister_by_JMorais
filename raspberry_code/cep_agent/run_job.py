"""Executa um job do cep_agent uma única vez e sai.

Usado pelo Render Cron Job (free tier) como alternativa ao scheduler
interno (scheduler.py), que exige um processo sempre ativo — algo que o
plano Free do Render não oferece (o web service dorme após ~15 min sem
tráfego). O ingest.py (ponte MQTT→Socket.IO) continua rodando na
Raspberry Pi via cep-agent.service; só o disparo dos relatórios
diário/mensal muda para o agendador nativo do Render.

Uso:
    python run_job.py diario [--data YYYY-MM-DD]
    python run_job.py mensal [--mes YYYY-MM]
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("job", choices=["diario", "mensal"])
    parser.add_argument("--data", default=None, help="YYYY-MM-DD (diário); padrão: ontem")
    parser.add_argument("--mes", default=None, help="YYYY-MM (mensal); padrão: mês anterior")
    args = parser.parse_args()

    if args.job == "diario":
        from jobs.diario import run_diario
        ok = asyncio.run(run_diario(data_brt=args.data))
    else:
        from jobs.mensal import run_mensal
        ok = asyncio.run(run_mensal(mes_brt=args.mes))

    if not ok:
        logger.error("[run_job] job %s falhou", args.job)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
