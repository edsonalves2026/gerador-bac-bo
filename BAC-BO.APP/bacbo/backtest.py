"""Backtester offline."""
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from .risk import Banca, kelly_fraction


@dataclass
class BacktestResult:
    nome: str
    total_sinais: int = 0
    wins_direto: int = 0
    wins_gale: int = 0
    losses: int = 0
    max_dd_consecutivo: int = 0
    banca_final: float = 100.0
    banca_pico: float = 100.0

    @property
    def win_rate(self) -> float:
        if self.total_sinais == 0:
            return 0.0
        return (self.wins_direto + self.wins_gale) / self.total_sinais * 100

    @property
    def gale_rate(self) -> float:
        if self.total_sinais == 0:
            return 0.0
        return self.wins_gale / self.total_sinais * 100

    @property
    def profit_pct(self) -> float:
        return (self.banca_final - 100) / 100 * 100

    def resumo(self) -> Dict:
        return {
            "nome": self.nome,
            "total": self.total_sinais,
            "win_rate": round(self.win_rate, 1),
            "gale_rate": round(self.gale_rate, 1),
            "loss_rate": round(100 - self.win_rate, 1),
            "max_dd_consec": self.max_dd_consecutivo,
            "banca_final": round(self.banca_final, 2),
            "profit_pct": round(self.profit_pct, 2),
        }


class Backtester:
    def __init__(
        self,
        cores: List[str],
        pontos: List[int],
        janela_min: int = 100,
        usar_kelly: bool = False,
        odd: float = 1.95,
    ):
        assert len(cores) == len(pontos), "cores e pontos desalinhados"
        self.cores = cores
        self.pontos = pontos
        self.janela_min = janela_min
        self.usar_kelly = usar_kelly
        self.odd = odd

    def rodar(
        self,
        nome: str,
        detector: Callable[[List[str], List[int]], Optional[tuple]],
    ) -> BacktestResult:
        res = BacktestResult(nome=nome)
        banca = Banca()
        loss_consec_atual = 0
        loss_consec_max = 0

        i = self.janela_min
        while i < len(self.cores) - 2:
            sinal = detector(self.cores[:i], self.pontos[:i])
            if not sinal:
                i += 1
                continue

            sugestao = sinal[0]
            confianca = sinal[1] if len(sinal) > 1 else 70.0

            r1 = self.cores[i]
            r2 = self.cores[i + 1]

            if self.usar_kelly:
                stake = max(0.5, kelly_fraction(confianca / 100, self.odd) * banca.saldo)
            else:
                stake = banca.aposta_base

            res.total_sinais += 1

            if r1 == sugestao or r1 == "🟡":
                if r1 == "🟡":
                    res.wins_direto += 1
                else:
                    res.wins_direto += 1
                banca.registrar("WIN_TIE" if r1 == "🟡" else "WIN", stake)
                loss_consec_atual = 0
                i += 2
            elif r2 == sugestao or r2 == "🟡":
                res.wins_gale += 1
                banca.registrar("WIN_G1", stake)
                loss_consec_atual = 0
                i += 3
            else:
                res.losses += 1
                banca.registrar("LOSS", stake)
                loss_consec_atual += 1
                loss_consec_max = max(loss_consec_max, loss_consec_atual)
                i += 3

        res.banca_final = banca.saldo
        res.banca_pico = banca.pico
        res.max_dd_consecutivo = loss_consec_max
        return res