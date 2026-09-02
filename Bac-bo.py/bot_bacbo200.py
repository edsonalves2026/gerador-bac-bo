import time
from datetime import datetime
from collections import Counter
import requests

# --- CONFIGURAÇÕES E CREDENCIAIS ---
INTERVALO_VERIFICACAO = 4
TELEGRAM_TOKEN = "7674538410:AAHxMA_oiw-RLDpJal8GmdqfQk9gPc4fm0E"
TELEGRAM_CHAT_ID = "-1002598636324"
MESA_ID = "cc71e81d-8b56-4868-91c7-7224be543dce"

SENSIBILIDADE_STRICT = 65.0  # Assertividade mínima requerida nas 30R

# --- ESTADOS GLOBAIS ---
sinal_ativo = False
sugestao_atual = None
tentativa = 0
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
    sinal_ativo = False
    sugestao_atual = None
    tentativa = 0
    historico_ciclo = []

    mensagem_start = (
        "🚀 *SESSÃO INICIADA / MESA REINICIADA*\n\n"
        "🟢 *Status:* Robô Ativo com Análise de Pontuação e Densidade de Tie (200R)\n"
        "🎯 *Estratégia:* Padrões Híbridos (Cor + Pontuação Vencedora)\n"
        "📈 *Radar Tie:* Exibição Numérica Exata (Ex: TIE_2, TIE_12, TIE_7, TIE_10)\n"
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

            # Assinatura de Cor + Pontuação (Ex: "BANKER_11", "PLAYER_8", "TIE_10")
            assinatura = f"{tipo}_{ponto}"

            resultados_tipos.append(tipo)
            uuids.append(uuid_rodada)
            resultados_pontos.append(ponto)
            assinaturas_compostas.append(assinatura)

        return resultados_tipos[::-1], uuids[::-1], resultados_pontos[::-1], assinaturas_compostas[::-1]
    except Exception:
        return [], [], [], []


def analisar_padrao_em_sequencia(lista_dados, tamanho_padrao=2):
    if len(lista_dados) < 50:
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

    prob_b_30, prob_p_30, tot_30 = calcular_taxa_janela(30)
    prob_b_50, prob_p_50, _ = calcular_taxa_janela(50)

    if tot_30 >= 2:
        if prob_b_30 >= SENSIBILIDADE_STRICT and prob_b_50 >= 50.0:
            return "BANKER", prob_b_30, prob_b_50, string_padrao
        if prob_p_30 >= SENSIBILIDADE_STRICT and prob_p_50 >= 50.0:
            return "PLAYER", prob_p_30, prob_p_50, string_padrao

    return None, 0.0, 0.0, ""


def buscar_sinal_inteligente(historico_tipos, assinaturas):
    for tam in [2, 3]:
        cor, p30, p50, padrao = analisar_padrao_em_sequencia(assinaturas, tamanho_padrao=tam)
        if cor:
            return cor, p30, p50, padrao, "Pontuação Vencedora"

    for tam in [2, 3]:
        cor, p30, p50, padrao = analisar_padrao_em_sequencia(historico_tipos, tamanho_padrao=tam)
        if cor:
            return cor, p30, p50, padrao, "Sequência de Cores"

    return None, 0.0, 0.0, "", ""


def analisar_densidade_e_gaps_tie(historico):
    if "TIE" not in historico or len(historico) < 50:
        return False, ""

    qtd_ties_30 = historico[-30:].count("TIE")
    qtd_ties_50 = historico[-50:].count("TIE")

    if qtd_ties_30 < 2 or qtd_ties_50 < 4:
        return False, ""

    total_rodadas = len(historico)
    indices_tie = [i for i, tipo in enumerate(historico) if tipo == "TIE"]
    gap_atual = (total_rodadas - 1) - indices_tie[-1]

    historico_50 = historico[-50:]
    indices_tie_50 = [i for i, tipo in enumerate(historico_50) if tipo == "TIE"]
    gaps_50 = [indices_tie_50[i] - indices_tie_50[i-1] - 1 for i in range(1, len(indices_tie_50))]

    if not gaps_50:
        return False, ""

    media_gap_50 = sum(gaps_50) / len(gaps_50)
    contagem_gaps = Counter(gaps_50)
    gaps_mais_comuns = [g[0] for g in contagem_gaps.most_common(3)]
    freq_gap_atual = contagem_gaps.get(gap_atual, 0)

    pertence_a_gaps_comuns = gap_atual in gaps_mais_comuns
    dentro_da_media = abs(gap_atual - media_gap_50) <= 1.5
    reincidencia_curta = gap_atual in [0, 1, 2, 3]

    if pertence_a_gaps_comuns or dentro_da_media or reincidencia_curta:
        nota_tie = (
            "🔥 *RADAR TIE AQUECIDO (JANELA IDEAL CONFIRMADA):*\n"
            f"• *Volume Recente:* `{qtd_ties_30}` Ties nas 30R | `{qtd_ties_50}` Ties nas 50R\n"
            f"• *Gap Atual:* `{gap_atual}R` sem Empate (Média da Mesa: `{media_gap_50:.1f}R`)\n"
            f"• *Recorrência Deste Intervalo:* Repetiu `{freq_gap_atual}x` nas últimas 50R\n"
            "💡 *Recomendação:* COBRIR PROTEÇÃO NO 🟢 EMPATE!"
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


def verificar_resultado_sinal(ultimo_resultado, última_assinatura):
    global sinal_ativo, sugestao_atual, tentativa

    emoji_sugestao = "🔴" if sugestao_atual == "BANKER" else "🔵"

    if ultimo_resultado == sugestao_atual or ultimo_resultado == "TIE":
        if ultimo_resultado == "TIE":
            registrar_resultado_entrada("WIN_TIE")
            enviar_mensagem_telegram(f"✅ *WIN NA PROTEÇÃO!* 🟢 (`{última_assinatura}`)")
        elif tentativa == 1:
            registrar_resultado_entrada("WIN_DIRETO")
            enviar_mensagem_telegram(f"✅ *WIN DIRETO DE PRIMEIRA!* {emoji_sugestao} (`{última_assinatura}`)")
        else:
            registrar_resultado_entrada("WIN_G1")
            enviar_mensagem_telegram(f"✅ *WIN NO GALE 1!* {emoji_sugestao} (`{última_assinatura}`)")
        
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

    if sinal_ativo:
        verificar_resultado_sinal(ultimo_resultado, ultima_assinatura)
        return

    sugestao_cor, prob_30, prob_50, padrao_str, tipo_analise = buscar_sinal_inteligente(historico_tipos, assinaturas)
    
    if sugestao_cor:
        sinal_ativo = True
        sugestao_atual = sugestao_cor
        tentativa = 1

        nome_cor = "🔴 BANKER" if sugestao_cor == "BANKER" else "🔵 PLAYER"
        tie_aquecido, nota_tie = analisar_densidade_e_gaps_tie(historico_tipos)

        ultimas_compostas = " | ".join(assinaturas[-5:])

        mensagem = (
            "🤖 *BAC BO PRO - SINAL VIP CONFIRMADO*\n\n"
            f"🎯 *ENTRADA PRINCIPAL:* {nome_cor}\n"
            "🛡️ *PROTEÇÃO:* 🟢 TIE (Empate)\n"
            "🔄 *GESTÃO:* Mão Leve (Até Gale 1)\n\n"
            f"📌 *Gatilho Detectado:* `{padrao_str}` ({tipo_analise})\n"
            "📊 *ASSERTIVIDADE DA ENTRADA:*\n"
            f"• *Momento (30R):* `{prob_30:.1f}%`\n"
            f"• *Ciclo (50R):* `{prob_50:.1f}%`"
        )

        if tie_aquecido:
            mensagem += f"\n\n{nota_tie}"

        mensagem += f"\n\n📝 *Últimas Rodadas:* `{ultimas_compostas}`"
        enviar_mensagem_telegram(mensagem)


def executar_robo():
    print("🚀 Executando robô Bac Bo com exibição numeral de Tie...")
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