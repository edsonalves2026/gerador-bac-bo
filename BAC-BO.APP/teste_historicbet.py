"""Teste do cliente HistoricBet com login automático."""
from bacbo.config import build_http_session
from bacbo.client_historicbet import HistoricBetClient

# ⚠️ Troque a senha na HistoricBet primeiro!
EMAIL = "edson-evaristo@hotmail.com"
PASSWORD = "Edinho1986*"

session = build_http_session()
client = HistoricBetClient(session, email=EMAIL, password=PASSWORD, timeout=10)

print("=" * 60)
print("TESTE 1: Login e busca inicial")
print("=" * 60)

cores, uuids, pontos, _, _ = client.buscar_historico(limite=10)
print(f"Retornou {len(cores)} rodadas")
if cores:
    print(f"Últimas 5: {list(zip(cores[-5:], pontos[-5:]))}")
else:
    print("❌ Nenhuma rodada retornada")

print()
print("=" * 60)
print("TESTE 2: Reutilização (mesmo token)")
print("=" * 60)

cores2, _, _, _, _ = client.buscar_historico(limite=5)
print(f"Retornou {len(cores2)} rodadas")

print()
print("=" * 60)
print("TESTE 3: Simular expiração")
print("=" * 60)

client.access_token_exp = 0
cores3, _, _, _, _ = client.buscar_historico(limite=5)
print(f"Retornou {len(cores3)} rodadas (após refazer login)")