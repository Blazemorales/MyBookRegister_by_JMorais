"""Constantes tabeladas para cartas de controle (Montgomery, Tabela XI do Apendice).

Fonte unica de A2, D3, D4 e d2 por tamanho de subgrupo `n`, usada tanto pelo
processamento de dados (limites das cartas) quanto pelos relatorios.

Formulas relacionadas (ver Simulado_Software_CEP.pdf):
  - Carta X (16-9):  LSC = x_bb + A2*r_bar ; LC = x_bb ; LIC = x_bb - A2*r_bar
  - Carta R (16-12): LSC = D4*r_bar       ; LC = r_bar ; LIC = D3*r_bar
  - Carta I (16-19): LSC = x_bar + 3*am_bar/d2 ; LIC = x_bar - 3*am_bar/d2
  - Sigma estimado a partir do alcance: sigma_hat = r_bar / d2
"""

# n: (A2, D3, D4, d2) — Tabela XI (Montgomery, Introducao ao CEP)
_TABELA = {
    2:  (1.880, 0.000, 3.267, 1.128),
    3:  (1.023, 0.000, 2.574, 1.693),
    4:  (0.729, 0.000, 2.282, 2.059),
    5:  (0.577, 0.000, 2.114, 2.326),
    6:  (0.483, 0.000, 2.004, 2.534),
    7:  (0.419, 0.076, 1.924, 2.704),
    8:  (0.373, 0.136, 1.864, 2.847),
    9:  (0.337, 0.184, 1.816, 2.970),
    10: (0.308, 0.223, 1.777, 3.078),
    11: (0.285, 0.256, 1.744, 3.173),
    12: (0.266, 0.283, 1.717, 3.258),
    13: (0.249, 0.307, 1.693, 3.336),
    14: (0.235, 0.328, 1.672, 3.407),
    15: (0.223, 0.347, 1.653, 3.472),
    16: (0.212, 0.363, 1.637, 3.532),
    17: (0.203, 0.378, 1.622, 3.588),
    18: (0.194, 0.391, 1.608, 3.640),
    19: (0.187, 0.403, 1.597, 3.689),
    20: (0.180, 0.415, 1.585, 3.735),
    21: (0.173, 0.425, 1.575, 3.778),
    22: (0.167, 0.434, 1.566, 3.819),
    23: (0.162, 0.443, 1.557, 3.858),
    24: (0.157, 0.451, 1.548, 3.895),
    25: (0.153, 0.459, 1.541, 3.931),
}


def _aproximar(n):
    """Aproxima as constantes para n fora da tabela (n grande).

    Usa d2 ~ proporcional e d3 ~ aproximacao assintotica; A2 = 3/(d2*sqrt(n)).
    So e acionado para n > 25, situacao incomum em cartas X-R.
    """
    import math
    # Aproximacao de d2 e d3 (Hartley) para n grande.
    d2 = 3.4873 + 0.0250141 * (n - 25) if n > 25 else 3.931
    d3 = 0.708
    a2 = 3.0 / (d2 * math.sqrt(n))
    d4 = 1.0 + 3.0 * d3 / d2
    d3_const = max(0.0, 1.0 - 3.0 * d3 / d2)
    return (a2, d3_const, d4, d2)


def constantes(n):
    """Retorna (A2, D3, D4, d2) para o tamanho de subgrupo `n`."""
    n = int(n)
    if n < 2:
        raise ValueError("Cartas X-R/R exigem n >= 2.")
    return _TABELA.get(n) or _aproximar(n)


def A2(n):
    return constantes(n)[0]


def D3(n):
    return constantes(n)[1]


def D4(n):
    return constantes(n)[2]


def d2(n):
    return constantes(n)[3]
