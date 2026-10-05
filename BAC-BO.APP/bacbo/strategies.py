"""Estratégias puras de detecção de sinal."""

from collections import Counter
from typing import List, Optional

Sinal = tuple  # (sugestao, confianca, fonte, descricao)

PONTOS_RAROS = {10, 11, 12}


# =============================================================================
# DETECTORES EXISTENTES
# =============================================================================

def detectar_streak(cores: List[str], n_min: int = 4) -> Optional[str]:
    if len(cores) < n_min:
        return None
    ultima = cores[-1]
    if ultima == "🟡":
        return None
    count = 0
    for c in reversed(cores):
        if c == ultima:
            count += 1
        elif c == "🟡":
            continue
        else:
            break
    return ultima if count >= n_min else None


def sinal_streak_fade(cores: List[str], n_min: int = 4) -> Optional[Sinal]:
    dominante = detectar_streak(cores, n_min)
    if not dominante:
        return None
    fade = "🔵" if dominante == "🔴" else "🔴"
    return (fade, 0.60, "streak_fade", f"Fade após streak de {dominante}")


def sinal_ponto_regressao(
    cores: List[str],
    pontos: List[int],
    lookback: int = 50,
) -> Optional[Sinal]:
    if len(pontos) < 3 or pontos[-1] not in PONTOS_RAROS:
        return None

    cores_win = cores[-lookback:]
    pontos_win = pontos[-lookback:]

    seguintes = []
    for i in range(len(pontos_win) - 1):
        if pontos_win[i] in PONTOS_RAROS:
            seguintes.append(cores_win[i + 1])

    if len(seguintes) < 3:
        return None

    v = seguintes.count("🔴")
    a = seguintes.count("🔵")
    if v + a < 3:
        return None

    if v >= a * 1.4:
        return (
            "🔴",
            round(v / (v + a) * 100, 1),
            "ponto_regressao",
            f"Após ponto raro ({pontos[-1]}), 🔴 {v}/{v+a}",
        )
    if a >= v * 1.4:
        return (
            "🔵",
            round(a / (v + a) * 100, 1),
            "ponto_regressao",
            f"Após ponto raro ({pontos[-1]}), 🔵 {a}/{v+a}",
        )
    return None


def sinal_espelho(cores: List[str], janela: int = 4) -> Optional[Sinal]:
    if len(cores) < janela:
        return None
    ult = cores[-janela:]
    if ult != ult[::-1]:
        return None
    sugestao = "🔵" if ult[0] == "🔴" else "🔴"
    return (sugestao, 0.55, "espelho", f"Espelho {' '.join(ult)}")


# =============================================================================
# NOVOS DETECTORES (Etapa 2)
# =============================================================================

def sinal_sanduiche(cores: List[str], min_ocorrencias: int = 3) -> Optional[Sinal]:
    """Detecta padrão sanduíche (X-Y-X) nas últimas 3 rodadas."""
    if len(cores) < 5:
        return None

    a, b, c = cores[-3], cores[-2], cores[-1]
    if a == "🟡" or b == "🟡" or c == "🟡":
        return None
    if a != c or a == b:
        return None

    ocorrencias = 0
    votos = {"🔴": 0, "🔵": 0}
    for i in range(len(cores) - 3):
        if cores[i] == a and cores[i + 1] == b and cores[i + 2] == a:
            proximo = cores[i + 3] if i + 3 < len(cores) else None
            if proximo in ("🔴", "🔵"):
                ocorrencias += 1
                votos[proximo] += 1

    if ocorrencias < min_ocorrencias:
        return None

    v = votos["🔴"]
    a_count = votos["🔵"]
    if v + a_count < min_ocorrencias:
        return None

    cor = "🔴" if v >= a_count else "🔵"
    conf = (max(v, a_count) / (v + a_count)) * 100
    return (
        cor,
        round(conf, 1),
        "sanduiche",
        f"Sanduíche {' '.join([a, b, c])} → {cor} ({max(v, a_count)}/{v+a_count})",
    )


def sinal_repeticao_numerica(
    cores: List[str],
    pontos: List[int],
    min_ocorrencias: int = 3,
) -> Optional[Sinal]:
    """Detecta quando o MESMO ponto sai 2x seguidas."""
    if len(pontos) < 4 or len(cores) < 4:
        return None

    if pontos[-1] != pontos[-2]:
        return None

    ponto_repetido = pontos[-1]
    ocorrencias = 0
    votos = {"🔴": 0, "🔵": 0}
    for i in range(len(pontos) - 2):
        if pontos[i] == ponto_repetido and pontos[i + 1] == ponto_repetido:
            proximo = cores[i + 2] if i + 2 < len(cores) else None
            if proximo in ("🔴", "🔵"):
                ocorrencias += 1
                votos[proximo] += 1

    if ocorrencias < min_ocorrencias:
        return None

    v = votos["🔴"]
    a = votos["🔵"]
    if v + a < min_ocorrencias:
        return None

    cor = "🔴" if v >= a else "🔵"
    conf = (max(v, a) / (v + a)) * 100
    return (
        cor,
        round(conf, 1),
        "repeticao_numerica",
        f"Ponto {ponto_repetido} repetiu → {cor} ({max(v, a)}/{v+a})",
    )


def sinal_ciclo_curto(
    cores: List[str],
    tamanho: int = 3,
    min_ocorrencias: int = 3,
) -> Optional[Sinal]:
    """Detecta ciclos curtos que se repetem."""
    if len(cores) < tamanho * 3:
        return None

    padrao_atual = cores[-tamanho:]
    if "🟡" in padrao_atual:
        return None

    ocorrencias = 0
    votos = {"🔴": 0, "🔵": 0}
    for i in range(len(cores) - tamanho):
        if cores[i : i + tamanho] == padrao_atual:
            proximo = cores[i + tamanho] if i + tamanho < len(cores) else None
            if proximo in ("🔴", "🔵"):
                ocorrencias += 1
                votos[proximo] += 1

    if ocorrencias < min_ocorrencias:
        return None

    v = votos["🔴"]
    a = votos["🔵"]
    if v + a < min_ocorrencias:
        return None

    cor = "🔴" if v >= a else "🔵"
    conf = (max(v, a) / (v + a)) * 100
    return (
        cor,
        round(conf, 1),
        "ciclo_curto",
        f"Ciclo {' '.join(padrao_atual)} → {cor} ({max(v, a)}/{v+a})",
    )


def sinal_zona_tie(
    cores: List[str],
    min_ties_janela: int = 3,
    janela: int = 10,
) -> Optional[Sinal]:
    """Se 3+ TIE nas últimas 10 rodadas → alto risco de TIE."""
    if len(cores) < janela:
        return None

    ultimas = cores[-janela:]
    qtd_tie = ultimas.count("🟡")

    if qtd_tie < min_ties_janela:
        return None

    votos = {"🔴": 0, "🔵": 0}
    for i in range(len(cores) - 1):
        if cores[i] == "🟡":
            proximo = cores[i + 1]
            if proximo in ("🔴", "🔵"):
                votos[proximo] += 1

    total = votos["🔴"] + votos["🔵"]
    if total < 3:
        return None

    v = votos["🔴"]
    a = votos["🔵"]
    cor = "🔴" if v >= a else "🔵"
    conf = (max(v, a) / total) * 100
    return (
        cor,
        round(conf, 1),
        "zona_tie",
        f"{qtd_tie} TIE em {janela} → após TIE, {cor} ({max(v, a)}/{total})",
    )


def sinal_forca_lado(
    cores: List[str],
    janela: int = 5,
    limiar: int = 4,
) -> Optional[Sinal]:
    """Segue o lado dominante nas últimas rodadas."""
    if len(cores) < janela:
        return None

    ultimas = cores[-janela:]
    v = ultimas.count("🔴")
    a = ultimas.count("🔵")

    if v >= limiar and v > a:
        conf = (v / janela) * 100
        return (
            "🔴",
            round(conf, 1),
            "forca_lado",
            f"🔴 {v}/{janela} → continuar 🔴",
        )
    if a >= limiar and a > v:
        conf = (a / janela) * 100
        return (
            "🔵",
            round(conf, 1),
            "forca_lado",
            f"🔵 {a}/{janela} → continuar 🔵",
        )

    return None


# =============================================================================
# CONFLUÊNCIA
# =============================================================================

def aplicar_confluencia(
    sinais: List[Sinal],
    min_ratio: float = 0.66,
) -> Optional[Sinal]:
    validos = [s for s in sinais if s is not None]
    if len(validos) < 2:
        return None

    contagem = Counter(s[0] for s in validos)
    cor, qtd = contagem.most_common(1)[0]
    if qtd / len(validos) < min_ratio:
        return None

    mesma_cor = [s for s in validos if s[0] == cor]
    confianca = sum(s[1] for s in mesma_cor) / len(mesma_cor)
    fontes = "+".join(sorted({s[2] for s in mesma_cor}))
    descricoes = " ‖ ".join(s[3] for s in mesma_cor)
    return (cor, round(confianca, 1), f"confluencia[{fontes}]", descricoes)