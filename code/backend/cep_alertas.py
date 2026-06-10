"""Análise CEP em streaming: estatística incremental + Kalman 1D + regras
de Nelson clássicas, sem importar numpy/scipy para não inflar o RSS do
caminho hot do Socket.IO.

Estado por canal vive em memória do processo. Quando reiniciar, perde o
histórico — aceitável: ao receber 20 pontos novos, a linha base se
reconstitui. Para hidratação futura, ler dos últimos N de
`medicoes_stream`.

Regras implementadas (5 das 8 clássicas de Nelson):
  1. Ponto fora de 3σ                          → severidade crítica
  2. 9 pontos consecutivos do mesmo lado       → atenção
  3. 6 pontos consecutivos monotônicos         → atenção
  5. 2 de 3 pontos consecutivos além de 2σ     → atenção
  + Kalman: estimativa desvia ≥X% da média     → atenção
"""
from __future__ import annotations

import logging
import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


logger = logging.getLogger(__name__)


# ── Configuração ───────────────────────────────────────────────────────

# Quantos pontos coletar antes de começar a checar regras (linha base).
CEP_JANELA_MIN = int(os.environ.get("CEP_JANELA_MIN", "20"))
# Tamanho máximo do buffer por canal — limita memória ao escalar.
CEP_JANELA_MAX = int(os.environ.get("CEP_JANELA_MAX", "200"))
# Parâmetros do filtro Kalman 1D (modelo escalar estacionário).
KALMAN_Q = float(os.environ.get("KALMAN_Q", "0.01"))   # ruído de processo
KALMAN_R = float(os.environ.get("KALMAN_R", "0.10"))   # ruído de medida
# Limiar do alerta "Kalman desviou" — % da média.
DESLOCAMENTO_PCT = float(os.environ.get("DESLOCAMENTO_PCT", "10"))


# ── Estado por canal ───────────────────────────────────────────────────

@dataclass
class EstadoCanal:
    """Acumulador incremental (Welford) + janela deslizante + Kalman 1D."""

    valores: deque = field(
        default_factory=lambda: deque(maxlen=CEP_JANELA_MAX)
    )
    n: int = 0
    media: float = 0.0  # média móvel (Welford)
    m2: float = 0.0     # soma dos quadrados dos desvios (Welford)
    kalman_x: Optional[float] = None
    kalman_p: float = 1.0

    def adicionar(self, valor: float) -> None:
        self.n += 1
        delta = valor - self.media
        self.media += delta / self.n
        self.m2 += delta * (valor - self.media)
        self.valores.append(valor)

        if self.kalman_x is None:
            self.kalman_x = valor
        else:
            # predict: variância cresce com Q (processo estacionário).
            self.kalman_p += KALMAN_Q
            # update: ganho * resíduo.
            k = self.kalman_p / (self.kalman_p + KALMAN_R)
            self.kalman_x += k * (valor - self.kalman_x)
            self.kalman_p *= 1 - k

    @property
    def desvio(self) -> float:
        if self.n < 2:
            return 0.0
        return (self.m2 / (self.n - 1)) ** 0.5


_estados: dict[str, EstadoCanal] = {}


def reset_canal(canal: str) -> None:
    """Limpa o estado de um canal — útil quando o dispositivo recalibra."""
    _estados.pop(canal, None)


def reset_todos() -> None:
    """Limpa todo o estado — útil em testes."""
    _estados.clear()


# ── Construtor de alertas ──────────────────────────────────────────────

def _novo_alerta(
    *,
    regra: str,
    severidade: str,
    mensagem: str,
    valor: float,
    estado: EstadoCanal,
    canal: str,
) -> dict:
    return {
        "regra": regra,
        "severidade": severidade,
        "mensagem": mensagem,
        "valor": valor,
        "media": estado.media,
        "desvio": estado.desvio,
        "canal": canal,
        "kalman": estado.kalman_x,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }


# ── Análise ────────────────────────────────────────────────────────────

def analisar_ponto(canal: str, valor: float) -> list[dict]:
    """Adiciona um ponto ao estado do canal e devolve alertas disparados.

    Retorna lista vazia até a janela base (`CEP_JANELA_MIN`) ser atingida.
    Cada alerta é um dict serializável (pronto para `sio.emit`).
    """
    estado = _estados.setdefault(canal, EstadoCanal())
    estado.adicionar(valor)

    if estado.n < CEP_JANELA_MIN:
        return []

    sigma = estado.desvio
    if sigma <= 0:
        return []  # série constante — nada a alertar

    alertas: list[dict] = []
    media = estado.media
    z = (valor - media) / sigma
    valores = list(estado.valores)

    # Regra 1 (Nelson) — ponto fora de 3σ.
    if abs(z) > 3:
        alertas.append(
            _novo_alerta(
                regra="nelson_1",
                severidade="critico",
                mensagem=f"ponto fora de 3σ ({z:+.2f}σ)",
                valor=valor,
                estado=estado,
                canal=canal,
            )
        )

    # Regra 2 — 9 pontos consecutivos do mesmo lado da média.
    if len(valores) >= 9:
        ultimos9 = valores[-9:]
        if all(v > media for v in ultimos9):
            alertas.append(
                _novo_alerta(
                    regra="nelson_2",
                    severidade="atencao",
                    mensagem="9 pontos consecutivos acima da média",
                    valor=valor,
                    estado=estado,
                    canal=canal,
                )
            )
        elif all(v < media for v in ultimos9):
            alertas.append(
                _novo_alerta(
                    regra="nelson_2",
                    severidade="atencao",
                    mensagem="9 pontos consecutivos abaixo da média",
                    valor=valor,
                    estado=estado,
                    canal=canal,
                )
            )

    # Regra 3 — 6 pontos consecutivos monotônicos.
    if len(valores) >= 6:
        ultimos6 = valores[-6:]
        if all(ultimos6[i] < ultimos6[i + 1] for i in range(5)):
            alertas.append(
                _novo_alerta(
                    regra="nelson_3",
                    severidade="atencao",
                    mensagem="6 pontos consecutivos crescentes",
                    valor=valor,
                    estado=estado,
                    canal=canal,
                )
            )
        elif all(ultimos6[i] > ultimos6[i + 1] for i in range(5)):
            alertas.append(
                _novo_alerta(
                    regra="nelson_3",
                    severidade="atencao",
                    mensagem="6 pontos consecutivos decrescentes",
                    valor=valor,
                    estado=estado,
                    canal=canal,
                )
            )

    # Regra 5 — 2 de 3 pontos além de 2σ no mesmo lado.
    if len(valores) >= 3:
        ultimos3 = valores[-3:]
        zs = [(v - media) / sigma for v in ultimos3]
        if sum(1 for zi in zs if zi > 2) >= 2:
            alertas.append(
                _novo_alerta(
                    regra="nelson_5",
                    severidade="atencao",
                    mensagem="2 de 3 pontos acima de +2σ",
                    valor=valor,
                    estado=estado,
                    canal=canal,
                )
            )
        elif sum(1 for zi in zs if zi < -2) >= 2:
            alertas.append(
                _novo_alerta(
                    regra="nelson_5",
                    severidade="atencao",
                    mensagem="2 de 3 pontos abaixo de -2σ",
                    valor=valor,
                    estado=estado,
                    canal=canal,
                )
            )

    # Kalman — estimativa filtrada desviou ≥ DESLOCAMENTO_PCT da média.
    if estado.kalman_x is not None and abs(media) > 1e-9:
        desloc_pct = abs(estado.kalman_x - media) / abs(media) * 100.0
        if desloc_pct >= DESLOCAMENTO_PCT:
            alertas.append(
                _novo_alerta(
                    regra="kalman_deslocamento",
                    severidade="atencao",
                    mensagem=f"Kalman desviou {desloc_pct:.1f}% da média",
                    valor=valor,
                    estado=estado,
                    canal=canal,
                )
            )

    return alertas


def extrair_escalar(payload: dict) -> Optional[float]:
    """Devolve o primeiro valor escalar útil do payload, ou None.

    O streaming CEP só faz sentido com um número por ponto — `valores`
    em lista, `dados` complexos, etc. passam direto sem análise.
    """
    for chave in ("valor", "value"):
        v = payload.get(chave)
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return float(v)
    return None
