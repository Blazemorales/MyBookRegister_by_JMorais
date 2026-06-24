import numpy as np
from scipy.integrate import dblquad
from scipy.stats import norm

def obter_d3(n):
    """
    Calcula e retorna a constante d3 para um tamanho de amostra n.
    """
    # f(xn, x1) é a densidade conjunta do máximo (xn) e do mínimo (x1)
    def densidade_conjunta(xn, x1, n):
        pdf_x1 = norm.pdf(x1)
        pdf_xn = norm.pdf(xn)
        cdf_x1 = norm.cdf(x1)
        cdf_xn = norm.cdf(xn)
        
        # gap_prob é a probabilidade de n-2 valores estarem entre os extremos
        gap_prob = np.power(np.clip(cdf_xn - cdf_x1, 0, 1), n - 2)
        
        return n * (n - 1) * gap_prob * pdf_x1 * pdf_xn

    # 1. Calcula E[w^2]
    f_w2 = lambda xn, x1: ((xn - x1)**2) * densidade_conjunta(xn, x1, n)
    e_w2, _ = dblquad(f_w2, -10, 10, lambda x1: x1, 10)

    # 2. Calcula E[w] (que é o próprio d2)
    f_w1 = lambda xn, x1: (xn - x1) * densidade_conjunta(xn, x1, n)
    d2, _ = dblquad(f_w1, -10, 10, lambda x1: x1, 10)
    
    # 3. Calcula d3: raiz da variância
    d3 = np.sqrt(max(0, e_w2 - d2**2))
    
    return d3
    print(f"O valor de d3 para n={n} é: {resultado_d3:.4f}")

# Se quiser conferir o D3 (usado no limite inferior):
# d2_valor = ... (calculado acima)
# D3 = max(0, 1 - 3 * (resultado_d3 / d2_valor))