"""Painel de Estatísticas: streaks máximos por cor + % de participação.

Suporta 3 modos de Gale:
  - SG (Sem Gale): conta streaks brutos
  - G1 (Gale 1):   absorve 1 rodada contrária dentro de um streak
  - G2 (Gale 2):   absorve até 2 rodadas contrárias dentro de um streak
"""
from dataclasses import dataclass
from typing import Dict, List, Tuple


# =============================================================================
# RESULTADO
# =============================================================================
@dataclass
class StatsResult:
    # Valores absolutos
    max_red: int = 0
    max_blue: int = 0
    max_tie: int = 0
    max_sem_tie: int = 0

    # Percentuais (participação do streak máximo no total de streaks)
    pct_red: float = 0.0
    pct_blue: float = 0.0
    pct_tie: float = 0.0
    pct_sem_tie: float = 0.0

    # Nº de streaks observados (usado como denominador do %)
    n_streaks_red: int = 0
    n_streaks_blue: int = 0
    n_streaks_tie: int = 0
    n_streaks_sem_tie: int = 0

    # Distribuição completa (opcional, útil p/ debug/UI detalhada)
    dist_red: List[int] = None
    dist_blue: List[int] = None
    dist_tie: List[int] = None
    dist_sem_tie: List[int] = None

    # Gale usado no cálculo (0, 1, 2)
    gale: int = 0

    # Total de rodadas analisadas
    total_rodadas: int = 0


# =============================================================================
# ANALISADOR
# =============================================================================
class StatsAnalyzer:
    """Calcula as estatísticas de streak para o painel da sidebar."""

    def __init__(self, cores: List[str]) -> None:
        self.cores = list(cores)

    # ------------------------------------------------------------------ API
    def calcular(self, gale: int = 0) -> StatsResult:
        """
        gale: 0 = SG, 1 = G1, 2 = G2.
        Aplica a transformação de absorção sobre as cores antes de contar.
        """
        if gale not in (0, 1, 2):
            raise ValueError("gale deve ser 0, 1 ou 2")

        # Em SG, usa as cores originais
        if gale == 0:
            seq = self.cores
        else:
            seq = self._aplicar_absorcao_gale(self.cores, gale)

        # Extrai streaks por "cor-alvo"
        dist_red = self._streaks_de_cor(seq, "🔴")
        dist_blue = self._streaks_de_cor(seq, "🔵")
        dist_tie = self._streaks_de_cor(seq, "🟡")
        dist_sem_tie = self._streaks_sem_cor(seq, "🟡")

        return StatsResult(
            max_red=max(dist_red, default=0),
            max_blue=max(dist_blue, default=0),
            max_tie=max(dist_tie, default=0),
            max_sem_tie=max(dist_sem_tie, default=0),
            pct_red=self._pct_maximo(dist_red),
            pct_blue=self._pct_maximo(dist_blue),
            pct_tie=self._pct_maximo(dist_tie),
            pct_sem_tie=self._pct_maximo(dist_sem_tie),
            n_streaks_red=len(dist_red),
            n_streaks_blue=len(dist_blue),
            n_streaks_tie=len(dist_tie),
            n_streaks_sem_tie=len(dist_sem_tie),
            dist_red=dist_red,
            dist_blue=dist_blue,
            dist_tie=dist_tie,
            dist_sem_tie=dist_sem_tie,
            gale=gale,
            total_rodadas=len(seq),
        )

    # -------------------------------------------------------- GALE / ABSORÇÃO
    @staticmethod
    def _aplicar_absorcao_gale(cores: List[str], gale: int) -> List[str]:
        """
        Simula o efeito do Gale sobre os streaks:
        se uma sequência contrária tem comprimento <= gale, ela é absorvida
        pela cor anterior.

        Ex (gale=1): 🔴 🔴 🔵 🔴 🔴  →  🔴 🔴 🔴 🔴 🔴
        Ex (gale=2): 🔴 🔵 🔵 🔴      →  🔴 🔴 🔴 🔴

        TIE nunca é absorvido — ele "protege" e devolve a aposta.
        """
        if gale <= 0 or len(cores) < 2:
            return list(cores)

        out: List[str] = []
        i = 0
        n = len(cores)

        while i < n:
            atual = cores[i]

            # TIE é copiado direto, não participa da absorção
            if atual == "🟡":
                out.append(atual)
                i += 1
                continue

            # Conta quantas iguais seguidas
            j = i
            while j < n and cores[j] == atual:
                j += 1

            bloco_atual = j - i

            # Verifica se o PRÓXIMO bloco é contrário e curto (<= gale)
            k = j
            bloco_oposto = 0
            oposto = None
            while k < n and cores[k] != "🟡" and cores[k] != atual:
                if oposto is None:
                    oposto = cores[k]
                elif cores[k] != oposto:
                    break
                bloco_oposto += 1
                k += 1

            if oposto is not None and 0 < bloco_oposto <= gale:
                # Absorve o bloco oposto na cor atual
                out.extend([atual] * (bloco_atual + bloco_oposto))
                i = k
            else:
                out.extend([atual] * bloco_atual)
                i = j

        return out

    # -------------------------------------------------------------- HELPERS
    @staticmethod
    def _streaks_de_cor(seq: List[str], cor: str) -> List[int]:
        """Comprimentos de todas as sequências consecutivas da cor alvo."""
        dist: List[int] = []
        i = 0
        n = len(seq)
        while i < n:
            if seq[i] == cor:
                j = i
                while j < n and seq[j] == cor:
                    j += 1
                dist.append(j - i)
                i = j
            else:
                i += 1
        return dist

    @staticmethod
    def _streaks_sem_cor(seq: List[str], cor: str) -> List[int]:
        """Comprimentos de sequências consecutivas SEM a cor alvo."""
        dist: List[int] = []
        i = 0
        n = len(seq)
        while i < n:
            if seq[i] != cor:
                j = i
                while j < n and seq[j] != cor:
                    j += 1
                dist.append(j - i)
                i = j
            else:
                i += 1
        return dist

    @staticmethod
    def _pct_maximo(dist: List[int]) -> float:
        """
        % de participação do streak máximo:
        quantas vezes o máximo ocorreu / total de streaks.
        """
        if not dist:
            return 0.0
        m = max(dist)
        ocorrencias_max = sum(1 for x in dist if x == m)
        return (ocorrencias_max / len(dist)) * 100.0
