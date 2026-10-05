"""Estratégias específicas para TIE — análise de intervalos."""
from collections import Counter
from typing import Any, Dict, List, Optional

Sinal = tuple  # (sugestao, confianca, fonte, descricao)


def analisar_intervalos_tie(
    cores: List[str],
    ultimas_n: int = 1000,
) -> Dict[str, Any]:
    """
    Analisa o histórico de TIE e retorna estatísticas completas dos intervalos.

    Retorna:
      - total_ties: nº de TIE na amostra
      - indices_tie: posições dos TIE
      - intervalos: lista de gaps entre TIE consecutivos
      - media_intervalo: média dos gaps
      - mediana_intervalo: mediana (mais robusta a outliers)
      - ultimo_intervalo: rodadas desde o último TIE
      - intervalos_frequentes: top 10 gaps mais comuns
      - alerta: True se estamos perto do próximo TIE previsto
      - rodadas_para_proximo: quantas rodadas faltam (baseado na média)
      - proximos_intervalos: lista de "alvos" para vigiar
    """
    if not cores:
        return _vazio()

    ultimas = cores[-ultimas_n:] if ultimas_n > 0 else cores
    indices_tie = [i for i, c in enumerate(ultimas) if c == "🟡"]

    if len(indices_tie) < 2:
        return {
            **_vazio(),
            "total_ties": len(indices_tie),
        }

    # Calcula intervalos entre TIE consecutivos
    intervalos = [
        indices_tie[i] - indices_tie[i - 1]
        for i in range(1, len(indices_tie))
    ]

    # Estatísticas
    media = sum(intervalos) / len(intervalos)
    intervalos_ordenados = sorted(intervalos)
    mediana = intervalos_ordenados[len(intervalos_ordenados) // 2]

    # Último intervalo: rodadas desde o último TIE até AGORA
    ultimo = len(ultimas) - 1 - indices_tie[-1]

    # Frequência dos intervalos (top 10)
    contagem = Counter(intervalos)
    intervalos_frequentes = contagem.most_common(10)

    # Alerta: estamos no intervalo previsto?
    # Se o último intervalo >= média - 1, é provável que o próximo venha logo
    alerta = ultimo >= (media - 1)

    # Quantas rodadas faltam
    rodadas_para_proximo = max(0, int(round(media - ultimo)))

    # Próximos intervalos alvo (média, mediana, e os mais comuns)
    proximos_intervalos = sorted(set([
        int(round(media)),
        mediana,
        *[k for k, _ in intervalos_frequentes[:5]],
    ]))

    return {
        "total_ties": len(indices_tie),
        "indices_tie": indices_tie,
        "intervalos": intervalos,
        "media_intervalo": round(media, 1),
        "mediana_intervalo": mediana,
        "ultimo_intervalo": ultimo,
        "intervalos_frequentes": intervalos_frequentes,
        "alerta": alerta,
        "rodadas_para_proximo": rodadas_para_proximo,
        "proximos_intervalos": proximos_intervalos,
        "total_rodadas": len(ultimas),
    }

def sinal_tie_intervalo(
    cores: List[str],
    ultimas_n: int = 1000,
    tolerancia: int = 2,
) -> Optional[Sinal]:
    """
    Gera sinal de entrada em 🟡 TIE quando estamos na janela provável
    do próximo TIE.

    Lógica:
      - Se `ultimo >= media - tolerancia`, o TIE está próximo
      - Confiança maior quanto mais próximo (ou passado) da média
      - Se `ultimo > media + tolerancia`, ainda é válido (TIE atrasado = iminente)
    """
    info = analisar_intervalos_tie(cores, ultimas_n)

    if not info.get("alerta"):
        return None

    ultimo = info.get("ultimo_intervalo", 0)
    media = info.get("media_intervalo", 0)
    mediana = info.get("mediana_intervalo", 0)
    total_ties = info.get("total_ties", 0)

    if total_ties < 2 or media == 0:
        return None

    # Se ainda está muito longe (antes da janela), não sugere
    if ultimo < (media - tolerancia):
        return None

    # Confiança: quanto mais próximo/acima da média, maior
    # Se ultimo >= media → confiança alta (TIE atrasado)
    if ultimo >= media:
        # Atrasado ou no ponto: confiança máxima
        confianca = 90.0 + min(5.0, (ultimo - media) * 0.5)
    else:
        # Ainda um pouco antes, mas na janela de tolerância
        diff = media - ultimo
        confianca = 90.0 - (diff * 10)

    confianca = max(65.0, min(95.0, confianca))

    descricao = (
        f"TIE há {ultimo} rodadas (média: {media:.0f}, "
        f"mediana: {mediana}) · {total_ties} TIE em {info.get('total_rodadas', 0)}"
    )

    return ("🟡", round(confianca, 1), "tie_intervalo", descricao)

def _vazio() -> Dict[str, Any]:
    return {
        "total_ties": 0,
        "indices_tie": [],
        "intervalos": [],
        "media_intervalo": 0,
        "mediana_intervalo": 0,
        "ultimo_intervalo": 0,
        "intervalos_frequentes": [],
        "alerta": False,
        "rodadas_para_proximo": 0,
        "proximos_intervalos": [],
        "total_rodadas": 0,
    }