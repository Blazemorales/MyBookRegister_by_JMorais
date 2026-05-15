import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse


router = APIRouter(tags=["cep"])

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_RELATORIOS = os.path.join(BASE_DIR, "CEP", "relatorios")
PASTA_RESULTADOS = os.path.join(BASE_DIR, "CEP", "amostras", "resultados")

CARTAS_VALIDAS = {"xr", "p", "u", "imr"}


@router.get("/")
def home() -> dict:
    return {
        "status": "online",
        "projeto": "CPE - Controle Estatístico de Processo",
        "endpoints": {
            "auth": ["/register", "/login", "/me"],
            "processar": "/processar",
            "relatorio_xr": "/relatorio/xr",
            "relatorio_p": "/relatorio/p",
            "relatorio_u": "/relatorio/u",
            "relatorio_imr": "/relatorio/imr",
            "validar_processo": "/validarprocesso",
            "resultados_cep": "/results/cep/{chart}",
        },
    }


@router.get("/processar")
def processar() -> JSONResponse:
    try:
        from CEP.cartas_controle.main import Main

        if Main.executar_completo():
            return JSONResponse(
                {"status": "sucesso", "message": "Dados processados e relatórios gerados"}
            )
        return JSONResponse(
            {"status": "erro", "message": "Falha ao processar dados"}, status_code=500
        )
    except Exception as exc:
        return JSONResponse({"status": "erro", "message": str(exc)}, status_code=500)


def _serve_pdf(nome_pdf: str):
    caminho = os.path.join(PASTA_RELATORIOS, nome_pdf)
    if not os.path.exists(caminho):
        raise HTTPException(status_code=404, detail=f"PDF {nome_pdf} não encontrado")
    return FileResponse(caminho, media_type="application/pdf", filename=nome_pdf)


@router.get("/relatorio/xr")
def relatorio_xr():
    try:
        from CEP.cartas_controle.main import Main

        Main.x()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return _serve_pdf("relatorio_XR.pdf")


@router.get("/relatorio/p")
def relatorio_p():
    try:
        from CEP.cartas_controle.main import Main

        Main.processar_dados()
        Main.p()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return _serve_pdf("relatorio_P.pdf")


@router.get("/relatorio/u")
def relatorio_u():
    try:
        from CEP.cartas_controle.main import Main

        Main.processar_dados()
        Main.u()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return _serve_pdf("relatorio_U.pdf")


@router.get("/relatorio/imr")
def relatorio_imr():
    return _serve_pdf("relatorio_IMR.pdf")


@router.get("/results/cep/{chart}")
def resultado_cep(chart: str):
    nome = chart.lower().strip()
    if nome not in CARTAS_VALIDAS:
        return JSONResponse(
            {"error": f"Carta '{chart}' inválida.", "validas": sorted(CARTAS_VALIDAS)},
            status_code=400,
        )

    caminho = os.path.join(PASTA_RESULTADOS, f"{nome}.json")
    if not os.path.exists(caminho):
        return JSONResponse(
            {"error": f"Resultado para '{nome}' não encontrado. Execute /processar primeiro."},
            status_code=404,
        )
    return FileResponse(caminho, media_type="application/json")


@router.get("/validarprocesso")
def validar_processo() -> JSONResponse:
    try:
        from CEP.cartas_controle.main import Main

        if Main.validar_processo():
            return JSONResponse(
                {"status": "sucesso", "message": "Processo de geração de relatórios validado com sucesso"}
            )
        return JSONResponse(
            {"status": "erro", "message": "Falha na validação do processo de geração de relatórios"},
            status_code=500,
        )
    except Exception as exc:
        return JSONResponse({"status": "erro", "message": str(exc)}, status_code=500)
