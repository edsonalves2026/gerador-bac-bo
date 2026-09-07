import json
import os
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
        st.error("⚠️ Credenciais do Telegram não configuradas no secrets.toml!")
        st.stop()

TELEGRAM_TOKEN, TELEGRAM_CHAT_ID = carregar_credenciais()

# -----------------------------------------------------------------------------
# 💾 PERSISTÊNCIA DE PADRÕES FIXOS EM ARQUIVO LOCAL (JSON)
# -----------------------------------------------------------------------------
ARQUIVO_PADROES = "padroes_fixos.json"

def carregar_padroes_locais():
    if os.path.exists(ARQUIVO_PADROES):
        try:
            with open(ARQUIVO_PADROES, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_padroes_locais(padroes):
    try:
        with open(ARQUIVO_PADROES, "w", encoding="utf-8") as f:
            json.dump(padroes, f, ensure_ascii=False, indent=4)
    except Exception as e:
        log_terminal(f"❌ Erro ao salvar JSON: {e}", CoresTerminal.VERMELHO)

if "PADROES_MANUAIS_COMPOSTOS" not in st.session_state:
    st.session_state.PADROES_MANUAIS_COMPOSTOS = carregar_padroes_locais()

# -----------------------------------------------------------------------------
# 🎛️ PAINEL DE CONTROLE (INTERFACE SIDEBAR)
# -----------------------------------------------------------------------------
st.sidebar.title("🎛️ Painel de Controle")

INTERVALO_VERIFICACAO = st.sidebar.slider(
    "⏱️ Intervalo de Verificação (s)",
    min_value=2, max_value=30, value=8, step=1
)

SENSIBILIDADE_MINIMA = st.sidebar.slider(
    "🎯 Sensibilidade Mínima (%)",
    min_value=50.0, max_value=95.0, value=65.0, step=1.0
)

TAMANHO_PADRAO = st.sidebar.slider(
    "📏 Tamanho do Padrão Dinâmico (rodadas)",
    min_value=2, max_value=8, value=3, step=1
)

MIN_OPERACOES_RANKING = st.sidebar.number_input(
    "🏆 Mínimo de Amostras p/ Ranking",
    min_value=1, max_value=10, value=4
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
# 🧠 ESTADOS INICIAIS
# -----------------------------------------------------------------------------
def inicializar_estados():
    estados = {
        "bot_rodando": False,
        "sinal_ativo": False,
        "sugestao_atual": None,
        "tentativa": 0,
        "ultimo_uuid_processado": None,
        "ultimo_uuid_sinal_enviado": None,
        "historico_sinais": [],
        "historico_ciclo": [],
        "log_eventos": [],
        "padrao_selecionado": None,
        "ranking_padroes": {}
    }
    for chave, valor in estados.items():
        if chave not in st.session_state:
            st.session_state[chave] = valor

inicializar_estados()

# -----------------------------------------------------------------------------
# ✉️ TELEGRAM E LOGS
# -----------------------------------------------------------------------------
def registrar_log(mensagem: str, cor_terminal=CoresTerminal.RESET):
    log_terminal(mensagem, cor_terminal)
    horario = datetime.now().strftime('%H:%M:%S')
    st.session_state.log_eventos.insert(0, f"[{horario}] {mensagem}")
    if len(st.session_state.log_eventos) > 50:
        st.session_state.log_eventos.pop()

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
# 🔌 BUSCA DE DADOS (API TIPMINER BAC BO)
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
                cor = "🔴"
            elif "PLAYER" in tipo or "BLUE" in tipo:
                cor = "🔵"
            elif "TIE" in tipo or "YELLOW" in tipo:
                cor = "🟡"
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
# 🧠 BUSCA HÍBRIDA DE PADRÕES
# -----------------------------------------------------------------------------
def analisar_multi_amostra(historico_cores: list, historico_compostos: list):
    tamanho_p = CONFIG["TAMANHO_PADRAO"]
    MINIMO_OCORRENCIAS = 3

    if len(historico_cores) < 5:
        return None, 0.0, 0.0, None

    for chave, item in st.session_state.PADROES_MANUAIS_COMPOSTOS.items():
        if not item.get("ativo", True):
            continue

        padrao_fixo = item["padrao"]
        tam_fixo = len(padrao_fixo)

        if len(historico_cores) < tam_fixo:
            continue

        eh_composto = any(" " in elem for elem in padrao_fixo)
        fatia_atual = historico_compostos[-tam_fixo:] if eh_composto else historico_cores[-tam_fixo:]

        if fatia_atual == padrao_fixo:
            sugestao = item["sugestao"]
            padrao_str = f"📌 FIXO [{chave}]: {' | '.join(padrao_fixo)}"
            return sugestao, 100.0, 100.0, padrao_str

    def buscar_frequencia(lista_historico, padrao_procurado):
        total, verm, azul = 0, 0, 0
        tam = len(padrao_procurado)
        
        for i in range(len(lista_historico) - tam):
            if lista_historico[i : i + tam] == padrao_procurado:
                proximo = historico_cores[i + tam]
                total += 1
                if proximo == "🔴":
                    verm += 1
                elif proximo == "🔵":
                    azul += 1

        if total < MINIMO_OCORRENCIAS:
            return 0.0, 0.0, total

        return (verm / total) * 100, (azul / total) * 100, total

    if len(historico_compostos) >= tamanho_p:
        padrao_comp = historico_compostos[-tamanho_p:]
        prob_r_comp, prob_b_comp, oc_comp = buscar_frequencia(historico_compostos, padrao_comp)

        if oc_comp >= MINIMO_OCORRENCIAS:
            padrao_comp_str = " | ".join(padrao_comp)
            if prob_r_comp >= CONFIG["SENSIBILIDADE_MINIMA"]:
                return "🔴", round(prob_r_comp, 1), round(prob_r_comp, 1), padrao_comp_str
            if prob_b_comp >= CONFIG["SENSIBILIDADE_MINIMA"]:
                return "🔵", round(prob_b_comp, 1), round(prob_b_comp, 1), padrao_comp_str

    if len(historico_cores) >= tamanho_p:
        padrao_cor = historico_cores[-tamanho_p:]
        prob_r_30, prob_b_30, _ = buscar_frequencia(historico_cores[-30:], padrao_cor)
        prob_r_tot, prob_b_tot, oc_tot = buscar_frequencia(historico_cores, padrao_cor)

        padrao_cor_str = " | ".join(padrao_cor)

        if oc_tot >= MINIMO_OCORRENCIAS:
            if prob_r_tot >= CONFIG["SENSIBILIDADE_MINIMA"]:
                return "🔴", round(prob_r_30, 1), round(prob_r_tot, 1), padrao_cor_str
            if prob_b_tot >= CONFIG["SENSIBILIDADE_MINIMA"]:
                return "🔵", round(prob_r_30, 1), round(prob_r_tot, 1), padrao_cor_str

    return None, 0.0, 0.0, None

# -----------------------------------------------------------------------------
# 📝 PLACAR E RESULTADOS
# -----------------------------------------------------------------------------
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
# 📊 RELATÓRIO MANUAL DE ASSERTIVIDADE (AJUSTADO PARA PERMITIR DIGITAÇÃO)
# -----------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("📊 Relatório Manual de Assertividade")

qtd_rodadas_relatorio = st.sidebar.slider(
    "Amostra de Rodadas:",
    min_value=10, max_value=200, value=200, step=10
)

# Campo que aceita digitação de números (1 a 12) ou nomes de cores (BANKER, PLAYER, TIE, ou números)
entrada_alvo_digitada = st.sidebar.text_input(
    "🔎 Digite o Valor ou Entradas Alvo (ex: 8, 10, PLAYER, BANKER):",
    placeholder="Ex: 8 ou 8, 10 ou PLAYER"
)

def processar_filtro_digitado(texto_input: str):
    """
    Interpreta o que o usuário digitou no campo de busca.
    Extrai números (1 a 12) mesmo com palavras como 'Tier', 'Ponto' e separa as entradas.
    Validado para PLAYER, BANKER e TIE.
    """
    if not texto_input:
        return [], []

    texto_upper = texto_input.upper()
    
    filtro_entradas = []
    filtro_pontos = []

    # Extrai cores/entradas (Banker, Player ou Tie/Empate)
    if "RED" in texto_upper or "BANKER" in texto_upper or "🔴" in texto_upper or "VERMELHO" in texto_upper:
        filtro_entradas.append("🔴 BANKER")
    if "BLUE" in texto_upper or "PLAYER" in texto_upper or "🔵" in texto_upper or "AZUL" in texto_upper:
        filtro_entradas.append("🔵 PLAYER")
    if "YELLOW" in texto_upper or "TIE" in texto_upper or "TIER" in texto_upper or "🟡" in texto_upper or "EMPATE" in texto_upper:
        filtro_entradas.append("🟡 TIE")

    # Extrai qualquer número de 1 a 12 presente no texto (ex: 'Tier 8', 'Ponto 10', '8')
    numeros_encontrados = re.findall(r'\b(1[0-2]|[1-9])\b', texto_input)
    for num in numeros_encontrados:
        filtro_pontos.append(num)

    return list(set(filtro_entradas)), list(set(filtro_pontos))

def gerar_e_enviar_relatorio_bacbo_pontos(limite_rodadas: int, texto_filtro: str):
    filtro_entradas, filtro_pontos = processar_filtro_digitado(texto_filtro)

    cores, uuids, pontos, compostos, exibicao = buscar_historico_api()

    if not cores or len(cores) < 10:
        return False, "⚠️ Histórico insuficiente retornado pela API."

    amostra_cores = cores[-limite_rodadas:]
    amostra_pontos = pontos[-limite_rodadas:]
    amostra_compostos = compostos[-limite_rodadas:]

    indices_tie = [i for i, c in enumerate(amostra_cores) if c == "🟡"]
    total_ties = len(indices_tie)

    if total_ties >= 2:
        gaps_tie = [indices_tie[i] - indices_tie[i-1] for i in range(1, total_ties)]
        media_rodadas_tie = sum(gaps_tie) / len(gaps_tie)
        tempo_medio_min = (media_rodadas_tie * 30) / 60
        txt_estatistica_tie = (
            f"🟡 *Saídas do TIE:* `{total_ties}x` na amostra\n"
            f"⏱️ *Intervalo Médio do TIE:* A cada `{media_rodadas_tie:.1f}` rodadas "
            f"(~`{tempo_medio_min:.1f}` min)"
        )
    elif total_ties == 1:
        txt_estatistica_tie = f"🟡 *Saídas do TIE:* Apenas `1x` na amostra selecionada."
    else:
        txt_estatistica_tie = f"🟡 *Saídas do TIE:* Nenhum Empate nas últimas `{len(amostra_cores)}` rodadas."

    contagem_padroes = {}

    if filtro_pontos:
        pontos_alvo = [int(p) for p in filtro_pontos]
        cores_alvo = []
        if filtro_entradas:
            if "🔴 BANKER" in filtro_entradas: cores_alvo.append("🔴")
            if "🔵 PLAYER" in filtro_entradas: cores_alvo.append("🔵")
            if "🟡 TIE" in filtro_entradas: cores_alvo.append("🟡")
        else:
            cores_alvo = ["🔴", "🔵", "🟡"]

        for i in range(len(amostra_cores) - 1):
            cor_atual = amostra_cores[i]
            ponto_atual = amostra_pontos[i]

            if ponto_atual in pontos_alvo and cor_atual in cores_alvo:
                chave_padrao = f"Mão Gatilho: {cor_atual} ({ponto_atual})"
                sugestao_alvo = cores_alvo[0] if len(cores_alvo) == 1 else cor_atual
                nome_sugestao = "🔴 BANKER" if sugestao_alvo == "🔴" else ("🔵 PLAYER" if sugestao_alvo == "🔵" else "🟡 TIE")

                if chave_padrao not in contagem_padroes:
                    contagem_padroes[chave_padrao] = {
                        "total": 0,
                        "acertos_direto": 0,
                        "acertos_gale": 0,
                        "sugestao": nome_sugestao
                    }

                contagem_padroes[chave_padrao]["total"] += 1

                res_1 = amostra_cores[i + 1]
                if res_1 == sugestao_alvo or res_1 == "🟡":
                    contagem_padroes[chave_padrao]["acertos_direto"] += 1
                elif i + 2 < len(amostra_cores):
                    res_2 = amostra_cores[i + 2]
                    if res_2 == sugestao_alvo or res_2 == "🟡":
                        contagem_padroes[chave_padrao]["acertos_gale"] += 1
    else:
        tamanho_p = CONFIG["TAMANHO_PADRAO"]
        for i in range(tamanho_p, len(amostra_cores) - 1):
            sub_cores = amostra_cores[:i]
            sub_compostos = amostra_compostos[:i]

            sugestao, prob30, prob50, padrao_str = analisar_multi_amostra(sub_cores, sub_compostos)

            if not sugestao or not padrao_str:
                continue

            nome_sugestao = "🔴 BANKER" if sugestao == "🔴" else ("🔵 PLAYER" if sugestao == "🔵" else "🟡 TIE")

            if filtro_entradas and nome_sugestao not in filtro_entradas:
                continue

            if padrao_str not in contagem_padroes:
                contagem_padroes[padrao_str] = {
                    "total": 0,
                    "acertos_direto": 0,
                    "acertos_gale": 0,
                    "sugestao": nome_sugestao
                }

            contagem_padroes[padrao_str]["total"] += 1

            res_1 = amostra_cores[i]
            if res_1 == sugestao or res_1 == "🟡":
                contagem_padroes[padrao_str]["acertos_direto"] += 1
            elif i + 1 < len(amostra_cores):
                res_2 = amostra_cores[i + 1]
                if res_2 == sugestao or res_2 == "🟡":
                    contagem_padroes[padrao_str]["acertos_gale"] += 1

    if not contagem_padroes:
        return False, f"⚠️ Nenhum padrão atendeu aos critérios digitados ('{texto_filtro}') nas últimas {len(amostra_cores)} rodadas."

    total_sinais = sum(p["total"] for p in contagem_padroes.values())
    total_diretos = sum(p["acertos_direto"] for p in contagem_padroes.values())
    total_gales = sum(p["acertos_gale"] for p in contagem_padroes.values())
    total_acertos = total_diretos + total_gales
    taxa_geral = (total_acertos / total_sinais * 100) if total_sinais > 0 else 0.0

    filtros_aplicados = []
    if filtro_entradas:
        filtros_aplicados.append(f"Cores: `{', '.join(filtro_entradas)}`")
    if filtro_pontos:
        filtros_aplicados.append(f"Pontos: `{', '.join(filtro_pontos)}`")

    txt_filtros = f"\n🎯 *Filtros Digitados:* `{texto_filtro}`" if texto_filtro else ""

    msg = (
        f"📊 *RELATÓRIO DE ASSERTIVIDADE HISTÓRICA*\n"
        f"🆔 *Mesa:* `{CONFIG['MESA_ID'][:8]}...`\n"
        f"🔄 *Amostra Analisada:* Últimas `{len(amostra_cores)}` rodadas{txt_filtros}\n"
        f"-----------------------------------\n"
        f"{txt_estatistica_tie}\n"
        f"-----------------------------------\n"
        f"🎯 *Total Ocorrências:* `{total_sinais}` | 🚀 *Assertividade:* `{taxa_geral:.1f}%`\n"
        f"🎯 *Win Direto:* `{total_diretos}` | 🔄 *Win Gale 1:* `{total_gales}`\n"
        f"-----------------------------------\n"
        f"🏆 *OCORRÊNCIAS ENCONTRADAS:*\n"
    )

    padroes_ordenados = sorted(
        contagem_padroes.items(),
        key=lambda x: ((x[1]["acertos_direto"] + x[1]["acertos_gale"]) / x[1]["total"]) if x[1]["total"] > 0 else 0,
        reverse=True
    )

    for padrao, info in padroes_ordenados[:5]:
        total_p = info["total"]
        acertos_p = info["acertos_direto"] + info["acertos_gale"]
        taxa_p = (acertos_p / total_p * 100) if total_p > 0 else 0.0
        msg += (
            f"\n• `{padrao}`\n"
            f"  ➔ Alvo: *{info['sugestao']}* | Taxa: `{taxa_p:.1f}%` ({acertos_p}/{total_p})\n"
        )

    msg += "\n⚠️ *Relatório estatístico gerado sob demanda.*"

    if enviar_mensagem_telegram(msg):
        return True, "✅ Relatório enviado com sucesso ao Telegram!"
    else:
        return False, "❌ Falha ao enviar a mensagem ao Telegram."

if st.sidebar.button("📤 Gerar e Enviar Relatório Manual"):
    with st.spinner("Processando histórico..."):
        sucesso, msg_status = gerar_e_enviar_relatorio_bacbo_pontos(
            qtd_rodadas_relatorio,
            entrada_alvo_digitada
        )
        if sucesso:
            st.sidebar.success(msg_status)
        else:
            st.sidebar.warning(msg_status)

# -----------------------------------------------------------------------------
# 📌 GERENCIADOR DE PADRÕES FIXOS NA SIDEBAR
# -----------------------------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("📌 Cadastrar Padrão Fixo Manual")

with st.sidebar.form("form_novo_padrao", clear_on_submit=True):
    nome_padrao = st.text_input("Nome do Padrão", placeholder="Ex: Duplo 10 e 8")
    sequencia_input = st.text_input(
        "Sequência (separada por vírgula)", 
        placeholder="Ex: 🔴 10, 🔵 8 ou 🔴, 🔴"
    )
    sugestao_entrada = st.selectbox("Entrada Recomendada", ["🔴 BANKER", "🔵 PLAYER", "🟡 TIE"])
    btn_salvar = st.form_submit_button("➕ Salvar Padrão Fixo")

    if btn_salvar and sequencia_input and nome_padrao:
        lista_seq = [item.strip() for item in sequencia_input.split(",")]
        
        if "BANKER" in sugestao_entrada:
            cor_sugestao, nome_sugestao = "🔴", "BANKER"
        elif "PLAYER" in sugestao_entrada:
            cor_sugestao, nome_sugestao = "🔵", "PLAYER"
        else:
            cor_sugestao, nome_sugestao = "🟡", "TIE"

        st.session_state.PADROES_MANUAIS_COMPOSTOS[nome_padrao] = {
            "padrao": lista_seq,
            "sugestao": cor_sugestao,
            "nome_sugestao": nome_sugestao,
            "ativo": True
        }
        salvar_padroes_locais(st.session_state.PADROES_MANUAIS_COMPOSTOS)
        st.sidebar.success(f"Padrão '{nome_padrao}' salvo!")

if st.session_state.PADROES_MANUAIS_COMPOSTOS:
    st.sidebar.markdown("**Padrões Salvos:**")
    for chave, item in list(st.session_state.PADROES_MANUAIS_COMPOSTOS.items()):
        seq_txt = " | ".join(item["padrao"])
        st.sidebar.text(f"• {chave}: [{seq_txt}] ➔ {item['sugestao']}")
        if st.sidebar.button(f"🗑️ Remover {chave}", key=f"del_{chave}"):
            del st.session_state.PADROES_MANUAIS_COMPOSTOS[chave]
            salvar_padroes_locais(st.session_state.PADROES_MANUAIS_COMPOSTOS)
            st.rerun()

# -----------------------------------------------------------------------------
# 🔄 LÓGICA DE PROCESSAMENTO DE RODADAS
# -----------------------------------------------------------------------------
def processar_rodada():
    cores, uuids, pontos, compostos, exibicao = buscar_historico_api()
    if not uuids:
        return

    uuid_atual = uuids[-1]
    
    if uuid_atual != st.session_state.ultimo_uuid_processado:
        st.session_state.ultimo_uuid_processado = uuid_atual
        registrar_log(f"Nova rodada: {exibicao[-1]}", CoresTerminal.AZUL)

    if st.session_state.bot_rodando:
        ultimo_resultado = cores[-1]
        ultimo_ponto = pontos[-1]

        if st.session_state.sinal_ativo:
            verificar_resultado(ultimo_resultado, ultimo_ponto)

        if not st.session_state.sinal_ativo:
            sugestao, prob30, prob50, padrao = analisar_multi_amostra(cores, compostos)

            if sugestao and st.session_state.ultimo_uuid_sinal_enviado != uuid_atual:
                st.session_state.sinal_ativo = True
                st.session_state.sugestao_atual = sugestao
                st.session_state.tentativa = 1
                st.session_state.padrao_selecionado = padrao
                st.session_state.ultimo_uuid_sinal_enviado = uuid_atual

                nome_cor = "🔴 BANKER" if sugestao == "🔴" else ("🔵 PLAYER" if sugestao == "🔵" else "🟡 TIE")

                mensagem = (
                    "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
                    f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
                    "🛡️ *PROTEÇÃO:* 🟡 TIE (Empate)\n"
                    "🔄 *GESTÃO:* Até Gale 1\n\n"
                    f"🔍 *PADRÃO IDENTIFICADO:*\n`{padrao}`\n\n"
                    f"📊 *ASSERTIVIDADE:* 30R: `{prob30:.1f}%` | 50R: `{prob50:.1f}%`\n\n"
                    f"{formatar_ranking_telegram()}\n\n"
                    f"{obter_texto_placar()}"
                )

                if enviar_mensagem_telegram(mensagem):
                    registrar_log(f"SINAL ENVIADO: {nome_cor} | Padrão: {padrao}", CoresTerminal.VERDE)

def verificar_resultado(ultimo_resultado: str, ponto_resultado: int = None):
    if not st.session_state.sinal_ativo:
        return

    esperado = st.session_state.sugestao_atual
    padrao_usado = st.session_state.padrao_selecionado
    acertou = (ultimo_resultado == esperado) or (ultimo_resultado == "🟡")

    texto_resultado_com_ponto = f"{ultimo_resultado} ({ponto_resultado})" if ponto_resultado is not None else ultimo_resultado

    if acertou:
        tipo_win = "WIN_TIE" if ultimo_resultado == "🟡" else ("WIN" if st.session_state.tentativa == 1 else "WIN_G1")
        registrar_resultado(tipo_win, padrao_usado)
        txt_win = "WIN DIRETO! 🎯" if tipo_win == "WIN" else ("WIN NO GALE 1! 🎯" if tipo_win == "WIN_G1" else f"WIN_TIE {texto_resultado_com_ponto}")
        
        enviar_mensagem_telegram(f"✅ *{txt_win}*\nResultado: `{texto_resultado_com_ponto}`\n\n{obter_texto_placar()}")
        st.session_state.sinal_ativo = False
        st.session_state.padrao_selecionado = None

    elif st.session_state.tentativa == 1:
        st.session_state.tentativa = 2
        enviar_mensagem_telegram(f"⚠️ *NÃO BATEU 1ª → GALE 1*\nMantém: {esperado}")
    else:
        registrar_resultado("LOSS", padrao_usado)
        enviar_mensagem_telegram(f"❌ *LOSS CONFIRMADO*\nResultado: `{texto_resultado_com_ponto}`\n\n{obter_texto_placar()}")
        st.session_state.sinal_ativo = False
        st.session_state.padrao_selecionado = None

# -----------------------------------------------------------------------------
# 🖥️ INTERFACE DASHBOARD STREAMLIT
# -----------------------------------------------------------------------------
st.title("🤖 Monitor Bac-Bo VIP")

col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("▶️ Ligar Robô"):
    st.session_state.bot_rodando = True
    st.rerun()

if col_btn2.button("⏸️ Pausar Robô"):
    st.session_state.bot_rodando = False
    st.rerun()

col1, col2, col3, col4 = st.columns(4)
status_str = "🟢 MONITORANDO" if st.session_state.bot_rodando else "🔴 PAUSADO"
col1.metric("Status do Robô", status_str)
col2.metric("Entrada Atual", st.session_state.sugestao_atual or "—")
col3.metric("Tentativa", f"Gale {st.session_state.tentativa - 1}" if st.session_state.tentativa > 1 else "1ª Entrada")
col4.metric("Padrão em Uso", f"{st.session_state.padrao_selecionado}" if st.session_state.padrao_selecionado else "—")

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

# -----------------------------------------------------------------------------
# ⚡ FRAGMENTO ISOLADO (ATUALIZAÇÃO EM SEGUNDO PLANO SEM TRAVAR A TELA)
# -----------------------------------------------------------------------------
@st.fragment(run_every=CONFIG["INTERVALO_VERIFICACAO"])
def renderizar_logs_e_processar():
    processar_rodada()
    st.subheader("📋 Logs do Sistema")
    st.code("\n".join(st.session_state.log_eventos[:15]), language=None)

renderizar_logs_e_processar()
