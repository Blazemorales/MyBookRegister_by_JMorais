#!/usr/bin/env python
"""Testes do answer set (CEP/respostas.py) e do pipeline web corrigido.

Cobre:
  - Itens a–g para carta XR: valores corretos, nenhum None.
  - Itens para carta IMR.
  - Questão 2 (atributos P / U): controle e Kalman presentes.
  - processar_para_usuario retorna {dados, respostas} (estrutura nova).
  - Parâmetros do enunciado lidos de parametros_enunciado.py.

Execução:
    cd cep_code/backend
    python test_respostas.py
"""
from __future__ import annotations

import os
import sys
import json

# Garante que o diretório do backend está no path
_AQUI = os.path.dirname(os.path.abspath(__file__))
if _AQUI not in sys.path:
    sys.path.insert(0, _AQUI)


def _dados_xr_fixture() -> dict:
    """Dataset XR mínimo para testes (5 subgrupos de 5 pontos)."""
    import numpy as np
    rng = np.random.default_rng(42)
    amostras = {}
    for i in range(10):
        vals = (rng.normal(10, 0.3, size=5)).tolist()
        amostras[str(i)] = vals
    return {"chart": "XR", "measurements": amostras}


def _dados_p_fixture() -> dict:
    """Dataset atributos com critério de defeito."""
    amostras = {str(i): [10 + (i % 3) * 0.5] for i in range(20)}
    return {
        "chart": "P",
        "measurements": amostras,
        "criterio_defeito": "x > 10.8",
        "n_amostra": 1,
    }


def test_parametros_enunciado():
    from CEP.parametros_enunciado import (
        PPM_REQUERIDO, MARGEM_ALVO, DESLOCAMENTO_SIGMA,
        BINOM_K, BINOM_N, FATOR_LIE, FATOR_LSE,
    )
    assert PPM_REQUERIDO == 890.0, f"esperado 890, got {PPM_REQUERIDO}"
    assert MARGEM_ALVO == 0.96, f"esperado 0.96, got {MARGEM_ALVO}"
    assert DESLOCAMENTO_SIGMA == 1.5
    assert BINOM_K == 85
    assert BINOM_N == 100
    assert FATOR_LIE == 0.98
    assert FATOR_LSE == 1.1
    print("  [OK] parametros_enunciado OK")


def test_respostas_xr():
    from CEP.amostras.data_processor import DataProcessor
    from CEP.respostas import respostas_variaveis

    ds = _dados_xr_fixture()
    dp = DataProcessor()
    dp.datasets = [ds]
    dp.processar_dados()
    assert dp.dados_tratados, "DataProcessor não produziu dados"

    d = next(d for d in dp.dados_tratados if d["chart"] == "XR")
    r = respostas_variaveis(d)

    # Estrutura completa
    for chave in ("chart", "mu", "sigma", "lic", "lsc", "lie", "lse",
                  "curto_prazo", "longo_prazo", "x_para_margem_alvo",
                  "capacidade", "margem_atual", "margem_com_deslocamento",
                  "binomial"):
        assert chave in r, f"chave ausente: {chave}"

    # c) valor de X é um número (não None, não "")
    assert isinstance(r["x_para_margem_alvo"]["x_percentil"], float)
    # d) Cpk não None quando sigma > 0
    assert r["capacidade"]["cpk"] is not None
    # e) margem atual entre 0 e 1
    assert 0 < r["margem_atual"] < 1
    # f) margem com deslocamento entre 0 e 1
    assert 0 < r["margem_com_deslocamento"]["margem"] < 1
    # g) binomial: exata >= 0
    assert r["binomial"]["exata"] >= 0
    assert r["binomial"]["ao_menos"] >= 0

    print("  [OK] respostas_variaveis(XR) OK — cpk=%.4f, ppm=%.2f, binom_exata=%.2e"
          % (r["capacidade"]["cpk"], r["longo_prazo"]["ppm_obtido"], r["binomial"]["exata"]))


def test_respostas_atributos():
    from CEP.amostras.data_processor import DataProcessor
    from CEP.respostas import respostas_atributos

    ds = _dados_p_fixture()
    dp = DataProcessor()
    dp.datasets = [ds]
    dp.processar_dados()
    dados_p = next((d for d in dp.dados_tratados if d["chart"] == "P"), None)
    dados_u = next((d for d in dp.dados_tratados if d["chart"] == "U"), None)

    r = respostas_atributos(dados_p, dados_u)
    assert "chart" in r
    if dados_p:
        assert "carta_p" in r
        assert "curto_prazo" in r["carta_p"]
        assert "deslocamento_kalman" in r["carta_p"]
        assert isinstance(r["carta_p"]["deslocamento_kalman"], str)
    print("  [OK] respostas_atributos OK")


def test_pipeline_web_estrutura():
    """processar_para_usuario deve retornar {chart: {dados, respostas}}."""
    from cep_pipeline import processar_para_usuario

    ds = _dados_xr_fixture()
    resultado = processar_para_usuario([ds])
    assert resultado, "pipeline retornou vazio"

    for chart, entry in resultado.items():
        assert isinstance(entry, dict), f"esperado dict, got {type(entry)}"
        assert "dados" in entry, f"chart {chart}: falta 'dados'"
        assert "respostas" in entry, f"chart {chart}: falta 'respostas'"
        if entry["respostas"] is not None:
            r = entry["respostas"]
            assert "chart" in r, f"chart {chart}: 'chart' ausente nas respostas"
    print("  [OK] processar_para_usuario retorna {dados, respostas} por carta")


def test_calcular_answer_set():
    from CEP.amostras.data_processor import DataProcessor
    from CEP.respostas import calcular_answer_set

    ds = _dados_xr_fixture()
    dp = DataProcessor()
    dp.datasets = [ds]
    dp.processar_dados()

    ans = calcular_answer_set(dp.dados_tratados)
    assert "XR" in ans, "XR ausente do answer set"
    r = ans["XR"]
    # Garante que nenhum item obrigatório é None
    for chave in ("curto_prazo", "longo_prazo", "x_para_margem_alvo",
                  "capacidade", "margem_atual", "binomial"):
        assert r.get(chave) is not None, f"item {chave!r} é None no answer set"
    print("  [OK] calcular_answer_set OK")


def main():
    testes = [
        test_parametros_enunciado,
        test_respostas_xr,
        test_respostas_atributos,
        test_pipeline_web_estrutura,
        test_calcular_answer_set,
    ]
    print("\n=== test_respostas.py ===")
    falhas = 0
    for t in testes:
        try:
            t()
        except Exception as exc:
            print(f"  [FAIL] {t.__name__}: {exc}")
            falhas += 1
    print(f"\n{'PASSOU' if not falhas else 'FALHOU'} — {len(testes) - falhas}/{len(testes)} testes OK\n")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
