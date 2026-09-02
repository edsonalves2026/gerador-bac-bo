import time
import uuid
from datetime import datetime
from collections import Counter
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 🖨️ LOG COLORIDO NO TERMINAL
# -----------------------------------------------------------------------------
class CoresTerminal:
    AZUL = "\033[94m"
    VERDE = "\033[92m"
    VERMELHO = "\033[91m"
    AMARELO = "\033[93m"
    CIANO = "\033[96m"
    RESET = "\033[0m"

def log_terminal(mensagem: str, cor: str = CoresTerminal.RESET):
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

@st.cache_resource
def carregar_credenciais():
    try:
        return st.secrets["TELEGRAM_TOKEN"], st.secrets["TELEGRAM_CHAT_ID"]
    except (KeyError, Exception):
        log_terminal("⚠️ Credenciais não configuradas no secrets.toml", CoresTerminal.AMARELO)
        st.error("⚠️ Credenciais do Telegram não configuradas!")
        st.stop()

TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = carregar_credenciais()

# -----------------------------------------------------------------------------
# 🎛️ PAINEL DE CONTROLE (INTERFACE)
# -----------------------------------------------------------------------------
st.sidebar.title("🎛️ Painel de Controle")

INTERVALO_VERIFICACAO = st.sidebar.slider(
    "⏱️ Intervalo de Verificação (s)",
    min_value=2, max_value=30, value=5, step=1
)

SENSIBILIDADE_MINIMA = st.sidebar.slider(
    "🎯 Sensibilidade Mínima (%)",
    min_value=50.0, max_value=95.0, value=70.0, step=1.0
)

TAMANHO_PADRAO = st.sidebar.slider(
    "📏 Tamanho do Padrão (rodadas)",
    min_value=2, max_value=8, value=3, step=1
)

MIN_OPERACOES_RANKING = st.sidebar.number_input(
    "🏆 Mínimo de Amostras p/ Ranking",
    min_value=1, max_value=10, value=3
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
    "MIN_OPERACOES_RANKING": MIN_OPERACOES_RANKING,
    "LIMITE_RODADAS": 200,
    "MAX_GALE": 1,
    "TIMEZONE": "America/Sao_Paulo",
    "TIMEOUT_API": 10,
    "TIMEOUT_TELEGRAM": 5
}

# -----------------------------------------------------------------------------
# 🎯 PADRÕES MANUAIS COMPOSTOS
# -----------------------------------------------------------------------------
PADROES_MANUAIS_COMPOSTOS = {
    "composto_manual_1": {
        "padrao": ["🔴 11", "🔵 8", "🔴 11"],
        "sugestao": "🔵",
        "nome_sugestao": "PLAYER",
        "ativo": True,
        "tamanho_padrao": 3
    },
    "composto_manual_2": {
        "padrao": ["🔵 8", "🔴 11", "🔵 8"],
        "sugestao": "🔴",
        "nome_sugestao": "BANKER",
        "ativo": True,
        "tamanho_padrao": 3
    }
}

# -----------------------------------------------------------------------------
# 🧠 ESTADOS
# -----------------------------------------------------------------------------
def inicializar_estados():
    estados = {
        "sinal_ativo": False,
        "sugestao_atual": None,
        "tentativa": 0,
        "ultimo_uuid_processado": None,
        "ultimo_uuid_sinal_enviado": None,
        "ultimo_uuid_tie_enviado": None,
        "ultimo_uuid_tie_direto_enviado": None,
        "historico_sinais": [],
        "historico_ciclo": [],
        "historico_usos": {},
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
# 📝 LOGS E RESULTADOS
# -----------------------------------------------------------------------------
def registrar_log(mensagem: str, cor_terminal=CoresTerminal.RESET):
    log_terminal(mensagem, cor_terminal)
    horario = datetime.now().strftime('%H:%M:%S')
    st.session_state.log_eventos.insert(0, f"[{horario}] {mensagem}")
    if len(st.session_state.log_eventos) > 50:
        st.session_state.log_eventos.pop()

def registrar_resultado(resultado: str, padrao_usado: str = None):
    st.session_state.historico_sinais.append(resultado)
    if len(st.session_state.historico_sinais) > 50:
        st.session_state.historico_sinais.pop()

    st.session_state.historico_ciclo.append(resultado)

    if padrao_usado:
        if padrao_usado not in st.session_state.ranking_padroes:
            st.session_state.ranking_padroes[padrao_usado] = {"wins": 0, "total": 0}
        
        st.session_state.ranking_padroes[padrao_usado]["total"] += 1
        if resultado in ["WIN", "WIN_G1", "WIN_TIE"]:
            st.session_state.ranking_padroes[padrao_usado]["wins"] += 1

    processar_fechamento_ciclo()

# -----------------------------------------------------------------------------
# 📊 FECHAMENTO DE CICLO (50 SINAIS)
# -----------------------------------------------------------------------------
def processar_fechamento_ciclo():
    historico = st.session_state.historico_ciclo
    total = len(historico)

    if total < 50:
        return

    wins_diretos = historico.count("WIN")
    wins_g1 = historico.count("WIN_G1")
    wins_tie = historico.count("WIN_TIE")
    losses = historico.count("LOSS")

    total_wins = wins_diretos + wins_g1 + wins_tie
    assertividade = (total_wins / total * 100) if total > 0 else 0

    mensagem = (
        "📊 *ASSERTIVIDADE FINAL - CICLO DE 50 ENTRADAS*\n\n"
        f"🎯 *Win Direto:* `{wins_diretos}`\n"
        f"🔄 *Win Gale 1:* `{wins_g1}`\n"
        f"🟡 *Win Proteção (Tie):* `{wins_tie}`\n"
        f"❌ *Loss:* `{losses}`\n\n"
        f"🚀 *ASSERTIVIDADE GLOBAL:* `{assertividade:.1f}%`\n"
        "─────────────────────────────\n"
        "🔄 *Ciclo concluído! Reiniciando contador para as próximas 50.*"
    )

    enviar_mensagem_telegram(mensagem)
    registrar_log("📊 CICLO DE 50 CONCLUÍDO!", CoresTerminal.CIANO)
    st.session_state.historico_ciclo = []

# -----------------------------------------------------------------------------
# 🏆 RANKING FILTRADO E FORMATADO
# -----------------------------------------------------------------------------
def calcular_ranking_padroes():
    ranking = []
    min_ops = CONFIG["MIN_OPERACOES_RANKING"]

    for padrao, dados in st.session_state.ranking_padroes.items():
        if dados["total"] >= min_ops:
            assertividade = (dados["wins"] / dados["total"]) * 100
            ranking.append({
                "padrao": padrao,
                "acertos": dados["wins"],
                "total": dados["total"],
                "assertividade": assertividade
            })
    return sorted(ranking, key=lambda x: (x["assertividade"], x["total"]), reverse=True)

def formatar_ranking_telegram() -> str:
    ranking = calcular_ranking_padroes()
    if not ranking:
        return "🏆 *Ranking de Padrões:* Aguardando amostragem mínima."

    linhas = ["🏆 *PADRÕES MAIS ASSERTIVOS DA SESSÃO:*"]
    for i, item in enumerate(ranking[:5], 1):
        linhas.append(
            f"{i}. `{item['padrao']}` → *{item['assertividade']:.1f}%* "
            f"({item['acertos']}/{item['total']})"
        )
    return "\n".join(linhas)

def obter_texto_placar() -> str:
    historico = st.session_state.historico_sinais
    if not historico:
        return "📊 *PLACAR:* Aguardando primeiras entradas..."

    total = len(historico)
    wins_direto = historico.count("WIN")
    wins_g1 = historico.count("WIN_G1")
    wins_tie = historico.count("WIN_TIE")
    losses = historico.count("LOSS")
    assertividade = ((wins_direto + wins_g1 + wins_tie) / total * 100) if total > 0 else 0

    return (
        f"📊 *PLACAR ACUMULADO ({total} entradas):*\n"
        f"• 🎯 Win Direto: `{wins_direto}` | 🔄 Gale 1: `{wins_g1}`\n"
        f"• 🟡 Proteção Tie: `{wins_tie}` | ❌ Loss: `{losses}`\n"
        f"• 🚀 *Assertividade:* `{assertividade:.1f}%`"
    )

# -----------------------------------------------------------------------------
# ✉️ TELEGRAM
# -----------------------------------------------------------------------------
def enviar_mensagem_telegram(texto: str) -> bool:
    if not texto or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
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
        registrar_log("✅ Mensagem enviada ao Telegram!", CoresTerminal.VERDE)
        return True
    except Exception as e:
        registrar_log(f"❌ Falha no Telegram: {str(e)[:80]}", CoresTerminal.VERMELHO)
        return False

# -----------------------------------------------------------------------------
# 🔌 BUSCA DE DADOS (API)
# -----------------------------------------------------------------------------
def buscar_historico_api():
    url = (
        f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{CONFIG['MESA_ID']}/history"
        f"?limit={CONFIG['LIMITE_RODADAS']}&timezone={CONFIG['TIMEZONE'].replace('/', '%2F')}&_cb={uuid.uuid4()}"
    )
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

    try:
        response = requests.get(url, headers=headers, timeout=CONFIG["TIMEOUT_API"])
        if response.status_code != 200:
            return [], [], [], [], []

        dados = response.json()
        if not isinstance(dados, list):
            return [], [], [], [], []

        cores, uuids, pontos, compostos, exibicao_rodadas = [], [], [], [], []
        for item in dados:
            tipo = str(item.get("type", "")).upper()
            uuid_r = item.get("uuid", "")
            ponto = item.get("result", 0)

            if "BANKER" in tipo or "RED" in tipo:
                cor, nome = "🔴", "BANKER"
            elif "PLAYER" in tipo or "BLUE" in tipo:
                cor, nome = "🔵", "PLAYER"
            elif "TIE" in tipo or "YELLOW" in tipo:
                cor, nome = "🟡", "TIE"
            else:
                continue

            if not uuid_r:
                continue

            cores.append(cor)
            uuids.append(uuid_r)
            pontos.append(ponto)
            compostos.append(f"{cor} {ponto}")
            exibicao_rodadas.append(f"{cor} ({ponto})")

        return cores[::-1], uuids[::-1], pontos[::-1], compostos[::-1], exibicao_rodadas[::-1]

    except Exception:
        return [], [], [], [], []

# -----------------------------------------------------------------------------
# 🧠 BUSCA HÍBRIDA DE PADRÕES (CORES + COMPOSTOS)
# -----------------------------------------------------------------------------
def analisar_multi_amostra(historico_cores: list, historico_compostos: list):
    tamanho_p = CONFIG["TAMANHO_PADRAO"]
    MINIMO_OCORRENCIAS = 3

    if len(historico_cores) < 50:
        return None, 0.0, 0.0, None

    def buscar_em_lista(amostra, padrao):
        total, verm, azul = 0, 0, 0
        tam = len(padrao)
        for i in range(len(amostra) - tam):
            if amostra[i : i + tam] == padrao:
                proximo = historico_cores[i + tam] if len(amostra) == len(historico_cores) else amostra[i + tam]
                total += 1
                if proximo == "🔴":
                    verm += 1
                elif proximo == "🔵":
                    azul += 1
        if total < MINIMO_OCORRENCIAS:
            return 0.0, 0.0, total
        return (verm / total) * 100, (azul / total) * 100, total

    # 1. Testa busca com Padrão Composto (Cor + Número)
    padrao_comp = historico_compostos[-tamanho_p:]
    prob_r_c, prob_b_c, oc_c = buscar_em_lista(historico_compostos, padrao_comp)

    if oc_c >= MINIMO_OCORRENCIAS:
        if prob_r_c >= CONFIG["SENSIBILIDADE_MINIMA"]:
            return "🔴", round(prob_r_c, 1), round(prob_r_c, 1), " | ".join(padrao_comp)
        if prob_b_c >= CONFIG["SENSIBILIDADE_MINIMA"]:
            return "🔵", round(prob_b_c, 1), round(prob_b_c, 1), " | ".join(padrao_comp)

    # 2. Fallback para busca por Sequência de Cores
    padrao_cor = historico_cores[-tamanho_p:]
    prob_r_30, prob_b_30, _ = buscar_em_lista(historico_cores[-50:], padrao_cor)
    prob_r_tot, prob_b_tot, oc_tot = buscar_em_lista(historico_cores, padrao_cor)

    padrao_str = " | ".join(padrao_cor)
    st.session_state.ultimo_analise = {
        "padrao": padrao_str,
        "prob30_r": round(prob_r_30, 1), "prob30_b": round(prob_b_30, 1),
        "prob50_r": round(prob_r_tot, 1), "prob50_b": round(prob_b_tot, 1),
        "tamanho": tamanho_p
    }

    if prob_r_tot >= CONFIG["SENSIBILIDADE_MINIMA"] and oc_tot >= MINIMO_OCORRENCIAS:
        return "🔴", round(prob_r_30, 1), round(prob_r_tot, 1), padrao_str
    if prob_b_tot >= CONFIG["SENSIBILIDADE_MINIMA"] and oc_tot >= MINIMO_OCORRENCIAS:
        return "🔵", round(prob_b_30, 1), round(prob_b_tot, 1), padrao_str

    return None, 0.0, 0.0, None

# -----------------------------------------------------------------------------
# 📈 ESTUDO DE TIE
# -----------------------------------------------------------------------------
def calcular_estudo_tie(historico_cores: list) -> str:
    if "🟡" not in historico_cores or len(historico_cores) < 50:
        return "⚪ *Status Tie:* Dados insuficientes."

    indices = [i for i, c in enumerate(historico_cores) if c == "🟡"]
    distancia = (len(historico_cores) - 1) - indices[-1]
    gaps = [indices[i] - indices[i-1] - 1 for i in range(1, len(indices))]
    vezes = Counter(gaps).get(distancia, 0)

    if vezes >= 2:
        return f"🔥 *PROBABILIDADE ALTA!* `{distancia}R` sem Tie ocorreu `{vezes}x`."
    if distancia <= 3:
        return f"⚡ *ZONA DE ECO!* Apenas `{distancia}R` desde o último Tie."
    return f"📊 *Status Normal:* `{distancia}R` sem Tie (freq: {vezes}x)."

def verificar_radar_tie_aquecido(historico_cores: list, uuid_atual: str):
    if len(historico_cores) < 50 or "🟡" not in historico_cores[-20:]:
        return
    if st.session_state.get("ultimo_uuid_tie_enviado") == uuid_atual:
        return

    dist = (len(historico_cores) - 1) - [i for i, c in enumerate(historico_cores) if c == "🟡"][-1]
    if dist in [0, 1, 2, 3, 17]:
        st.session_state["ultimo_uuid_tie_enviado"] = uuid_atual
        enviar_mensagem_telegram(
            f"⚠️ *RADAR TIE - ZONA AQUECIDA* 🟡\n"
            f"• Distância Atual: `{dist}R` sem Empate.\n"
            f"💡 Considere reforçar a cobertura no TIE."
        )

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
        tipo_win = "WIN_TIE" if ultimo_resultado == "🟡" else ("WIN" if st.session_state.tentativa == 1 else "WIN_G1")
        registrar_resultado(tipo_win, padrao_usado)
        
        txt_win = "GREEN DE PRIMEIRA! 🟡" if tipo_win == "WIN_TIE" else ("WIN DIRETO! 🎯" if tipo_win == "WIN" else "WIN NO GALE 1! 🎯")
        enviar_mensagem_telegram(f"✅ *{txt_win}*\nResultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}")
        
        st.session_state.sinal_ativo = False
        st.session_state.padrao_selecionado = None

    elif st.session_state.tentativa == 1:
        st.session_state.tentativa = 2
        enviar_mensagem_telegram(f"⚠️ *NÃO BATEU 1ª → GALE 1*\nMantém: {esperado}")
    else:
        registrar_resultado("LOSS", padrao_usado)
        enviar_mensagem_telegram(f"❌ *LOSS CONFIRMADO*\nResultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}")
        st.session_state.sinal_ativo = False
        st.session_state.padrao_selecionado = None

# -----------------------------------------------------------------------------
# 🔄 LOOP PRINCIPAL
# -----------------------------------------------------------------------------
def processar_rodada():
    cores, uuids, pontos, compostos, exibicao = buscar_historico_api()
    if not uuids:
        return

    uuid_atual = uuids[-1]
    if uuid_atual != st.session_state.ultimo_uuid_processado:
        st.session_state.ultimo_uuid_processado = uuid_atual
        registrar_log(f"Nova rodada: {exibicao[-1]}", CoresTerminal.AZUL)

    ultimo_resultado = cores[-1]

    verificar_radar_tie_aquecido(cores, uuid_atual)

    if st.session_state.sinal_ativo:
        verificar_resultado(ultimo_resultado)

    if not st.session_state.sinal_ativo:
        sugestao, prob30, prob50, padrao = analisar_multi_amostra(cores, compostos)

        if sugestao and st.session_state.ultimo_uuid_sinal_enviado != uuid_atual:
            st.session_state.sinal_ativo = True
            st.session_state.sugestao_atual = sugestao
            st.session_state.tentativa = 1
            st.session_state.padrao_selecionado = padrao
            st.session_state.ultimo_uuid_sinal_enviado = uuid_atual

            nome_cor = "🔴 BANKER" if sugestao == "🔴" else "🔵 PLAYER"
            
            mensagem = (
                "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
                f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
                "🛡️ *PROTEÇÃO:* 🟡 TIE (Empate)\n"
                "🔄 *GESTÃO:* Até Gale 1\n\n"
                f"🔍 *PADRÃO IDENTIFICADO:*\n`{padrao}`\n\n"
                f"📊 *ASSERTIVIDADE:* 30R: `{prob30:.1f}%` | 50R: `{prob50:.1f}%`\n\n"
                f"{calcular_estudo_tie(cores)}\n\n"
                f"{formatar_ranking_telegram()}\n\n"
                f"{obter_texto_placar()}"
            )

            if enviar_mensagem_telegram(mensagem):
                registrar_log(f"SINAL ENVIADO: {nome_cor} | Padrão: {padrao}", CoresTerminal.VERDE)

# -----------------------------------------------------------------------------
# 🖥️ INTERFACE PAINEL
# -----------------------------------------------------------------------------
st.title("🤖 Monitor Bac-Bo VIP")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Status", "🔴 ATIVO" if st.session_state.sinal_ativo else "🟢 AGUARDANDO")
col2.metric("Entrada", st.session_state.sugestao_atual or "—")
col3.metric("Tentativa", f"Gale {st.session_state.tentativa - 1}" if st.session_state.tentativa > 1 else "1ª Entrada")
col4.metric("Padrão em Uso", f"`{st.session_state.padrao_selecionado}`" if st.session_state.padrao_selecionado else "—")

st.subheader("🏆 Ranking de Padrões Mais Assertivos")
ranking = calcular_ranking_padroes()
if ranking:
    st.dataframe(
        [
            {
                "Posição": f"#{i}",
                "Padrão": item["padrao"],
                "Acertos": item["acertos"],
                "Total Entradas": item["total"],
                "Assertividade": f"{item['assertividade']:.1f}%"
            }
            for i, item in enumerate(ranking, 1)
        ],
        use_container_width=True, hide_index=True
    )
else:
    st.info(f"⏳ Aguardando padrões atingirem o mínimo de {CONFIG['MIN_OPERACOES_RANKING']} entradas para exibição.")

st.subheader("📋 Logs do Sistema")
log_container = st.empty()

processar_rodada()
log_container.code("\n".join(st.session_state.log_eventos[:15]), language=None)

time.sleep(CONFIG["INTERVALO_VERIFICACAO"])
st.rerun()
