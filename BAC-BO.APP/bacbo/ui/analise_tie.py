"""Painel de Análise de TIE — intervalos e previsões."""
from collections import Counter
from typing import List

import streamlit as st

from ..strategies_tie import analisar_intervalos_tie


def renderizar_analise_tie(worker, num_rodadas: int = 1000) -> None:
    """Renderiza painel completo de análise de TIE."""
    st.markdown("### 🟡 Análise de TIE")
    st.caption(
        "Analisa os intervalos históricos entre TIE e prevê quando "
        "o próximo deve sair."
    )

    # Busca dados do banco local
    try:
        rows = worker.db.carregar_rodadas(
            mesa_id=worker.config.mesa_id,
            limite=int(num_rodadas),
        )
    except Exception as e:
        st.error(f"❌ Erro ao carregar rodadas: {e}")
        return

    if not rows:
        st.info("Sem rodadas no banco local ainda.")
        return

    cores = [r[0] for r in rows]
    info = analisar_intervalos_tie(cores, ultimas_n=num_rodadas)

    total_ties = info.get("total_ties", 0)
    intervalos = info.get("intervalos", [])
    media = info.get("media_intervalo", 0)
    mediana = info.get("mediana_intervalo", 0)
    ultimo = info.get("ultimo_intervalo", 0)
    alerta = info.get("alerta", False)
    rodadas_para_proximo = info.get("rodadas_para_proximo", 0)
    total_rodadas = info.get("total_rodadas", 0)

    # ---- Cards de métricas ----
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total de TIE", total_ties)
    c2.metric("Média Intervalo", f"{media:.1f}" if media else "—")
    c3.metric("Mediana", mediana if mediana else "—")
    c4.metric(
        "Último Intervalo",
        ultimo,
        delta=f"⚠️ Faltam {rodadas_para_proximo}" if alerta else "OK",
        delta_color="inverse" if alerta else "normal",
    )

    # ---- Alerta visual ----
    if alerta:
        st.warning(
            f"⚠️ **ALERTA DE TIE ATIVO** — Último TIE há **{ultimo} rodadas**. "
            f"Média histórica é **{media:.1f}**. "
            f"**Entrada em TIE é provável!**"
        )
    else:
        st.info(
            f"Último TIE há **{ultimo} rodadas**. "
            f"Média histórica é **{media:.1f}**. "
            f"Faltam ~**{rodadas_para_proximo}** rodadas para o próximo."
        )

    # ---- Progresso visual ----
    if media > 0:
        progresso = min(1.0, ultimo / media)
        st.progress(progresso, text=f"Progresso até próximo TIE: {progresso*100:.0f}%")

    # ---- Histograma dos intervalos ----
    if intervalos:
        st.markdown("#### 📊 Distribuição dos Intervalos")
        contagem = Counter(intervalos)
        # Ordena por intervalo
        dados_ordenados = dict(sorted(contagem.items())[:20])
        st.bar_chart(dados_ordenados)

        # ---- Top 10 intervalos mais comuns ----
        st.markdown("#### 🔝 Top 10 Intervalos Mais Frequentes")
        top10 = contagem.most_common(10)
        st.dataframe(
            [
                {
                    "Intervalo (rodadas)": k,
                    "Ocorrências": v,
                    "% do total": f"{v / len(intervalos) * 100:.1f}%",
                }
                for k, v in top10
            ],
            use_container_width=True,
            hide_index=True,
        )

        # ---- Estatísticas detalhadas ----
        with st.expander("📈 Estatísticas Completas"):
            import statistics

            col_esq, col_dir = st.columns(2)
            with col_esq:
                st.markdown("**Intervalos:**")
                st.write(f"Mínimo: `{min(intervalos)}` rodadas")
                st.write(f"Máximo: `{max(intervalos)}` rodadas")
                st.write(f"Média: `{media:.1f}` rodadas")
                st.write(f"Mediana: `{mediana}` rodadas")
                if len(intervalos) > 1:
                    st.write(f"Desvio padrão: `{statistics.stdev(intervalos):.1f}`")

            with col_dir:
                st.markdown("**Total de TIE:**")
                st.write(f"TIE na amostra: `{total_ties}`")
                st.write(f"Rodadas analisadas: `{total_rodadas}`")
                st.write(
                    f"Taxa de TIE: "
                    f"`{(total_ties / total_rodadas * 100):.1f}%`"
                )

    # ---- Tabela de previsão ----
    st.markdown("#### 🎯 Previsões para os Próximos TIE")
    proximos = info.get("proximos_intervalos", [])
    if proximos:
        st.write("Baseado no histórico, os próximos TIE devem sair após:")
        for alvo in proximos[:5]:
            if alvo > ultimo:
                faltam = alvo - ultimo
                st.write(f"• `{alvo}` rodadas (faltam **{faltam}**)")
            else:
                st.write(f"• `{alvo}` rodadas (⚠️ **atrasado** há {ultimo - alvo})")
    else:
        st.info("Amostra insuficiente para previsões.")