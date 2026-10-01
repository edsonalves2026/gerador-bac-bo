"""Analisador de padrões de cores e números — sobre as últimas N rodadas."""
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# ESTATÍSTICAS DE UM PADRÃO
# =============================================================================
@dataclass
class PatternStats:
    padrao: str = ""                      # ex: "🔴🔵🔵🔵" ou "10"
    tipo: str = "cor"                     # "cor" | "numero" | "seq_numero"
    ocorrencias: int = 0
    sugestao: str = ""                    # 🔴 / 🔵
    acertos_direto: int = 0               # SG
    acertos_gale1: int = 0                # G1
    acertos_gale2: int = 0                # G2
    reds: int = 0                         # RED (todas perdas)

    @property
    def total_avaliado(self) -> int:
        return self.acertos_direto + self.acertos_gale1 + self.acertos_gale2 + self.reds

    @property
    def taxa_acerto(self) -> float:
        t = self.total_avaliado
        if t == 0:
            return 0.0
        return ((self.acertos_direto + self.acertos_gale1 + self.acertos_gale2) / t) * 100

    @property
    def taxa_direto(self) -> float:
        t = self.total_avaliado
        if t == 0:
            return 0.0
        return (self.acertos_direto / t) * 100

    def resumo_curto(self) -> str:
        return (
            f"{self.padrao} Apareceu {self.ocorrencias} vezes "
            f"Pode indicar -> {self.sugestao} ({self.taxa_acerto:.2f}%) "
            f"SG:{self.acertos_direto} G1:{self.acertos_gale1} "
            f"G2:{self.acertos_gale2} RED:{self.reds}"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "padrao": self.padrao,
            "tipo": self.tipo,
            "ocorrencias": self.ocorrencias,
            "sugestao": self.sugestao,
            "sg": self.acertos_direto,
            "g1": self.acertos_gale1,
            "g2": self.acertos_gale2,
            "red": self.reds,
            "taxa": round(self.taxa_acerto, 2),
            "taxa_direto": round(self.taxa_direto, 2),
        }


# =============================================================================
# ANALISADOR PRINCIPAL
# =============================================================================
class PatternsAnalyzer:
    """
    Analisa as últimas N rodadas e devolve os padrões mais assertivos.
    Os 4 filtros expostos na UI são:
      - num_rodadas:     janela analisada (ex: 500)
      - tamanho_padrao:  quantas cores compõem a sequência (ex: 4)
      - min_ocorrencias: amostra mínima (ex: 15)
      - min_taxa:        assertividade mínima em % (ex: 90)
      - usar_gale:       0, 1 ou 2
    """

    def __init__(self, cores: List[str], pontos: List[int]) -> None:
        if len(cores) != len(pontos):
            raise ValueError("cores e pontos devem ter o mesmo tamanho")
        self.cores = cores
        self.pontos = pontos

    # ------------------------------------------------------------------ CORES
    def analisar_cores(
        self,
        tamanho: int = 4,
        min_ocorrencias: int = 4,
        min_taxa: float = 85.0,
        usar_gale: int = 2,
    ) -> List[PatternStats]:
        """Sequências de N cores → próxima cor mais provável."""
        if len(self.cores) < tamanho + 2:
            return []

        # Agrupa índices de ocorrência por sequência
        buckets: Dict[Tuple[str, ...], List[int]] = defaultdict(list)
        for i in range(len(self.cores) - tamanho):
            seq = tuple(self.cores[i : i + tamanho])
            buckets[seq].append(i + tamanho)  # índice da PRÓXIMA rodada

        resultados: List[PatternStats] = []
        for seq, idxs in buckets.items():
            if len(idxs) < min_ocorrencias:
                continue

            proximas = [self.cores[i] for i in idxs if i < len(self.cores)]
            votos = [c for c in proximas if c in ("🔴", "🔵")]
            if len(votos) < min_ocorrencias:
                continue

            sugestao = "🔴" if votos.count("🔴") >= votos.count("🔵") else "🔵"

            sg, g1, g2, red = self._avaliar_posicoes(idxs, sugestao, usar_gale)

            ps = PatternStats(
                padrao="".join(seq), tipo="cor",
                ocorrencias=len(idxs), sugestao=sugestao,
                acertos_direto=sg, acertos_gale1=g1,
                acertos_gale2=g2, reds=red,
            )
            if ps.taxa_acerto >= min_taxa:
                resultados.append(ps)

        resultados.sort(key=lambda p: (p.taxa_acerto, p.ocorrencias), reverse=True)
        return resultados

    # --------------------------------------------------------------- NÚMEROS
    def analisar_numeros(
        self,
        min_ocorrencias: int = 4,
        min_taxa: float = 85.0,
        usar_gale: int = 2,
    ) -> List[PatternStats]:
        """Cada número individual (2..12) → próxima cor mais provável."""
        buckets: Dict[int, List[int]] = defaultdict(list)
        for i, p in enumerate(self.pontos):
            if i + 1 < len(self.cores):
                buckets[p].append(i + 1)

        resultados: List[PatternStats] = []
        for num, idxs in buckets.items():
            if len(idxs) < min_ocorrencias:
                continue

            proximas = [self.cores[i] for i in idxs if i < len(self.cores)]
            votos = [c for c in proximas if c in ("🔴", "🔵")]
            if len(votos) < min_ocorrencias:
                continue

            sugestao = "🔴" if votos.count("🔴") >= votos.count("🔵") else "🔵"
            sg, g1, g2, red = self._avaliar_posicoes(idxs, sugestao, usar_gale)

            ps = PatternStats(
                padrao=str(num), tipo="numero",
                ocorrencias=len(idxs), sugestao=sugestao,
                acertos_direto=sg, acertos_gale1=g1,
                acertos_gale2=g2, reds=red,
            )
            if ps.taxa_acerto >= min_taxa:
                resultados.append(ps)

        resultados.sort(key=lambda p: (p.taxa_acerto, p.ocorrencias), reverse=True)
        return resultados

    # ---------------------------------------------------- SEQUÊNCIAS DE NÚMEROS
    def analisar_sequencia_numeros(
        self,
        tamanho: int = 2,
        min_ocorrencias: int = 3,
        min_taxa: float = 80.0,
        usar_gale: int = 2,
    ) -> List[PatternStats]:
        """Sequências de N números (ex: 8→10) → próxima cor."""
        if len(self.pontos) < tamanho + 2:
            return []

        buckets: Dict[Tuple[int, ...], List[int]] = defaultdict(list)
        for i in range(len(self.pontos) - tamanho):
            seq = tuple(self.pontos[i : i + tamanho])
            buckets[seq].append(i + tamanho)

        resultados: List[PatternStats] = []
        for seq, idxs in buckets.items():
            if len(idxs) < min_ocorrencias:
                continue

            proximas = [self.cores[i] for i in idxs if i < len(self.cores)]
            votos = [c for c in proximas if c in ("🔴", "🔵")]
            if len(votos) < min_ocorrencias:
                continue

            sugestao = "🔴" if votos.count("🔴") >= votos.count("🔵") else "🔵"
            sg, g1, g2, red = self._avaliar_posicoes(idxs, sugestao, usar_gale)

            ps = PatternStats(
                padrao="→".join(str(x) for x in seq), tipo="seq_numero",
                ocorrencias=len(idxs), sugestao=sugestao,
                acertos_direto=sg, acertos_gale1=g1,
                acertos_gale2=g2, reds=red,
            )
            if ps.taxa_acerto >= min_taxa:
                resultados.append(ps)

        resultados.sort(key=lambda p: (p.taxa_acerto, p.ocorrencias), reverse=True)
        return resultados

    # -------------------------------------------------------------- HELPERS
    def _avaliar_posicoes(
        self, idxs_proxima: List[int], sugestao: str, usar_gale: int,
    ) -> Tuple[int, int, int, int]:
        """
        Para cada índice de "próxima rodada", verifica se a sugestão
        acertou direto (SG), no gale 1, gale 2 ou se deu RED.
        TIE conta como acerto protegido.
        """
        sg = g1 = g2 = red = 0
        for idx in idxs_proxima:
            r1 = self.cores[idx] if idx < len(self.cores) else None
            r2 = self.cores[idx + 1] if idx + 1 < len(self.cores) else None
            r3 = self.cores[idx + 2] if idx + 2 < len(self.cores) else None

            if r1 == sugestao or r1 == "🟡":
                sg += 1
            elif usar_gale >= 1 and (r2 == sugestao or r2 == "🟡"):
                g1 += 1
            elif usar_gale >= 2 and (r3 == sugestao or r3 == "🟡"):
                g2 += 1
            else:
                red += 1
        return sg, g1, g2, red

    # ---------------------------------------------------------- UNIFICADO
    def analisar_tudo(
        self,
        tamanho_cor: int = 4,
        min_ocorrencias: int = 4,
        min_taxa: float = 85.0,
        usar_gale: int = 2,
    ) -> Dict[str, List[PatternStats]]:
        """Retorna tudo de uma vez para a UI renderizar."""
        return {
            "cores": self.analisar_cores(
                tamanho=tamanho_cor,
                min_ocorrencias=min_ocorrencias,
                min_taxa=min_taxa,
                usar_gale=usar_gale,
            ),
            "numeros": self.analisar_numeros(
                min_ocorrencias=min_ocorrencias,
                min_taxa=min_taxa,
                usar_gale=usar_gale,
            ),
            "sequencias": self.analisar_sequencia_numeros(
                tamanho=2,
                min_ocorrencias=max(2, min_ocorrencias - 1),
                min_taxa=max(60.0, min_taxa - 10.0),
                usar_gale=usar_gale,
            ),
        }
