from bacbo.patterns_analyzer import PatternsAnalyzer, PatternStats


class TestPatternStats:
    def test_taxa_acerto(self):
        p = PatternStats(
            "teste",
            ocorrencias=10,
            acertos_direto=6,
            acertos_gale1=2,
            acertos_gale2=1,
            reds=1,
        )
        # 9/10 = 90%
        assert p.taxa_acerto == 90.0

    def test_zero_sem_amostra(self):
        p = PatternStats("vazio")
        assert p.taxa_acerto == 0.0

    def test_resumo_formato(self):
        p = PatternStats(
            "🔴🔵🔵🔵",
            ocorrencias=23,
            sugestao="🔵",
            acertos_direto=17,
            acertos_gale1=3,
            acertos_gale2=3,
            reds=0,
        )
        r = p.resumo_curto()
        assert "🔴🔵🔵🔵" in r
        assert "23 vezes" in r
        assert "100.00%" in r


class TestAnalisarCores:
    def test_poucas_ocorrencias(self):
        cores = ["🔴", "🔵", "🔵", "🔵"]
        pontos = [8, 10, 8, 6]
        a = PatternsAnalyzer(cores, pontos)
        assert a.analisar_cores(tamanho=4, min_ocorrencias=4) == []

    def test_padrao_repetido(self):
        cores = ["🔴", "🔵", "🔵", "🔵", "🔵"] * 6
        pontos = list(range(len(cores)))
        a = PatternsAnalyzer(cores, pontos)
        res = a.analisar_cores(tamanho=4, min_ocorrencias=3, min_taxa=80.0)
        assert len(res) > 0
        assert any("🔵" in p.padrao for p in res)

    def test_filtro_assertividade(self):
        import random

        random.seed(42)
        cores = [random.choice(["🔴", "🔵"]) for _ in range(200)]
        pontos = [random.randint(2, 12) for _ in range(200)]
        a = PatternsAnalyzer(cores, pontos)
        res = a.analisar_cores(tamanho=3, min_ocorrencias=4, min_taxa=95.0)
        for p in res:
            assert p.taxa_acerto >= 95.0


class TestAnalisarNumeros:
    def test_numero_inexistente(self):
        cores = ["🔴"] * 5
        pontos = [2, 3, 4, 5, 6]
        a = PatternsAnalyzer(cores, pontos)
        assert a.analisar_numeros(min_ocorrencias=3) == []

    def test_numero_repetido(self):
        cores = []
        pontos = []
        for _ in range(6):
            cores += ["🔴", "🔵"]
            pontos += [7, 5]
        a = PatternsAnalyzer(cores, pontos)
        res = a.analisar_numeros(min_ocorrencias=4, min_taxa=80.0)
        num7 = [p for p in res if p.padrao == "7"]
        assert len(num7) == 1
        assert num7[0].sugestao == "🔵"
        assert num7[0].taxa_acerto == 100.0


class TestSequenciaNumeros:
    def test_sequencia_detectada(self):
        cores = []
        pontos = []
        for _ in range(5):
            cores += ["🔴", "🔵", "🔴", "🔴"]
            pontos += [8, 10, 7, 5]
        a = PatternsAnalyzer(cores, pontos)
        res = a.analisar_sequencia_numeros(tamanho=2, min_ocorrencias=3, min_taxa=50.0)
        seq_8_10 = [p for p in res if p.padrao == "8→10"]
        assert len(seq_8_10) == 1
        assert seq_8_10[0].sugestao == "🔴"
