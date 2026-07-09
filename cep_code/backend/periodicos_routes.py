"""Rotas para stream por período e relatórios periódicos (diário/mensal).

Autenticação:
  - Usuários humanos: JWT normal (Bearer do /login).
  - Dispositivo RPi: JWT de serviço gerado por POST /device/token
    usando o RPI_DEVICE_TOKEN compartilhado.

Endpoints expostos:
  POST /device/token                — RPi troca RPI_DEVICE_TOKEN por JWT curto
  GET  /stream/diario               — pontos de medicoes_stream de um dia (BRT)
  GET  /stream/periodo              — pontos de medicoes_stream num intervalo
  POST /relatorios/{tipo}           — RPi publica resultado pronto
  GET  /relatorios/{tipo}/latest    — frontend lê o mais recente
  GET  /relatorios/{tipo}/{periodo} — frontend lê período específico
  GET  /relatorios/{tipo}/list      — frontend lista histórico
"""
from __future__ import annotations

import io
import json
import logging
import os
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from auth import create_access_token, decode_token, get_current_user, oauth2_scheme

logger = logging.getLogger(__name__)

router = APIRouter(tags=["periodicos"])

RPI_DEVICE_TOKEN = os.environ.get("RPI_DEVICE_TOKEN", "")

_db_manager = None


def set_db_manager(mgr) -> None:
    global _db_manager
    _db_manager = mgr


def get_db():
    if _db_manager is None:
        raise RuntimeError("DB manager not initialized")
    return _db_manager


# ---------------------------------------------------------------------------
# Auth de dispositivo
# ---------------------------------------------------------------------------

class DeviceTokenIn(BaseModel):
    token: str


@router.post("/device/token")
async def device_token(payload: DeviceTokenIn) -> dict:
    """Troca o RPI_DEVICE_TOKEN por um JWT curto (role=rpi, 24 h)."""
    if not RPI_DEVICE_TOKEN:
        raise HTTPException(status_code=503, detail="device auth não configurado no servidor")
    if payload.token != RPI_DEVICE_TOKEN:
        raise HTTPException(status_code=401, detail="token de dispositivo inválido")
    jwt = create_access_token(
        {"sub": "rpi_device", "role": "rpi"},
        expires_delta=timedelta(hours=24),
    )
    return {"access_token": jwt, "token_type": "bearer"}


async def _get_rpi_or_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Aceita tanto o JWT de usuário quanto o JWT de serviço (role=rpi).

    O JWT de serviço (sub="rpi_device") não corresponde a nenhum usuário
    real no banco, então não pode passar pela checagem de user_id do
    get_current_user — só o JWT de usuário humano passa por ela.
    """
    payload = decode_token(token)
    if payload.get("role") == "rpi":
        return {"username": payload.get("sub", "rpi_device"), "user_id": None, "role": "rpi"}
    return await get_current_user(token)


# ---------------------------------------------------------------------------
# Stream por período
# ---------------------------------------------------------------------------

@router.get("/stream/diario")
async def stream_diario(
    data: str = Query(..., description="Data em BRT, formato YYYY-MM-DD"),
    canal: str = Query("default"),
    user: dict = Depends(_get_rpi_or_user),
) -> JSONResponse:
    """Retorna todos os pontos de medicoes_stream de um dia (horário BRT)."""
    db = get_db()
    try:
        pontos = await db.medicoes_do_dia(data, canal)
    except Exception as exc:
        logger.exception("falha ao buscar stream diário")
        raise HTTPException(status_code=500, detail=str(exc))
    return JSONResponse({"data": data, "canal": canal, "total": len(pontos), "pontos": pontos})


@router.get("/stream/periodo")
async def stream_periodo(
    inicio: str = Query(..., description="Início BRT YYYY-MM-DD"),
    fim: str = Query(..., description="Fim BRT YYYY-MM-DD (inclusivo)"),
    canal: str = Query("default"),
    user: dict = Depends(_get_rpi_or_user),
) -> JSONResponse:
    """Retorna pontos de medicoes_stream num intervalo de datas (BRT)."""
    db = get_db()
    try:
        pontos = await db.medicoes_do_periodo(inicio, fim, canal)
    except Exception as exc:
        logger.exception("falha ao buscar stream do período")
        raise HTTPException(status_code=500, detail=str(exc))
    return JSONResponse({"inicio": inicio, "fim": fim, "canal": canal,
                         "total": len(pontos), "pontos": pontos})


# ---------------------------------------------------------------------------
# Relatórios periódicos
# ---------------------------------------------------------------------------

TIPOS_VALIDOS = {"diario", "mensal"}


def _validar_tipo(tipo: str) -> str:
    t = tipo.lower().strip()
    if t not in TIPOS_VALIDOS:
        raise HTTPException(status_code=400, detail=f"tipo inválido (esperado: {sorted(TIPOS_VALIDOS)})")
    return t


class RelatorioIn(BaseModel):
    periodo: str
    canal: str = "default"
    dados: dict
    charts: Optional[dict] = None


@router.post("/relatorios/{tipo}")
async def publicar_relatorio(
    tipo: str,
    payload: RelatorioIn,
    pdf_file: Optional[UploadFile] = File(None),
    user: dict = Depends(_get_rpi_or_user),
) -> JSONResponse:
    """RPi publica o resultado de um período.

    O PDF pode ser enviado via multipart como campo `pdf_file`, ou omitido.
    """
    t = _validar_tipo(tipo)
    pdf_bytes: Optional[bytes] = None
    if pdf_file is not None:
        pdf_bytes = await pdf_file.read() or None

    db = get_db()
    try:
        rid = await db.salvar_relatorio_periodico(
            tipo=t,
            periodo=payload.periodo,
            dados=payload.dados,
            canal=payload.canal,
            charts=payload.charts,
            pdf=pdf_bytes,
        )
    except Exception as exc:
        logger.exception("falha ao salvar relatório periódico")
        raise HTTPException(status_code=500, detail=str(exc))

    return JSONResponse({"ok": True, "id": rid, "tipo": t, "periodo": payload.periodo})


def _serializar_relatorio(row: dict) -> dict:
    out = {
        "id": row["id"],
        "tipo": row["tipo"],
        "periodo": row["periodo"],
        "canal": row["canal"],
        "gerado_em": row["gerado_em"].isoformat() if hasattr(row.get("gerado_em"), "isoformat") else str(row.get("gerado_em")),
    }
    if "dados" in row:
        d = row["dados"]
        out["dados"] = json.loads(d) if isinstance(d, str) else d
    if "charts" in row and row["charts"] is not None:
        c = row["charts"]
        out["charts"] = json.loads(c) if isinstance(c, str) else c
    # pdf não é serializado no JSON — use o endpoint de download
    return out


@router.get("/relatorios/{tipo}/list")
async def listar_relatorios(
    tipo: str,
    canal: str = Query("default"),
    limite: int = Query(30, ge=1, le=100),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    t = _validar_tipo(tipo)
    db = get_db()
    rows = await db.listar_relatorios_periodicos(t, canal, limite)
    return JSONResponse([_serializar_relatorio(r) for r in rows])


@router.get("/relatorios/{tipo}/latest")
async def relatorio_latest(
    tipo: str,
    canal: str = Query("default"),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    t = _validar_tipo(tipo)
    db = get_db()
    row = await db.ultimo_relatorio_periodico(t, canal)
    if row is None:
        raise HTTPException(status_code=404, detail=f"nenhum relatório {t} encontrado")
    return JSONResponse(_serializar_relatorio(row))


@router.get("/relatorios/{tipo}/{periodo}")
async def relatorio_por_periodo(
    tipo: str,
    periodo: str,
    canal: str = Query("default"),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    t = _validar_tipo(tipo)
    db = get_db()
    row = await db.relatorio_periodico_por_periodo(t, periodo, canal)
    if row is None:
        raise HTTPException(status_code=404, detail=f"relatório {t}/{periodo} não encontrado")
    return JSONResponse(_serializar_relatorio(row))


@router.get("/relatorios/{tipo}/{periodo}/pdf")
async def relatorio_pdf(
    tipo: str,
    periodo: str,
    canal: str = Query("default"),
    user: dict = Depends(get_current_user),
) -> StreamingResponse:
    t = _validar_tipo(tipo)
    db = get_db()
    row = await db.relatorio_periodico_por_periodo(t, periodo, canal)
    if row is None:
        raise HTTPException(status_code=404, detail=f"relatório {t}/{periodo} não encontrado")
    pdf: Optional[bytes] = row.get("pdf")
    if not pdf:
        raise HTTPException(status_code=404, detail="PDF não disponível para este relatório")
    nome = f"relatorio_{t}_{periodo.replace('-', '')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{nome}"'},
    )
