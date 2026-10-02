"""Tabela Bac Bo — grade visual das últimas N rodadas.

Layout:
  1) Grade principal: 22 colunas × 6 linhas = 132 células
     Preenchimento VERTICAL (topo→base, esquerda→direita).
     Rodada mais recente fica na PRIMEIRA célula (topo-esquerda).
  2) Histórico: mesma grade, preenchendo da DIREITA para a ESQUERDA.
     Rodada mais recente fica na ÚLTIMA célula da primeira linha.
"""
from typing import List, Optional, Tuple

import streamlit as st


# =============================================================================
# CONSTANTES
# =============================================================================
COR_HEX = {
    "🔴": "#ef4444",
    "🔵": "#3b82f6",
    "🟡": "#eab308",
}

GRADE_COLS = 22
GRADE_ROWS = 6
GRADE_TOTAL = GRADE_COLS * GRADE_ROWS   # 132

TAM_CELULA_PX = 30
GAP_PX = 3


# =============================================================================
# API PÚBLICA
# =============================================================================
def renderizar_tabela_bacbo(worker, num_rodadas: int = 200) -> None:
    """Renderiza grade + histórico + estatísticas (fonte: SQLite local)."""
    st.markdown("### 🎰 Tabela Bac Bo")

    # ---- Busca do SQLite local (sempre disponível, sem limite de API) ----
    try:
        rows = worker.db.carregar_rodadas(
            mesa_id=worker.config.mesa_id,
            limite=int(num_rodadas),
        )
    except Exception as e:
        st.error(f"❌ Erro ao carregar rodadas do banco: {e}")
        return

    if not rows:
        st.info(
            "Sem rodadas no banco local ainda. "
            "O robô precisa rodar alguns minutos para acumular dados."
        )
        return

    # Separa em cores e pontos
    cores = [r[0] for r in rows]
    pontos = [r[1] for r in rows]

    total = len(cores)
    cor_dom = _cor_dominante(cores)

    # ---- Cabeçalho dinâmico ----
    total_banco = worker.db.total_rodadas(worker.config.mesa_id)

    col_info1, col_info2 = st.columns([3, 2])
    with col_info1:
        st.caption(
            f"**Exibindo {total} rodadas** "
            f"(de {total_banco} no banco) · cor dominante: **{cor_dom}**"
        )
    with col_info2:
        st.caption(
            f"Grade principal: **{GRADE_ROWS}×{GRADE_COLS}** "
            f"= {GRADE_TOTAL} células"
        )

    # ---- 1) Grade principal (22×6) ----
    st.markdown("##### 📋 Grade Principal")
    st.caption(
        "Nova rodada entra no **canto inferior-direito** e preenche de baixo para cima"
    )
    _render_grade(
        cores=cores,
        pontos=pontos,
        total_celulas=GRADE_TOTAL,
        cols=GRADE_COLS,
        ordem="vertical_baixo_direita_para_esquerda",
    )

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # ---- 2) Histórico (usa a quantidade exata do slider) ----
    st.markdown("##### 📜 Histórico (mais recente à direita)")
    st.caption(
        f"Nova rodada entra na **primeira linha, à direita**. "
        f"Exibindo as últimas **{total}** rodadas."
    )
    _render_grade(
        cores=cores,
        pontos=pontos,
        total_celulas=len(cores),
        cols=GRADE_COLS,
        ordem="horizontal_direita_para_esquerda",
    )

    # ---- Legenda ----
    st.caption("🔴 BANKER · 🔵 PLAYER · 🟡 TIE")

    # ---- Distribuição ----
    _render_distribuicao(cores)

# =============================================================================
# RENDER DE UMA GRADE
# =============================================================================
def _render_grade(
    cores: List[str],
    pontos: List[int],
    total_celulas: int,
    cols: int,
    ordem: str,
) -> None:
    """
    Renderiza uma grade de `cols` colunas com `total_celulas` elementos.

    ordem:
      - "vertical_baixo_direita_para_esquerda":
          Grade Principal. Preenche coluna por coluna, DE BAIXO PARA CIMA,
          da DIREITA para a ESQUERDA. Nova rodada entra no canto inferior-direito.

      - "horizontal_direita_para_esquerda":
          Histórico. Preenche linha por linha, na PRIMEIRA LINHA, da DIREITA
          para a ESQUERDA. Nova rodada entra no canto superior-direito.
    """
    # Pega as últimas `total_celulas` rodadas (mais novas primeiro)
    pares = list(
        zip(
            reversed(cores[-total_celulas:]),
            reversed(pontos[-total_celulas:]),
        )
    )
    # Ajusta para exatamente `total_celulas`
    while len(pares) < total_celulas:
        pares.append((None, None))

    rows = (total_celulas + cols - 1) // cols
    visual = [None] * (rows * cols)

    if ordem == "vertical_baixo_direita_para_esquerda":
        # Preenche coluna por coluna, de baixo para cima,
        # começando pela coluna mais à DIREITA.
        for idx, item in enumerate(pares):
            if idx >= rows * cols:
                break
            col_from_left = cols - 1 - (idx // rows)   # direita → esquerda
            row = rows - 1 - (idx % rows)              # baixo → cima
            visual[row * cols + col_from_left] = item

    elif ordem == "horizontal_direita_para_esquerda":
        # Preenche linha por linha, da DIREITA para a ESQUERDA,
        # começando pela PRIMEIRA linha (topo).
        for idx, item in enumerate(pares):
            if idx >= rows * cols:
                break
            row = idx // cols                            # topo → base
            col_from_left = cols - 1 - (idx % cols)      # direita → esquerda
            visual[row * cols + col_from_left] = item

    else:
        raise ValueError(f"Ordem desconhecida: {ordem}")

    # ---- Monta HTML ----
    html = [
        "<div style='"
        "background:#0e0e15;padding:12px;border-radius:10px;"
        "border:1px solid #2a2a35;overflow-x:auto;"
        "font-family:-apple-system,Segoe UI,sans-serif;"
        "'>",
        f"<div style='display:grid;"
        f"grid-template-columns:repeat({cols},{TAM_CELULA_PX}px);"
        f"gap:{GAP_PX}px;"
        f"justify-content:flex-start;"
        f"'>",
    ]

    for item in visual:
        if item is None:
            cor, ponto = None, None
        else:
            cor, ponto = item

        if cor is None:
            html.append(
                f"<div style='"
                f"width:{TAM_CELULA_PX}px;height:{TAM_CELULA_PX}px;"
                f"border-radius:50%;background:#1a1a1e;"
                f"border:1px solid #222;"
                f"'></div>"
            )
        else:
            bg = COR_HEX.get(cor, "#666")
            html.append(
                f"<div style='"
                f"width:{TAM_CELULA_PX}px;height:{TAM_CELULA_PX}px;"
                f"border-radius:50%;background:{bg};color:#fff;"
                f"display:flex;align-items:center;justify-content:center;"
                f"font-size:12px;font-weight:700;"
                f"box-shadow:0 0 0 1px rgba(0,0,0,0.35);"
                f"'>{ponto}</div>"
            )

    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)

# =============================================================================
# DISTRIBUIÇÃO / ESTATÍSTICAS RÁPIDAS
# =============================================================================
def _render_distribuicao(cores: List[str]) -> None:
    total = len(cores)
    if total == 0:
        return

    cont_r = cores.count("🔴")
    cont_b = cores.count("🔵")
    cont_t = cores.count("🟡")

    st.markdown("##### 📊 Distribuição das Rodadas Exibidas")
    c1, c2, c3 = st.columns(3)
    c1.metric(
        "🔴 BANKER", f"{cont_r}",
        f"{(cont_r / total * 100):.1f}%",
    )
    c2.metric(
        "🔵 PLAYER", f"{cont_b}",
        f"{(cont_b / total * 100):.1f}%",
    )
    c3.metric(
        "🟡 TIE", f"{cont_t}",
        f"{(cont_t / total * 100):.1f}%",
    )


# =============================================================================
# HELPERS
# =============================================================================
def _cor_dominante(cores: List[str]) -> str:
    """Retorna a cor mais frequente com porcentagem."""
    if not cores:
        return "—"
    contagem = {c: cores.count(c) for c in ("🔴", "🔵", "🟡")}
    cor, n = max(contagem.items(), key=lambda kv: kv[1])
    pct = (n / len(cores)) * 100
    return f"{cor} ({pct:.1f}%)"