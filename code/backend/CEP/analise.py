"""Cálculos probabilísticos do simulado CEP (Questões 1 e 2).

Implementa, de forma isolada e testável, cada item pedido nas perguntas:

Questão 1 (cartas de variáveis X-R e I-MR):
  - curto prazo: 1 ponto fora de +/-3 sigma  -> `sob_controle_curto_prazo`
  - longo prazo: ppm obtido < ppm requerido (890) -> `ppm_processo`, `atende_longo_prazo`
  - valor de X para 96% de margem de sucesso -> `quantil_para_rendimento`
  - capacidade (16-21), inclusive com LIE=0.98*LIC e LSE=1.1*LSC -> `cpk`, `capacidade_por_limites`
  - margem de sucesso com deslocamento de +1.5 sigma -> `rendimento_com_deslocamento`
  - probabilidade de acertar 85 em 100 tentativas -> `prob_binomial`

Questão 2 (cartas de atributos P e U):
  - sob controle no curto prazo            -> `sob_controle_curto_prazo`
  - existe deslocamento?                   -> use o Kalman já existente (Cartas)

Convenções: todas as probabilidades usam a Normal padrão (item 7 do PDF).
"""

from math import sqrt
from scipy.stats import norm, binom


# ---------------------------------------------------------------------------
# Capacidade do processo (item 4 / fórmula 16-21)
# ---------------------------------------------------------------------------
def cp(sigma, lse, lie):
    """Cp = (LSE - LIE) / (6 sigma). Capacidade potencial (processo centrado)."""
    if sigma <= 0:
        return None
    return (lse - lie) / (6.0 * sigma)


def cpk(mu, sigma, lse, lie):
    """Cpk = min[(LSE - mu)/3sigma, (mu - LIE)/3sigma] (fórmula 16-21)."""
    if sigma <= 0:
        return None
    cpu = (lse - mu) / (3.0 * sigma)
    cpl = (mu - lie) / (3.0 * sigma)
    return min(cpu, cpl)


def capacidade_por_limites(mu, sigma, lic, lsc, fator_lie=0.98, fator_lse=1.1):
    """Capacidade usando especificações DERIVADAS dos limites de controle.

    Conforme a Questão 1: LIE = fator_lie * LIC e LSE = fator_lse * LSC.
    Retorna dict com lie, lse, cp e cpk.
    """
    lie = fator_lie * lic
    lse = fator_lse * lsc
    return {
        "lie": lie,
        "lse": lse,
        "cp": cp(sigma, lse, lie),
        "cpk": cpk(mu, sigma, lse, lie),
    }


# ---------------------------------------------------------------------------
# Rendimento / ppm (item 9, longo prazo)
# ---------------------------------------------------------------------------
def fracao_fora_spec(mu, sigma, lse, lie):
    """Fração esperada fora das especificações (Normal): P(x<LIE) + P(x>LSE)."""
    if sigma <= 0:
        return 0.0
    p_abaixo = norm.cdf((lie - mu) / sigma)
    p_acima = 1.0 - norm.cdf((lse - mu) / sigma)
    return p_abaixo + p_acima


def rendimento(mu, sigma, lse, lie):
    """Margem de sucesso = P(LIE <= x <= LSE) = 1 - fração fora."""
    return 1.0 - fracao_fora_spec(mu, sigma, lse, lie)


def ppm_processo(mu, sigma, lse, lie):
    """ppm obtido = fração fora das especificações x 1e6."""
    return fracao_fora_spec(mu, sigma, lse, lie) * 1_000_000.0


def atende_longo_prazo(mu, sigma, lse, lie, ppm_requerido=890.0):
    """Avalia o longo prazo: ppm obtido < ppm requerido (default 890)."""
    obtido = ppm_processo(mu, sigma, lse, lie)
    return {
        "ppm_obtido": obtido,
        "ppm_requerido": ppm_requerido,
        "atende": obtido < ppm_requerido,
    }


def rendimento_com_deslocamento(mu, sigma, lse, lie, deslocamento_sigmas=1.5):
    """Margem de sucesso após deslocar a média em `deslocamento_sigmas`*sigma."""
    mu_desloc = mu + deslocamento_sigmas * sigma
    return rendimento(mu_desloc, sigma, lse, lie)


# ---------------------------------------------------------------------------
# Quantil para um rendimento alvo (item: "valor de X para 95% de sucesso")
# ---------------------------------------------------------------------------
def quantil_para_rendimento(mu, sigma, rendimento_alvo=0.96, lado="superior"):
    """Valor de X associado a um rendimento alvo, via inversa da Normal.

    lado='superior': X tal que P(x <= X) = rendimento_alvo (percentil).
    lado='central' : meia-largura simétrica, retorna (X_inf, X_sup) cobrindo
                     `rendimento_alvo` da distribuição.
    """
    if lado == "central":
        alfa = 1.0 - rendimento_alvo
        z = norm.ppf(1.0 - alfa / 2.0)
        return (mu - z * sigma, mu + z * sigma)
    return norm.ppf(rendimento_alvo, loc=mu, scale=sigma)


# ---------------------------------------------------------------------------
# Binomial (item 8) — "acertar k em n tentativas"
# ---------------------------------------------------------------------------
def prob_binomial(k, n, p):
    """Distribuição Binomial (fórmula da página 4).

    Retorna dict com:
      exata    = P(X = k)
      ao_menos = P(X >= k)
      ate      = P(X <= k)
    """
    return {
        "exata": float(binom.pmf(k, n, p)),
        "ao_menos": float(binom.sf(k - 1, n, p)),
        "ate": float(binom.cdf(k, n, p)),
    }


# ---------------------------------------------------------------------------
# Controle de curto prazo (item 9 / Questão 2)
# ---------------------------------------------------------------------------
def sob_controle_curto_prazo(valores, lic, lsc):
    """Curto prazo: processo sob controle se NENHUM ponto sai de [LIC, LSC]."""
    fora = [
        {"indice": i, "valor": float(v)}
        for i, v in enumerate(valores)
        if v > lsc or v < lic
    ]
    return {"sob_controle": len(fora) == 0, "pontos_fora": fora}


if __name__ == "__main__":
    # Auto-teste com números conferíveis à mão.
    mu, sigma = 540.0, 2.3132
    lse, lie = 545.0, 535.0
    print("ppm:", round(ppm_processo(mu, sigma, lse, lie), 2))
    print("rendimento:", round(rendimento(mu, sigma, lse, lie), 6))
    print("Cpk:", round(cpk(mu, sigma, lse, lie), 4))
    print("X96 (percentil):", round(quantil_para_rendimento(mu, sigma, 0.96), 4))
    print("rend. +1.5sigma:", round(rendimento_com_deslocamento(mu, sigma, lse, lie, 1.5), 6))
    print("binom 85/100 @p=0.96:", prob_binomial(85, 100, 0.96))
    # Sanidade: rendimento simétrico ~ Cpk via ppm
    assert abs(rendimento(mu, sigma, lse, lie) + fracao_fora_spec(mu, sigma, lse, lie) - 1.0) < 1e-12
    print("OK")
