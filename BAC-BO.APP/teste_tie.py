"""Teste do detector de TIE por intervalo."""
from bacbo.strategies_tie import analisar_intervalos_tie, sinal_tie_intervalo


# Simula histórico com TIE a cada ~15 rodadas
cores = []
for i in range(500):
    if i % 15 == 0:
        cores.append("🟡")
    elif i % 2 == 0:
        cores.append("🔴")
    else:
        cores.append("🔵")

info = analisar_intervalos_tie(cores, ultimas_n=500)
print("=== ANÁLISE DE TIE ===")
print(f"Total de TIE: {info['total_ties']}")
print(f"Média do intervalo: {info['media_intervalo']}")
print(f"Mediana: {info['mediana_intervalo']}")
print(f"Último intervalo: {info['ultimo_intervalo']}")
print(f"Alerta ativo: {info['alerta']}")
print(f"Faltam: {info['rodadas_para_proximo']} rodadas")
print(f"Top 5 intervalos: {info['intervalos_frequentes'][:5]}")

sinal = sinal_tie_intervalo(cores, ultimas_n=500)
print()
print("=== SINAL ===")
print(f"Sinal: {sinal}")
# Simula o caso em que ESTAMOS na janela (último TIE há 15 rodadas)
cores2 = []
for i in range(200):
    if i % 15 == 0 and i < 180:  # último TIE no índice 180
        cores2.append("🟡")
    elif i % 2 == 0:
        cores2.append("🔴")
    else:
        cores2.append("🔵")

print("\n=== TESTE 2: Na janela do próximo TIE ===")
info2 = analisar_intervalos_tie(cores2, ultimas_n=200)
print(f"Último intervalo: {info2['ultimo_intervalo']}")
print(f"Média: {info2['media_intervalo']}")
print(f"Alerta ativo: {info2['alerta']}")
print(f"Faltam: {info2['rodadas_para_proximo']} rodadas")

sinal2 = sinal_tie_intervalo(cores2, ultimas_n=200, tolerancia=3)
print(f"Sinal: {sinal2}")
# Simula o caso em que ESTAMOS na janela
cores2 = []
for i in range(200):
    if i % 15 == 0 and i < 180:
        cores2.append("🟡")
    elif i % 2 == 0:
        cores2.append("🔴")
    else:
        cores2.append("🔵")

print("\n=== TESTE 2: Na janela do próximo TIE ===")
info2 = analisar_intervalos_tie(cores2, ultimas_n=200)
print(f"Último intervalo: {info2['ultimo_intervalo']}")
print(f"Média: {info2['media_intervalo']}")
print(f"Alerta ativo: {info2['alerta']}")
print(f"Faltam: {info2['rodadas_para_proximo']} rodadas")

sinal2 = sinal_tie_intervalo(cores2, ultimas_n=200, tolerancia=3)
print(f"Sinal: {sinal2}")
