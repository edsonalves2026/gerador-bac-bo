from bacbo.backtest import Backtester


def _historico(cor_predominante, n=200):
    return [cor_predominante] * n, [5] * n


def test_backtester_detecta_win_rate_alto():
    cores, pontos = _historico("🔴", 200)
    bt = Backtester(cores, pontos, janela_min=50)

    def sempre_vermelho(c, p):
        return ("🔴", 90.0, "test", "")

    r = bt.rodar("sempre_vermelho", sempre_vermelho)
    assert r.total_sinais > 0
    assert r.win_rate > 90


def test_backtester_sem_sinal():
    cores, pontos = _historico("🔴", 100)
    bt = Backtester(cores, pontos, janela_min=50)

    def nada(c, p):
        return None

    r = bt.rodar("vazio", nada)
    assert r.total_sinais == 0
    assert r.win_rate == 0.0


def test_backtester_loss_e_gale():
    cores = ["🔴"] * 100
    pontos = [5] * 100
    bt = Backtester(cores, pontos, janela_min=50)

    def sempre_azul(c, p):
        return ("🔵", 70.0, "test", "")

    r = bt.rodar("sempre_azul", sempre_azul)
    assert r.losses > 0
    assert r.wins_direto == 0
    assert r.wins_gale == 0


def test_backtester_banca_simulada():
    cores, pontos = _historico("🔴", 200)
    bt = Backtester(cores, pontos, janela_min=50)

    def sempre_vermelho(c, p):
        return ("🔴", 90.0, "t", "")

    r = bt.rodar("v", sempre_vermelho)
    assert r.banca_final > 100.0
    assert r.profit_pct > 0