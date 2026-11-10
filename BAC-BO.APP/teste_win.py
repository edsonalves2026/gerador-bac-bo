from unittest.mock import MagicMock
from bacbo.worker import BacBoWorker
from bacbo.config import BacBoConfig
from bacbo.db import Database


class FN:
    def send(self, t):
        return True


client = MagicMock()
db = Database(":memory:")
w = BacBoWorker(client, FN(), db, BacBoConfig())

w.state["sinal_ativo"] = True
w.state["sugestao_atual"] = "X"
w.state["tentativa"] = 1
w.state["padrao_selecionado"] = "teste"

saldo_antes = w.banca.saldo
w._verificar_resultado("X", 8, "uuid_novo")

print("Saldo antes:", saldo_antes)
print("Saldo depois:", w.banca.saldo)
print("Historico:", w.state["historico_sinais"])

assert w.banca.saldo > saldo_antes, "Banca nao subiu"
assert "WIN" in w.state["historico_sinais"], "WIN nao registrado"
print("OK - fluxo WIN funcionando")
