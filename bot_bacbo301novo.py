import time
from datetime import datetime
from collections import Counter
import requests
import streamlit as st

# --- CONFIGURAÇÃO DA PÁGINA STREAMLIT ---
st.set_page_config(page_title="Monitor Bac-Bo Telegram", page_icon="🤖", layout="wide")

# --- CREDENCIAIS (Via Streamlit Secrets ou Fallback) ---
TELEGRAM_TOKEN = st.secrets.get("TELEGRAM_TOKEN", "8961731012:AAFsDYcVN5VbCFMsOW_Mc3V95WEZ_ogbZBw")
TELEGRAM_CHAT_ID = st.secrets.get("TELEGRAM_CHAT_ID", "-1004319410022")
MESA_ID = "cc71e81d-8b56-4868-91c7-7224be543dce"

INTERVALO_VERIFICACAO = 5
SENSIBILIDADE_STRICT = 70.0

# --- ESTADOS GLOBAIS DA SESSÃO ---
if "sinal_ativo" not in st.session_state:
    st.session_state.sinal_ativo = False
if "sugestao_atual" not in st.session_state:
    st.session_state.sugestao_atual = None
if "tentativa" not in st.session_state:
    st.session_state.tentativa = 0
if "ultimo_uuid_processado" not in st.session_state:
    st.session_state.ultimo_uuid_processado = None
if "ultimo_uuid_sinal_enviado" not in st.session_state:
    st.session_state.ultimo_uuid_sinal_enviado = None
if "historico_sinais" not in st.session_state:
    st.session_state.historico_sinais = []
if "log_eventos" not in st.session_state:
    st.session_state.log_eventos = []

def registrar_log(mensagem):
    horario = datetime.now().strftime('%H:%M:%S')
    st.session_state.log_eventos.insert(0, f"[{horario}] {mensagem}")

def registrar_resultado(resultado):
    st.session_state.historico_sinais.append(resultado)
    if len(st.session_state.historico_sinais) > 50:
        st.session_state.historico_sinais.pop(0)

def obter_texto_placar():
    if not st.session_state.historico_sinais:
        return "📊 *PLACAR:* Aguardando primeiras entradas da sessão..."

    total = len(st.session_state.historico_sinais)
    wins_diretos = st.session_state.historico_sinais.count("WIN")
    wins_g1 = st.session_state.historico_sinais.count("WIN_G1")
    wins_tie = st.session_state.historico_sinais.count("WIN_TIE")
    losses = st.session_state.historico_sinais.count("LOSS")
    
    total_wins = wins_diretos + wins_g1 + wins_tie
    assertividade = (total_wins / total * 100) if total > 0 else 0

    return (
        f"📊 *PLACAR ACUMULADO (Últimas {total} entradas):*\n"
        f"• 🎯 Win Direto: `{wins_diretos}`\n"
        f"• 🔄 Win Gale 1: `{wins_g1}`\n"
        f"• 🟢 Tie (Proteção): `{wins_tie}`\n"
        f"• ❌ Loss: `{losses}`\n"
        f"• 🚀 *Assertividade:* `{assertividade:.1f}%`"
    )

def enviar_mensagem_telegram(texto):
    if not texto:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        registrar_log(f"Erro Telegram: {e}")

def buscar_historico_api():
    url_api = f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{MESA_ID}/history?limit=200&timezone=America%2FSao_Paulo"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        response = requests.get(url_api, headers=headers, timeout=10)
        if response.status_code != 200:
            return [], [], []

        dados = response.json()
        if not isinstance(dados, list):
            return [], [], []

        resultados_cores, uuids, resultados_pontos = [], [], []

        for item in dados:
            vencedor = str(item.get("type", "")).upper()
            uuid_rodada = item.get("uuid", "")
            ponto_vencedor = item.get("result", 0)

            if "BANKER" in vencedor or "RED" in vencedor:
                resultados_cores.append("🔴")
            elif "PLAYER" in vencedor or "BLUE" in vencedor:
                resultados_cores.append("🔵")
            elif "TIE" in vencedor or "YELLOW" in vencedor:
                resultados_cores.append("🟢")
            else:
                continue

            uuids.append(uuid_rodada)
            resultados_pontos.append(ponto_vencedor)

        return resultados_cores[::-1], uuids[::-1], resultados_pontos[::-1]
    except Exception as e:
        registrar_log(f"Erro ao buscar API: {e}")
        return [], [], []

def analisar_multi_amostra(historico_cores, tamanho_padrao=4):
    if len(historico_cores) < 51:
        return None, 0.0, 0.0

    padrao_atual = historico_cores[-tamanho_padrao:]

    def obter_probabilidade(r):
        amostra = historico_cores[-r:]
        total, b_cnt, p_cnt = 0, 0, 0
        for i in range(len(amostra) - tamanho_padrao):
            if amostra[i : i + tamanho_padrao] == padrao_atual:
                total += 1
                proximo = amostra[i + tamanho_padrao]
                if proximo == "🔴":
                    b_cnt += 1
                elif proximo == "🔵":
                    p_cnt += 1
        prob_b = (b_cnt / total * 100) if total > 0 else 0
        prob_p = (p_cnt / total * 100) if total > 0 else 0
        return prob_b, prob_p

    prob_b_30, prob_p_30 = obter_probabilidade(30)
    prob_b_50, prob_p_50 = obter_probabilidade(50)

    if prob_b_30 >= SENSIBILIDADE_STRICT and prob_b_50 >= SENSIBILIDADE_STRICT:
        return "🔴", prob_b_30, prob_b_50
    elif prob_p_30 >= SENSIBILIDADE_STRICT and prob_p_50 >= SENSIBILIDADE_STRICT:
        return "🔵", prob_p_30, prob_p_50

    return None, 0.0, 0.0

def calcular_estudo_probabilidade_tie(historico_cores):
    if "🟢" not in historico_cores or len(historico_cores) < 50:
        return "⚪ *Status Tie:* Dados insuficientes para análise."

    total_rodadas = len(historico_cores)
    indices_tie = [i for i, cor in enumerate(historico_cores) if cor == "🟢"]
    distancia_atual = (total_rodadas - 1) - indices_tie[-1]

    gaps_historico = []
    for idx in range(1, len(indices_tie)):
        gap = indices_tie[idx] - indices_tie[idx - 1] - 1
        gaps_historico.append(gap)

    contagem_gaps = Counter(gaps_historico)
    freq_distancia_atual = contagem_gaps.get(distancia_atual, 0)

    if freq_distancia_atual >= 2:
        status = f"🔥 *PROBABILIDADE ALTA!* O intervalo de `{distancia_atual}R` sem Tie pagou `{freq_distancia_atual}x` nas últimas 200 rodadas."
    elif distancia_atual in [0, 1, 2, 3]:
        status = f"⚡ *ZONA DE ECO/REPETIÇÃO!* Apenas `{distancia_atual}R` desde o último Tie."
    else:
        status = f"📊 *Status Normal:* `{distancia_atual}R` sem Tie (Frequência histórica do gap: {freq_distancia_atual}x)."

    return status

def verificar_resultado_sinal(ultimo_resultado):
    if ultimo_resultado == st.session_state.sugestao_atual or ultimo_resultado == "🟢":
        if ultimo_resultado == "🟢":
            registrar_resultado("WIN_TIE")
            if st.session_state.tentativa == 1:
                placar = obter_texto_placar()
                enviar_mensagem_telegram(f"✅ *GREEN DE PRIMEIRA!* 🟢\nResultado da Mesa: `{ultimo_resultado}`\n\n{placar}")
            else:
                pass  # Silêncio no Gale no Tie
        elif st.session_state.tentativa == 1:
            registrar_resultado("WIN")
            placar = obter_texto_placar()
            enviar_mensagem_telegram(f"✅ *WIN DIRETO DE PRIMEIRA!* 🎯\nResultado da Mesa: `{ultimo_resultado}`\n\n{placar}")
        else:
            registrar_resultado("WIN_G1")
            placar = obter_texto_placar()
            enviar_mensagem_telegram(f"✅ *WIN NO GALE 1!* 🎯\nResultado da Mesa: `{ultimo_resultado}`\n\n{placar}")

        st.session_state.sinal_ativo = False

    elif st.session_state.tentativa == 1:
        st.session_state.tentativa = 2
        enviar_mensagem_telegram(f"⚠️ *NÃO BATEU NA 1ª! VAMOS PARA O GALE 1*\nEntrada Mantida: {st.session_state.sugestao_atual}")

    elif st.session_state.tentativa == 2:
        registrar_resultado("LOSS")
        placar = obter_texto_placar()
        enviar_mensagem_telegram(f"❌ *LOSS CONFIRMADO*\nResultado da Mesa: `{ultimo_resultado}`\n\n{placar}")
        st.session_state.sinal_ativo = False

# --- INTERFACE E EXECUÇÃO ---
st.title("🤖 Monitor de Sinais Bac-Bo")

col1, col2, col3 = st.columns(3)
col1.metric("Status do Sinal", "ATIVO" if st.session_state.sinal_ativo else "AGUARDANDO")
col2.metric("Sugestão Atual", st.session_state.sugestao_atual or "Nenhuma")
col3.metric("Gale Atual", st.session_state.tentativa)

st.subheader("Logs de Monitoramento")
log_container = st.empty()

def processar_rodada():
    cores, uuids, pontos = buscar_historico_api()

    if not uuids:
        return

    uuid_atual = uuids[-1]

    if uuid_atual != st.session_state.ultimo_uuid_processado:
        st.session_state.ultimo_uuid_processado = uuid_atual
        ultimo_resultado = cores[-1]

        registrar_log(f"Nova rodada processada: {ultimo_resultado} ({uuid_atual})")

        if st.session_state.sinal_ativo:
            verificar_resultado_sinal(ultimo_resultado)

        if not st.session_state.sinal_ativo:
            sugestao_cor, prob_30, prob_50 = analisar_multi_amostra(cores)

            if sugestao_cor and st.session_state.ultimo_uuid_sinal_enviado != uuid_atual:
                st.session_state.sinal_ativo = True
                st.session_state.sugestao_atual = sugestao_cor
                st.session_state.tentativa = 1
                st.session_state.ultimo_uuid_sinal_enviado = uuid_atual

                nome_cor = "🔴 BANKER" if sugestao_cor == "🔴" else "🔵 PLAYER"
                estudo_tie = calcular_estudo_probabilidade_tie(cores)
                placar = obter_texto_placar()

                mensagem = (
                    "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
                    f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
                    "🛡️ *PROTEÇÃO:* 🟢 TIE (Empate)\n"
                    "🔄 *GESTÃO:* Mão Leve (Até Gale 1)\n\n"
                    "📊 *ASSERTIVIDADE DA ENTRADA:*\n"
                    f"• *Momento (30R):* `{prob_30:.1f}%`\n"
                    f"• *Ciclo (50R):* `{prob_50:.1f}%`\n\n"
                    "📈 *ESTUDO DE PROBABILIDADE DO TIE (200R):*\n"
                    f"{estudo_tie}\n\n"
                    f"{placar}\n\n"
                    f"📝 *Últimas 10 Rodadas:*\n`{' | '.join(cores[-10:])}`"
                )
                enviar_mensagem_telegram(mensagem)

processar_rodada()
log_container.write("\n".join(st.session_state.log_eventos[:15]))

time.sleep(INTERVALO_VERIFICACAO)
st.rerun()
