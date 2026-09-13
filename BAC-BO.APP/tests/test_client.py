from unittest.mock import MagicMock
from bacbo.client import TipminerClient


def _resp(payload, status=200):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    return m


def test_sucesso_inverte_ordem():
    session = MagicMock()
    session.get.return_value = _resp([
        {"type": "BANKER", "uuid": "a", "result": 8},
        {"type": "PLAYER", "uuid": "b", "result": 10},
        {"type": "TIE",    "uuid": "c", "result": 1},
    ])
    cores, uuids, pontos, comp, exib = TipminerClient(session).buscar_historico("m1")
    assert cores == ["🟡", "🔵", "🔴"]
    assert uuids == ["c", "b", "a"]
    assert pontos == [1, 10, 8]
    assert comp == ["🟡 1", "🔵 10", "🔴 8"]


def test_status_erro():
    session = MagicMock()
    session.get.return_value = _resp([], status=500)
    assert TipminerClient(session).buscar_historico("x") == ([], [], [], [], [])


def test_json_nao_lista():
    session = MagicMock()
    session.get.return_value = _resp({"erro": "x"})
    assert TipminerClient(session).buscar_historico("x") == ([], [], [], [], [])


def test_excecao_de_rede():
    session = MagicMock()
    session.get.side_effect = Exception("network")
    assert TipminerClient(session).buscar_historico("x") == ([], [], [], [], [])


def test_tipo_desconhecido_ignorado():
    session = MagicMock()
    session.get.return_value = _resp([
        {"type": "WEIRD", "uuid": "z", "result": 5},
        {"type": "BANKER", "uuid": "a", "result": 3},
    ])
    cores, uuids, *_ = TipminerClient(session).buscar_historico("m")
    assert cores == ["🔴"] and uuids == ["a"]