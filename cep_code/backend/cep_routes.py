"""Rotas CEP autenticadas, com persistência em Postgres."""
from __future__ import annotations

import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from auth import get_current_user
from cep_pipeline import (
    gerar_pdf_para,
    normalizar_payload_upload,
    processar_para_usuario,
)


logger = logging.getLogger(__name__)
router = APIRouter(tags=["cep"])

CARTAS_VALIDAS = {"xr", "p", "u", "imr"}

_db_manager = None


def set_db_manager(mgr) -> None:
    global _db_manager
    _db_manager = mgr


def get_db():
    if _db_manager is None:
        raise RuntimeError("DB manager not initialized")
    return _db_manager


@router.get("/")
def home() -> dict:
    return {
        "status": "online",
        "projeto": "CPE - Controle Estatístico de Processo",
        "endpoints": {
            "auth": ["/register", "/login", "/me"],
            "upload": "/upload (POST, multipart file)",
            "processar": "/processar",
            "relatorio": "/relatorio/{xr|p|u|imr}",
            "resultados": "/results/cep/{xr|p|u|imr}",
        },
    }


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="arquivo vazio")
    try:
        datasets = normalizar_payload_upload(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"JSON inválido: {e}")

    if not datasets:
        raise HTTPException(status_code=400, detail="nenhum dataset no arquivo")

    db = get_db()
    ids: list[int] = []
    for ds in datasets:
        chart = (ds.get("chart") or ds.get("Chart") or "").upper()
        if chart not in {"XR", "P", "U", "IMR"}:
            raise HTTPException(
                status_code=400,
                detail=f"chart inválido em dataset: {chart!r}",
            )
        amostra_id = await db.salvar_amostra(user["user_id"], chart, ds)
        ids.append(amostra_id)

    return JSONResponse(
        {
            "status": "sucesso",
            "message": f"{len(ids)} dataset(s) salvos",
            "amostra_ids": ids,
        }
    )


@router.get("/processar")
async def processar(user: dict = Depends(get_current_user)) -> JSONResponse:
    db = get_db()
    amostras = await db.amostras_do_usuario(user["user_id"])
    if not amostras:
        raise HTTPException(
            status_code=404,
            detail="nenhuma amostra carregada — envie um JSON em /upload",
        )

    payloads = []
    for row in amostras:
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        payloads.append(payload)

    try:
        tratados = processar_para_usuario(payloads)
    except Exception as exc:
        logger.exception("falha ao processar amostras do usuário")
        raise HTTPException(status_code=500, detail=f"falha ao processar: {exc}")

    if not tratados:
        raise HTTPException(
            status_code=422,
            detail="pipeline não produziu nenhum resultado",
        )

    salvos = []
    for chart, entry in tratados.items():
        # entry é {dados: ..., respostas: ...} — persistimos o objeto completo
        dados_completos = {
            "dados": entry.get("dados", entry),
            "respostas": entry.get("respostas"),
            "respostas_q2": entry.get("respostas_q2"),
        }
        await db.salvar_resultado(
            user_id=user["user_id"],
            chart=chart,
            dados=dados_completos,
        )
        salvos.append(chart)

    return JSONResponse(
        {
            "status": "sucesso",
            "message": f"processado: {', '.join(salvos)}",
            "charts": salvos,
        }
    )


def _validar_chart(chart: str) -> str:
    nome = chart.lower().strip()
    if nome not in CARTAS_VALIDAS:
        raise HTTPException(
            status_code=400,
            detail=f"carta inválida (esperado: {sorted(CARTAS_VALIDAS)})",
        )
    return nome


@router.get("/results/cep/{chart}")
async def resultado_cep(
    chart: str,
    user: dict = Depends(get_current_user),
):
    nome = _validar_chart(chart)
    db = get_db()
    res = await db.ultimo_resultado(user["user_id"], nome.upper())
    if res is None:
        raise HTTPException(
            status_code=404,
            detail=f"resultado para '{nome}' não encontrado — execute /processar antes",
        )
    dados = res["dados"]
    if isinstance(dados, str):
        dados = json.loads(dados)
    # Compatibilidade retroativa: se o registro antigo não tem a estrutura nova,
    # devolve como está. Registros novos já têm {dados, respostas, respostas_q2}.
    return JSONResponse(dados)


@router.get("/relatorio/{chart}")
async def relatorio(
    chart: str,
    user: dict = Depends(get_current_user),
):
    nome = _validar_chart(chart)
    db = get_db()
    res = await db.ultimo_resultado(user["user_id"], nome.upper())
    if res is None:
        raise HTTPException(
            status_code=404,
            detail=f"resultado para '{nome}' não encontrado — execute /processar antes",
        )

    pdf: Optional[bytes] = res["pdf"]
    if pdf is None:
        raw = res["dados"]
        if isinstance(raw, str):
            raw = json.loads(raw)
        # Novos registros têm estrutura {dados: ..., respostas: ...}
        dados = raw.get("dados", raw) if isinstance(raw, dict) and "dados" in raw else raw
        try:
            pdf = gerar_pdf_para(nome.upper(), dados)
        except Exception as exc:
            logger.exception("falha ao gerar PDF on-demand")
            raise HTTPException(status_code=500, detail=str(exc))

        async with db.pool.acquire() as conn:
            await conn.execute(
                "UPDATE resultados SET pdf = $1 WHERE id = $2",
                pdf,
                res["id"],
            )

    return StreamingResponse(
        io.BytesIO(pdf),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="relatorio_{nome.upper()}.pdf"',
        },
    )
