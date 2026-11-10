"""Mede o delay da API Iadados em relação ao tempo real."""
import time
from datetime import datetime
from bacbo.config import build_http_session
from bacbo.client_iadados import IadadosClient

session = build_http_session()
client = IadadosClient(session, timeout=10)

print("Testando delay da API Iadados...\n")
print(f"Horário atual: {datetime.now().strftime('%H:%M:%S')}\n")

cores, uuids, pontos, _, _ = client.buscar_historico(limite=5)

if not cores:
    print("❌ Sem dados")
else:
    # Olha o horário da última rodada retornada
    # Como a API retorna decrescente, o UUID mais recente tem o horário
    print(f"Últimas 5 rodadas retornadas:")
    for i, (cor, ponto, uid) in enumerate(zip(cores[-5:], pontos[-5:], uuids[-5:])):
        print(f"  {i+1}. {cor} {ponto}  →  {uid}")
        