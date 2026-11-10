"""Teste do cliente HistoricBet com login automático."""
from bacbo.config import build_http_session
from bacbo.client_historicbet import HistoricBetClient

EMAIL = "SEU_EMAIL_AQUI"
PASSWORD = "SUA_SENHA_AQUI"

session = build_http_session()
client = HistoricBetClient(session, email=EMAIL, password=PASSWORD, timeout=10)

print("=== TESTE 1: Login inicial ===")
cores, uuids, pontos, _, _ = client.buscar_historico(limite=10)
print(f"Retornou {len(cores)} rodadas")
if cores:
    print(f"Últimas 5: {list(zip(cores[-5:], pontos[-5:]))}")

print("\n=== TESTE 2: Reutilização (mesmo token) ===")
cores2, _, pontos2, _, _ = client.buscar_historico(limite=5)
print(f"Retornou {len(cores2)} rodadas")

print("\n=== TESTE 3: Forçar expiração ===")
client.access_token_exp = 0  # Força expiração
cores3, _, _, _, _ = client.buscar_historico(limite=5)
print(f"Retornou {len(cores3)} rodadas (login automático)")
