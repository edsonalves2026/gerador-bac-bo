"""Compara as últimas rodadas de cada API."""
from bacbo.config import build_http_session
from bacbo.client import TipminerClient
from bacbo.client_historicbet import HistoricBetClient
from bacbo.client_iadados import IadadosClient

MESA_ID = "cc71e81d-8b56-4868-91c7-7224be543dce"

session = build_http_session()

print("=" * 60)
print("COMPARANDO APIs — Últimas 10 rodadas")
print("=" * 60)

# Tipminer
print("\n🔷 TIPMINER")
try:
    tip = TipminerClient(session, timeout=10)
    cores, uuids, pontos, _, _ = tip.buscar_historico(
        mesa_id=MESA_ID, limite=10
    )
    if cores:
        print(f"   Últimas 10: {' '.join(cores[-10:])}")
        print(f"   Pontos:     {pontos[-10:]}")
        print(f"   UUIDs:      {uuids[-3:]}")
    else:
        print("   ❌ Sem dados")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# HistoricBet
print("\n🔶 HISTORICBET")
try:
    hb = HistoricBetClient(session, email="edson-evaristo@hotmail.com",
                            password="SUA_SENHA", timeout=10)
    cores, uuids, pontos, _, _ = hb.buscar_historico(limite=10)
    if cores:
        print(f"   Últimas 10: {' '.join(cores[-10:])}")
        print(f"   Pontos:     {pontos[-10:]}")
        print(f"   UUIDs:      {uuids[-3:]}")
    else:
        print("   ❌ Sem dados")
except Exception as e:
    print(f"   ❌ Erro: {e}")

# Iadados
print("\n🟢 IADADOS")
try:
    iad = IadadosClient(session, timeout=10)
    cores, uuids, pontos, _, _ = iad.buscar_historico(limite=10)
    if cores:
        print(f"   Últimas 10: {' '.join(cores[-10:])}")
        print(f"   Pontos:     {pontos[-10:]}")
        print(f"   UUIDs:      {uuids[-3:]}")
    else:
        print("   ❌ Sem dados")
except Exception as e:
    print(f"   ❌ Erro: {e}")

print("\n" + "=" * 60)
print("COMO INTERPRETAR:")
print("  - Se as 3 APIs retornarem AS MESMAS cores → problema no seu banco")
print("  - Se UMA retornar diferente → essa API tem bug")
print("=" * 60)
