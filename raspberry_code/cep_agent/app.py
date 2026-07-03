"""FastAPI do agente CEP na Raspberry Pi.

Sobe com: uvicorn app:app --host 0.0.0.0 --port $AGENT_PORT
(gerenciado pelo systemd: cep-agent.service)

Endpoints:
  GET  /health               — liveness probe
  POST /run/diario           — disparo manual do job diário
  POST /run/mensal           — disparo manual do job mensal
  GET  /reports/diario/latest  — último relatório diário em cache local
  GET  /reports/mensal/latest  — último relatório mensal em cache local
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from config import AGENT_PORT, SCHEDULER_ENABLED
from scheduler import criar_scheduler

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))

_scheduler = criar_scheduler()
_ingest_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _ingest_task

    # Inicia o scheduler de cron (03:00 e dia 1) — pulado se outro
    # agendador (ex.: Render Cron Job) já dispara os jobs, pra não gerar
    # o mesmo relatório duas vezes.
    if SCHEDULER_ENABLED:
        _scheduler.start()
        logger.info("[app] APScheduler iniciado")
    else:
        logger.info("[app] APScheduler desativado (SCHEDULER_ENABLED=false)")

    # Inicia a ponte MQTT → Socket.IO em background
    from ingest import run as run_ingest
    _ingest_task = asyncio.create_task(run_ingest(), name="cep_ingest")
    logger.info("[app] ponte de ingestão MQTT→Socket.IO iniciada")

    try:
        yield
    finally:
        if SCHEDULER_ENABLED:
            _scheduler.shutdown(wait=False)
        if _ingest_task and not _ingest_task.done():
            _ingest_task.cancel()


app = FastAPI(title="CEP Agent — Raspberry Pi", lifespan=lifespan)


@app.get("/health")
def health():
    if not SCHEDULER_ENABLED:
        return {"ok": True, "scheduler_enabled": False, "scheduled_jobs": []}
    jobs = [{"id": j.id, "next_run": str(j.next_run_time)} for j in _scheduler.get_jobs()]
    return {"ok": True, "scheduler_enabled": True, "scheduled_jobs": jobs}


@app.post("/run/diario")
async def run_diario(data: str | None = Query(None, description="YYYY-MM-DD; padrão: ontem")):
    """Dispara o job diário manualmente."""
    from jobs.diario import run_diario as _run
    ok = await _run(data_brt=data)
    if not ok:
        raise HTTPException(status_code=500, detail="Job diário falhou — veja o log")
    return {"ok": True, "data": data}


@app.post("/run/mensal")
async def run_mensal(mes: str | None = Query(None, description="YYYY-MM; padrão: mês anterior")):
    """Dispara o job mensal manualmente."""
    from jobs.mensal import run_mensal as _run
    ok = await _run(mes_brt=mes)
    if not ok:
        raise HTTPException(status_code=500, detail="Job mensal falhou — veja o log")
    return {"ok": True, "mes": mes}


@app.get("/reports/diario/latest")
def diario_latest():
    """Último relatório diário salvo no SQLite local."""
    import sqlite3, json as _json
    from pathlib import Path
    db = Path(__file__).parent / "relatorios_locais.db"
    if not db.exists():
        raise HTTPException(status_code=404, detail="Nenhum relatório diário disponível ainda")
    con = sqlite3.connect(db)
    row = con.execute(
        "SELECT periodo, dados, gerado_em FROM relatorios_diarios ORDER BY gerado_em DESC LIMIT 1"
    ).fetchone()
    con.close()
    if not row:
        raise HTTPException(status_code=404, detail="Nenhum relatório diário disponível ainda")
    return JSONResponse({"periodo": row[0], "dados": _json.loads(row[1]), "gerado_em": row[2]})


@app.get("/reports/mensal/latest")
def mensal_latest():
    """Placeholder — o mensal não é armazenado localmente (vai direto ao backend)."""
    raise HTTPException(status_code=501, detail="Relatório mensal consultado pelo backend /relatorios/mensal/latest")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=AGENT_PORT)
