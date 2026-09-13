from bacbo.strategies import (
    aplicar_confluencia,
    detectar_streak,
    sinal_espelho,
    sinal_ponto_regressao,
    sinal_streak_fade,
)


class TestStreak:
    def test_sem_streak(self):
        assert detectar_streak(["🔴", "🔵", "🔴"], n_min=3) is None

    def test_streak_de_4(self):
        assert detectar_streak(["🔵", "🔴", "🔴", "🔴", "🔴"], n_min=4) == "🔴"

    def test_tie_nao_quebra(self):
        assert detectar_streak(["🔴", "🟡", "🔴", "🔴", "🟡", "🔴"], n_min=4) == "🔴"

    def test_fade_sugere_oposto(self):
        s = sinal_streak_fade(["🔵", "🔴", "🔴", "🔴", "🔴"], n_min=4)
        assert s[0] == "🔵"
        assert s[2] == "streak_fade"


class TestPontoRegressao:
    def test_sem_ponto_raro_no_fim(self):
        assert sinal_ponto_regressao(["🔴"] * 30, [5] * 30) is None

    def test_detecta_tendencia(self):
        cores = ["🔴", "🔴", "🔴", "🔴", "🔵"] + ["🔴"] * 20
        pontos = [10, 11, 12, 10, 11] + [5] * 20
        s = sinal_ponto_regressao(cores, pontos)
        assert s is not None
        assert s[0] == "🔴"
        assert s[2] == "ponto_regressao"

    def test_amostra_insuficiente(self):
        assert sinal_ponto_regressao(["🔴"] * 3, [10, 10, 10]) is None


class TestEspelho:
    def test_espelho_puro(self):
        s = sinal_espelho(["🔴", "🔵", "🔵", "🔴"])
        assert s[0] == "🔵"

    def test_nao_espelho(self):
        assert sinal_espelho(["🔴", "🔵", "🔴", "🔵"]) is None


class TestConfluencia:
    def test_dois_iguais(self):
        sinais = [("🔴", 80.0, "a", ""), ("🔴", 70.0, "b", "")]
        r = aplicar_confluencia(sinais)
        assert r[0] == "🔴"
        assert "confluencia" in r[2]

    def test_discordantes_retorna_none(self):
        sinais = [("🔴", 80.0, "a", ""), ("🔵", 70.0, "b", "")]
        assert aplicar_confluencia(sinais) is None

    def test_tres_com_maioria(self):
        sinais = [("🔴", 80.0, "a", ""), ("🔴", 70.0, "b", ""), ("🔵", 60.0, "c", "")]
        r = aplicar_confluencia(sinais, min_ratio=0.66)
        assert r[0] == "🔴"

    def test_um_sinal_so_nao_e_confluencia(self):
        assert aplicar_confluencia([("🔴", 80.0, "a", "")]) is None