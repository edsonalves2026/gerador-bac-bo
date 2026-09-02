import time
from datetime import datetime
from collections import Counter
import requests

# --- CONFIGURAÇÕES E CREDENCIAIS ---
INTERVALO_VERIFICACAO = 4
TELEGRAM_TOKEN = "7674538410:AAHxMA_oiw-RLDpJal8GmdqfQk9gPc4fm0E"
TELEGRAM_CHAT_ID = "-1002598636324"
MESA_ID = "cc71e81d-8b56-4868-91c7-7224be543dce"

# --- REGRAS DE ASSERTIVIDADE (20R / 40R) ---
ASSERTIVIDADE_20R = 70.0  # Momento Quente
ASSERTIVIDADE_40R = 65.0  # Tendência do Ciclo

# --- ESTADOS GLOBAIS ---
sinal_ativo = False
sugestao_atual = None
tentativa = 0
historico_ciclo = []
ultimo_gap_alertado = -1  # Evita duplicidade de alertas no mesmo Gap


def enviar_mensagem_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"[ERRO TELEGRAM] {e}")


def inicializar_bot_telegram():
    global sinal_ativo, sugestao_atual, tentativa, historico_ciclo, ultimo_gap_alertado
    sinal_ativo = False
    sugestao_atual = None
    tentativa = 0
    historico_ciclo = []
    ultimo_gap_alertado = -1

    mensagem_start = (
        "🚀 *SESSÃO INICIADA / MESA REINICIADA*\n\n"
        "🟢 *Status:* Robô Ativo com Motores INDEPENDENTES (Cores e Tie)\n"
        "🎯 *Análise Principal:* Sequências Estendidas (20R ≥ 70% | 40R ≥ 65%)\n"
        "📈 *Radar Tie Avulso:* Monitoramento Dinâmico de Gaps e Saltos nas 40R\n"
        "🔢 *Formatos:* Notificação de Tie Numeral Exato (Ex: TIE_2, TIE_12)\n\n"
        "⚠️ *Aguarde as análises para operar.*"
    )
    enviar_mensagem_telegram(mensagem_start)
    print("✅ Bot inicializado com sucesso!")


def buscar_historico_api():
    url_api = f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{MESA_ID}/history?limit=200&timezone=America%2FSao_Paulo"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    try:
        response = requests.get(url_api, headers=headers, timeout=10)
        if response.status_code != 200:
            return [], [], [], []

        dados = response.json()
        if not isinstance(dados, list):
            return [], [], [], []

        resultados_tipos, uuids, resultados_pontos, assinaturas_compostas = [], [], [], []

        for item in dados:
            vencedor = str(item.get("type", "")).upper()
            uuid_rodada = item.get("uuid", "")
            ponto = item.get("result", 0)

            if "BANKER" in vencedor:
                tipo = "BANKER"
            elif "PLAYER" in vencedor:
                tipo = "PLAYER"
            elif "TIE" in vencedor:
                tipo = "TIE"
            else:
                continue

            assinatura = f"{tipo}_{ponto}"

            resultados_tipos.append(tipo)
            uuids.append(uuid_rodada)
            resultados_pontos.append(ponto)
            assinaturas_compostas.append(assinatura)

        return resultados_tipos[::-1], uuids[::-1], resultados_pontos[::-1], assinaturas_compostas[::-1]
    except Exception:
        return [], [], [], []


def analisar_padrao_em_sequencia(lista_dados, tamanho_padrao=3):
    if len(lista_dados) < 40:
        return None, 0.0, 0.0, ""

    padrao_atual = lista_dados[-tamanho_padrao:]
    string_padrao = " ➔ ".join(padrao_atual)

    def calcular_taxa_janela(tamanho_janela):
        amostra = lista_dados[-tamanho_janela:]
        total, b_cnt, p_cnt = 0, 0, 0
        
        for i in range(len(amostra) - tamanho_padrao):
            if amostra[i : i + tamanho_padrao] == padrao_atual:
                total += 1
                proximo = amostra[i + tamanho_padrao]
                cor_proximo = proximo.split("_")[0] if "_" in proximo else proximo
                
                if cor_proximo == "BANKER":
                    b_cnt += 1
                elif cor_proximo == "PLAYER":
                    p_cnt += 1

        prob_b = (b_cnt / total * 100) if total > 0 else 0
        prob_p = (p_cnt / total * 100) if total > 0 else 0
        return prob_b, prob_p, total

    prob_b_20, prob_p_20, tot_20 = calcular_taxa_janela(20)
    prob_b_40, prob_p_40, _ = calcular_taxa_janela(40)

    if tot_20 >= 2:
        if prob_b_20 >= ASSERTIVIDADE_20R and prob_b_40 >= ASSERTIVIDADE_40R:
            return "BANKER", prob_b_20, prob_b_40, string_padrao
        if prob_p_20 >= ASSERTIVIDADE_20R and prob_p_40 >= ASSERTIVIDADE_40R:
            return "PLAYER", prob_p_20, prob_p_40, string_padrao

    return None, 0.0, 0.0, ""


def buscar_sinal_inteligente(historico_tipos, assinaturas):
    for tam in [5, 4, 3]:
        cor, p20, p40, padrao = analisar_padrao_em_sequencia(assinaturas, tamanho_padrao=tam)
        if cor:
            return cor, p20, p40, padrao, f"Pontuação Vencedora ({tam} casas)"

    for tam in [5, 4, 3]:
        cor, p20, p40, padrao = analisar_padrao_em_sequencia(historico_tipos, tamanho_padrao=tam)
        if cor:
            return cor, p20, p40, padrao, f"Sequência de Cores ({tam} casas)"

    return None, 0.0, 0.0, "", ""


def verificar_radar_tie_independente(historico, assinaturas):
    """
    Motor isolado que dispara alertas EXCLUSIVOS de entrada em TIE.
    """
    global ultimo_gap_alertado

    if "TIE" not in historico or len(historico) < 40:
        return

    qtd_ties_20 = historico[-20:].count("TIE")
    qtd_ties_40 = historico[-40:].count("TIE")

    # Mínimos requeridos para considerar a mesa aquecida
    if qtd_ties_20 < 2 or qtd_ties_40 < 3:
        return

    total_rodadas = len(historico)
    indices_tie = [i for i, tipo in enumerate(historico) if tipo == "TIE"]
    gap_atual = (total_rodadas - 1) - indices_tie[-1]

    # Trava para não repetiu o mesmo alerta na mesma rodada
    if gap_atual == ultimo_gap_alertado:
        return

    historico_40 = historico[-40:]
    indices_tie_40 = [i for i, tipo in enumerate(historico_40) if tipo == "TIE"]
    gaps_40 = [indices_tie_40[i] - indices_tie_40[i-1] - 1 for i in range(1, len(indices_tie_40))]

    if not gaps_40:
        return

    media_gap_40 = sum(gaps_40) / len(gaps_40)
    contagem_gaps = Counter(gaps_40)
    gaps_mais_comuns = [g[0] for g in contagem_gaps.most_common(3)]
    freq_gap_atual = contagem_gaps.get(gap_atual, 0)

    pertence_a_gaps_comuns = gap_atual in gaps_mais_comuns
    dentro_da_media = abs(gap_atual - media_gap_40) <= 1.0
    reincidencia_curta = gap_atual in [0, 1, 2, 3]

    if pertence_a_gaps_comuns or dentro_da_media or reincidencia_curta:
        ultimo_gap_alertado = gap_atual
        ultimas_compostas = " | ".join(assinaturas[-5:])

        mensagem_tie = (
            "🟢 *ALERTA EXCLUSIVO - RADAR TIE AQUECIDO*\n\n"
            "🎯 *ENTRADA:* 🟢 **EMPATE (TIE)**\n"
            "🔄 *GESTAO:* Mão Leve (Entrada Única / Janela Curta)\n\n"
            "📊 *ANÁLISE ESTATÍSTICA DO EMPATE:*\n"
            f"• *Volume:* `{qtd_ties_20}` Ties nas 20R | `{qtd_ties_40}` Ties nas 40R\n"
            f"• *Gap Atual:* `{gap_atual}R` sem Empate (Média: `{media_gap_40:.1f}R`)\n"
            f"• *Frequência do Intervalo:* Repetiu `{freq_gap_atual}x` recentemente\n\n"
            f"📝 *Últimas Rodadas:* `{ultimas_compostas}`"
        )
        enviar_mensagem_telegram(mensagem_tie)


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


def verificar_resultado_sinal(ultimo_resultado, ultima_assinatura):
    global sinal_ativo, sugestao_atual, tentativa

    emoji_sugestao = "🔴" if sugestao_atual == "BANKER" else "🔵"

    if ultimo_resultado == sugestao_atual or ultimo_resultado == "TIE":
        if ultimo_resultado == "TIE":
            registrar_resultado_entrada("WIN_TIE")
            enviar_mensagem_telegram(f"✅ *WIN NA PROTEÇÃO!* 🟢 (`{ultima_assinatura}`)")
        elif tentativa == 1:
            registrar_resultado_entrada("WIN_DIRETO")
            enviar_mensagem_telegram(f"✅ *WIN DIRETO DE PRIMEIRA!* {emoji_sugestao} (`{ultima_assinatura}`)")
        else:
            registrar_resultado_entrada("WIN_G1")
            enviar_mensagem_telegram(f"✅ *WIN NO GALE 1!* {emoji_sugestao} (`{ultima_assinatura}`)")
        
        sinal_ativo = False

    elif tentativa == 1:
        tentativa = 2
        enviar_mensagem_telegram(f"⚠️ *NÃO BATEU NA 1ª! VAMOS PARA O GALE 1*\nEntrada Mantida: {emoji_sugestao} *{sugestao_atual}*")

    elif tentativa == 2:
        registrar_resultado_entrada("LOSS")
        enviar_mensagem_telegram("❌ *LOSS CONFIRMADO*")
        sinal_ativo = False


def processar_rodada(historico_tipos, historico_pontos, assinaturas):
    global sinal_ativo, sugestao_atual, tentativa

    ultimo_resultado = historico_tipos[-1]
    ultima_assinatura = assinaturas[-1]

    # 1. Processa fechamento de sinal em andamento (se houver)
    if sinal_ativo:
        verificar_resultado_sinal(ultimo_resultado, ultima_assinatura)
        return

    # 2. Executa o Radar de Tie Independente a cada nova rodada
    verificar_radar_tie_independente(historico_tipos, assinaturas)

    # 3. Analisa Padrões de Cor/Pontuação para sinais de Banker/Player
    sugestao_cor, prob_20, prob_40, padrao_str, tipo_analise = buscar_sinal_inteligente(historico_tipos, assinaturas)
    
    if sugestao_cor:
        sinal_ativo = True
        sugestao_atual = sugestao_cor
        tentativa = 1

        nome_cor = "🔴 BANKER" if sugestao_cor == "BANKER" else "🔵 PLAYER"
        ultimas_compostas = " | ".join(assinaturas[-5:])

        mensagem = (
            "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
            f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
            "🛡️ *PROTEÇÃO:* 🟢 TIE (Empate)\n"
            "🔄 *GESTÃO:* Mão Leve (Até Gale 1)\n\n"
            f"📌 *Gatilho Detectado:* `{padrao_str}` ({tipo_analise})\n"
            "📊 *ASSERTIVIDADE DA ENTRADA:*\n"
            f"• *Momento (20R):* `{prob_20:.1f}%`\n"
            f"• *Ciclo (40R):* `{prob_40:.1f}%`\n\n"
            f"📝 *Últimas Rodadas:* `{ultimas_compostas}`"
        )

        enviar_mensagem_telegram(mensagem)


def executar_robo():
    print("🚀 Executando robô Bac Bo com Radar Tie 100% Independente...")
    inicializar_bot_telegram()

    historico_tipos, uuids_anteriores, _, assinaturas = buscar_historico_api()

    while True:
        time.sleep(INTERVALO_VERIFICACAO)
        tipos_atuais, uuids_atuais, pontos_atuais, assinaturas_atuais = buscar_historico_api()

        if not uuids_atuais or not uuids_anteriores:
            continue

        if uuids_atuais[-1] != uuids_anteriores[-1]:
            uuids_anteriores = uuids_atuais
            print(f"🔄 [{datetime.now().strftime('%H:%M:%S')}] Nova rodada: {assinaturas_atuais[-1]}")
            processar_rodada(tipos_atuais, pontos_atuais, assinaturas_atuais)


if __name__ == "__main__":
    executar_robo()