import pytest
from bacbo.risk import Banca, StopRules, kelly_fraction, sugerir_unidade


class TestBanca:
    def test_win_aumenta_saldo(self):
        b = Banca()
        b.registrar("WIN", stake=1.0)
        assert b.saldo == 101.0

    def test_loss_desconta_gale(self):
        b = Banca()
        b.registrar("LOSS", stake=1.0)
        assert b.saldo == 97.0

    def test_tie_neutro(self):
        b = Banca()
        b.registrar("WIN_TIE", stake=1.0)
        assert b.saldo == 100.0

    def test_drawdown_rastreado(self):
        b = Banca()
        b.registrar("LOSS", stake=1.0)
        b.registrar("LOSS", stake=1.0)
        assert b.drawdown_max == 6.0

    def test_retorno_pct(self):
        b = Banca()
        b.registrar("WIN", stake=5.0)
        assert b.retorno_pct == pytest.approx(5.0)


class TestKelly:
    def test_fracao_positiva_com_edge(self):
        f = kelly_fraction(0.60, odd=1.95)
        assert 0 < f <= 0.05

    def test_fracao_zero_sem_edge(self):
        assert kelly_fraction(0.40, odd=1.95) == 0.0

    def test_cap_respeitado(self):
        assert kelly_fraction(0.99, odd=2.0) <= 0.05

    def test_sugerir_unidade(self):
        u = sugerir_unidade(75.0, odd=1.95)
        assert u >= 0


class TestStopRules:
    def _banca_padrao(self):
        return Banca(inicial=100.0)

    def test_ok_sem_historico(self):
        assert StopRules().avaliar([], self._banca_padrao(), 0) is None

    def test_stop_loss_consecutivo(self):
        h = ["WIN", "LOSS", "LOSS", "LOSS"]
        r = StopRules(stop_loss_consecutivo=3).avaliar(h, self._banca_padrao(), 0)
        assert "STOP-LOSS" in r

    def test_stop_drawdown(self):
        b = self._banca_padrao()
        b.drawdown_max = 10.0
        r = StopRules(stop_drawdown_unidades=5.0).avaliar([], b, 0)
        assert "drawdown" in r.lower()

    def test_stop_win(self):
        b = self._banca_padrao()
        b.saldo = 120.0
        r = StopRules(stop_win_sessao=10.0).avaliar([], b, 0)
        assert "STOP-WIN" in r

    def test_overtrading(self):
        r = StopRules(max_entradas_hora=5).avaliar([], self._banca_padrao(), 5)
        assert "entradas/h" in r

    def test_cooldown_apos_loss(self):
        h = ["WIN", "LOSS"]
        assert StopRules(cooldown_apos_loss=2).precisa_cooldown(h) == 2

    def test_cooldown_cumprido(self):
        h = ["LOSS", "WIN", "WIN"]
        assert StopRules(cooldown_apos_loss=2).precisa_cooldown(h) == 0