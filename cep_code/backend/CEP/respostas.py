"""Answer set compartilhado — Q1 (variáveis) e Q2 (atributos).

Único ponto de cálculo das respostas do PDF. Usado por:
  - gerar_entrega.py  (entrega offline)
  - cep_pipeline.py   (caminho web / API)
  - jobs/diario.py    (consolidação da Raspberry Pi)

Cada função devolve um dict JSON-serializável com todos os itens pedidos
no enunciado. Nenhum item em branco.
"""
from __future__ import annotations

import importlib.util
import os

_AQUI = os.path.dirname(os.path.abspath(__file__))


def _carregar_analise():
    """Importa analise.py de forma robusta (pacote ou arquivo direto)."""
    try:
        from cep_code.backend.CEP import analise as _m
        return _m
    except ModuleNotFoundError:
        pass
    try:
        from CEP import analise as _m          # quando cwd é backend/
        return _m
    except ModuleNotFoundError:
        pass
    spec = importlib.util.spec_from_file_location(
        "cep_analise", os.path.join(_AQUI, "analise.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _carregar_cartas():
    """Importa Cartas.py de forma robusta."""
    try:
        from cep_code.backend.CEP.cartas_controle.Cartas import Cartas
        return Cartas
    except ModuleNotFoundError:
        pass
    try:
        from CEP.cartas_controle.Cartas import Cartas
        return Cartas
    except ModuleNotFoundError:
        pass
    spec = importlib.util.spec_from_file_location(
        "cep_cartas",
        os.path.join(_AQUI, "cartas_controle", "Cartas.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Cartas


def _carregar_params():
    try:
        from cep_code.backend.CEP import parametros_enunciado as p
        return p
    except ModuleNotFoundError:
        pass
    try:
        from CEP import parametros_enunciado as p
        return p
    except ModuleNotFoundError:
        pass
    spec = importlib.util.spec_from_file_location(
        "cep_params", os.path.join(_AQUI, "parametros_enunciado.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Questão 1 — cartas de variáveis (XR e IMR)
# ---------------------------------------------------------------------------

def respostas_variaveis(dados: dict, params=None) -> dict:
    """Calcula o answer set completo para uma carta de variáveis.

    Retorna dict com todas as chaves do PDF (a–g para Q1, deslocamento
    para Q2 quando aplicável). JSON-serializável.

    Args:
        dados: dados tratados pelo DataProcessor (processar_tipo_xr ou _imr).
        params: módulo parametros_enunciado (carregado automaticamente se None).
    """
    analise = _carregar_analise()
    if params is None:
        params = _carregar_params()

    chart = dados.get("chart", "XR").upper()
    if chart == "XR":
        mu     = float(dados["x_double_bar"])
        sigma  = float(dados["sigma_individual"])
        lic    = float(dados["lic_x"])
        lsc    = float(dados["lsc_x"])
        valores = [float(s["media"]) for s in dados.get("estatisticas_por_amostra", [])]
    else:  # IMR
        mu     = float(dados["media_ind"])
        sigma  = float(dados["sigma_individual"])
        lic    = float(dados["lic_ind"])
        lsc    = float(dados["lsc_ind"])
        valores = [float(v) for v in dados.get("valores_individuais", [])]

    # Especificações derivadas dos limites de controle
    cap_dict = analise.capacidade_por_limites(
        mu, sigma, lic, lsc,
        params.FATOR_LIE, params.FATOR_LSE,
    )
    lie = cap_dict["lie"]
    lse = cap_dict["lse"]

    # a) Curto prazo
    curto = analise.sob_controle_curto_prazo(valores, lic, lsc)

    # b) Longo prazo (ppm vs 890)
    longo = analise.atende_longo_prazo(mu, sigma, lse, lie, params.PPM_REQUERIDO)

    # c) Valor de X para 96% de sucesso (retorna o VALOR, não uma probabilidade)
    x_percentil = float(analise.quantil_para_rendimento(
        mu, sigma, params.MARGEM_ALVO, lado="superior"
    ))
    x_intervalo = analise.quantil_para_rendimento(
        mu, sigma, params.MARGEM_ALVO, lado="central"
    )

    # d) Capacidade Cp / Cpk com LIE=0.98*LIC / LSE=1.1*LSC
    # (já calculado em cap_dict)

    # e) Margem de sucesso atual — P(LIE ≤ x ≤ LSE)
    margem_atual = float(analise.rendimento(mu, sigma, lse, lie))

    # f) Margem com deslocamento de +1.5σ
    margem_desloc = float(
        analise.rendimento_com_deslocamento(mu, sigma, lse, lie, params.DESLOCAMENTO_SIGMA)
    )

    # g) Binomial P(X=85 em 100 | p=margem_atual)
    binom = analise.prob_binomial(params.BINOM_K, params.BINOM_N, margem_atual)

    return {
        "chart": chart,
        # parâmetros do processo
        "mu": mu,
        "sigma": sigma,
        "lic": lic,
        "lsc": lsc,
        "lie": lie,
        "lse": lse,
        "fator_lie": params.FATOR_LIE,
        "fator_lse": params.FATOR_LSE,
        # a) curto prazo
        "curto_prazo": {
            "sob_controle": curto["sob_controle"],
            "pontos_fora": curto["pontos_fora"],
        },
        # b) longo prazo
        "longo_prazo": {
            "ppm_obtido": float(longo["ppm_obtido"]),
            "ppm_requerido": float(params.PPM_REQUERIDO),
            "atende": bool(longo["atende"]),
        },
        # c) valor de X para 96% de sucesso
        "x_para_margem_alvo": {
            "margem_alvo": params.MARGEM_ALVO,
            "x_percentil": x_percentil,
            "x_intervalo_inferior": float(x_intervalo[0]),
            "x_intervalo_superior": float(x_intervalo[1]),
        },
        # d) capacidade
        "capacidade": {
            "cp": float(cap_dict["cp"]) if cap_dict["cp"] is not None else None,
            "cpk": float(cap_dict["cpk"]) if cap_dict["cpk"] is not None else None,
        },
        # e) margem atual
        "margem_atual": margem_atual,
        # f) margem com deslocamento
        "margem_com_deslocamento": {
            "deslocamento_sigmas": params.DESLOCAMENTO_SIGMA,
            "margem": margem_desloc,
        },
        # g) binomial
        "binomial": {
            "k": params.BINOM_K,
            "n": params.BINOM_N,
            "p_usada": margem_atual,
            "exata": float(binom["exata"]),
            "ao_menos": float(binom["ao_menos"]),
            "ate": float(binom["ate"]),
        },
    }


# ---------------------------------------------------------------------------
# Questão 2 — cartas de atributos (P e U)
# ---------------------------------------------------------------------------

def respostas_atributos(dados_p: dict | None, dados_u: dict | None) -> dict:
    """Calcula o answer set de Q2 (controle + deslocamento Kalman).

    Args:
        dados_p: resultado de DataProcessor.processar_tipo_p, ou None.
        dados_u: resultado de DataProcessor.processar_tipo_u, ou None.
    """
    analise = _carregar_analise()
    Cartas  = _carregar_cartas()

    resultado: dict = {"chart": "atributos"}

    if dados_p:
        proporcoes = [float(p) for p in dados_p.get("proporcoes", [])]
        p_bar  = float(dados_p["P_bar"])
        lic_p  = float(dados_p["lic_P"])
        lsc_p  = float(dados_p["lsc_P"])

        curto_p = analise.sob_controle_curto_prazo(proporcoes, lic_p, lsc_p)
        kal_p   = Cartas.kalman_filter(proporcoes, p_bar)
        desloc_p = Cartas.aviso_deslocamento_kalman(kal_p, p_bar, "Carta P") or "Sem deslocamento significativo (Kalman)."

        resultado["carta_p"] = {
            "P_bar": p_bar,
            "lic_P": lic_p,
            "lsc_P": lsc_p,
            "curto_prazo": {
                "sob_controle": curto_p["sob_controle"],
                "pontos_fora": curto_p["pontos_fora"],
            },
            "deslocamento_kalman": desloc_p,
        }

    if dados_u:
        u_valores = [float(u) for u in dados_u.get("u_valores", [])]
        u_bar  = float(dados_u["U_bar"])
        lic_u  = float(dados_u["lic_u"])
        lsc_u  = float(dados_u["lsc_u"])

        curto_u = analise.sob_controle_curto_prazo(u_valores, lic_u, lsc_u)
        kal_u   = Cartas.kalman_filter(u_valores, u_bar)
        desloc_u = Cartas.aviso_deslocamento_kalman(kal_u, u_bar, "Carta U") or "Sem deslocamento significativo (Kalman)."

        resultado["carta_u"] = {
            "U_bar": u_bar,
            "lic_u": lic_u,
            "lsc_u": lsc_u,
            "curto_prazo": {
                "sob_controle": curto_u["sob_controle"],
                "pontos_fora": curto_u["pontos_fora"],
            },
            "deslocamento_kalman": desloc_u,
        }

    return resultado


# ---------------------------------------------------------------------------
# Conveniência: calcular tudo a partir dos dados_tratados
# ---------------------------------------------------------------------------

def calcular_answer_set(dados_tratados: list[dict], params=None) -> dict:
    """Recebe a lista de dados_tratados (output do DataProcessor) e devolve
    o answer set completo {chart: respostas} para todas as cartas.

    Retorno:
      {
        "XR":  <respostas_variaveis>,  # se presente
        "IMR": <respostas_variaveis>,  # se presente
        "atributos": <respostas_atributos>,  # sempre, mesmo que vazio
      }
    """
    por_chart = {d.get("chart", "").upper(): d for d in dados_tratados if d}
    resultado: dict = {}

    for chart in ("XR", "IMR"):
        if chart in por_chart:
            resultado[chart] = respostas_variaveis(por_chart[chart], params)

    dados_p = por_chart.get("P")
    dados_u = por_chart.get("U")
    if dados_p or dados_u:
        resultado["atributos"] = respostas_atributos(dados_p, dados_u)

    return resultado
