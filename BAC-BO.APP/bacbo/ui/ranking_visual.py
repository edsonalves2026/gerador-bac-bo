"""Componente visual do Ranking de Padrões — estilo cards."""
from typing import Any, Dict, List

import streamlit as st


def renderizar_ranking_visual(ranking: List[Dict[str, Any]]) -> None:
    """
    Renderiza o ranking de padrões como cards visuais.

    Cada card tem:
      - Badge numerado (1=ouro, 2=prata, 3=bronze)
      - Padrão (sequência de emojis ou texto)
      - Média de assertividade destacada
      - Badge do Gale (SG/G1/G2)
      - Percentual em verde
    """
    if not ranking:
        st.info("⏳ Aguardando mínimo de entradas para exibir o ranking.")
        return

    # Filtros de Gale
    col1, col2 = st.columns([3, 1])
    with col1:
        filtro_gale = st.selectbox(
            "Filtrar Gale:",
            ["Todos", "SG", "G1", "G2"],
            key="ranking_filtro_gale",
        )
    with col2:
        if st.button("⬇️", help="Baixar CSV", key="btn_baixar_ranking"):
            import pandas as pd
            df = pd.DataFrame(ranking)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Confirmar download",
                data=csv,
                file_name="ranking.csv",
                mime="text/csv",
                key="dl_ranking_csv",
            )

    # CSS customizado
    st.markdown("""
    <style>
    .ranking-card {
        background: linear-gradient(135deg, #1a1a1e 0%, #2a2a32 100%);
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 14px;
        border: 1px solid #333;
        transition: transform 0.2s;
    }
    .ranking-card:hover {
        transform: translateX(4px);
        border-color: #444;
    }
    .ranking-badge {
        min-width: 44px;
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 18px;
        color: #1a1a1e;
        flex-shrink: 0;
    }
    .badge-ouro { background: linear-gradient(135deg, #ffd700 0%, #ffb800 100%); }
    .badge-prata { background: linear-gradient(135deg, #c0c0c0 0%, #a8a8a8 100%); }
    .badge-bronze { background: linear-gradient(135deg, #cd7f32 0%, #b87333 100%); }
    .badge-normal { background: linear-gradient(135deg, #4a4a55 0%, #3a3a45 100%); color: #fff; }
    
    .ranking-info {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
        gap: 4px;
    }
    .ranking-media {
        color: #fff;
        font-weight: 700;
        font-size: 16px;
    }
    .ranking-media span {
        color: #7fdb7f;
        font-weight: 800;
        margin-left: 4px;
    }
    .ranking-padrao {
        color: #ccc;
        font-size: 14px;
        letter-spacing: 2px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .gale-badge {
        display: inline-block;
        background: #2a2a32;
        color: #aaa;
        padding: 2px 8px;
        border-radius: 6px;
        font-size: 11px;
        font-weight: 600;
        margin-left: 8px;
        border: 1px solid #444;
    }
    .pct-verde {
        color: #7fdb7f;
        font-weight: 800;
        font-size: 15px;
        margin-left: auto;
    }
    </style>
    """, unsafe_allow_html=True)

    # Filtra por Gale (baseado no conteúdo da string do padrão)
    ranking_filtrado = ranking
    if filtro_gale != "Todos":
        ranking_filtrado = [
            r for r in ranking
            if f"G{filtro_gale[1]}" in str(r.get("padrao", ""))
            or filtro_gale == "Todos"
        ]

    # Renderiza até 20 cards
    for i, item in enumerate(ranking_filtrado[:20]):
        padrao = item.get("padrao", "—")
        acertos = item.get("acertos", 0)
        total = item.get("total", 0)
        ass = item.get("assertividade", 0)

        # Badge numérico
        pos = i + 1
        if pos == 1:
            badge_class = "badge-ouro"
        elif pos == 2:
            badge_class = "badge-prata"
        elif pos == 3:
            badge_class = "badge-bronze"
        else:
            badge_class = "badge-normal"

        # Detecta o nível de Gale (procura "G1" ou "G2" na descrição)
        gale_tag = "SG"
        if "G2" in str(padrao) or "Gale 2" in str(padrao):
            gale_tag = "G2"
        elif "G1" in str(padrao) or "Gale 1" in str(padrao):
            gale_tag = "G1"

        # Calcula "média" — usa a assertividade como proxy
        media = ass / 100  # converte % para valor tipo 2.70

        html = (
            f'<div class="ranking-card">'
            f'  <div class="ranking-badge {badge_class}">{pos}</div>'
            f'  <div class="ranking-info">'
            f'    <div class="ranking-media">Média: {media:.2f}'
            f'      <span class="gale-badge">{gale_tag}</span>'
            f'    </div>'
            f'    <div class="ranking-padrao">{padrao}</div>'
            f'  </div>'
            f'  <div class="pct-verde">{ass:.0f}%</div>'
            f'</div>'
        )
        st.markdown(html, unsafe_allow_html=True)