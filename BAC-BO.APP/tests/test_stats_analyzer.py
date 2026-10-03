import pytest
from bacbo.stats_analyzer import StatsAnalyzer


# ------------------------------------------------------------------- básico
def test_amostra_vazia():
    r = StatsAnalyzer([]).calcular(gale=0)
    assert r.max_red == 0
    assert r.max_blue == 0
    assert r.max_tie == 0
    assert r.max_sem_tie == 0
    assert r.total_rodadas == 0


def test_streak_simples_sg():
    # 🔴🔴🔵🔴 → máx red=2, máx blue=1
    r = StatsAnalyzer(["🔴", "🔴", "🔵", "🔴"]).calcular(gale=0)
    assert r.max_red == 2
    assert r.max_blue == 1
    assert r.max_tie == 0


def test_maxima_tie():
    # 🔴🟡🟡🔵 → máx tie=2
    r = StatsAnalyzer(["🔴", "🟡", "🟡", "🔵"]).calcular(gale=0)
    assert r.max_tie == 2


def test_maxima_sem_tie():
    # 🔴🔴🔴🟡🔵🔵 → maior bloco sem tie = 3 (🔴🔴🔴)
    r = StatsAnalyzer(["🔴", "🔴", "🔴", "🟡", "🔵", "🔵"]).calcular(gale=0)
    assert r.max_sem_tie == 3


# ------------------------------------------------------------------- gale 1
def test_gale1_absorve_uma_rodada():
    # 🔴🔴🔵🔴🔴 → com G1, o 🔵 é absorvido → streak de 5
    r = StatsAnalyzer(["🔴", "🔴", "🔵", "🔴", "🔴"]).calcular(gale=1)
    assert r.max_red == 5


def test_gale1_nao_absorve_duas():
    # 🔴🔵🔵🔴 → G1 não absorve 2 seguidos → fica 🔴 | 🔵🔵 | 🔴
    r = StatsAnalyzer(["🔴", "🔵", "🔵", "🔴"]).calcular(gale=1)
    assert r.max_red == 1
    assert r.max_blue == 2


# ------------------------------------------------------------------- gale 2
def test_gale2_absorve_duas():
    # 🔴🔵🔵🔴 → G2 absorve os 2 🔵 → streak 🔴=4
    r = StatsAnalyzer(["🔴", "🔵", "🔵", "🔴"]).calcular(gale=2)
    assert r.max_red == 4


def test_gale2_nao_absorve_tres():
    # 🔴🔵🔵🔵🔴 → G2 não absorve 3 → streak máximo red=1
    r = StatsAnalyzer(["🔴", "🔵", "🔵", "🔵", "🔴"]).calcular(gale=2)
    assert r.max_red == 1
    assert r.max_blue == 3


# ----------------------------------------------------------- tie + absorção
def test_tie_nao_e_absorvido():
    # 🔴🟡🔴 → tie permanece, red fica separado em 2 streaks de 1
    r = StatsAnalyzer(["🔴", "🟡", "🔴"]).calcular(gale=2)
    assert r.max_red == 1
    assert r.max_tie == 1


# ------------------------------------------------------------------- % máximo
def test_percentual_quando_maximo_ocorre_uma_vez():
    # streaks 🔴 = [2, 1, 3] → máximo 3 ocorre 1 vez → 33.3%
    r = StatsAnalyzer(["🔴", "🔴", "🔵", "🔴", "🔵", "🔴", "🔴", "🔴"]).calcular(gale=0)
    assert r.max_red == 3
    assert r.n_streaks_red == 3
    assert r.pct_red == pytest.approx(33.33, abs=0.1)


def test_percentual_quando_maximo_se_repete():
    # streaks 🔴 = [3, 3, 1] → máximo 3 ocorre 2x → 66.7%
    cores = ["🔴"] * 3 + ["🔵"] + ["🔴"] * 3 + ["🔵"] + ["🔴"]
    r = StatsAnalyzer(cores).calcular(gale=0)
    assert r.max_red == 3
    assert r.n_streaks_red == 3
    assert r.pct_red == pytest.approx(66.67, abs=0.1)


def test_percentual_sem_streaks():
    r = StatsAnalyzer(["🔵", "🔵", "🔵"]).calcular(gale=0)
    assert r.pct_red == 0.0
    assert r.n_streaks_red == 0


# ------------------------------------------------------------------ validação
def test_gale_invalido():
    with pytest.raises(ValueError):
        StatsAnalyzer(["🔴"]).calcular(gale=3)


# --------------------------------------------------------------- integração
def test_gale_muda_o_resultado():
    cores = ["🔴", "🔵", "🔴", "🔵", "🔴"]  # streak red SG = 1
    sg = StatsAnalyzer(cores).calcular(gale=0)
    g1 = StatsAnalyzer(cores).calcular(gale=1)
    assert sg.max_red == 1
    assert g1.max_red == 5  # absorve todos os 🔵 isolados
