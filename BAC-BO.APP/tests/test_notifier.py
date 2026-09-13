from unittest.mock import MagicMock
from bacbo.notifier import TelegramNotifier


def _ok_session():
    s = MagicMock()
    r = MagicMock()
    r.raise_for_status = MagicMock()
    s.post.return_value = r
    return s


def test_send_ok():
    s = _ok_session()
    assert TelegramNotifier("tok", "chat", session=s).send("ola") is True
    assert s.post.called


def test_sem_token():
    s = MagicMock()
    assert TelegramNotifier("", "chat", session=s).send("ola") is False
    assert not s.post.called


def test_texto_vazio():
    s = MagicMock()
    assert TelegramNotifier("tok", "chat", session=s).send("") is False


def test_trunca_mensagem_longa():
    s = _ok_session()
    n = TelegramNotifier("tok", "chat", session=s)
    n.send("A" * 6000)
    enviado = s.post.call_args.kwargs["json"]["text"]
    assert len(enviado) <= n.MAX_LEN
    assert "truncada" in enviado


def test_falha_http():
    s = MagicMock()
    s.post.side_effect = Exception("boom")
    assert TelegramNotifier("tok", "chat", session=s).send("oi") is False