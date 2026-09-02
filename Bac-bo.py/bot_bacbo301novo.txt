import time
from datetime import datetime
from collections import Counter
import requests

# --- CONFIGURAÇÕES E CREDENCIAIS ---
INTERVALO_VERIFICACAO = 10
TELEGRAM_TOKEN = "8961731012:AAGNrkXrd1y6g5ze0hLjWbLIR7OVOL73RRk"
TELEGRAM_CHAT_ID = "-1004319410022"
MESA_ID = "cc71e81d-8b56-4868-91c7-7224be543dce"

SENSIBILIDADE_STRICT = 65.0  # Assertividade mínima requerida nas 30R

# --- CONFIGURAÇÕES PARA TAXA DE ASSERTIVIDADE ---
TAXA_ASSERTIVIDADE_ULTIMOS_100 = True

# --- CONFIGURAÇÕES PARA PADRÕES MANUAIS COMPOSTOS ---
PADROES_MANUAIS_COMPOSTOS = {
    "composto_manual_1": {
        "padrao": ["BANKER_11", "PLAYER_8", "BANKER_11"],
        "sugestao": "PLAYER",
        "ativo": False,
        "tamanho_padrao": 3
    },
    "composto_manual_2": {
        "padrao": ["PLAYER_8", "BANKER_11", "PLAYER_8"],
        "sugestao": "BANKER",
        "ativo": False,
        "tamanho_padrao": 3
    }
}

# --- ESTADOS GLOBAIS ---
sinal_ativo = False
sugestao_atual = None
tentativa = 0
historico_ciclo = []
historico_usos = {}

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
        "🟢 *Status:* Robô Ativo com Análise de Pontuação (200R)\n"
        "🎯 *Estratégia:* Padrões Híbridos (Cor + Pontuação Vencedora)\n"
        "📈 *Radar Tie:* Exibição Exclusiva para Empates Aquecidos\n"
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

            assinatura = f"{tipo}_{ponto}"

            resultados_tipos.append(tipo)
            uuids.append(uuid_rodada)
            resultados_pontos.append(ponto)
            assinaturas_compostas.append(assinatura)

        return resultados_tipos[::-1], uuids[::-1], resultados_pontos[::-1], assinaturas_compostas[::-1]
    except Exception:
        return [], [], [], []

def analisar_padrao_em_sequencia(lista_dados, tamanho_padrao=2):
    """Varre um histórico e busca qual cor tendeu a sair após a sequência atual."""
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

def analisar_padrao_em_sequencia_composto(lista_dados, padrao_atual):
    """Versão especializada para análise de padrões compostos"""
    if len(lista_dados) < 50:
        return 0.0, 0.0, 0

    padrao_cores = [item.split("_")[0] for item in padrao_atual]
    tamanho_padrao = len(padrao_cores)

    def calcular_taxa_janela(tamanho_janela):
        amostra = lista_dados[-tamanho_janela:]
        total, b_cnt, p_cnt = 0, 0, 0
        
        for i in range(len(amostra) - tamanho_padrao):
            amostra_cores = [item.split("_")[0] if "_" in item else item for item in amostra[i:i+tamanho_padrao]]
            
            if amostra_cores == padrao_cores:
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
        if prob_b_30 >= SENSIBILIDADE_STRICT and prob_b_50 >= 65.0:
            return prob_b_30, prob_b_50, tot_30
        if prob_p_30 >= SENSIBILIDADE_STRICT and prob_p_50 >= 65.0:
            return prob_p_30, prob_p_50, tot_30

    return 0.0, 0.0, 0

def buscar_padroes_manuais_compostos(historico_compostos):
    """Verifica se há padrões compostos manuais ativos no histórico"""
    for nome, config in PADROES_MANUAIS_COMPOSTOS.items():
        if not config["ativo"]:
            continue
            
        padrao = config["padrao"]
        tamanho_padrao = config["tamanho_padrao"]
        
        if len(historico_compostos) < tamanho_padrao:
            continue
            
        if historico_compostos[-tamanho_padrao:] == padrao:
            cor_sugestao = config["sugestao"]
            prob_30, prob_50, total = analisar_padrao_em_sequencia_composto(historico_compostos, padrao)
            
            return cor_sugestao, prob_30, prob_50, " ".join(padrao), "Padrão Composto Manual"

    return None, 0.0, 0.0, "", ""

def buscar_sinal_inteligente(historico_tipos, assinaturas):
    """Tenta padrões compostos manuais primeiro, depois padrões automáticos."""
    cor, p30, p50, padrao, tipo_analise = buscar_padroes_manuais_compostos(assinaturas)
    if cor:
        return cor, p30, p50, padrao, tipo_analise
    
    for tam in [2, 3, 4, 5]:
        cor, p30, p50, padrao = analisar_padrao_em_sequencia(assinaturas, tamanho_padrao=tam)
        if cor:
            return cor, p30, p50, padrao, "Pontuação Vencedora"

    for tam in [2, 3, 4, 5]:
        cor, p30, p50, padrao = analisar_padrao_em_sequencia(historico_tipos, tamanho_padrao=tam)
        if cor:
            return cor, p30, p50, padrao, "Sequência de Cores"

    return None, 0.0, 0.0, "", ""

def verificar_radar_tie_aquecido(historico):
    if "TIE" not in historico or len(historico) < 50:
        return False, ""

    if "TIE" not in historico[-30:]:
        return False, ""

    total_rodadas = len(historico)
    indices_tie = [i for i, tipo in enumerate(historico) if tipo == "TIE"]
    distancia_atual = (total_rodadas - 1) - indices_tie[-1]

    historico_50 = historico[-50:]
    indices_tie_50 = [i for i, tipo in enumerate(historico_50) if tipo == "TIE"]
    gaps_50 = [indices_tie_50[i] - indices_tie_50[i-1] - 1 for i in range(1, len(indices_tie_50))]
    freq_50 = Counter(gaps_50).get(distancia_atual, 0)

    historico_30 = historico[-30:]
    indices_tie_30 = [i for i, tipo in enumerate(historico_30) if tipo == "TIE"]
    gaps_30 = [indices_tie_30[i] - indices_tie_30[i-1] - 1 for i in range(1, len(indices_tie_30))]
    freq_30 = Counter(gaps_30).get(distancia_atual, 0)

    if freq_50 >= 2 or distancia_atual in [0, 1, 3, 6, 12, 16]:
        nota_tie = (
            "🔥 *NOTA ESPECIAL - TIE AQUECIDO (RADAR 100R):*\n"
            f"• Distância atual: `{distancia_atual}R` sem Empate.\n"
            f"• Frequência desse Gap nas 50R: `{freq_50}x`\n"
            f"• Frequência desse Gap nas 30R: `{freq_30}x`\n"
            "💡 *Recomendação:* Excelente janela para cobrir a proteção no 🟢 Empate!"
        )
        return True, nota_tie

    return False, ""

# --- EXECUÇÃO PRINCIPAL DO ROBÔ ---
if __name__ == "__main__":
    inicializar_bot_telegram()
    ultimo_uuid = None

    while True:
        try:
            tipos, uuids, pontos, assinaturas = buscar_historico_api()

            if uuids and uuids[-1] != ultimo_uuid:
                ultimo_uuid = uuids[-1]
                resultado_atual = tipos[-1]
                ponto_atual = pontos[-1]
                assinatura_atual = assinaturas[-1] # Ex: "BANKER_11" ou "TIE_10"
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Nova rodada detectada: {assinatura_atual} ({uuids[-1]})")

                if sinal_ativo:
                    if resultado_atual == sugestao_atual:
                        msg_status = "✅ *VICTORY BRK!*" if tentativa == 0 else "✅ *GREEN NO GALE 1!*"
                        msg = f"{msg_status}\n🎲 *Resultado:* `{resultado_atual} {ponto_atual}`"
                        enviar_mensagem_telegram(msg)
                        historico_ciclo.append("WIN_DIRETO" if tentativa == 0 else "WIN_G1")
                        sinal_ativo = False
                    elif resultado_atual == "TIE":
                        msg = f"🟢 *EMPATE (TIE)!* Proteção salva.\n🎲 *Resultado:* `TIE {ponto_atual}`"
                        enviar_mensagem_telegram(msg)
                        historico_ciclo.append("WIN_TIE")
                        sinal_ativo = False
                    elif tentativa == 0:
                        tentativa = 1
                        msg = f"⚠️ *VAMOS PARA O GALE 1!*\n🎲 *Último Resultado:* `{resultado_atual} {ponto_atual}`"
                        enviar_mensagem_telegram(msg)
                    else:
                        msg = f"❌ *RED!*\n🎲 *Resultado:* `{resultado_atual} {ponto_atual}`\nAguarde a próxima oportunidade."
                        enviar_mensagem_telegram(msg)
                        historico_ciclo.append("LOSS")
                        sinal_ativo = False

                if not sinal_ativo:
                    cor, p30, p50, padrao, tipo_analise = buscar_sinal_inteligente(tipos, assinaturas)
                    if cor:
                        sugestao_atual = cor
                        sinal_ativo = True
                        tentativa = 0
                        
                        tem_tie, nota_tie = verificar_radar_tie_aquecido(tipos)
                        
                        msg_sinal = (
                            f"🎯 *SINAL DETECTADO ({tipo_analise})*\n\n"
                            f"📌 *Entrar em:* `{cor}`\n"
                            f"📊 *Assertividade (30R / 50R):* `{p30:.1f}%` / `{p50:.1f}%`\n"
                            f"🔍 *Padrão Detectado:* `{padrao}`\n"
                            f"🎲 *Último Resultado Saído:* `{assinatura_atual.replace('_', ' ')}`\n"
                        )
                        if tem_tie:
                            msg_sinal += f"\n{nota_tie}"

                        enviar_mensagem_telegram(msg_sinal)

        except Exception as e:
            print(f"[ERRO NO LOOP PRINCIPAL] {e}")

        time.sleep(INTERVALO_VERIFICACAO)