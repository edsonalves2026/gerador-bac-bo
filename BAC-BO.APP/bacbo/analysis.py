"""Funções puras — sem estado, sem IO, totalmente testáveis.

Este módulo concentra a lógica de detecção de padrões:
- buscar_frequencia: conta ocorrências e devolve probabilidades
- analisar_multi_amostra: detector principal (padrões fixos + dinâmicos + AUTO_*)
- processar_filtro_digitado: parse do input do relatório manual
"""

import re
from typing import Any, Dict, List, Optional, Tuple

# =============================================================================
# CONSTANTES
# =============================================================================
MIN_OCORRENCIAS_PADRAO = 3
TAMANHO_JANELA_CURTA = 30  # usada no "prob 30" (curto prazo)
CORES_VALIDAS = ("🔴", "🔵", "🟡")


# =============================================================================
# BUSCA DE FREQUÊNCIA
# =============================================================================
def buscar_frequencia(
    lista_busca: List[str],
    padrao_procurado: List[str],
    lista_cores_ref: List[str],
    minimo_ocorrencias: int = MIN_OCORRENCIAS_PADRAO,
) -> Tuple[float, float, int]:
    """
    Conta quantas vezes `padrao_procurado` aparece em `lista_busca` e mede
    a cor que veio logo depois em `lista_cores_ref`.

    As duas listas DEVEM estar alinhadas por índice (ambas em ordem cronológica
    crescente). Retorna (prob_vermelho, prob_azul, total_ocorrencias).
    Se `total < minimo_ocorrencias`, as probabilidades são zeradas — mas o
    `total` continua sendo retornado para o caller decidir.
    """
    total, verm, azul = 0, 0, 0
    tam = len(padrao_procurado)

    # Guard: só precisa que lista_busca tenha ao menos `tam` elementos
    # (o "próximo" vem de lista_cores_ref, que pode ter o mesmo tamanho).
    if tam == 0 or len(lista_busca) < tam or len(lista_cores_ref) < tam:
        return 0.0, 0.0, 0

    for i in range(len(lista_busca) - tam + 1):
        if lista_busca[i : i + tam] == padrao_procurado:
            idx_prox = i + tam
            if idx_prox >= len(lista_cores_ref):
                break
            proximo = lista_cores_ref[idx_prox]
            total += 1
            if proximo == "🔴":
                verm += 1
            elif proximo == "🔵":
                azul += 1
            # TIE não conta como acerto de vermelho nem azul

    if total < minimo_ocorrencias:
        return 0.0, 0.0, total

    return (verm / total) * 100, (azul / total) * 100, total


# =============================================================================
# DETECTORES AUXILIARES (AUTO_*)
# =============================================================================
def _detectar_auto_cor(
    cores: List[str],
    padroes_manuais: Dict[str, Dict[str, Any]],
) -> Optional[Tuple[str, float, float, str]]:
    """
    Verifica padrões cadastrados automaticamente pelo patterns_analyzer
    (chave começando com 'AUTO_COR_'). Retorna o primeiro match.
    """
    if not padroes_manuais:
        return None

    for chave, item in padroes_manuais.items():
        if not chave.startswith("AUTO_COR_"):
            continue
        if not item.get("ativo", True):
            continue

        seq = item.get("padrao") or []
        tam = len(seq)
        if tam == 0 or len(cores) < tam:
            continue

        if cores[-tam:] == seq:
            return (
                item["sugestao"],
                95.0,
                95.0,
                f"🎯 AUTO_COR [{chave}]: {' '.join(seq)}",
            )
    return None


def _detectar_auto_num(
    pontos: List[int],
    padroes_manuais: Dict[str, Dict[str, Any]],
) -> Optional[Tuple[str, float, float, str]]:
    """
    Verifica se o ÚLTIMO número bateu com algum padrão AUTO_NUM_* cadastrado.
    """
    if not padroes_manuais or not pontos:
        return None

    ultimo = str(pontos[-1])
    chave = f"AUTO_NUM_{ultimo}"

    item = padroes_manuais.get(chave)
    if not item or not item.get("ativo", True):
        return None

    return (
        item["sugestao"],
        90.0,
        90.0,
        f"🎯 AUTO_NUM [{chave}]: após número {ultimo}",
    )

    # -------- 3b) AUTO_SEQ_* (sequências de números) --------
    if historico_pontos:
        for chave, item in padroes_manuais.items():
            if not chave.startswith("AUTO_SEQ_"):
                continue
            if not item.get("ativo", True):
                continue

            seq = item.get("padrao") or []
            tam = len(seq)
            if tam == 0 or len(historico_pontos) < tam:
                continue

            # Converte os últimos pontos para string para comparar
            ultimos_str = [str(p) for p in historico_pontos[-tam:]]
            if ultimos_str == [str(x) for x in seq]:
                return (
                    item["sugestao"],
                    90.0,
                    90.0,
                    f"🎯 AUTO_SEQ [{chave}]: após {'→'.join(str(x) for x in seq)}",
                )

# =============================================================================
# DETECTOR PRINCIPAL
# =============================================================================
def analisar_multi_amostra(
    historico_cores: List[str],
    historico_compostos: List[str],
    padroes_manuais: Optional[Dict[str, Dict[str, Any]]] = None,
    tamanho_p: int = 3,
    sensibilidade: float = 65.0,
    historico_pontos: Optional[List[int]] = None,
) -> Tuple[Optional[str], float, float, Optional[str]]:
    """
    Detector principal. Retorna (sugestao, prob_curta, prob_total, descricao).

    Ordem de prioridade:
      1) Padrões fixos manuais (match exato no fim do histórico)
      2) Padrões AUTO_COR_* (sequência exata)
      3) Padrões AUTO_NUM_* (número que acabou de sair)
      4) Padrão composto dinâmico (cor + ponto)
      5) Padrão simples dinâmico (só cor)

    Retorna (None, 0.0, 0.0, None) se nenhum padrão atingir a sensibilidade.
    """
    padroes_manuais = padroes_manuais or {}
    min_oc = MIN_OCORRENCIAS_PADRAO

    if len(historico_cores) < 5:
        return None, 0.0, 0.0, None

    # -------- 1) Padrões fixos cadastrados manualmente --------
    for chave, item in padroes_manuais.items():
        # AUTO_* tem detector próprio abaixo
        if chave.startswith("AUTO_"):
            continue
        if not item.get("ativo", True):
            continue

        padrao_fixo = item.get("padrao") or []
        tam = len(padrao_fixo)
        if tam == 0 or len(historico_cores) < tam:
            continue

        # Detecta se o padrão é composto (contém ponto) ou só cor
        eh_composto = any(" " in str(e) for e in padrao_fixo)
        fatia = (
            historico_compostos[-tam:]
            if eh_composto and len(historico_compostos) >= tam
            else historico_cores[-tam:]
        )

        if fatia == padrao_fixo:
            return (
                item["sugestao"],
                100.0,
                100.0,
                f"📌 FIXO [{chave}]: {' | '.join(str(x) for x in padrao_fixo)}",
            )

    # -------- 2) AUTO_COR_* (sequência exata no fim) --------
    r = _detectar_auto_cor(historico_cores, padroes_manuais)
    if r:
        return r

    # -------- 3) AUTO_NUM_* (último número saiu) --------
    if historico_pontos:
        r = _detectar_auto_num(historico_pontos, padroes_manuais)
        if r:
            return r

    # -------- 4) Padrão composto dinâmico (cor + ponto) --------
    if len(historico_compostos) >= tamanho_p:
        pad = historico_compostos[-tamanho_p:]
        pr, pb, oc = buscar_frequencia(
            historico_compostos, pad, historico_cores, min_oc
        )
        if oc >= min_oc:
            descricao = " | ".join(pad)
            if pr >= sensibilidade and pr >= pb:
                return "🔴", round(pr, 1), round(pr, 1), descricao
            if pb >= sensibilidade and pb > pr:
                return "🔵", round(pb, 1), round(pb, 1), descricao

    # -------- 5) Padrão simples dinâmico (só cor) --------
    if len(historico_cores) >= tamanho_p:
        pad = historico_cores[-tamanho_p:]

        # Probabilidade de curto prazo (últimas 30 rodadas)
        pr30, pb30, _ = buscar_frequencia(
            historico_cores[-TAMANHO_JANELA_CURTA:], pad, historico_cores, min_oc
        )
        # Probabilidade histórica total
        prt, pbt, ocs = buscar_frequencia(historico_cores, pad, historico_cores, min_oc)

        if ocs >= min_oc:
            descricao = " | ".join(pad)
            if prt >= sensibilidade and prt >= pbt:
                return "🔴", round(pr30, 1), round(prt, 1), descricao
            if pbt >= sensibilidade and pbt > prt:
                return "🔵", round(pb30, 1), round(pbt, 1), descricao

    return None, 0.0, 0.0, None


# =============================================================================
# PARSE DO FILTRO DIGITADO (relatório manual)
# =============================================================================
def processar_filtro_digitado(texto: str) -> Tuple[List[str], List[str]]:
    """
    Interpreta o texto do usuário no relatório manual. Aceita:
      - "PLAYER" / "BANKER" / "TIE" / "EMPATE" / "AZUL" / "VERMELHO"
      - Emojis 🔴 🔵 🟡
      - Números de 2 a 12 (Bac Bo real; "1" e "13" são ignorados)
    Retorna (entradas, pontos) já deduplicados.
    """
    if not texto:
        return [], []

    t = texto.upper()
    entradas: List[str] = []
    pontos: List[str] = []

    if any(k in t for k in ("RED", "BANKER", "🔴", "VERMELHO")):
        entradas.append("🔴 BANKER")
    if any(k in t for k in ("BLUE", "PLAYER", "🔵", "AZUL")):
        entradas.append("🔵 PLAYER")
    if any(k in t for k in ("YELLOW", "TIE", "TIER", "🟡", "EMPATE")):
        entradas.append("🟡 TIE")

    # Números válidos de Bac Bo: 2 a 12
    for num in re.findall(r"\b(\d{1,2})\b", texto):
        try:
            n = int(num)
        except ValueError:
            continue
        if 2 <= n <= 12:
            pontos.append(str(n))

    return sorted(set(entradas)), sorted(set(pontos))


# =============================================================================
# HELPERS DE COMPATIBILIDADE (mantidos para imports antigos)
# =============================================================================
def sugestao_para_nome(sugestao: str) -> str:
    """Converte '🔴' → '🔴 BANKER', etc. Útil para mensagens."""
    return {
        "🔴": "🔴 BANKER",
        "🔵": "🔵 PLAYER",
        "🟡": "🟡 TIE",
    }.get(sugestao, "—")


def nome_para_sugestao(nome: str) -> Optional[str]:
    """Inverso de sugestao_para_nome."""
    nome_u = nome.upper()
    if "BANKER" in nome_u or "VERMELHO" in nome_u:
        return "🔴"
    if "PLAYER" in nome_u or "AZUL" in nome_u:
        return "🔵"
    if "TIE" in nome_u or "EMPATE" in nome_u:
        return "🟡"
    return None
