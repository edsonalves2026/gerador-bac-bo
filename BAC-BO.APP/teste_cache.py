"""Teste local — simula o cache do Streamlit."""
import time

from bacbo.config import BacBoConfig, build_http_session
from bacbo.client import TipminerClient
from bacbo.db import Database
from bacbo.worker import BacBoWorker


CACHE = {}


class FakeNotifier:
    def send(self, t):
        return True


def get_worker_cached():
    if "worker" not in CACHE:
        print("🔧 Criando worker novo...")
        session = build_http_session()
        client = TipminerClient(session, timeout=10)
        db = Database(":memory:")
        w = BacBoWorker(
            client, FakeNotifier(), db,
            BacBoConfig(intervalo_verificacao=3)
        )
        w.start()
        CACHE["worker"] = w
    else:
        print("♻️ Reutilizando worker do cache")
    return CACHE["worker"]


def main():
    print("=" * 60)
    print("TESTE 2: Simula cache do Streamlit")
    print("=" * 60)

    for i in range(3):
        print(f"\n--- Acesso {i+1} ---")
        w = get_worker_cached()
        state = w.get_state()
        bot = state["bot_rodando"]
        rodadas = state["rodadas_persistidas"]
        print(f"  bot_rodando={bot} rodadas={rodadas}")
        time.sleep(5)

    print("\n--- Aguardando 15 segundos (simula inatividade) ---")
    time.sleep(15)

    print("\n--- Acesso 4 (após 15s) ---")
    w = get_worker_cached()
    state = w.get_state()
    bot = state["bot_rodando"]
    rodadas = state["rodadas_persistidas"]
    print(f"  bot_rodando={bot} rodadas={rodadas}")

    print("\n✅ Teste 2 concluído")


if __name__ == "__main__":
    main()