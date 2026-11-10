"""Debug: ver os dados CRUS da API iadados."""
import requests

# Captura o cookie PHPSESSID antes (F12 → Application → Cookies)
COOKIE = "PHPSESSID=dmgs1vqs610m6noii055dij srt"  # ← atualize com seu cookie

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://iadados.com/index.php",
    "Cookie": COOKIE,
}

url = "https://iadados.com/php/bacbo_history_proxy.php?page=1&limit=10"

print("Buscando dados CRUS do iadados...\n")
resp = requests.get(url, headers=headers, timeout=10)

print(f"Status: {resp.status_code}\n")

if resp.status_code == 200:
    dados = resp.json()
    print(f"Total de rodadas: {len(dados.get('data', []))}\n")

    print("=" * 80)
    print("ÚLTIMAS 10 RODADAS (formato bruto):")
    print("=" * 80)

    for item in dados.get("data", [])[:10]:
        print(
            f"  resultado={item.get('resultado'):>2}  "
            f"cor={item.get('cor'):>1}  "
            f"winner={item.get('winner'):>8}  "
            f"score={item.get('score'):>2}  "
            f"hora={item.get('hora')}"
        )

    print("\n" + "=" * 80)
    print("MAPA DE CORES:")
    print("  'A' → Azul    → 🔵 (PLAYER)")
    print("  'V' → Vermelho → 🔴 (BANKER)")
    print("  'E' → Empate   → 🟡 (TIE)")
    print("=" * 80)
else:
    print(f"Erro: {resp.text[:500]}")
    