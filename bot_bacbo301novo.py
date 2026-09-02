import time
from datetime import datetime
from collections import Counter
import requests
import streamlit as st

# -----------------------------------------------------------------------------
# 🛡️ CONFIGURAÇÕES E SEGURANÇA
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Monitor Bac-Bo Telegram",
    page_icon="🤖",
    layout="wide"
)

# --- CARREGAMENTO SEGURO DE CREDENCIAIS ---
def carregar_credenciais():
    """Carrega credenciais com prioridade em st.secrets, sem valores hardcoded."""
    try:
        return (
            st.secrets["TELEGRAM_TOKEN"],
            st.secrets["TELEGRAM_CHAT_ID"]
        )
    except (KeyError, Exception):
        st.error("⚠️ Credenciais do Telegram não configuradas! Configure em .streamlit/secrets.toml")
        st.stop()

TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = carregar_credenciais()

# --- CONFIGURAÇÕES DA APLICAÇÃO ---
CONFIG = {
    "MESA_ID": "cc71e81d-8b56-4868-91c7-7224be543dce",
    "INTERVALO_VERIFICACAO": 5,
    "SENSIBILIDADE_MINIMA": 70.0,
    "TAMANHO_PADRAO": 4,
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
        "log_eventos": []
    }
    for chave, valor in estados.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

inicializar_estados()

# -----------------------------------------------------------------------------
# 📝 SISTEMA DE LOGS
# -----------------------------------------------------------------------------
def registrar_log(mensagem: str) -> None:
    """Registra evento com horário, limitando o histórico."""
    horario = datetime.now().strftime('%H:%M:%S')
    entrada = f"[{horario}] {mensagem}"
    st.session_state.log_eventos.insert(0, entrada)
    if len(st.session_state.log_eventos) > 50:
        st.session_state.log_eventos.pop()

def registrar_resultado(resultado: str) -> None:
    """Armazena resultado do sinal com limite de histórico."""
    st.session_state.historico_sinais.append(resultado)
    if len(st.session_state.historico_sinais) > 50:
        st.session_state.historico_sinais.pop(0)

# -----------------------------------------------------------------------------
# 📊 PLACAR E ESTATÍSTICAS
# -----------------------------------------------------------------------------
def obter_texto_placar() -> str:
    """Gera resumo de desempenho formatado."""
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
        f"• 🟢 Tie (Proteção): `{wins_tie}`\n"
        f"• ❌ Loss: `{losses}`\n"
        f"• 🚀 *Assertividade:* `{assertividade:.1f}%`"
    )

# -----------------------------------------------------------------------------
# ✉️ ENVIO DE MENSAGENS — TELEGRAM
# -----------------------------------------------------------------------------
def enviar_mensagem_telegram(texto: str) -> bool:
    """Envia mensagem ao Telegram com tratamento de erros completo."""
    if not texto or not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        registrar_log("⚠️ Mensagem vazia ou credenciais incompletas")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=CONFIG["TIMEOUT_TELEGRAM"]
        )
        response.raise_for_status()
        return True
    except requests.exceptions.Timeout:
        registrar_log("⏱️ Tempo esgotado ao enviar ao Telegram")
    except requests.exceptions.ConnectionError:
        registrar_log("📡 Sem conexão com Telegram")
    except requests.exceptions.HTTPError as e:
        registrar_log(f"❌ Erro Telegram: {response.status_code}")
    except Exception as e:
        registrar_log(f"⚠️ Erro inesperado Telegram: {str(e)[:80]}")
    return False

# -----------------------------------------------------------------------------
# 🔌 BUSCA DE DADOS — API
# -----------------------------------------------------------------------------
def buscar_historico_api() -> tuple[list, list, list]:
    """Busca rodadas com validação robusta de formato e dados."""
    url = (
        f"{API_BASE_URL}/{CONFIG['MESA_ID']}/history"
        f"?limit={CONFIG['LIMITE_RODADAS']}"
        f"&timezone={CONFIG['TIMEZONE'].replace('/', '%2F')}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Monitor Bac-Bo)",
        "Accept": "application/json"
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=CONFIG["TIMEOUT_API"]
        )
        response.raise_for_status()
        dados = response.json()

        if not isinstance(dados, list):
            registrar_log("⚠️ Formato inesperado da API (esperava lista)")
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
                cor = "🟢"
            else:
                continue

            if not uuid_rodada:
                continue

            cores.append(cor)
            uuids.append(uuid_rodada)
            pontos.append(ponto)

        if not uuids:
            registrar_log("⚠️ API retornou sem rodadas válidas")
            return [], [], []

        return cores[::-1], uuids[::-1], pontos[::-1]

    except requests.exceptions.Timeout:
        registrar_log("⏱️ API demorou demais para responder")
    except requests.exceptions.ConnectionError:
        registrar_log("📡 Sem conexão com a API")
    except Exception as e:
        registrar_log(f"❌ Erro na API: {str(e)[:80]}")

    return [], [], []

# -----------------------------------------------------------------------------
# 🧠 ANÁLISE DE PADRÕES
# -----------------------------------------------------------------------------
def analisar_multi_amostra(historico_cores: list) -> tuple[str | None, float, float]:
    """Analisa padrão em múltiplas janelas de tempo com validação."""
    minimo_rodadas = 51
    if len(historico_cores) < minimo_rodadas:
        return None, 0.0, 0.0

    padrao = historico_cores[-CONFIG["TAMANHO_PADRAO"]:]

    def calcular_probabilidade(amostra_tamanho: int) -> tuple[float, float]:
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

    if prob_r_30 >= sensibilidade and prob_r_50 >= sensibilidade:
        return "🔴", round(prob_r_30, 1), round(prob_r_50, 1)
    elif prob_b_30 >= sensibilidade and prob_b_50 >= sensibilidade:
        return "🔵", round(prob_b_30, 1), round(prob_b_50, 1)

    return None, 0.0, 0.0

# -----------------------------------------------------------------------------
# 📈 ESTUDO DE TIE / EMPATE
# -----------------------------------------------------------------------------
def calcular_estudo_tie(historico_cores: list) -> str:
    """Analisa frequência e intervalo de empates."""
    if "🟢" not in historico_cores or len(historico_cores) < 50:
        return "⚪ *Status Tie:* Dados insuficientes para análise."

    indices = [i for i, c in enumerate(historico_cores) if c == "🟢"]
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
def verificar_resultado(ultimo_resultado: str) -> None:
    """Compara resultado com sinal ativo e registra desempenho."""
    if not st.session_state.sinal_ativo:
        return

    esperado = st.session_state.sugestao_atual
    acertou = (ultimo_resultado == esperado) or (ultimo_resultado == "🟢")

    if acertou:
        if ultimo_resultado == "🟢":
            registrar_resultado("WIN_TIE")
            if st.session_state.tentativa == 1:
                enviar_mensagem_telegram(
                    f"✅ *GREEN DE PRIMEIRA!* 🟢\n"
                    f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
                )
        elif st.session_state.tentativa == 1:
            registrar_resultado("WIN")
            enviar_mensagem_telegram(
                f"✅ *WIN DIRETO!* 🎯\n"
                f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
            )
        else:
            registrar_resultado("WIN_G1")
            enviar_mensagem_telegram(
                f"✅ *WIN NO GALE 1!* 🎯\n"
                f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
            )
        st.session_state.sinal_ativo = False

    elif st.session_state.tentativa == 1:
        st.session_state.tentativa = 2
        enviar_mensagem_telegram(
            f"⚠️ *NÃO BATEU NA 1ª! VAMOS PARA O GALE 1*\n"
            f"Entrada mantida: {esperado}"
        )
    else:
        registrar_resultado("LOSS")
        enviar_mensagem_telegram(
            f"❌ *LOSS CONFIRMADO*\n"
            f"Resultado: `{ultimo_resultado}`\n\n{obter_texto_placar()}"
        )
        st.session_state.sinal_ativo = False

# -----------------------------------------------------------------------------
# 🔄 PROCESSAMENTO PRINCIPAL
# -----------------------------------------------------------------------------
def processar_rodada():
    """Fluxo completo: buscar → analisar → enviar → acompanhar."""
    cores, uuids, _ = buscar_historico_api()

    if not uuids:
        registrar_log("⏳ Aguardando dados da API...")
        return

    uuid_atual = uuids[-1]

    # Ignorar se rodada já foi processada
    if uuid_atual == st.session_state.ultimo_uuid_processado:
        return

    st.session_state.ultimo_uuid_processado = uuid_atual
    ultimo_resultado = cores[-1]
    registrar_log(f"🔄 Nova rodada: {ultimo_resultado} | UUID: {uuid_atual[:12]}...")

    # Verificar resultado de sinal em andamento
    if st.session_state.sinal_ativo:
        verificar_resultado(ultimo_resultado)

    # Emitir NOVO sinal se não houver um ativo
    if not st.session_state.sinal_ativo:
        sugestao, prob30, prob50 = analisar_multi_amostra(cores)

        if sugestao and st.session_state.ultimo_uuid_sinal_enviado != uuid_atual:
            st.session_state.sinal_ativo = True
            st.session_state.sugestao_atual = sugestao
            st.session_state.tentativa = 1
            st.session_state.ultimo_uuid_sinal_enviado = uuid_atual

            nome_cor = "🔴 BANKER" if sugestao == "🔴" else "🔵 PLAYER"
            estudo_tie = calcular_estudo_tie(cores)
            placar = obter_texto_placar()

            mensagem = (
                "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
                f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
                "🛡️ *PROTEÇÃO:* 🟢 TIE (Empate)\n"
                "🔄 *GESTÃO:* Até Gale 1\n\n"
                "📊 *ASSERTIVIDADE DA ENTRADA:*\n"
                f"• *Momento (30R):* `{prob30:.1f}%`\n"
                f"• *Ciclo (50R):* `{prob50:.1f}%`\n\n"
                f"📈 *ESTUDO DE TIE:*\n{estudo_tie}\n\n"
                f"{placar}\n\n"
                f"📝 *Últimas 10 Rodadas:*\n`{' | '.join(cores[-10:])}`"
            )

            if enviar_mensagem_telegram(mensagem):
                registrar_log(f"✅ Sinal enviado: {nome_cor}")
            else:
                registrar_log("❌ Falha ao enviar sinal ao Telegram")
                st.session_state.sinal_ativo = False


# -----------------------------------------------------------------------------
# 🖥️ INTERFACE DO USUÁRIO
# -----------------------------------------------------------------------------
st.title("🤖 Monitor de Sinais Bac-Bo")

col1, col2, col3 = st.columns(3)
col1.metric("Status do Sinal", "ATIVO" if st.session_state.sinal_ativo else "AGUARDANDO")
col2.metric("Sugestão Atual", st.session_state.sugestao_atual or "—")
col3.metric("Gale Atual", st.session_state.tentativa or "—")

st.subheader("📋 Logs de Monitoramento")
log_container = st.empty()

# Execução
processar_rodada()
log_container.code("\n".join(st.session_state.log_eventos[:15]), language=None)

# Controle de taxa de atualização
time.sleep(CONFIG["INTERVALO_VERIFICACAO"])
st.rerun()
