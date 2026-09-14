"""Entry point Streamlit — apenas UI."""
import hashlib
import pandas as pd
import streamlit as st

from bacbo.analysis import analisar_multi_amostra
from bacbo.backtest import Backtester
from bacbo.client import TipminerClient
from bacbo.config import BacBoConfig, CoresTerminal, build_http_session, log_terminal
from bacbo.db import Database
from bacbo.notifier import TelegramNotifier
from bacbo.strategies import sinal_espelho, sinal_ponto_regressao, sinal_streak_fade
from bacbo.worker import BacBoWorker

st.set_page_config(page_title="Monitor Bac-Bo Telegram", page_icon="🤖", layout="wide")


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
        st.error("⚠️ Configure TELEGRAM_TOKEN e TELEGRAM_CHAT_ID no secrets.toml")
        st.stop()

    session = build_http_session()
    client = TipminerClient(session, timeout=10)
    notifier = TelegramNotifier(token, chat_id, session=session, timeout=5)
    db = Database("bacbo.db")
    w = BacBoWorker(client, notifier, db, BacBoConfig())
    w.start()
    return w


worker = get_worker()

# ---------- Sidebar: parâmetros base ----------
st.sidebar.title("🎛️ Painel de Controle")

INTERVALO = st.sidebar.slider("⏱️ Intervalo (s)", 2, 30, worker.config.intervalo_verificacao)
SENS = st.sidebar.slider("🎯 Sensibilidade (%)", 50.0, 95.0,
                          worker.config.sensibilidade_minima, 1.0)
TAM = st.sidebar.slider("📏 Tamanho Padrão", 2, 8, worker.config.tamanho_padrao)
MINR = st.sidebar.number_input("🏆 Mín. Amostras Ranking", 1, 10,
                                worker.config.min_operacoes_ranking)
MESA = st.sidebar.text_input("🆔 ID da Mesa", value=worker.config.mesa_id)

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
if c1.button("▶️ Ligar Robô"):
    worker.start()
    st.rerun()
if c2.button("⏸️ Pausar Robô"):
    worker.stop()
    st.rerun()

# ---------- Feature flags ----------
st.sidebar.divider()
st.sidebar.subheader("🧪 Estratégias Ativas")
use_streak = st.sidebar.checkbox("Streak Fade", value=worker.config.usar_streak_fade)
use_ponto = st.sidebar.checkbox("Regressão de Ponto", value=worker.config.usar_ponto_regressao)
use_espelho = st.sidebar.checkbox("Espelho", value=worker.config.usar_espelho)
use_confl = st.sidebar.checkbox("Exigir Confluência", value=worker.config.usar_confluencia)
use_kelly = st.sidebar.checkbox("Kelly Sizing", value=worker.config.usar_kelly)

worker.update_config(
    usar_streak_fade=use_streak,
    usar_ponto_regressao=use_ponto,
    usar_espelho=use_espelho,
    usar_confluencia=use_confl,
    usar_kelly=use_kelly,
)

# ---------- Gestão de risco ----------
st.sidebar.divider()
st.sidebar.subheader("🛡️ Gestão de Risco")
usar_gestao = st.sidebar.checkbox("Ativar Trava de Risco & Cooldown", value=worker.config.usar_gestao_risco)
sl_consec = st.sidebar.number_input("Stop-Loss (LOSS seguidos)", 1, 10,
                                     worker.config.stop_loss_consecutivo)
dd_max = st.sidebar.number_input("Stop Drawdown (u)", 1.0, 5000.0,
                                  worker.config.stop_drawdown_unidades, 0.5)
sw_max = st.sidebar.number_input("Stop-Win (u)", 1.0, 10000.0,
                                  worker.config.stop_win_sessao, 0.5)
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
fds = st.sidebar.checkbox("Operar fim de semana", value=worker.config.operar_fim_de_semana)
worker.update_config(hora_inicio=h_ini, hora_fim=h_fim, operar_fim_de_semana=fds)

# ---------- Relatório manual ----------
st.sidebar.divider()
st.sidebar.subheader("📊 Relatório Manual")
qtd = st.sidebar.slider("Amostra:", 10, 200, 200, 10)
filtro = st.sidebar.text_input("🔎 Alvo (ex: 8, PLAYER)")
if st.sidebar.button("📤 Enviar Relatório"):
    ok, msg = worker.gerar_relatorio(qtd, filtro)
    (st.sidebar.success if ok else st.sidebar.warning)(msg)

# ---------- Cadastro de padrão ----------
st.sidebar.divider()
st.sidebar.subheader("📌 Cadastrar Padrão Fixo")
with st.sidebar.form("form_padrao", clear_on_submit=True):
    nome = st.text_input("Nome", placeholder="Ex: Duplo 10/8")
    seq = st.text_input("Sequência (vírgula)", placeholder="🔴 10, 🔵 8")
    sug = st.selectbox("Entrada", ["🔴 BANKER", "🔵 PLAYER", "🟡 TIE"])
    if st.form_submit_button("➕ Salvar") and nome and seq:
        lista = [x.strip() for x in seq.split(",")]
        cor = {"🔴 BANKER": "🔴", "🔵 PLAYER": "🔵", "🟡 TIE": "🟡"}[sug]
        worker.add_padrao(nome, lista, cor)
        st.rerun()

state = worker.get_state()
if state["PADROES_MANUAIS_COMPOSTOS"]:
    st.sidebar.markdown("**Padrões salvos:**")
    for chave, item in list(state["PADROES_MANUAIS_COMPOSTOS"].items()):
        st.sidebar.text(f"• {chave}: {' | '.join(item['padrao'])} ➔ {item['sugestao']}")
        key_hash = hashlib.md5(chave.encode()).hexdigest()[:8]
        if st.sidebar.button(f"🗑️ Remover {chave}", key=f"del_{key_hash}"):
            worker.remover_padrao(chave)
            st.rerun()

# ---------- Backtest ----------
st.sidebar.divider()
st.sidebar.subheader("🔬 Backtest")
janela_min_bt = st.sidebar.number_input("Mín. histórico p/ backtest", 50, 500, 100, 10)
rodar_bt = st.sidebar.button("▶️ Rodar Backtest")

# ---------- Dashboard ----------
st.title("🤖 Monitor Bac-Bo VIP")
state = worker.get_state()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Status", "🟢 MONITORANDO" if state["bot_rodando"] else "🔴 PAUSADO")
c2.metric("Entrada Atual", state["sugestao_atual"] or "—")
c3.metric("Tentativa", f"Gale {state['tentativa'] - 1}" if state["tentativa"] > 1 else "1ª")
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
            st.warning(f"⚠️ Só {len(rows)} rodadas. Deixe o bot rodar mais.")
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

            df = pd.DataFrame(resultados).sort_values("win_rate", ascending=False)
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
    st.info(f"⏳ Aguardando mínimo de {worker.config.min_operacoes_ranking} entradas.")

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
        st.dataframe(pivot.style.format("{:.1f}%", na_rep="—"),
                     use_container_width=True)
    else:
        st.info("Sem dados de contexto ainda.")

# ---------- Logs ----------
@st.fragment(run_every=INTERVALO)
def renderizar_logs() -> None:
    s = worker.get_state()
    st.subheader("📋 Logs")
    st.code("\n".join(s["log_eventos"][:15]), language=None)


renderizar_logs()
