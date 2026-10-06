"""Grade Principal com barras de proporção horizontais (estilo da imagem).

Grade em 22 colunas × 6 linhas, preenchimento:
- Nova rodada entra no canto INFERIOR-DIREITO
- Sobe pela coluna (baixo → cima)
- Vai para a coluna anterior (direita → esquerda)
"""
from typing import List

import streamlit as st


COR_HEX = {
    "🔴": "#ef4444",
    "🔵": "#3b82f6",
    "🟡": "#eab308",
}

TAM_CELULA = 28      # ← reduzido de 32 para 28
GAP_CELULA = 3


def renderizar_grade_horizontal(
    cores: List[str],
    pontos: List[int],
    cols: int = 22,
    rows: int = 6,
) -> None:
    if not cores:
        st.info("Sem rodadas para exibir.")
        return

    total = len(cores)
    cont_r = cores.count("🔴")
    cont_b = cores.count("🔵")
    cont_t = cores.count("🟡")

    pct_r = (cont_r / total) * 100 if total else 0
    pct_b = (cont_b / total) * 100 if total else 0
    pct_t = (cont_t / total) * 100 if total else 0

    # ---- Barra de proporção ----
    _render_barra_proporcao(pct_b, pct_t, pct_r)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    # ---- Layout: grade (mais larga) + coluna de %s (compacta) ----
    # Proporção ajustada: [5, 2] dá mais espaço para a grade
    # E usamos [7, 2] se a tela for pequena? Vamos tentar [5, 2]
    col_grade, col_pct = st.columns([6, 2], gap="small")

    with col_grade:
        _render_grade(cores, pontos, cols, rows)

    with col_pct:
        _render_porcentagens_por_linha(cores, cols, rows)


def _render_barra_proporcao(pct_b: float, pct_t: float, pct_r: float) -> None:
    """Renderiza a barra horizontal tri-color."""
    html = (
        '<div style="'
        'display:flex;'
        'height:44px;'
        'border-radius:8px;'
        'overflow:hidden;'
        'font-family:-apple-system,Segoe UI,sans-serif;'
        'font-weight:700;'
        'font-size:15px;'
        'color:#fff;'
        'box-shadow:0 2px 8px rgba(0,0,0,0.3);'
        '">'
    )

    if pct_b > 0:
        html += (
            f'<div style="width:{pct_b}%;'
            f'background:linear-gradient(135deg,#3b82f6,#2563eb);'
            f'display:flex;align-items:center;justify-content:center;">'
            f'{pct_b:.0f}%</div>'
        )
    if pct_t > 0:
        html += (
            f'<div style="width:{pct_t}%;'
            f'background:linear-gradient(135deg,#eab308,#ca8a04);'
            f'display:flex;align-items:center;justify-content:center;'
            f'font-size:12px;">'
            f'{pct_t:.0f}%</div>'
        )
    if pct_r > 0:
        html += (
            f'<div style="width:{pct_r}%;'
            f'background:linear-gradient(135deg,#ef4444,#dc2626);'
            f'display:flex;align-items:center;justify-content:center;">'
            f'{pct_r:.0f}%</div>'
        )

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _preparar_grid(
    cores: List[str], pontos: List[int], cols: int, rows: int,
):
    """
    Retorna matriz [rows][cols] com as rodadas distribuídas.
    Nova rodada entra no canto INFERIOR-DIREITO.
    """
    total_celulas = cols * rows

    cores_uso = list(cores[-total_celulas:])
    pontos_uso = list(pontos[-total_celulas:])

    while len(cores_uso) < total_celulas:
        cores_uso.insert(0, None)
        pontos_uso.insert(0, None)

    cores_recentes = list(reversed(cores_uso))
    pontos_recentes = list(reversed(pontos_uso))

    grade = [[None] * cols for _ in range(rows)]

    for idx, (cor, ponto) in enumerate(zip(cores_recentes, pontos_recentes)):
        if idx >= total_celulas:
            break
        col = cols - 1 - (idx // rows)   # direita → esquerda
        row = rows - 1 - (idx % rows)    # baixo → cima
        if 0 <= col < cols:
            grade[row][col] = (cor, ponto)

    return grade


def _render_grade(
    cores: List[str], pontos: List[int], cols: int, rows: int,
) -> None:
    """Renderiza o grid de células com HTML."""
    grade = _preparar_grid(cores, pontos, cols, rows)

    # Largura total da grade em pixels
    largura_total = cols * TAM_CELULA + (cols - 1) * GAP_CELULA

    html = [
        '<div style="'
        'background:#1a1a1e;'
        'padding:10px;'
        'border-radius:10px;'
        'border:1px solid #2a2a32;'
        f'width:{largura_total + 20}px;'      # ← largura fixa para não estourar
        'overflow:hidden;'                     # ← corta se ultrapassar
        'box-sizing:border-box;'
        '">',
        f'<div style="display:grid;'
        f'grid-template-columns:repeat({cols},{TAM_CELULA}px);'
        f'gap:{GAP_CELULA}px;">',
    ]

    for row in grade:
        for cell in row:
            if cell is None or cell[0] is None:
                html.append(
                    f'<div style="width:{TAM_CELULA}px;'
                    f'height:{TAM_CELULA}px;border-radius:50%;'
                    f'background:#0e0e15;border:1px solid #222;"></div>'
                )
            else:
                cor, ponto = cell
                bg = COR_HEX.get(cor, "#666")
                html.append(
                    f'<div style="width:{TAM_CELULA}px;'
                    f'height:{TAM_CELULA}px;border-radius:50%;'
                    f'background:{bg};color:#fff;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:12px;font-weight:700;">'      # ← fonte 12px
                    f'{ponto}</div>'
                )

    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def _render_porcentagens_por_linha(
    cores: List[str], cols: int, rows: int,
) -> None:
    """Coluna com as % por linha."""
    grade_cores = _preparar_grid(
        cores, pontos=[0] * len(cores), cols=cols, rows=rows
    )

    html = [
        '<div style="'
        'background:#1a1a1e;'
        'padding:12px;'
        'border-radius:10px;'
        'border:1px solid #2a2a32;'
        'width:100%;'              # ← ocupa toda a largura da coluna
        'box-sizing:border-box;'
        '">',
        f'<div style="display:flex;flex-direction:column;gap:{GAP_CELULA}px;">',
    ]

    for row in grade_cores:
        cores_linha = [c[0] for c in row if c and c[0] is not None]
        total_linha = len(cores_linha)

        if total_linha == 0:
            html.append(
                f'<div style="height:{TAM_CELULA}px;display:flex;'
                f'align-items:center;padding-left:8px;">'
                f'<span style="color:#333;font-size:11px;">—</span>'
                f'</div>'
            )
            continue

        n_r = cores_linha.count("🔴")
        n_b = cores_linha.count("🔵")
        n_t = cores_linha.count("🟡")

        pct_r = (n_r / total_linha) * 100
        pct_b = (n_b / total_linha) * 100
        pct_t = (n_t / total_linha) * 100

        dominante = max(
            [("🔴", n_r), ("🔵", n_b), ("🟡", n_t)],
            key=lambda x: x[1],
        )[0]

        html.append(
            f'<div style="height:{TAM_CELULA}px;display:flex;'
            f'align-items:center;gap:8px;justify-content:space-between;">'
            f'<span style="color:{COR_HEX[dominante]};font-size:16px;">●</span>'
            f'<span style="color:#ef4444;font-weight:700;font-size:12px;'
            f'min-width:38px;text-align:right;">{pct_r:.0f}%</span>'
            f'<span style="color:#3b82f6;font-weight:700;font-size:12px;'
            f'min-width:38px;text-align:right;">{pct_b:.0f}%</span>'
            f'<span style="color:#eab308;font-weight:700;font-size:12px;'
            f'min-width:38px;text-align:right;">{pct_t:.0f}%</span>'
            f'</div>'
        )

    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)