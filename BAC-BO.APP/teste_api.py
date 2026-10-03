"""Diagnóstico: ver o que a API está retornando."""
import requests

mesa_id = "cc71e81d-8b56-4868-91c7-7224be543dce"
url = (
    f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{mesa_id}/history"
    f"?timezone=America%2FSao_Paulo&subject=filter&limit=200"
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://tipminer.com/",
    "Origin": "https://tipminer.com",
}

r = requests.get(url, headers=headers, timeout=10)

print(f"Status HTTP: {r.status_code}")
print(f"Content-Type: {r.headers.get('Content-Type', '?')}")
print(f"Tamanho: {len(r.content)} bytes")
print(f"\nPrimeiros 500 caracteres:\n")
print(r.text[:500])