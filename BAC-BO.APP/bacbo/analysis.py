"""Funções puras — sem estado, sem IO, totalmente testáveis."""
import re
from typing import Any, Dict, List, Optional, Tuple


def buscar_frequencia(
    lista_busca: List[str],
    padrao_procurado: List[str],
    lista_cores_ref: List[str],
    minimo_ocorrencias: int = 3,
) -> Tuple[float, float, int]:
    total, verm, azul = 0, 0, 0
    tam = len(padrao_procurado)

    for i in range(len(lista_busca) - tam):
        if lista_busca[i : i + tam] == padrao_procurado:
            proximo = lista_cores_ref[i + tam]
            total += 1
            if proximo == "🔴":
                verm += 1
            elif proximo == "🔵":
                azul += 1

    if total < minimo_ocorrencias:
        return 0.0, 0.0, total

    return (verm / total) * 100, (azul / total) * 100, total


def analisar_multi_amostra(
    historico_cores: List[str],
    historico_compostos: List[str],
    padroes_manuais: Dict[str, Dict[str, Any]],
    tamanho_p: int,
    sensibilidade: float,
) -> Tuple[Optional[str], float, float, Optional[str]]:
    min_oc = 3
    if len(historico_cores) < 5:
        return None, 0.0, 0.0, None

    # 1) Padrões fixos cadastrados manualmente
    for chave, item in padroes_manuais.items():
        if not item.get("ativo", True):
            continue
        padrao_fixo = item["padrao"]
        tam = len(padrao_fixo)
        if len(historico_cores) < tam:
            continue
        eh_composto = any(" " in str(e) for e in padrao_fixo)
        fatia = historico_compostos[-tam:] if eh_composto else historico_cores[-tam:]
        if fatia == padrao_fixo:
            return (
                item["sugestao"],
                100.0,
                100.0,
                f"📌 FIXO [{chave}]: {' | '.join(padrao_fixo)}",
            )

    # 2) Padrão composto dinâmico (cor + ponto)
    if len(historico_compostos) >= tamanho_p:
        pad = historico_compostos[-tamanho_p:]
        pr, pb, oc = buscar_frequencia(historico_compostos, pad, historico_cores, min_oc)
        if oc >= min_oc:
            s = " | ".join(pad)
            if pr >= sensibilidade:
                return "🔴", round(pr, 1), round(pr, 1), s
            if pb >= sensibilidade:
                return "🔵", round(pb, 1), round(pb, 1), s

    # 3) Padrão simples (só cor)
    if len(historico_cores) >= tamanho_p:
        pad = historico_cores[-tamanho_p:]
        pr30, pb30, _ = buscar_frequencia(historico_cores[-30:], pad, historico_cores, min_oc)
        prt, pbt, ocs = buscar_frequencia(historico_cores, pad, historico_cores, min_oc)
        if ocs >= min_oc:
            s = " | ".join(pad)
            if prt >= sensibilidade:
                return "🔴", round(pr30, 1), round(prt, 1), s
            if pbt >= sensibilidade:
                return "🔵", round(pb30, 1), round(pbt, 1), s

    return None, 0.0, 0.0, None


def processar_filtro_digitado(texto: str) -> Tuple[List[str], List[str]]:
    if not texto:
        return [], []
    t = texto.upper()
    entradas, pontos = [], []

    if any(k in t for k in ("RED", "BANKER", "🔴", "VERMELHO")):
        entradas.append("🔴 BANKER")
    if any(k in t for k in ("BLUE", "PLAYER", "🔵", "AZUL")):
        entradas.append("🔵 PLAYER")
    if any(k in t for k in ("YELLOW", "TIE", "TIER", "🟡", "EMPATE")):
        entradas.append("🟡 TIE")

    for num in re.findall(r"\b(1[0-2]|[1-9])\b", texto):
        pontos.append(num)

    return list(set(entradas)), list(set(pontos))