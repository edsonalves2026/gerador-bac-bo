import pytest
from bacbo.analysis import (
    analisar_multi_amostra,
    buscar_frequencia,
    nome_para_sugestao,
    processar_filtro_digitado,
    sugestao_para_nome,
)


# ------------------------------------------------------------ buscar_frequencia
class TestBuscarFrequencia:
    def test_uma_ocorrencia(self):
        pr, pb, oc = buscar_frequencia(["🔴"], ["🔴"], ["🔴", "🔵"], 1)
        assert (pr, pb, oc) == (100.0, 0.0, 1)

    def test_sem_ocorrencia(self):
        pr, pb, oc = buscar_frequencia(["🔵"], ["🔴"], ["🔵"], 1)
        assert oc == 0 and pr == 0.0 and pb == 0.0

    def test_abaixo_minimo_zera(self):
        pr, pb, oc = buscar_frequencia(["🔴"], ["🔴"], ["🔴", "🔴"], 5)
        assert pr == 0.0 and pb == 0.0 and oc == 1

    def test_listas_vazias(self):
        assert buscar_frequencia([], [], [], 1) == (0.0, 0.0, 0)

    def test_multiplas_ocorrencias(self):
        busca = ["X", "X", "X"]
        ref = ["🔴", "🔴", "🔵", "🔴"]
        pr, pb, oc = buscar_frequencia(busca, ["X"], ref, 1)
        assert oc == 3
        assert pr == pytest.approx(66.67, 0.1)
        assert pb == pytest.approx(33.33, 0.1)

    def test_tie_nao_conta(self):
        pr, pb, oc = buscar_frequencia(["X"], ["X"], ["🔴", "🟡"], 1)
        # total=1, verm=1 → 100%, tie ignorado
        assert oc == 1 and pr == 100.0


# ------------------------------------------------------- analisar_multi_amostra
class TestAnalisarMultiAmostra:
    def test_historico_curto(self):
        r = analisar_multi_amostra(["🔴"], ["🔴 1"], {}, 3, 65.0)
        assert r == (None, 0.0, 0.0, None)

    def test_sem_padroes_e_sem_match(self):
        # Histórico aleatório sem padrão claro
        cores = ["🔴", "🔵", "🔴", "🔵", "🔴", "🔵"]
        comp = [f"{c} {i}" for i, c in enumerate(cores)]
        r = analisar_multi_amostra(cores, comp, None, 3, 99.0)
        assert r[0] is None

    def test_padrao_fixo_encontrado(self):
        padroes = {"t": {"padrao": ["🔴", "🔵"], "sugestao": "🔴", "ativo": True}}
        cores = ["🔴", "🔵", "🔴", "🔴", "🔴", "🔵"]
        sug, _, _, desc = analisar_multi_amostra(cores, cores, padroes, 3, 65.0)
        assert sug == "🔴"
        assert "FIXO" in desc

    def test_padrao_fixo_inativo_ignorado(self):
        padroes = {"t": {"padrao": ["🔴", "🔵"], "sugestao": "🔴", "ativo": False}}
        sug, *_ = analisar_multi_amostra(["🔴", "🔵"], ["🔴", "🔵"], padroes, 3, 65.0)
        assert sug is None

    def test_auto_cor_detectado(self):
        padroes = {
            "AUTO_COR_🔴🔵🔴": {
                "padrao": ["🔴", "🔵", "🔴"],
                "sugestao": "🔵",
                "ativo": True,
            }
        }
        cores = ["🔵", "🔴", "🔵", "🔴"]     # termina em 🔴🔵🔴
        comp = [f"{c} {i}" for i, c in enumerate(cores)]
        sug, conf, _, desc = analisar_multi_amostra(cores, comp, padroes, 3, 65.0)
        assert sug == "🔵"
        assert "AUTO_COR" in desc

    def test_auto_num_detectado(self):
        padroes = {
            "AUTO_NUM_10": {"padrao": ["10"], "sugestao": "🔵", "ativo": True}
        }
        cores = ["🔴", "🔵", "🔴", "🔵"]
        comp = [f"{c} {i}" for i, c in enumerate(cores)]
        pontos = [8, 9, 10, 8]
        sug, _, _, desc = analisar_multi_amostra(
            cores, comp, padroes, 3, 65.0, historico_pontos=pontos
        )
        assert sug == "🔵"
        assert "AUTO_NUM" in desc

    def test_padrao_dinamico_cor(self):
        cores = ["🔴", "🔵", "🔴"] * 4
        comp = [f"{c} {i}" for i, c in enumerate(cores)]
        sug, _, _, desc = analisar_multi_amostra(cores, comp, {}, 3, 65.0)
        assert sug == "🔴"
        assert desc is not None


# --------------------------------------------------- processar_filtro_digitado
class TestProcessarFiltroDigitado:
    def test_vazio(self):
        assert processar_filtro_digitado("") == ([], [])

    def test_apenas_numeros_validos(self):
        e, p = processar_filtro_digitado("8, 10, 12")
        assert e == []
        assert p == ["10", "12", "8"]

    def test_ignora_1_e_13(self):
        _, p = processar_filtro_digitado("1 13 5 2 12")
        assert p == ["12", "2", "5"]

    def test_apenas_entrada(self):
        e, p = processar_filtro_digitado("PLAYER")
        assert e == ["🔵 PLAYER"] and p == []

    def test_misto(self):
        e, p = processar_filtro_digitado("BANKER 8")
        assert e == ["🔴 BANKER"]
        assert p == ["8"]

    def test_ordenado_e_deduplicado(self):
        _, p = processar_filtro_digitado("8 8 10 10")
        assert p == ["10", "8"]


# ------------------------------------------------------------ helpers de nome
class TestHelpersNome:
    def test_sugestao_para_nome(self):
        assert sugestao_para_nome("🔴") == "🔴 BANKER"
        assert sugestao_para_nome("🔵") == "🔵 PLAYER"
        assert sugestao_para_nome("🟡") == "🟡 TIE"

    def test_nome_para_sugestao(self):
        assert nome_para_sugestao("BANKER") == "🔴"
        assert nome_para_sugestao("PLAYER") == "🔵"
        assert nome_para_sugestao("TIE") == "🟡"
        assert nome_para_sugestao("desconhecido") is None
