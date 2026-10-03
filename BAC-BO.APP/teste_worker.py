"""Teste local do worker — simula 30s de execução."""
import time

from bacbo.config import BacBoConfig, build_http_session
from bacbo.client import TipminerClient
from bacbo.db import Database
from bacbo.worker import BacBoWorker


# Notifier falso (não envia mensagens reais)
class FakeNotifier:
    def send(self, texto):
        print(f"[FAKE TELEGRAM] {texto[:80]}...")
        return True


def main():
    print("=" * 60)
    print("TESTE 1: Worker rodando 30 segundos")
    print("=" * 60)

    session = build_http_session()
    client = TipminerClient(session, timeout=10)
    db = Database(":memory:")
    notifier = FakeNotifier()
    config = BacBoConfig(intervalo_verificacao=3)
    w = BacBoWorker(client, notifier, db, config)

    print("🚀 Iniciando worker...")
    w.start()

    for i in range(30):
        time.sleep(1)
        state = w.get_state()
        bot = state["bot_rodando"]
        sinal = state["sinal_ativo"]
        rodadas = state["rodadas_persistidas"]
        print(f"[{i+1:02d}s] bot_rodando={bot} sinal_ativo={sinal} rodadas={rodadas}")

    print("🛑 Parando worker...")
    w.stop()
    time.sleep(2)
    print("✅ Teste 1 concluído")


if __name__ == "__main__":
    main()