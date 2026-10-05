"""Entry point Streamlit — apenas UI."""
import hashlib
import os
import sys
import traceback
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# Timezone Brasília — evita UTC no Streamlit Cloud
TZ_BR = ZoneInfo("America/Sao_Paulo")


def _agora_br() -> datetime:
    return datetime.now(TZ_BR)


st.set_page_config(
    page_title="Monitor Bac-Bo Telegram",
    page_icon="🤖",
    layout="wide",
)


# -----------------------------------------------------------------------------
# DIAGNÓSTICO DE IMPORTS — mostra erro detalhado se algo falhar
# -----------------------------------------------------------------------------
def _importar_seguro(nome_modulo: str, nomes: str = None) -> bool:
    try:
        if nomes:
            from importlib import import_module
            m = import_module(nome_modulo)
            for n in nomes.split(","):
                getattr(m, n.strip())
        else:
            __import__(nome_modulo)
        return True
    except Exception:
        import traceback as _tb
        print(f"❌ FALHA IMPORT {nome_modulo}:\n{_tb.format_exc()}", flush=True)
        st.error(f"❌ Falha ao importar `{nome_modulo}`")
        st.code(_tb.format_exc(), language="python")
        st.stop()

# Dependências externas
for _mod in ["pandas", "requests", "streamlit"]:
    try:
        __import__(_mod)
    except ImportError:
        st.error(f"❌ Dependência faltando: `{_mod}`")
        st.code(traceback.format_exc(), language="python")
        st.info("Verifique se `requirements.txt` está correto e foi commitado.")
        st.stop()

# Imports internos (um por um, para isolar erros)
_importar_seguro("bacbo.config", "BacBoConfig, CoresTerminal, build_http_session")
_importar_seguro("bacbo.analysis", "analisar_multi_amostra, processar_filtro_digitado")
_importar_seguro("bacbo.client", "TipminerClient")
_importar_seguro("bacbo.db", "Database")
_importar_seguro("bacbo.notifier", "TelegramNotifier")
_importar_seguro("bacbo.feed_service", "FeedService")
_importar_seguro("bacbo.patterns_analyzer", "PatternsAnalyzer")
_importar_seguro("bacbo.stats_analyzer", "StatsAnalyzer")
_importar_seguro("bacbo.analysis_service", "AnalysisService")
_importar_seguro("bacbo.worker", "BacBoWorker")
_importar_seguro(
    "bacbo.strategies",
    "sinal_streak_fade, sinal_ponto_regressao, sinal_espelho, aplicar_confluencia",
)
_importar_seguro("bacbo.backtest", "Backtester")
_importar_seguro("bacbo.risk", "Banca, StopRules, sugerir_unidade")
_importar_seguro("bacbo.ui.estrategia_modal", "render_estrategia_sidebar")
_importar_seguro("bacbo.ui.tabela_bacbo", "renderizar_tabela_bacbo")

# -----------------------------------------------------------------------------
# Só agora os imports "de verdade"
# -----------------------------------------------------------------------------
from bacbo.analysis import analisar_multi_amostra
from bacbo.backtest import Backtester
from bacbo.client import TipminerClient
from bacbo.config import BacBoConfig, CoresTerminal, build_http_session, log_terminal
from bacbo.db import Database
from bacbo.notifier import TelegramNotifier
from bacbo.strategies import (
    sinal_espelho,
    sinal_ponto_regressao,
    sinal_streak_fade,
)
from bacbo.ui.estrategia_modal import render_estrategia_sidebar
from bacbo.ui.tabela_bacbo import renderizar_tabela_bacbo
from bacbo.worker import BacBoWorker


# =============================================================================
# BOOTSTRAP — Worker
# =============================================================================
def carregar_credenciais():
    try:
        return st.secrets["TELEGRAM_TOKEN"], st.secrets["TELEGRAM_CHAT_ID"]
    except Exception as e:
        log_terminal(f"⚠️ Credenciais ausentes: {e}", CoresTerminal.AMARELO)
        return None, None

@st.cache_resource
def get_worker() -> BacBoWorker:
    token, chat_id = carregar_credenciais()
    if not token or not chat_id:
        st.error("⚠️ Configure TELEGRAM_TOKEN e TELEGRAM_CHAT_ID nos Secrets")
        st.stop()

    session = build_http_session()
    client = TipminerClient(session, timeout=10)
    notifier = TelegramNotifier(token, chat_id, session=session, timeout=5)
    db = Database("bacbo.db")
    w = BacBoWorker(client, notifier, db, BacBoConfig())

    log_terminal(f"🚀 Worker criado. Iniciando motor...", CoresTerminal.VERDE)
    w.start()
    log_terminal(f"✅ Worker iniciado. bot_rodando={w.state['bot_rodando']}", CoresTerminal.VERDE)

    return w

worker = get_worker()


# =============================================================================
# 🎛️ SIDEBAR — Parâmetros base
# =============================================================================
st.sidebar.title("🎛️ Painel de Controle")

INTERVALO = st.sidebar.slider(
    "⏱️ Intervalo (s)", 2, 30, worker.config.intervalo_verificacao
)
SENS = st.sidebar.slider(
    "🎯 Sensibilidade (%)", 50.0, 95.0, worker.config.sensibilidade_minima, 1.0
)
TAM = st.sidebar.slider(
    "📏 Tamanho Padrão", 2, 8, worker.config.tamanho_padrao
)
MINR = st.sidebar.number_input(
    "🏆 Mín. Amostras Ranking", 1, 10, worker.config.min_operacoes_ranking
)
MESA = st.sidebar.text_input("🆔 ID da Mesa", value=worker.config.mesa_id)

LIMITE_MOTOR = st.sidebar.slider(
    "📊 Rodadas do Motor (200-500)",
    min_value=200, max_value=500, value=worker.config.limite_rodadas, step=50,
    help="Quantas rodadas o motor busca a cada ciclo. Maiores valores = mais histórico.",
)
worker.update_config(limite_rodadas=int(LIMITE_MOTOR))

worker.update_config(
    mesa_id=MESA,
    intervalo_verificacao=INTERVALO,
    sensibilidade_minima=SENS,
    tamanho_padrao=TAM,
    min_operacoes_ranking=int(MINR),
)

# ---------- Controles do robô ----------
st.sidebar.divider()
c1, c2 = st.sidebar.columns(2)
if c1.button("▶️ Ligar Robô", use_container_width=True):
    worker.start()
    st.rerun()
if c2.button("⏸️ Pausar Robô", use_container_width=True):
    worker.stop()
    st.rerun()

# ---------- Feature flags ----------
st.sidebar.divider()
st.sidebar.subheader("🧪 Estratégias Ativas")
use_streak = st.sidebar.checkbox("Streak Fade", value=worker.config.usar_streak_fade)
use_ponto = st.sidebar.checkbox(
    "Regressão de Ponto", value=worker.config.usar_ponto_regressao
)
use_espelho = st.sidebar.checkbox("Espelho", value=worker.config.usar_espelho)
use_confl = st.sidebar.checkbox(
    "Exigir Confluência", value=worker.config.usar_confluencia
)
st.sidebar.markdown("**🔬 Detectores Avançados**")

use_sanduiche = st.sidebar.checkbox(
    "Sanduíche (X-Y-X)", value=worker.config.usar_sanduiche,
    help="Detecta padrão tipo 🔴🔵🔴 e aposta na quebra",
)
use_rep_num = st.sidebar.checkbox(
    "Repetição Numérica", value=worker.config.usar_repeticao_numerica,
    help="Detecta mesmo ponto 2x seguidas",
)
use_ciclo = st.sidebar.checkbox(
    "Ciclo Curto", value=worker.config.usar_ciclo_curto,
    help="Padrões de 3 cores que se repetem",
)
use_zona_tie = st.sidebar.checkbox(
    "Zona de TIE", value=worker.config.usar_zona_tie,
    help="3+ TIE em 10 rodadas → alerta",
)
use_forca = st.sidebar.checkbox(
    "Força de Lado", value=worker.config.usar_forca_lado,
    help="Segue o lado dominante (4+ de 5)",
)
use_tie_intervalo = st.sidebar.checkbox(
    "🎯 TIE por Intervalo",
    value=worker.config.usar_tie_intervalo,
    help="Analisa intervalos históricos entre TIE para prever o próximo",
)

use_kelly = st.sidebar.checkbox("Kelly Sizing", value=worker.config.usar_kelly)

st.sidebar.markdown("**🎯 Filtro de Confiança**")
conf_min = st.sidebar.slider(
    "Confiança mínima (%)", min_value=50.0, max_value=90.0,
    value=worker.config.confianca_minima_sinal, step=1.0,
    help="Só envia sinal se a confiança for >= este valor",
)
priorizar = st.sidebar.checkbox(
    "Priorizar >80%", value=worker.config.priorizar_alta_confianca,
    help="Se ativo, prefere padrões de alta confiança quando disponíveis",
)
worker.update_config(
    confianca_minima_sinal=float(conf_min),
    priorizar_alta_confianca=priorizar,
)

worker.update_config(
    usar_streak_fade=use_streak,
    usar_ponto_regressao=use_ponto,
    usar_espelho=use_espelho,
    usar_confluencia=use_confl,
    usar_kelly=use_kelly,
    # Novos detectores (Etapa 2)
    usar_sanduiche=use_sanduiche,
    usar_repeticao_numerica=use_rep_num,
    usar_ciclo_curto=use_ciclo,
    usar_zona_tie=use_zona_tie,
    usar_forca_lado=use_forca,
    usar_tie_intervalo=use_tie_intervalo,
)

# ---------- Gestão de risco ----------
st.sidebar.divider()
st.sidebar.subheader("🛡️ Gestão de Risco")
usar_gestao = st.sidebar.checkbox(
    "Ativar Trava de Risco & Cooldown", value=worker.config.usar_gestao_risco
)
sl_consec = st.sidebar.number_input(
    "Stop-Loss (LOSS seguidos)", 1, 10, worker.config.stop_loss_consecutivo
)
dd_max = st.sidebar.number_input(
    "Stop Drawdown (u)", 1.0, 5000.0, worker.config.stop_drawdown_unidades, 0.5
)
sw_max = st.sidebar.number_input(
    "Stop-Win (u)", 1.0, 10000.0, worker.config.stop_win_sessao, 0.5
)
worker.update_config(
    usar_gestao_risco=usar_gestao,
    stop_loss_consecutivo=int(sl_consec),
    stop_drawdown_unidades=float(dd_max),
    stop_win_sessao=float(sw_max),
)

# ---------- Janela horária ----------
st.sidebar.divider()
st.sidebar.subheader("🕐 Janela Operacional")
h_ini = st.sidebar.slider("Hora início", 0, 23, worker.config.hora_inicio)
h_fim = st.sidebar.slider("Hora fim", 0, 23, worker.config.hora_fim)
fds = st.sidebar.checkbox(
    "Operar fim de semana", value=worker.config.operar_fim_de_semana
)
worker.update_config(hora_inicio=h_ini, hora_fim=h_fim, operar_fim_de_semana=fds)

# ---------- Relatório manual ----------
st.sidebar.divider()
st.sidebar.subheader("📊 Relatório Manual")
qtd = st.sidebar.slider("Amostra:", 10, 200, 200, 10)
filtro = st.sidebar.text_input("🔎 Alvo (ex: 8, PLAYER)")
if st.sidebar.button("📤 Enviar Relatório", use_container_width=True):
    ok, msg = worker.gerar_relatorio(qtd, filtro)
    (st.sidebar.success if ok else st.sidebar.warning)(msg)


# =============================================================================
# 🎯 ESTRATÉGIA PERSONALIZADA (com modal/formulário próprio)
# =============================================================================
render_estrategia_sidebar(worker)


# =============================================================================
# 📊 ANÁLISE ESTATÍSTICA — filtros + resultados
# =============================================================================
st.sidebar.divider()
st.sidebar.subheader("📊 Análise Estatística")

# ---- Filtros ----
col_a, col_b, col_c = st.sidebar.columns(3)
num_rodadas = col_a.number_input(
    "Nº rodadas", min_value=50, max_value=1000, value=500, step=50,
    key="analise_num_rodadas",
)
tam_cor = col_b.number_input(
    "Tam.", min_value=2, max_value=6, value=4,
    key="analise_tam_cor",
)
min_taxa = col_c.number_input(
    "% Acerto", min_value=50.0, max_value=100.0, value=85.0, step=1.0,
    key="analise_min_taxa",
)

col_d, col_e = st.sidebar.columns(2)
min_oc = col_d.number_input(
    "Ocorr. Mín", min_value=2, max_value=50, value=8,
    key="analise_min_oc",
)
gales = col_e.selectbox(
    "Gale", [0, 1, 2], index=2,
    format_func=lambda x: f"G{x}",
    key="analise_gales",
)

col_f, col_g = st.sidebar.columns(2)
btn_analisar = col_f.button("🔄 Analisar", use_container_width=True)
btn_forcar = col_g.button(
    "⚡ Forçar", use_container_width=True, help="Ignora o cache"
)

if btn_analisar or btn_forcar:
    with st.spinner(f"Analisando últimas {num_rodadas} rodadas..."):
        analise = worker.analysis_service.obter_analise(
            mesa_id=worker.config.mesa_id,
            timezone=worker.config.timezone,
            num_rodadas=int(num_rodadas),
            tamanho_cor=int(tam_cor),
            min_ocorrencias=int(min_oc),
            min_taxa=float(min_taxa),
            usar_gale=int(gales),
            forcar=bool(btn_forcar),
        )
        st.session_state["_analise_atual"] = analise

# ---- Renderiza resultado ----
analise = st.session_state.get("_analise_atual")

if analise:
    res = analise["resultados"]
    total_rod = analise.get("total_rodadas", 0)
    ts = analise.get("timestamp", "")
    cache_tag = "💾 cache" if analise.get("cacheado") else "🌐 ao vivo"

    st.sidebar.caption(f"Analisadas {total_rod} rodadas · {ts} · {cache_tag}")

    if analise.get("erro"):
        st.sidebar.warning(f"⚠️ {analise['erro']}")

    # ============ 🎨 ANÁLISES DE CORES ============
    if res["cores"]:
        with st.sidebar.expander(
            f"🎨 Análises de Cores ({len(res['cores'])})", expanded=True,
        ):
            for i, p in enumerate(res["cores"][:30]):
                cols = st.columns([6, 1])
                with cols[0]:
                    st.markdown(
                        f"<div style='font-size:12px;line-height:1.35;color:#ddd'>"
                        f"<span style='letter-spacing:2px;font-size:14px'>"
                        f"{p.padrao}</span> Apareceu <b>{p.ocorrencias}</b> vezes<br>"
                        f"Pode indicar → <b>{p.sugestao}</b> "
                        f"<span style='color:#7fdb7f'>({p.taxa_acerto:.2f}%)</span> "
                        f"<span style='color:#888;font-size:11px'>"
                        f"SG:{p.acertos_direto} G1:{p.acertos_gale1} "
                        f"G2:{p.acertos_gale2} RED:{p.reds}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with cols[1]:
                    key_unique = f"add_cor_{i}_{hash(str(p.padrao)) % 1_000_000}"
                    if st.button("➕", key=key_unique,
                                 help="Ativar como padrão fixo"):
                        nome_auto = f"AUTO_COR_{p.padrao}"
                        worker.add_padrao(nome_auto, list(p.padrao), p.sugestao)
                        st.toast(f"Padrão {p.padrao} ativado!", icon="✅")
    else:
        st.sidebar.info("Nenhum padrão de cor atende aos filtros.")

    # ============ 🔢 ANÁLISES DE NÚMEROS ============
    if res["numeros"]:
        with st.sidebar.expander(
            f"🔢 Análises de Números ({len(res['numeros'])})", expanded=False,
        ):
            for i, p in enumerate(res["numeros"][:30]):
                cols = st.columns([6, 1])
                with cols[0]:
                    st.markdown(
                        f"<div style='font-size:12px;line-height:1.35;color:#ddd'>"
                        f"<b style='font-size:16px'>{p.padrao}</b> "
                        f"Apareceu <b>{p.ocorrencias}</b> vezes<br>"
                        f"Pode indicar → <b>{p.sugestao}</b> "
                        f"<span style='color:#7fdb7f'>({p.taxa_acerto:.2f}%)</span> "
                        f"<span style='color:#888;font-size:11px'>"
                        f"SG:{p.acertos_direto} G1:{p.acertos_gale1} "
                        f"G2:{p.acertos_gale2} RED:{p.reds}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                with cols[1]:
                    key_unique = f"add_num_{i}_{hash(str(p.padrao)) % 1_000_000}"
                    if st.button("➕", key=key_unique,
                                 help="Ativar após este número"):
                        nome_auto = f"AUTO_NUM_{p.padrao}"
                        worker.add_padrao(nome_auto, [str(p.padrao)], p.sugestao)
                        st.toast(f"Número {p.padrao} ativado!", icon="✅")
    else:
        st.sidebar.info("Nenhum padrão numérico atende aos filtros.")

    # ============ 🔗 SEQUÊNCIAS DE NÚMEROS ============
    if res["sequencias"]:
        with st.sidebar.expander(
            f"🔗 Sequências de Números ({len(res['sequencias'])})",
            expanded=False,
        ):
            for i, p in enumerate(res["sequencias"][:15]):
                st.markdown(
                    f"<div style='font-size:12px;line-height:1.35;color:#ddd'>"
                    f"<b>{p.padrao}</b> ×{p.ocorrencias} → "
                    f"<b>{p.sugestao}</b> "
                    f"<span style='color:#7fdb7f'>({p.taxa_acerto:.2f}%)</span> "
                    f"<span style='color:#888;font-size:11px'>"
                    f"SG:{p.acertos_direto} G1:{p.acertos_gale1} "
                    f"G2:{p.acertos_gale2} RED:{p.reds}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # ============ 📊 ESTATÍSTICAS ============
    if analise.get("stats"):
        stats = analise["stats"]
        gale_label = {0: "SG", 1: "G1", 2: "G2"}.get(stats.gale, "—")

        with st.sidebar.container(border=True):
            st.markdown(f"#### 📊 Estatísticas · `{gale_label}`")

            c1, c2 = st.columns(2)
            with c1:
                st.markdown(
                    f"<div style='background:#1e1e2e;border-radius:6px;"
                    f"padding:6px 8px;display:flex;justify-content:space-between;"
                    f"font-size:12px'>"
                    f"<span>Máx 🔴:</span><b>{stats.max_red}</b>"
                    f"<span style='color:#7fdb7f;font-size:10px;margin-left:4px'>"
                    f"({stats.pct_red:.0f}%)</span></div>",
                    unsafe_allow_html=True,
                )
            with c2:
                st.markdown(
                    f"<div style='background:#1e1e2e;border-radius:6px;"
                    f"padding:6px 8px;display:flex;justify-content:space-between;"
                    f"font-size:12px'>"
                    f"<span>Máx 🔵:</span><b>{stats.max_blue}</b>"
                    f"<span style='color:#7fdb7f;font-size:10px;margin-left:4px'>"
                    f"({stats.pct_blue:.0f}%)</span></div>",
                    unsafe_allow_html=True,
                )

            c3, c4 = st.columns(2)
            with c3:
                st.markdown(
                    f"<div style='background:#1e1e2e;border-radius:6px;"
                    f"padding:6px 8px;display:flex;justify-content:space-between;"
                    f"font-size:12px;margin-top:4px'>"
                    f"<span>Máx 🟡:</span><b>{stats.max_tie}</b>"
                    f"<span style='color:#7fdb7f;font-size:10px;margin-left:4px'>"
                    f"({stats.pct_tie:.0f}%)</span></div>",
                    unsafe_allow_html=True,
                )
            with c4:
                st.markdown(
                    f"<div style='background:#1e1e2e;border-radius:6px;"
                    f"padding:6px 8px;display:flex;justify-content:space-between;"
                    f"font-size:12px;margin-top:4px'>"
                    f"<span>Máx sem 🟡:</span><b>{stats.max_sem_tie}</b>"
                    f"<span style='color:#7fdb7f;font-size:10px;margin-left:4px'>"
                    f"({stats.pct_sem_tie:.0f}%)</span></div>",
                    unsafe_allow_html=True,
                )


# =============================================================================
# 🔬 BACKTEST
# =============================================================================
st.sidebar.divider()
st.sidebar.subheader("🔬 Backtest")
janela_min_bt = st.sidebar.number_input(
    "Mín. histórico p/ backtest", 50, 500, 100, 10, key="bt_janela_min"
)
rodar_bt = st.sidebar.button("▶️ Rodar Backtest", use_container_width=True)


# =============================================================================
# 📡 PAINEL "SINAIS AO VIVO"
# =============================================================================
def _cor_css(cor: str) -> tuple:
    mapa = {
        "verde":    ("#0d2818", "#1a5c2e", "#4ade80"),
        "vermelho": ("#2a0f13", "#7f1d1d", "#f87171"),
        "amarelo":  ("#2a2108", "#78350f", "#fbbf24"),
        "azul":     ("#0c1e35", "#1e40af", "#60a5fa"),
        "cinza":    ("#1a1a1e", "#333", "#aaa"),
    }
    return mapa.get(cor, mapa["cinza"])


def renderizar_feed():
    state = worker.get_state()
    eventos = state.get("feed_eventos", [])

    col_title, col_btn = st.columns([5, 1])
    col_title.markdown("### 📡 Sinais ao Vivo")
    if col_btn.button("🗑️", key="limpar_feed", help="Limpar feed"):
        worker.feed.limpar()
        st.rerun()

    if not eventos:
        st.info("Nenhum sinal ainda. Ligue o robô para começar a monitorar.")
        return

    with st.container(height=520, border=True):
        for ev in eventos[:40]:
            bg, border, text = _cor_css(ev["cor"])
            icone = ev.get("icone", "•")
            titulo = ev.get("titulo", "")
            corpo = ev.get("corpo", "")
            sub = ev.get("subtitulo", "")
            ts = ev.get("ts", "")

            html = (
                f"<div style='"
                f"background:{bg};border:1px solid {border};"
                f"border-radius:8px;padding:10px 12px;margin-bottom:8px;"
                f"font-family:-apple-system,Segoe UI,sans-serif;'>"
                f"<div style='display:flex;justify-content:space-between;"
                f"align-items:center;margin-bottom:4px'>"
                f"<span style='color:{text};font-weight:600;font-size:12px;"
                f"letter-spacing:0.5px'>{icone} {titulo}</span>"
                f"<span style='color:#666;font-size:11px'>{ts}</span>"
                f"</div>"
                f"<div style='color:#e5e5e5;font-size:13px;line-height:1.4'>"
                f"{corpo}</div>"
                f"{f'<div style=\'color:#888;font-size:11px;margin-top:4px\'>{sub}</div>' if sub else ''}"
                f"</div>"
            )
            st.markdown(html, unsafe_allow_html=True)


@st.fragment(run_every=3)
def renderizar_feed_auto():
    renderizar_feed()


renderizar_feed_auto()


# =============================================================================
# 🖥️ DASHBOARD — status, banca, ranking, contexto, logs
# =============================================================================
st.title("🤖 Monitor Bac-Bo VIP")
state = worker.get_state()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Status", "🟢 MONITORANDO" if state["bot_rodando"] else "🔴 PAUSADO")
c2.metric("Entrada Atual", state["sugestao_atual"] or "—")
c3.metric(
    "Tentativa",
    f"Gale {state['tentativa'] - 1}" if state["tentativa"] > 1 else "1ª",
)
c4.metric("Padrão", state["padrao_selecionado"] or "—")

# ---------- Banca ----------
st.subheader("💼 Banca & Risco")
b = state["banca"]
bc1, bc2, bc3, bc4 = st.columns(4)
bc1.metric("Saldo", f"{b['saldo']:.2f}u", f"{b['retorno_pct']:+.1f}%")
bc2.metric("Pico", f"{b['pico']:.2f}u")
bc3.metric("Drawdown Máx", f"{b['drawdown_max']:.2f}u", delta_color="inverse")
bc4.metric("Rodadas Persistidas", state["rodadas_persistidas"])

if state["motivo_bloqueio"]:
    st.error(f"🛑 {state['motivo_bloqueio']}")


# ---------- Backtest UI ----------
if rodar_bt:
    with st.spinner("Rodando backtest..."):
        rows = worker.db.carregar_rodadas(worker.config.mesa_id)
        if len(rows) < janela_min_bt + 10:
            st.warning(
                f"⚠️ Só {len(rows)} rodadas no banco. "
                f"Deixe o robô rodar mais para acumular histórico."
            )
        else:
            cores_bt = [r[0] for r in rows]
            pontos_bt = [r[1] for r in rows]
            bt = Backtester(cores_bt, pontos_bt, janela_min=int(janela_min_bt))
            resultados = []

            def det_principal(c, p):
                comp = [f"{cc} {pp}" for cc, pp in zip(c, p)]
                s, _, _, d = analisar_multi_amostra(
                    c, comp, {}, worker.config.tamanho_padrao,
                    worker.config.sensibilidade_minima,
                )
                if not s:
                    return None
                return (s, 70.0, "principal", d or "")

            def det_streak(c, p):
                return sinal_streak_fade(c, worker.config.streak_min)

            def det_ponto(c, p):
                return sinal_ponto_regressao(c, p)

            def det_espelho(c, p):
                return sinal_espelho(c)

            for nome, fn in [
                ("principal", det_principal),
                ("streak_fade", det_streak),
                ("ponto_regressao", det_ponto),
                ("espelho", det_espelho),
            ]:
                resultados.append(bt.rodar(nome, fn).resumo())

            df = pd.DataFrame(resultados).sort_values(
                "win_rate", ascending=False
            )
            st.subheader("🔬 Resultado do Backtest")
            st.dataframe(df, use_container_width=True, hide_index=True)


# ---------- Ranking ----------
st.subheader("🏆 Ranking de Padrões")
r = worker.calcular_ranking()
if r:
    st.dataframe(
        [{
            "Posição": f"#{i}",
            "Padrão": it["padrao"],
            "Acertos": it["acertos"],
            "Total": it["total"],
            "Assertividade": f"{it['assertividade']:.1f}%",
        } for i, it in enumerate(r, 1)],
        use_container_width=True, hide_index=True,
    )
else:
    st.info(
        f"⏳ Aguardando mínimo de {worker.config.min_operacoes_ranking} entradas."
    )


# ---------- Contexto ----------
with st.expander("📊 Assertividade por Contexto (hora × dia)"):
    ctx = worker.db.carregar_contexto()
    if ctx:
        df_ctx = pd.DataFrame(ctx)
        df_ctx["taxa"] = (df_ctx["wins"] / df_ctx["total"] * 100).round(1)
        dias = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
        df_ctx["dia"] = df_ctx["dia_semana"].map(lambda i: dias[i])
        pivot = df_ctx.pivot_table(
            index="dia", columns="hora", values="taxa", aggfunc="mean",
        )
        st.dataframe(
            pivot.style.format("{:.1f}%", na_rep="—"),
            use_container_width=True,
        )
    else:
        st.info("Sem dados de contexto ainda.")


# ---------- Logs ----------
@st.fragment(run_every=INTERVALO)
def renderizar_logs() -> None:
    s = worker.get_state()
    st.subheader("📋 Logs")
    st.code("\n".join(s["log_eventos"][:15]), language=None)


renderizar_logs()

# ---------- 🎰 Tabela Bac Bo ----------
st.divider()

# Slider para escolher quantas rodadas exibir
NUM_RODADAS_TABELA = st.slider(
    "🎰 Rodadas na Tabela Bac Bo",
    min_value=50, max_value=1000, value=200, step=50,
    help="A API suporta até 1000+ rodadas.",
    key="tabela_num_rodadas",
)

# Botão opcional para forçar atualização
col_a, col_b = st.columns([1, 5])
with col_a:
    if st.button("🔄 Atualizar Tabela", use_container_width=True,
                 key="btn_atualizar_tabela"):
        if "_tabela_cache" in st.session_state:
            del st.session_state["_tabela_cache"]


@st.fragment(run_every=10)
def renderizar_tabela_auto():
    renderizar_tabela_bacbo(worker, num_rodadas=int(NUM_RODADAS_TABELA))


renderizar_tabela_auto()
