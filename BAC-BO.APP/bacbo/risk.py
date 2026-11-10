"""Gestão de risco — banca, Kelly, stop-loss, cooldown."""
from dataclasses import dataclass
from itertools import takewhile
from typing import List, Optional


@dataclass
class Banca:
    """Banca principal (entradas 🔴/🔵)."""
    inicial: float = 100.0
    aposta_base: float = 1.0
    multiplicador_gale: float = 2.0
    unidade_atual: float = 1.0 
    saldo: float = None
    pico: float = None
    drawdown_max: float = 0.0

    def __post_init__(self):
        if self.saldo is None:
            self.saldo = self.inicial
        if self.pico is None:
            self.pico = self.inicial

    def definir_unidade(self, unidade: float, max_pct: float = 0.02) -> None:
        """Define a unidade para o próximo sinal, limitada a max_pct da banca."""
        max_seguro = max(0.1, self.saldo * max_pct)
        self.unidade_atual = min(unidade, max_seguro)

    def registrar(self, resultado: str, stake: Optional[float] = None) -> float:
        stake = stake or self.unidade_atual
        if resultado in ("WIN", "WIN_G1"):
            delta = +stake
        elif resultado == "WIN_TIE":
            # TIE como proteção de entrada normal: stake devolvido (empate)
            delta = 0.0
        elif resultado == "LOSS":
            # Perdeu entrada + Gale 1 → -stake * (1 + multiplicador_gale)
            delta = -stake * (1 + self.multiplicador_gale)
        else:
            delta = 0.0

        self.saldo += delta
        self.unidade_atual = self.aposta_base
        self.pico = max(self.pico, self.saldo)
        self.drawdown_max = max(self.drawdown_max, self.pico - self.saldo)
        return delta

    @property
    def retorno_pct(self) -> float:
        return ((self.saldo - self.inicial) / self.inicial) * 100


# =============================================================================
# 🟡 BANCA DE TIE — REGRAS DIFERENTES
# =============================================================================
@dataclass
class BancaTie:
    """
    Banca exclusiva para entradas de TIE.

    Regras:
      - WIN_TIE: aposta ganha (odd alta, ex: 8:1 ou 9:1)
      - LOSS: aposta perde (100% do valor, sem Gale)
    """
    inicial: float = 100.0
    aposta_base: float = 1.0
    odd_alvo: float = 9.0
    unidade_atual: float = 1.0
    saldo: float = None
    pico: float = None
    drawdown_max: float = 0.0

    def __post_init__(self):
        if self.saldo is None:
            self.saldo = self.inicial
        if self.pico is None:
            self.pico = self.inicial
            self.unidade_atual = self.aposta_base

    def definir_unidade(self, unidade: float, max_pct: float = 0.02) -> None:
        """Define a unidade para o próximo sinal (limitada a max_pct da banca)."""
        # Nunca aposta mais de 5% da banca atual
        max_seguro = max(0.1, self.saldo * max_pct)
        self.unidade_atual = min(unidade, max_seguro)        

    def registrar(self, resultado: str, stake: Optional[float] = None) -> float:
        stake = stake or self.unidade_atual

        if resultado in ("WIN", "WIN_TIE"):
            delta = +stake * (self.odd_alvo - 1)
        elif resultado == "LOSS":
            delta = -stake
        else:
            delta = 0.0

        self.saldo += delta
        self.unidade_atual = self.aposta_base
        self.pico = max(self.pico, self.saldo)
        self.drawdown_max = max(self.drawdown_max, self.pico - self.saldo)
        return delta

    @property
    def retorno_pct(self) -> float:
        return ((self.saldo - self.inicial) / self.inicial) * 100


# =============================================================================
# 🔧 FUNÇÕES AUXILIARES
# =============================================================================
def kelly_fraction(
    p_win: float,
    odd: float = 1.95,
    fracao: float = 0.25,
    cap: float = 0.05,
) -> float:
    if p_win <= 0 or p_win >= 1:
        return 0.0
    b = odd - 1
    if b <= 0:
        return 0.0
    q = 1 - p_win
    k = (b * p_win - q) / b
    return max(0.0, min(k * fracao, cap))


def sugerir_unidade(
    assertividade_pct: float,
    unidades_max: float = 2.0,
    odd: float = 1.95,
) -> float:
    """Retorna unidades (0..unidades_max) via Kelly fracionário (50%)."""
    p = assertividade_pct / 100
    k = kelly_fraction(p, odd=odd, fracao=0.25, cap=unidades_max / 100)
    if k <= 0:
        return 0.0
    return round(min(k * 100, unidades_max), 2)


def sugerir_unidade_tie(
    assertividade_pct: float,
    odd: float = 9.0,
    fracao_kelly: float = 0.10,
    cap: float = 0.03,
    unidades_max: float = 3.0,
) -> float:
    """
    Sugere unidades para TIE usando Kelly fracionário (10%).
    Limita a 3% da banca (cap) e a unidades_max.
    """
    p = assertividade_pct / 100
    k = kelly_fraction(p, odd=odd, fracao=fracao_kelly, cap=cap)
    if k <= 0:
        return 0.0
    return round(min(k * 100, unidades_max), 2)


@dataclass
class StopRules:
    stop_loss_consecutivo: int = 3
    stop_drawdown_unidades: float = 5.0
    stop_win_sessao: float = 10.0
    cooldown_apos_loss: int = 2
    max_entradas_hora: int = 20

    def avaliar(
        self,
        historico: List[str],
        banca: Banca,
        entradas_ultima_hora: int,
    ) -> Optional[str]:
        consec = 0
        for r in reversed(historico):
            if r == "LOSS":
                consec += 1
            elif r in ("WIN", "WIN_G1", "WIN_TIE"):
                break
        if consec >= self.stop_loss_consecutivo:
            return f"🛑 STOP-LOSS: {consec} LOSS consecutivos"

        if banca.drawdown_max >= self.stop_drawdown_unidades:
            return f"🛑 STOP-LOSS: drawdown de {banca.drawdown_max:.1f}u"

        if banca.saldo - banca.inicial >= self.stop_win_sessao:
            return f"🎯 STOP-WIN: +{banca.saldo - banca.inicial:.1f}u"

        if entradas_ultima_hora >= self.max_entradas_hora:
            return f"⏱️ Limite de {self.max_entradas_hora} entradas/h atingido"

        return None

    def precisa_cooldown(self, historico: List[str]) -> int:
        if not historico or historico[-1] != "LOSS":
            return 0
        seguidos = list(takewhile(lambda r: r != "LOSS", reversed(historico[:-1])))
        return max(0, self.cooldown_apos_loss - len(seguidos))