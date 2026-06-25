"""APScheduler com cron BRT — diário 03:00, mensal dia 1 às 03:05.

Iniciado no lifespan do FastAPI (app.py). Um único processo,
sem estado compartilhado entre jobs.
"""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_BRT = ZoneInfo("America/Sao_Paulo")


def criar_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=_BRT)

    scheduler.add_job(
        _job_diario,
        CronTrigger(hour=3, minute=0, timezone=_BRT),
        id="cep_diario",
        name="Relatório CEP Diário (03:00 BRT)",
        replace_existing=True,
        misfire_grace_time=3600,  # tolera até 1h de atraso (Pi ficou desligada)
    )

    scheduler.add_job(
        _job_mensal,
        CronTrigger(day=1, hour=3, minute=5, timezone=_BRT),
        id="cep_mensal",
        name="Relatório CEP Mensal (dia 1, 03:05 BRT)",
        replace_existing=True,
        misfire_grace_time=7200,
    )

    return scheduler


async def _job_diario() -> None:
    from jobs.diario import run_diario
    try:
        ok = await run_diario()
        if not ok:
            logger.error("[scheduler] job diário falhou")
    except Exception:
        logger.exception("[scheduler] exceção no job diário")


async def _job_mensal() -> None:
    from jobs.mensal import run_mensal
    try:
        ok = await run_mensal()
        if not ok:
            logger.error("[scheduler] job mensal falhou")
    except Exception:
        logger.exception("[scheduler] exceção no job mensal")
