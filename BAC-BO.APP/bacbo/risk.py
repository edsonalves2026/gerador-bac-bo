"""Gestão de risco — banca, Kelly, stop-loss, cooldown."""
from dataclasses import dataclass
from itertools import takewhile
from typing import List, Optional


@dataclass
class Banca:
    inicial: float = 100.0
    aposta_base: float = 1.0
    multiplicador_gale: float = 2.0
    saldo: float = None
    pico: float = None
    drawdown_max: float = 0.0

    def __post_init__(self):
        if self.saldo is None:
            self.saldo = self.inicial
        if self.pico is None:
            self.pico = self.inicial

    def registrar(self, resultado: str, stake: Optional[float] = None) -> float:
        stake = stake or self.aposta_base
        if resultado == "WIN":
            delta = +stake
        elif resultado == "WIN_G1":
            delta = +stake
        elif resultado == "WIN_TIE":
            delta = 0.0
        elif resultado == "LOSS":
            delta = -stake * (1 + self.multiplicador_gale)
        else:
            delta = 0.0

        self.saldo += delta
        self.pico = max(self.pico, self.saldo)
        self.drawdown_max = max(self.drawdown_max, self.pico - self.saldo)
        return delta

    @property
    def retorno_pct(self) -> float:
        return ((self.saldo - self.inicial) / self.inicial) * 100


def kelly_fraction(
    p_win: float, odd: float = 1.95, fracao: float = 0.25, cap: float = 0.05,
) -> float:
    if p_win <= 0 or p_win >= 1:
        return 0.0
    b = odd - 1
    q = 1 - p_win
    k = (b * p_win - q) / b
    return max(0.0, min(k * fracao, cap))


def sugerir_unidade(
    assertividade_pct: float, unidades_max: float = 3.0, odd: float = 1.95,
) -> float:
    p = assertividade_pct / 100
    k = kelly_fraction(p, odd=odd, fracao=0.5)
    return round(k * 100, 2) if k > 0 else 0.0


@dataclass
class StopRules:
    stop_loss_consecutivo: int = 3
    stop_drawdown_unidades: float = 5.0
    stop_win_sessao: float = 10.0
    cooldown_apos_loss: int = 2
    max_entradas_hora: int = 20

    def avaliar(
        self, historico: List[str], banca: Banca, entradas_ultima_hora: int,
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