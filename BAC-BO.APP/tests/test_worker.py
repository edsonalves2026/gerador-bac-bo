import time

from tests.conftest import make_payload

BASE_CORES = ["🔴", "🔵", "🔴"] * 4
BASE_PONTOS = list(range(1, 13))
BASE_UUIDS = [f"u{i:02d}" for i in range(12)]


def _push_base(fake_client):
    fake_client.responses.append(make_payload(BASE_CORES, BASE_UUIDS, BASE_PONTOS))


def test_start_stop(worker):
    worker.start()
    assert worker.state["bot_rodando"] is True
    worker.stop()
    time.sleep(0.1)
    assert worker.state["bot_rodando"] is False


def test_rodada_sem_dados(worker):
    worker.state["bot_rodando"] = True
    worker._processar_rodada()
    assert worker.state["sinal_ativo"] is False


def test_envia_novo_sinal(worker, fake_client, fake_notifier):
    _push_base(fake_client)
    worker.state["bot_rodando"] = True
    # Desliga confluência para o teste ficar determinístico
    worker.config.usar_confluencia = False
    worker._processar_rodada()

    assert worker.state["sinal_ativo"] is True
    assert worker.state["sugestao_atual"] in ("🔴", "🔵")
    assert len(fake_notifier.messages) >= 1


def test_nao_duplica_sinal_mesma_rodada(worker, fake_client, fake_notifier):
    payload = make_payload(BASE_CORES, BASE_UUIDS, BASE_PONTOS)
    fake_client.responses.extend([payload, payload])
    worker.state["bot_rodando"] = True
    worker.config.usar_confluencia = False
    worker._processar_rodada()
    worker._processar_rodada()

    assert len(fake_notifier.messages) == 1


def test_win_direto(worker, fake_client, fake_notifier):
    _push_base(fake_client)
    worker.state["bot_rodando"] = True
    worker.config.usar_confluencia = False
    worker._processar_rodada()
    assert worker.state["sinal_ativo"]
    esperado = worker.state["sugestao_atual"]

    fake_client.responses.append(make_payload(
        BASE_CORES + [esperado],
        BASE_UUIDS + ["nova"],
        BASE_PONTOS + [99],
    ))
    worker._processar_rodada()

    assert worker.state["sinal_ativo"] is False
    assert "WIN" in worker.state["historico_sinais"]


def test_gale_e_loss(worker, fake_client, fake_notifier):
    _push_base(fake_client)
    worker.state["bot_rodando"] = True
    worker.config.usar_confluencia = False
    worker._processar_rodada()
    esperado = worker.state["sugestao_atual"]
    errado = "🔵" if esperado == "🔴" else "🔴"

    fake_client.responses.append(make_payload(
        BASE_CORES + [errado], BASE_UUIDS + ["r1"], BASE_PONTOS + [1],
    ))
    worker._processar_rodada()
    assert worker.state["tentativa"] == 2
    assert worker.state["sinal_ativo"] is True

    fake_client.responses.append(make_payload(
        BASE_CORES + [errado, errado], BASE_UUIDS + ["r1", "r2"], BASE_PONTOS + [1, 2],
    ))
    worker._processar_rodada()
    assert worker.state["sinal_ativo"] is False
    assert "LOSS" in worker.state["historico_sinais"]


def test_tie_conta_win(worker, fake_client, fake_notifier):
    _push_base(fake_client)
    worker.state["bot_rodando"] = True
    worker.config.usar_confluencia = False
    worker._processar_rodada()

    fake_client.responses.append(make_payload(
        BASE_CORES + ["🟡"], BASE_UUIDS + ["tie"], BASE_PONTOS + [0],
    ))
    worker._processar_rodada()
    assert "WIN_TIE" in worker.state["historico_sinais"]


def test_ranking_apos_minimo(worker):
    worker.config.min_operacoes_ranking = 2
    worker._registrar_resultado("WIN", "pX")
    worker._registrar_resultado("WIN", "pX")
    r = worker.calcular_ranking()
    assert len(r) == 1
    assert r[0]["assertividade"] == 100.0


def test_add_e_remove_padrao(worker, memory_db):
    worker.add_padrao("p1", ["🔴", "🔵"], "🔴")
    assert "p1" in worker.state["PADROES_MANUAIS_COMPOSTOS"]
    assert "p1" in memory_db.carregar_padroes()

    worker.remover_padrao("p1")
    assert "p1" not in worker.state["PADROES_MANUAIS_COMPOSTOS"]
    assert "p1" not in memory_db.carregar_padroes()