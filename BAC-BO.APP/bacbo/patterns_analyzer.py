"""Analisador de padrões de cores e números — igual às imagens."""
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class PatternStats:
    """Estatísticas de um padrão (sequência de cores OU número)."""
    padrao: str                          # ex: "🔴🔵🔵🔵" ou "10"
    ocorrencias: int = 0                 # quantas vezes apareceu
    sugestao: str = ""                   # 🔴 / 🔵 / 🟡 (cor dominante após o padrão)
    acertos_direto: int = 0              # SG (acertos na 1ª)
    acertos_gale1: int = 0               # G1 (acertos no gale 1)
    acertos_gale2: int = 0               # G2 (acertos no gale 2)
    reds: int = 0                        # RED (perdas totais)
    amostra_min: int = 0                 # ocorrências válidas p/ cálculo

    @property
    def total_amostra(self) -> int:
        return self.acertos_direto + self.acertos_gale1 + self.acertos_gale2 + self.reds

    @property
    def taxa_acerto(self) -> float:
        """(SG + G1 + G2) / total * 100"""
        t = self.total_amostra
        if t == 0:
            return 0.0
        return ((self.acertos_direto + self.acertos_gale1 + self.acertos_gale2) / t) * 100

    def resumo_curto(self) -> str:
        """Formato exato da imagem."""
        return (
            f"{self.padrao} Apareceu {self.ocorrencias} vezes "
            f"Pode indicar -> {self.sugestao} ({self.taxa_acerto:.2f}%) "
            f"SG:{self.acertos_direto} G1:{self.acertos_gale1} "
            f"G2:{self.acertos_gale2} RED:{self.reds}"
        )


# =============================================================================
# ANALISADOR BASE
# =============================================================================
class PatternsAnalyzer:
    """
    Analisa o histórico de rodadas e extrai:
      - padrões de N cores consecutivas
      - padrões de N números
    Com estatísticas de próxima rodada (Gale 0/1/2).
    """

    def __init__(self, cores: List[str], pontos: List[int]) -> None:
        assert len(cores) == len(pontos), "cores e pontos devem ter o mesmo tamanho"
        self.cores = cores
        self.pontos = pontos

    # ------------------------------------------------------------------ cores
    def analisar_cores(
        self,
        tamanho: int = 4,
        min_ocorrencias: int = 4,
        min_assertividade: float = 85.0,
        usar_gale: int = 2,
    ) -> List[PatternStats]:
        """
        Procura sequências de `tamanho` cores que se repetem e calcula
        qual a próxima cor mais provável.
        """
        # Conta as sequências
        contagem: Dict[Tuple[str, ...], List[int]] = defaultdict(list)

        for i in range(len(self.cores) - tamanho):
            seq = tuple(self.cores[i : i + tamanho])
            idx_proxima = i + tamanho
            contagem[seq].append(idx_proxima)

        resultados: List[PatternStats] = []

        for seq, indices_proximas in contagem.items():
            if len(indices_proximas) < min_ocorrencias:
                continue

            # Descobre qual cor mais veio após essa sequência
            proximas_cores = [self.cores[i] for i in indices_proximas if i < len(self.cores)]
            if not proximas_cores:
                continue

            # Ignora TIE na votação principal
            votos = [c for c in proximas_cores if c in ("🔴", "🔵")]
            if len(votos) < min_ocorrencias:
                continue

            cont_r = votos.count("🔴")
            cont_b = votos.count("🔵")
            sugestao = "🔴" if cont_r >= cont_b else "🔵"

            # Analisa cada aparição: bateu direto, gale 1, gale 2 ou red
            sg = g1 = g2 = red = 0
            for idx in indices_proximas:
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

            ps = PatternStats(
                padrao="".join(seq),
                ocorrencias=len(indices_proximas),
                sugestao=sugestao,
                acertos_direto=sg,
                acertos_gale1=g1,
                acertos_gale2=g2,
                reds=red,
                amostra_min=min_ocorrencias,
            )

            if ps.taxa_acerto >= min_assertividade:
                resultados.append(ps)

        resultados.sort(key=lambda p: (p.taxa_acerto, p.ocorrencias), reverse=True)
        return resultados

    # --------------------------------------------------------------- números
    def analisar_numeros(
        self,
        min_ocorrencias: int = 4,
        min_assertividade: float = 85.0,
        usar_gale: int = 2,
    ) -> List[PatternStats]:
        """
        Analisa cada número individual (2..12) e qual a próxima cor
        mais provável quando ele sai.
        """
        # Agrupa posições por número
        posicoes_por_numero: Dict[int, List[int]] = defaultdict(list)
        for i, p in enumerate(self.pontos):
            posicoes_por_numero[p].append(i)

        resultados: List[PatternStats] = []

        for numero, posicoes in posicoes_por_numero.items():
            if len(posicoes) < min_ocorrencias:
                continue

            # Vê o que veio DEPOIS de cada ocorrência do número
            proximas = [self.cores[i + 1] for i in posicoes if i + 1 < len(self.cores)]
            votos = [c for c in proximas if c in ("🔴", "🔵")]
            if len(votos) < min_ocorrencias:
                continue

            cont_r = votos.count("🔴")
            cont_b = votos.count("🔵")
            sugestao = "🔴" if cont_r >= cont_b else "🔵"

            sg = g1 = g2 = red = 0
            for i in posicoes:
                r1 = self.cores[i + 1] if i + 1 < len(self.cores) else None
                r2 = self.cores[i + 2] if i + 2 < len(self.cores) else None
                r3 = self.cores[i + 3] if i + 3 < len(self.cores) else None

                if r1 == sugestao or r1 == "🟡":
                    sg += 1
                elif usar_gale >= 1 and (r2 == sugestao or r2 == "🟡"):
                    g1 += 1
                elif usar_gale >= 2 and (r3 == sugestao or r3 == "🟡"):
                    g2 += 1
                else:
                    red += 1

            ps = PatternStats(
                padrao=str(numero),
                ocorrencias=len(posicoes),
                sugestao=sugestao,
                acertos_direto=sg,
                acertos_gale1=g1,
                acertos_gale2=g2,
                reds=red,
                amostra_min=min_ocorrencias,
            )

            if ps.taxa_acerto >= min_assertividade:
                resultados.append(ps)

        resultados.sort(key=lambda p: (p.taxa_acerto, p.ocorrencias), reverse=True)
        return resultados

    # ------------------------------------------- sequência de 2 números
    def analisar_sequencia_numeros(
        self,
        tamanho: int = 2,
        min_ocorrencias: int = 3,
        min_assertividade: float = 80.0,
        usar_gale: int = 2,
    ) -> List[PatternStats]:
        """
        Analisa sequências de `tamanho` números (ex: 8→10, 6→8)
        e a próxima cor.
        """
        contagem: Dict[Tuple[int, ...], List[int]] = defaultdict(list)
        for i in range(len(self.pontos) - tamanho):
            seq = tuple(self.pontos[i : i + tamanho])
            contagem[seq].append(i + tamanho)

        resultados: List[PatternStats] = []

        for seq, indices in contagem.items():
            if len(indices) < min_ocorrencias:
                continue

            proximas = [self.cores[i] for i in indices if i < len(self.cores)]
            votos = [c for c in proximas if c in ("🔴", "🔵")]
            if len(votos) < min_ocorrencias:
                continue

            cont_r = votos.count("🔴")
            cont_b = votos.count("🔵")
            sugestao = "🔴" if cont_r >= cont_b else "🔵"

            sg = g1 = g2 = red = 0
            for i in indices:
                r1 = self.cores[i] if i < len(self.cores) else None
                r2 = self.cores[i + 1] if i + 1 < len(self.cores) else None
                r3 = self.cores[i + 2] if i + 2 < len(self.cores) else None

                if r1 == sugestao or r1 == "🟡":
                    sg += 1
                elif usar_gale >= 1 and (r2 == sugestao or r2 == "🟡"):
                    g1 += 1
                elif usar_gale >= 2 and (r3 == sugestao or r3 == "🟡"):
                    g2 += 1
                else:
                    red += 1

            ps = PatternStats(
                padrao="→".join(str(x) for x in seq),
                ocorrencias=len(indices),
                sugestao=sugestao,
                acertos_direto=sg,
                acertos_gale1=g1,
                acertos_gale2=g2,
                reds=red,
            )

            if ps.taxa_acerto >= min_assertividade:
                resultados.append(ps)

        resultados.sort(key=lambda p: (p.taxa_acerto, p.ocorrencias), reverse=True)
        return resultados
