import time
from bacbo.feed_service import Evento, FeedEvent, FeedService


def test_push_e_ordem():
    f = FeedService()
    f.push(FeedEvent(tipo="info", titulo="A", corpo="1"))
    time.sleep(0.001)
    f.push(FeedEvent(tipo="info", titulo="B", corpo="2"))
    f.push(FeedEvent(tipo="info", titulo="C", corpo="3"))

    evs = f.eventos()
    assert [e.titulo for e in evs] == ["C", "B", "A"]


def test_push_entrada_formata_corpo():
    f = FeedService()
    f.push_entrada("🔵", gale_max=1)
    ev = f.eventos()[0]
    assert ev.tipo == Evento.ENTRADA
    assert "🔵" in ev.corpo
    assert "Azul" in ev.corpo
    assert ev.cor == "amarelo"
    assert "1 gale" in ev.subtitulo


def test_push_resultado_win():
    f = FeedService()
    f.push_resultado("WIN")
    ev = f.eventos()[0]
    assert ev.cor == "verde"
    assert "GREEN" in ev.corpo


def test_push_resultado_loss():
    f = FeedService()
    f.push_resultado("LOSS")
    ev = f.eventos()[0]
    assert ev.cor == "vermelho"


def test_push_bloqueio():
    f = FeedService()
    f.push_bloqueio("3 LOSS seguidos")
    ev = f.eventos()[0]
    assert ev.tipo == Evento.BLOQUEIO
    assert ev.cor == "vermelho"
    assert "3 LOSS" in ev.corpo


def test_limpar():
    f = FeedService()
    f.push_info("oi")
    f.push_info("tchau")
    f.limpar()
    assert f.eventos() == []


def test_max_eventos_respeitado():
    f = FeedService()
    for i in range(150):
        f.push(FeedEvent(tipo="info", titulo=f"e{i}", corpo="x"))
    evs = f.eventos()
    assert len(evs) == f.MAX_EVENTOS


def test_limite_no_acesso():
    f = FeedService()
    for i in range(10):
        f.push(FeedEvent(tipo="info", titulo=f"e{i}", corpo="x"))
    assert len(f.eventos(limite=5)) == 5
