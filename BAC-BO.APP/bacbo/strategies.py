"""Estratégias puras de detecção de sinal."""
from collections import Counter
from typing import List, Optional


Sinal = tuple  # (sugestao, confianca, fonte, descricao)

PONTOS_RAROS = {10, 11, 12}


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
    cores: List[str], pontos: List[int], lookback: int = 50,
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
        return ("🔴", round(v / (v + a) * 100, 1), "ponto_regressao",
                f"Após ponto raro ({pontos[-1]}), 🔴 {v}/{v+a}")
    if a >= v * 1.4:
        return ("🔵", round(a / (v + a) * 100, 1), "ponto_regressao",
                f"Após ponto raro ({pontos[-1]}), 🔵 {a}/{v+a}")
    return None


def sinal_espelho(cores: List[str], janela: int = 4) -> Optional[Sinal]:
    if len(cores) < janela:
        return None
    ult = cores[-janela:]
    if ult != ult[::-1]:
        return None
    sugestao = "🔵" if ult[0] == "🔴" else "🔴"
    return (sugestao, 0.55, "espelho", f"Espelho {' '.join(ult)}")


def aplicar_confluencia(
    sinais: List[Sinal], min_ratio: float = 0.66,
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