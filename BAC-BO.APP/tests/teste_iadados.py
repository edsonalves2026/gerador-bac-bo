"""Teste do cliente iadados.com."""
import os
from bacbo.config import build_http_session
from bacbo.client_iadados import IadadosClient

# Configure o cookie via env var (temporário)
os.environ["IADADOS_COOKIE"] = "PHPSESSID=dmgs1vqs610m6noii055dij srt"

session = build_http_session()
client = IadadosClient(session, timeout=10)

print("Testando iadados.com...")
cores, uuids, pontos, _, _ = client.buscar_historico(limite=10)

print(f"Retornou {len(cores)} rodadas")
if cores:
    print(f"Últimas 5: {list(zip(cores[-5:], pontos[-5:]))}")
else:
    print("❌ Nenhuma rodada retornada")
    