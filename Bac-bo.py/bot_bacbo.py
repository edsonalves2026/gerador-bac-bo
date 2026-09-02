import time
from datetime import datetime
from collections import Counter
import requests

# --- CONFIGURAÇÕES E CREDENCIAIS ---
INTERVALO_VERIFICACAO = 4
TELEGRAM_TOKEN = "8961731012:AAGNrkXrd1y6g5ze0hLjWbLIR7OVOL73RRk"
TELEGRAM_CHAT_ID = "-1004319410022"
MESA_ID = "cc71e81d-8b56-4868-91c7-7224be543dce"

SENSIBILIDADE_STRICT = 70.0

# --- ESTADOS GLOBAIS ---
sinal_ativo = False
sugestao_atual = None
tentativa = 0

# Estado independente para o Tie
sinal_tie_solo_ativo = False
ultimo_tie_notificado_uuid = None

# --- HISTÓRICO DO CICLO (50 ENTRADAS) ---
historico_ciclo = []


def enviar_mensagem_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRO TELEGRAM] {e}")


def inicializar_bot_telegram():
    global sinal_ativo, sugestao_atual, tentativa, historico_ciclo
    global sinal_tie_solo_ativo, ultimo_tie_notificado_uuid
    
    sinal_ativo = False
    sugestao_atual = None
    tentativa = 0
    sinal_tie_solo_ativo = False
    ultimo_tie_notificado_uuid = None
    historico_ciclo = []

    mensagem_start = (
        "🚀 *SESSÃO INICIADA / MESA REINICIADA*\n\n"
        "🟢 *Status:* Robô Ativo e Analisando a Mesa\n"
        "🎯 *Filtro VIP:* Confluência 70%+ (30R & 50R)\n"
        "📈 *Radar Tie:* Alertas Independentes (20R & 50R)\n"
        "📊 *Placar:* Relatório automático ao fechar 50 entradas\n\n"
        "⚠️ *Aguarde o próximo sinal para operar.*"
    )
    
    enviar_mensagem_telegram(mensagem_start)
    print("✅ Bot inicializado com sucesso!")


def buscar_historico_api():
    url_api = f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{MESA_ID}/history?limit=200&timezone=America%2FSao_Paulo"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

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
    except Exception:
        return [], [], []


def calcular_frequencia_tie(historico_cores):
    """Calcula a contagem e porcentagem de empates nas últimas 10R e 20R."""
    amostra_10 = historico_cores[-10:] if len(historico_cores) >= 10 else historico_cores
    amostra_20 = historico_cores[-20:] if len(historico_cores) >= 20 else historico_cores

    count_10 = amostra_10.count("🟢")
    count_20 = amostra_20.count("🟢")

    pct_10 = (count_10 / len(amostra_10) * 100) if amostra_10 else 0.0
    pct_20 = (count_20 / len(amostra_20) * 100) if amostra_20 else 0.0

    return (
        "📊 *FREQUÊNCIA DE TIE (EMPATE):*\n"
        f"• *ÚLTIMAS 10R:* `{count_10}x` (`{pct_10:.1f}%`)\n"
        f"• *ÚLTIMAS 20R:* `{count_20}x` (`{pct_20:.1f}%`)"
    )


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


def verificar_radar_tie_aquecido(historico_cores):
    """Filtro do Tie ajustado para amostras de 20R e 50R."""
    if "🟢" not in historico_cores or len(historico_cores) < 50:
        return False, ""

    if "🟢" not in historico_cores[-20:]:
        return False, ""

    total_rodadas = len(historico_cores)
    indices_tie = [i for i, cor in enumerate(historico_cores) if cor == "🟢"]
    distancia_atual = (total_rodadas - 1) - indices_tie[-1]

    gaps_historico = []
    for idx in range(1, len(indices_tie)):
        gap = indices_tie[idx] - indices_tie[idx - 1] - 1
        gaps_historico.append(gap)

    contagem_gaps = Counter(gaps_historico)
    freq_distancia_atual = contagem_gaps.get(distancia_atual, 0)
    bloco_frequencia = calcular_frequencia_tie(historico_cores)

    if freq_distancia_atual >= 2 or distancia_atual in [0, 1, 2, 3]:
        nota_tie = (
            "🔥 *ALERTA INDEPENDENTE - RADAR TIE AQUECIDO*\n\n"
            "🎯 *ENTRADA EXCLUSIVA:* 🟢 TIE (EMPATE)\n"
            f"• Distância atual: `{distancia_atual}R` sem Tie.\n"
            f"• Repetição histórica do Gap: `{freq_distancia_atual}x` nas amostras (20R/50R).\n\n"
            f"{bloco_frequencia}\n\n"
            "💡 *Recomendação:* Entrada direta no Empate sem Gale!"
        )
        return True, nota_tie

    return False, ""


def processar_fechamento_ciclo():
    global historico_ciclo

    total = len(historico_ciclo)
    wins_diretos = historico_ciclo.count("WIN_DIRETO")
    wins_g1 = historico_ciclo.count("WIN_G1")
    wins_tie = historico_ciclo.count("WIN_TIE")
    losses = historico_ciclo.count("LOSS")

    total_wins = wins_diretos + wins_g1 + wins_tie
    assertividade = (total_wins / total * 100) if total > 0 else 0

    mensagem_fechamento = (
        "📊 *BALANÇO FINAL - CICLO DE 50 RODADAS OPERADAS*\n\n"
        f"🎯 *Win Direto (1ª Entrada):* `{wins_diretos}`\n"
        f"🔄 *Win no Gale 1:* `{wins_g1}`\n"
        f"🟢 *Win na Proteção (Tie):* `{wins_tie}`\n"
        f"❌ *Loss Confirmado:* `{losses}`\n\n"
        f"🚀 *ASSERTIVIDADE GLOBAL:* `{assertividade:.1f}%`\n"
        "─────────────────────────────\n"
        "🔄 *Ciclo concluído! Contador reiniciado para os próximos 50 sinais.*"
    )

    enviar_mensagem_telegram(mensagem_fechamento)
    historico_ciclo = []


def registrar_resultado_entrada(resultado_tipo):
    global historico_ciclo
    historico_ciclo.append(resultado_tipo)
    
    if len(historico_ciclo) >= 50:
        processar_fechamento_ciclo()


def verificar_resultado_sinal(ultimo_resultado, ultimo_ponto):
    global sinal_ativo, sugestao_atual, tentativa

    nome_resultado = "BANKER" if ultimo_resultado == "🔴" else "PLAYER" if ultimo_resultado == "🔵" else "TIE"

    if ultimo_resultado == sugestao_atual or ultimo_resultado == "🟢":
        if ultimo_resultado == "🟢":
            registrar_resultado_entrada("WIN_TIE")
            enviar_mensagem_telegram(
                f"✅ *WIN NA PROTEÇÃO (TIE)!* 🟢\n"
                f"Resultado: `{nome_resultado} {ultimo_ponto}` ({ultimo_resultado})"
            )
        elif tentativa == 1:
            registrar_resultado_entrada("WIN_DIRETO")
            enviar_mensagem_telegram(
                f"✅ *WIN DIRETO DE PRIMEIRA!* 🎯\n"
                f"Resultado: `{nome_resultado} {ultimo_ponto}` ({ultimo_resultado})"
            )
        else:
            registrar_resultado_entrada("WIN_G1")
            enviar_mensagem_telegram(
                f"✅ *WIN NO GALE 1!* 🎯\n"
                f"Resultado: `{nome_resultado} {ultimo_ponto}` ({ultimo_resultado})"
            )
        
        sinal_ativo = False

    elif tentativa == 1:
        tentativa = 2
        enviar_mensagem_telegram(f"⚠️ *NÃO BATEU NA 1ª! VAMOS PARA O GALE 1*\nEntrada Mantida: {sugestao_atual}")

    elif tentativa == 2:
        registrar_resultado_entrada("LOSS")
        enviar_mensagem_telegram(
            f"❌ *LOSS CONFIRMADO*\n"
            f"Resultado: `{nome_resultado} {ultimo_ponto}` ({ultimo_resultado})"
        )
        sinal_ativo = False


def processar_rodada(historico_cores, historico_pontos, uuid_atual):
    global sinal_ativo, sugestao_atual, tentativa
    global sinal_tie_solo_ativo, ultimo_tie_notificado_uuid

    ultimo_resultado = historico_cores[-1]
    ultimo_ponto = historico_pontos[-1]
    nome_resultado = "BANKER" if ultimo_resultado == "🔴" else "PLAYER" if ultimo_resultado == "🔵" else "TIE"

    # 1. VERIFICAÇÃO DO RESULTADO DO SINAL EXCLUSIVO DO TIE (INDIVIDUAL / SILENCIOSO NO LOSS)
    if sinal_tie_solo_ativo:
        if ultimo_resultado == "🟢":
            enviar_mensagem_telegram(
                f"🔥 *VICTORY BRK!* 🟢🟢\n"
                f"Resultado: `{nome_resultado} {ultimo_ponto}` ({ultimo_resultado})"
            )
        # Se não bater (Banker ou Player), não faz nada e não envia nenhuma mensagem.
        sinal_tie_solo_ativo = False

    # 2. PROCESSAMENTO DE ENTRADAS EM ANDAMENTO (SINAIS PRINCIPAIS 🔴/🔵)
    if sinal_ativo:
        verificar_resultado_sinal(ultimo_resultado, ultimo_ponto)
        return

    # 3. RADAR TIE INDEPENDENTE (ALERTA SOLO)
    tie_aquecido, nota_tie = verificar_radar_tie_aquecido(historico_cores)
    if tie_aquecido and ultimo_tie_notificado_uuid != uuid_atual:
        enviar_mensagem_telegram(nota_tie)
        ultimo_tie_notificado_uuid = uuid_atual
        sinal_tie_solo_ativo = True

    # 4. ANÁLISE DE ENTRADAS PRINCIPAIS (🔴 BANKER / 🔵 PLAYER)
    sugestao_cor, prob_30, prob_50 = analisar_multi_amostra(historico_cores)
    
    if sugestao_cor:
        sinal_ativo = True
        sugestao_atual = sugestao_cor
        tentativa = 1

        nome_cor = "🔴 BANKER" if sugestao_cor == "🔴" else "🔵 PLAYER"
        bloco_frequencia = calcular_frequencia_tie(historico_cores)

        mensagem = (
            "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
            f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
            "🛡️ *PROTEÇÃO:* 🟢 TIE (Empate)\n"
            "🔄 *GESTÃO:* Mão Leve (Até Gale 1)\n\n"
            "📊 *ASSERTIVIDADE DA ENTRADA:*\n"
            f"• *Momento (30R):* `{prob_30:.1f}%`\n"
            f"• *Ciclo (50R):* `{prob_50:.1f}%`\n\n"
            f"📝 *Últimas 10 Rodadas:*\n`{' | '.join(historico_cores[-10:])}`\n\n"
            f"{bloco_frequencia}"
        )

        enviar_mensagem_telegram(mensagem)


def executar_robo():
    print("🚀 Executando robô Bac Bo...")
    inicializar_bot_telegram()

    historico_cores, uuids_anteriores, _ = buscar_historico_api()

    while True:
        time.sleep(INTERVALO_VERIFICACAO)
        cores_atuais, uuids_atuais, pontos_atuais = buscar_historico_api()

        if not uuids_atuais or not uuids_anteriores:
            continue

        if uuids_atuais[-1] != uuids_anteriores[-1]:
            uuids_anteriores = uuids_atuais
            uuid_atual = uuids_atuais[-1]
            print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Nova rodada: {cores_atuais[-1]} ({pontos_atuais[-1]})")
            processar_rodada(cores_atuais, pontos_atuais, uuid_atual)


if __name__ == "__main__":
    executar_robo()