"""Teste para verificar se a API aceita paginação via 'before='."""
import time
import uuid

import requests


mesa_id = "cc71e81d-8b56-4868-91c7-7224be543dce"
tz = "America%2FSao_Paulo"
cb = uuid.uuid4()
ts = int(time.time() * 1000)

# ---- 1) Página 1 ----
url1 = (
    f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{mesa_id}/history"
    f"?timezone={tz}&subject=filter&limit=200&t={ts}&_cb={cb}"
)
r1 = requests.get(url1, timeout=10)
dados1 = r1.json()
print(f"Página 1: {len(dados1)} rodadas")
print(f"Mais antiga: {dados1[-1]['instant']}")
print(f"Mais nova:   {dados1[0]['instant']}")

# ---- 2) Tenta paginar com before= ----
instant_antigo = dados1[-1]["instant"]
url2 = (
    f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{mesa_id}/history"
    f"?timezone={tz}&subject=filter&limit=200&before={instant_antigo}&t={ts}"
)
r2 = requests.get(url2, timeout=10)
dados2 = r2.json()
print(f"\nPágina 2 (com before=): {len(dados2)} rodadas")
if dados2:
    print(f"1ª rodada: {dados2[0]['instant']}")
    print(f"Última:    {dados2[-1]['instant']}")

# ---- 3) Compara uuids ----
uuids1 = {d["uuid"] for d in dados1}
uuids2 = {d["uuid"] for d in dados2}
em_comum = len(uuids1 & uuids2)
print(f"\nRodadas em comum: {em_comum} de {len(uuids1)}")
if em_comum == len(uuids1):
    print("❌ API IGNOROU o before= (retornou a mesma página)")
else:
    print(f"✅ API respeitou o before= ({em_comum} em comum, "
          f"{len(uuids2 - uuids1)} novas)")
    