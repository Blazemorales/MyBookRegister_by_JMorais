"""Parâmetros fixos do enunciado do simulado CEP.

Fonte única: todos os módulos (gerar_entrega.py, respostas.py,
cep_pipeline.py) importam daqui. Para alterar qualquer valor basta
editar este arquivo.
"""

PPM_REQUERIDO     = 890.0   # ppm máximo exigido (longo prazo)
MARGEM_ALVO       = 0.96    # rendimento alvo: X p/ 96% de sucesso
DESLOCAMENTO_SIGMA = 1.5    # deslocamento da média para item f
BINOM_K           = 85      # acertos mínimos (binomial, item g)
BINOM_N           = 100     # tentativas (binomial, item g)
FATOR_LIE         = 0.98    # LIE = FATOR_LIE * LIC
FATOR_LSE         = 1.1     # LSE = FATOR_LSE * LSC
