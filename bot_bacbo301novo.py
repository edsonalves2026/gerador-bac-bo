import time
from datetime import datetime
from collections import Counter
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 🖨️ FUNÇÃO DE LOG COLORIDO NO TERMINAL (VS Code)
# -----------------------------------------------------------------------------
class CoresTerminal:
    AZUL = "\033[94m"
    VERDE = "\033[92m"
    VERMELHO = "\033[91m"
    AMARELO = "\033[93m"
    CIANO = "\033[96m"
    RESET = "\033[0m"

def log_terminal(mensagem: str, cor: str = CoresTerminal.RESET):
    """Exibe log formatado no terminal do VS Code com cores."""
    horario = datetime.now().strftime('%H:%M:%S')
    linha = f"{cor}[{horario}] {mensagem}{CoresTerminal.RESET}"
    print(linha)
    return linha

# -----------------------------------------------------------------------------
# 🛡️ CONFIGURAÇÕES E SEGURANÇA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Monitor Bac-Bo Telegram",
    page_icon="🤖",
    layout="wide"
)

# --- CARREGAMENTO SEGURO DE CREDENCIAIS ---
@st.cache_resource
def carregar_credenciais():
    try:
        return st.secrets["TELEGRAM_TOKEN"], st.secrets["TELEGRAM_CHAT_ID"]
    except (KeyError, Exception):
        log_terminal("⚠️ Credenciais não configuradas! Verifique secrets.toml", CoresTerminal.AMARELO)
        st.error("⚠️ Credenciais do Telegram não configuradas!")
        st.stop()

TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = carregar_credenciais()

# -----------------------------------------------------------------------------
# 🎛️ PAINEL DE CONTROLES VISUAIS (NA INTERFACE)
# -----------------------------------------------------------------------------
st.sidebar.title("🎛️ Painel de Controle")

INTERVALO_VERIFICACAO = st.sidebar.slider(
    "⏱️ Intervalo de Verificação (segundos)",
    min_value=2, max_value=30, value=5, step=1
)

SENSIBILIDADE_MINIMA = st.sidebar.slider(
    "🎯 Sensibilidade Mínima (%)",
    min_value=50.0, max_value=95.0, value=70.0, step=1.0
)

TAMANHO_PADRAO = st.sidebar.slider(
    "📏 Tamanho do Padrão (rodadas)",
    min_value=2, max_value=8, value=4, step=1
)

st.sidebar.divider()
MESA_ID = st.sidebar.text_input(
    "🆔 ID da Mesa",
    value="cc71e81d-8b56-4868-91c7-7224be543dce"
)

CONFIG = {
    "MESA_ID": MESA_ID,
    "INTERVALO_VERIFICACAO": INTERVALO_VERIFICACAO,
    "SENSIBILIDADE_MINIMA": SENSIBILIDADE_MINIMA,
    "TAMANHO_PADRAO": TAMANHO_PADRAO,
    "LIMITE_RODADAS": 200,
    "MAX_GALE": 2,
    "TIMEZONE": "America/Sao_Paulo",
    "TIMEOUT_API": 10,
    "TIMEOUT_TELEGRAM": 5
}

API_BASE_URL = "https://api.core.public.tipminer.com/v1/bac-bo/rounds"

# -----------------------------------------------------------------------------
# 🧠 INICIALIZAÇÃO DE ESTADOS
# -----------------------------------------------------------------------------
def inicializar_estados():
    estados = {
        "sinal_ativo": False,
        "sugestao_atual": None,
        "tentativa": 0,
        "ultimo_uuid_processado": None,
        "ultimo_uuid_sinal_enviado": None,
        "historico_sinais": [],
        "log_eventos": [],
        "padrao_selecionado": None,
        "ranking_padroes": {},
        "ultimo_analise": None
    }
    for chave, valor in estados.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

inicializar_estados()

# -----------------------------------------------------------------------------
# 📝 SISTEMA DE LOGS (TERMINAL + INTERFACE)
# -----------------------------------------------------------------------------
def registrar_log(mensagem: str, cor_terminal=CoresTerminal.RESET):
    log_terminal(mensagem, cor_terminal)
    horario = datetime.now().strftime('%H:%M:%S')
    entrada = f"[{horario}] {mensagem}"
    st.session_state.log_eventos.insert(0, entrada)
    if len(st.session_state.log_eventos) > 50:
        st.session_state.log_eventos.pop()

def registrar_resultado(resultado: str, padrao_usado: str = None):
    st.session_state.historico_sinais.append(resultado)
    if len(st.session_state.historico_sinais) > 50:
        st.session_state.historico_sinais.pop()

    if padrao_usado and resultado in ["WIN", "WIN_G1", "WIN_TIE"]:
        if padrao_usado not in st.session_state.ranking_padroes:
            st.session_state.ranking_padroes[padrao_usado] = {"wins": 0, "total": 0}
        st.session_state.ranking_padroes[padrao_usado]["wins"] += 1
        st.session_state.ranking_padroes[padrao_usado]["total"] += 1
    elif padrao_usado and resultado == "LOSS":
        if padrao_usado not in st.session_state.ranking_padroes:
            st.session_state.ranking_padroes[padrao_usado] = {"wins": 0, "total": 0}
        st.session_state.ranking_padroes[padrao_usado]["total"] += 1

# -----------------------------------------------------------------------------
# 📊 PLACAR E ESTATÍSTICAS
# -----------------------------------------------------------------------------
def obter_texto_placar() -> str:
    historico = st.session_state.historico_sinais
    if not historico:
        return "📊 *PLACAR:* Aguardando primeiras entradas da sessão..."

    total = len(historico)
    wins_direto = historico.count("WIN")
    wins_g1 = historico.count("WIN_G1")
    wins_tie = historico.count("WIN_TIE")
    losses = historico.count("LOSS")
    total_wins = wins_direto + wins_g1 + wins_tie
    assertividade = (total_wins / total * 100) if total > 0 else 0

    return (
        f"📊 *PLACAR ACUMULADO (Últimas {total} entradas):*\n"
        f"• 🎯 Win Direto: `{wins_direto}`\n"
        f"• 🔄 Win Gale 1: `{wins_g1}`\n"
        f"• 🟡 Tie (Proteção): `{wins_tie}`\n"
        f"• ❌ Loss: `{losses}`\n"
        f"• 🚀 *Assertividade:* `{assertividade:.1f}%`"
    )

# -----------------------------------------------------------------------------
# 🏆 RANKING DE PADRÕES MAIS ASSERTIVOS
# -----------------------------------------------------------------------------
def calcular_ranking_padroes():
    ranking = []
    for padrao, dados in st.session_state.ranking_padroes.items():
        if dados["total"] > 0:
            assertividade = (dados["wins"] / dados["total"]) * 100
            ranking.append({
                "padrao": padrao,
                "acertos": dados["wins"],
                "total": dados["total"],
                "assertividade": assertividade
            })
    return sorted(ranking, key=lambda x: x["assertividade"], reverse=True)

def formatar_ranking_telegram() -> str:
    ranking = calcular_ranking_padroes()
    if not ranking:
        return "📊 *Ranking de Padrões:* Sem dados suficientes ainda."

    linhas = ["🏆 *PADRÕES MAIS ASSERTIVOS:*"]
    for i, item in enumerate(ranking[:5], 1):
        linhas.append(
            f"{i}. `{item['padrao']}` → {item['assertividade']:.1f}% "
            f"({item['acertos']}/{item['total']})"
        )
    return "\n".join(linhas)

# -----------------------------------------------------------------------------
# ✉️ ENVIO DE MENSAGENS — TELEGRAM
# -----------------------------------------------------------------------------
def enviar_mensagem_telegram(texto: str) -> bool:
    if not texto or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        registrar_log("⚠️ Mensagem vazia ou credenciais incompletas", CoresTerminal.AMARELO)
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(url, json=payload, timeout=CONFIG["TIMEOUT_TELEGRAM"])
        response.raise_for_status()
        registrar_log("✅ Mensagem enviada ao Telegram", CoresTerminal.VERDE)
        return True
    except Exception as e:
        registrar_log(f"❌ Erro Telegram: {str(e)[:60]}", CoresTerminal.VERMELHO)
        return False

# -----------------------------------------------------------------------------
# 🔌 BUSCA DE DADOS — API
# -----------------------------------------------------------------------------
def buscar_historico_api():
    url = (
        f"{API_BASE_URL}/{CONFIG['MESA_ID']}/history"
        f"?limit={CONFIG['LIMITE_RODADAS']}"
        f"&timezone={CONFIG['TIMEZONE'].replace('/', '%2F')}"
    )
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=CONFIG["TIMEOUT_API"])
        response.raise_for_status()
        dados = response.json()

        if not isinstance(dados, list):
            registrar_log("⚠️ API retornou formato inesperado", CoresTerminal.AMARELO)
            return [], [], []

        cores, uuids, pontos = [], [], []
        for item in dados:
            tipo = str(item.get("type", "")).upper().strip()
            uuid_rodada = item.get("uuid", "")
            ponto = item.get("result", 0)

            if "BANKER" in tipo or "RED" in tipo:
                cor = "🔴"
            elif "PLAYER" in tipo or "BLUE" in tipo:
                cor = "🔵"
            elif "TIE" in tipo or "YELLOW" in tipo:
                cor = "🟡"
            else:
                continue

            if not uuid_rodada:
                continue
            cores.append(cor)
            uuids.append(uuid_rodada)
            pontos.append(ponto)

        if uuids:
            registrar_log(f"✅ {len(uuids)} rodadas carregadas da API", CoresTerminal.VERDE)
        return cores[::-1], uuids[::-1], pontos[::-1]

    except Exception as e:
        registrar_log(f"❌ Erro API: {str(e)[:60]}", CoresTerminal.VERMELHO)
        return [], [], []

# -----------------------------------------------------------------------------
# 🧠 ANÁLISE DE PADRÕES COM IDENTIFICAÇÃO
# -----------------------------------------------------------------------------
def analisar_multi_amostra(historico_cores: list):
    minimo_rodadas = 51
    if len(historico_cores) < minimo_rodadas:
        return None, 0.0, 0.0, None

    padrao = historico_cores[-CONFIG["TAMANHO_PADRAO"]:]
    padrao_str = " | ".join(padrao)

    def calcular_probabilidade(amostra_tamanho: int):
        amostra = historico_cores[-amostra_tamanho:]
        total_ocorrencias = vermelho = azul = 0

        for i in range(len(amostra) - CONFIG["TAMANHO_PADRAO"]):
            if amostra[i:i+CONFIG["TAMANHO_PADRAO"]] == padrao:
                total_ocorrencias += 1
                proximo = amostra[i + CONFIG["TAMANHO_PADRAO"]]
                if proximo == "🔴":
                    vermelho += 1
                elif proximo == "🔵":
                    azul += 1

        if total_ocorrencias == 0:
            return 0.0, 0.0
        return (
            vermelho / total_ocorrencias * 100,
            azul / total_ocorrencias * 100
        )

    prob_r_30, prob_b_30 = calcular_probabilidade(30)
    prob_r_50, prob_b_50 = calcular_probabilidade(50)
    sensibilidade = CONFIG["SENSIBILIDADE_MINIMA"]

    st.session_state.ultimo_analise = {
        "padrao": padrao_str,
        "prob30_r": round(prob_r_30, 1),
        "prob30_b": round(prob_b_30, 1),
        "prob50_r": round(prob_r_50, 1),
        "prob50_b": round(prob_b_50, 1),
        "tamanho": CONFIG["TAMANHO_PADRAO"]
    }

    if prob_r_30 >= sensibilidade and prob_r_50 >= sensibilidade:
        return "🔴", round(prob_r_30, 1), round(prob_r_50, 1), padrao_str
    elif prob_b_30 >= sensibilidade and prob_b_50 >= sensibilidade:
        return "🔵", round(prob_b_30, 1), round(prob_b_50, 1), padrao_str

    return None, 0.0, 0.0, None

# -----------------------------------------------------------------------------
# 📈 ESTUDO DE TIE / EMPATE
# -----------------------------------------------------------------------------
def calcular_estudo_tie(historico_cores: list) -> str:
    if "🟡" not in historico_cores or len(historico_cores) < 50:
        return "⚪ *Status Tie:* Dados insuficientes para análise."

    indices = [i for i, c in enumerate(historico_cores) if c == "🟡"]
    distancia_atual = (len(historico_cores) - 1) - indices[-1]

    gaps = [indices[i] - indices[i-1] - 1 for i in range(1, len(indices))]
    freq = Counter(gaps)
    vezes = freq.get(distancia_atual, 0)

    if vezes >= 2:
        return (f"🔥 *PROBABILIDADE ALTA!* Intervalo de `{distancia_atual}R` sem Tie "
                f"ocorreu `{vezes}x` no histórico.")
    elif distancia_atual <= 3:
        return f"⚡ *ZONA DE ECO!* Apenas `{distancia_atual}R` desde o último Tie."
    return f"📊 *Status Normal:* `{distancia_atual}R` sem Tie (frequência: {vezes}x)."

# -----------------------------------------------------------------------------
# ✅ VERIFICAÇÃO DE RESULTADO
# -----------------------------------------------------------------------------
def verificar_resultado(ultimo_resultado: str):
    if not st.session_state.sinal_ativo:
        return

    esperado = st.session_state.sugestao_atual
    padrao_usado = st.session_state.padrao_selecionado
    acertou = (ultimo_resultado == esperado) or (ultimo_resultado == "🟡")

    if acertou:
        if ultimo_resultado == "🟡":
            registrar_resultado("WIN_TIE", padrao_usado)
            registrar_log(f"✅ GREEN DE PRIMEIRA! Tie protegeu → {padrao_usado}", CoresTerminal.VERDE)
            if st.session_state.tentativa == 1:
                enviar_mensagem_telegram(
                    f"✅ *GREEN DE PRIMEIRA!* 🟡\n"
                    f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
                )
        elif st.session_state.tentativa == 1:
            registrar_resultado("WIN", padrao_usado)
            registrar_log(f"✅ WIN DIRETO! Padrão: {padrao_usado}", CoresTerminal.VERDE)
            enviar_mensagem_telegram(
                f"✅ *WIN DIRETO!* 🎯\n"
                f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
            )
        else:
            registrar_resultado("WIN_G1", padrao_usado)
            registrar_log(f"✅ WIN NO GALE 1! Padrão: {padrao_usado}", CoresTerminal.VERDE)
            enviar_mensagem_telegram(
                f"✅ *WIN NO GALE 1!* 🎯\n"
                f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
            )
        st.session_state.sinal_ativo = False
        st.session_state.padrao_selecionado = None

    elif st.session_state.tentativa == 1:
        st.session_state.tentativa = 2
        registrar_log(f"⚠️ Não bateu 1ª → Gale 1. Padrão: {padrao_usado}", CoresTerminal.AMARELO)
        enviar_mensagem_telegram(
            f"⚠️ *NÃO BATEU NA 1ª! VAMOS PARA O GALE 1*\n"
            f"Entrada mantida: {esperado}"
        )
    else:
        registrar_resultado("LOSS", padrao_usado)
        registrar_log(f"❌ LOSS CONFIRMADO! Padrão: {padrao_usado}", CoresTerminal.VERMELHO)
        enviar_mensagem_telegram(
            f"❌ *LOSS CONFIRMADO*\n"
            f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
        )
        st.session_state.sinal_ativo = False
        st.session_state.padrao_selecionado = None

# -----------------------------------------------------------------------------
# 🔄 PROCESSAMENTO PRINCIPAL
# -----------------------------------------------------------------------------
def processar_rodada():
    cores, uuids, _ = buscar_historico_api()

    if not uuids:
        registrar_log("⏳ Aguardando dados da API...", CoresTerminal.AMARELO)
        return

    uuid_atual = uuids[-1]

    if uuid_atual == st.session_state.ultimo_uuid_processado:
        return

    st.session_state.ultimo_uuid_processado = uuid_atual
    ultimo_resultado = cores[-1]
    registrar_log(f"🔄 Nova rodada: {ultimo_resultado} | UUID: {uuid_atual[:12]}...", CoresTerminal.CIANO)

    if st.session_state.sinal_ativo:
        verificar_resultado(ultimo_resultado)

    if not st.session_state.sinal_ativo:
        sugestao, prob30, prob50, padrao = analisar_multi_amostra(cores)

        if sugestao and st.session_state.ultimo_uuid_sinal_enviado != uuid_atual:
            st.session_state.sinal_ativo = True
            st.session_state.sugestao_atual = sugestao
            st.session_state.tentativa = 1
            st.session_state.padrao_selecionado = padrao
            st.session_state.ultimo_uuid_sinal_enviado = uuid_atual

            nome_cor = "🔴 BANKER" if sugestao == "🔴" else "🔵 PLAYER"
            estudo_tie = calcular_estudo_tie(cores)
            placar = obter_texto_placar()
            ranking = formatar_ranking_telegram()

            mensagem = (
                "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
                f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
                "🛡️ *PROTEÇÃO:* 🟡 TIE (Empate)\n"
                "🔄 *GESTÃO:* Até Gale 1\n\n"
                f"🔍 *PADRÃO DETECTADO ({CONFIG['TAMANHO_PADRAO']}R):*\n`{padrao}`\n"
                "📊 *ASSERTIVIDADE DA ENTRADA:*\n"
                f"• *Momento (30R):* `{prob30:.1f}%`\n"
                f"• *Ciclo (50R):* `{prob50:.1f}%`\n\n"
                f"📈 *ESTUDO DE TIE:*\n{estudo_tie}\n\n"
                f"{ranking}\n\n"
                f"{placar}\n\n"
                f"📝 *Últimas 10 Rodadas:*\n`{' | '.join(cores[-10:])}`"
            )

            if enviar_mensagem_telegram(mensagem):
                registrar_log(f"✅ SINAL ENVIADO → {nome_cor} | Padrão: {padrao}", CoresTerminal.VERDE)
            else:
                registrar_log("❌ Falha ao enviar sinal", CoresTerminal.VERMELHO)
                st.session_state.sinal_ativo = False
                st.session_state.padrao_selecionado = None

# -----------------------------------------------------------------------------
# 🖥️ INTERFACE COMPLETA COM PAINÉIS
# -----------------------------------------------------------------------------
st.title("🤖 Monitor de Sinais Bac-Bo")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Status do Sinal", "🔴 ATIVO" if st.session_state.sinal_ativo else "🟢 AGUARDANDO")
col2.metric("Sugestão Atual", st.session_state.sugestao_atual or "—")
col3.metric("Gale Atual", st.session_state.tentativa or "—")
col4.metric("Padrão Selecionado", f"`{st.session_state.padrao_selecionado}`" if st.session_state.padrao_selecionado else "—")

st.subheader("🔍 Padrão Analisado na Última Verificação")
ult = st.session_state.ultimo_analise
if ult:
    st.info(f"""
    **Padrão ({ult['tamanho']} rodadas):** `{ult['padrao']}`

    | Janela | 🔴 Banker | 🔵 Player |
    |---|---|---|
    | Últimas 30R | {ult['prob30_r']:.1f}% | {ult['prob30_b']:.1f}% |
    | Últimas 50R | {ult['prob50_r']:.1f}% | {ult['prob50_b']:.1f}% |

    **Sensibilidade configurada:** {CONFIG['SENSIBILIDADE_MINIMA']}%
    """)
else:
    st.info("⏳ Aguardando primeira análise...")

st.subheader("🏆 Ranking de Padrões Mais Assertivos")
ranking = calcular_ranking_padroes()
if ranking:
    st.dataframe(
        [
            {
                "Posição": f"#{i}",
                "Padrão": item["padrao"],
                "Acertos": item["acertos"],
                "Total": item["total"],
                "Assertividade %": f"{item['assertividade']:.1f}%"
            }
            for i, item in enumerate(ranking, 1)
        ],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("⏳ Aguardando primeiros resultados para montar ranking...")

st.subheader("📋 Logs de Monitoramento (Terminal + Interface)")
log_container = st.empty()

processar_rodada()
log_container.code("\n".join(st.session_state.log_eventos[:15]), language=None)

time.sleep(CONFIG["INTERVALO_VERIFICACAO"])
st.rerun()
