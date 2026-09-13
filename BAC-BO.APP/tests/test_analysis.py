import pytest
from bacbo.analysis import (
    analisar_multi_amostra,
    buscar_frequencia,
    processar_filtro_digitado,
)


class TestBuscarFrequencia:
    def test_uma_ocorrencia(self):
        pr, pb, oc = buscar_frequencia(["🔴"], ["🔴"], ["🔴", "🔵"], 1)
        assert (pr, pb, oc) == (100.0, 0.0, 1)

    def test_sem_ocorrencia(self):
        pr, pb, oc = buscar_frequencia(["🔵"], ["🔴"], ["🔵"], 1)
        assert oc == 0

    def test_abaixo_minimo_zera_probabilidades(self):
        pr, pb, oc = buscar_frequencia(["🔴"], ["🔴"], ["🔴", "🔴"], 5)
        assert pr == 0.0 and pb == 0.0 and oc == 1

    def test_multiplas_ocorrencias(self):
        busca = ["X", "X", "X"]
        ref = ["🔴", "🔴", "🔵", "🔴"]
        pr, pb, oc = buscar_frequencia(busca, ["X"], ref, 1)
        assert oc == 3
        assert pr == pytest.approx(66.67, 0.1)
        assert pb == pytest.approx(33.33, 0.1)


class TestAnalisarMultiAmostra:
    def test_historico_curto(self):
        assert analisar_multi_amostra(["🔴"], ["🔴 1"], {}, 3, 65.0) == (None, 0.0, 0.0, None)

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

    def test_padrao_dinamico_cor(self):
        cores = ["🔴", "🔵", "🔴"] * 4
        comp = [f"{c} {i}" for i, c in enumerate(cores)]
        sug, _, _, desc = analisar_multi_amostra(cores, comp, {}, 3, 65.0)
        assert sug == "🔴"
        assert desc is not None


class TestProcessarFiltroDigitado:
    def test_vazio(self):
        assert processar_filtro_digitado("") == ([], [])

    def test_apenas_numeros(self):
        e, p = processar_filtro_digitado("8, 10, 12")
        assert e == []
        assert sorted(p) == ["10", "12", "8"]

    def test_apenas_entrada(self):
        e, p = processar_filtro_digitado("PLAYER")
        assert e == ["🔵 PLAYER"] and p == []

    def test_misto(self):
        e, p = processar_filtro_digitado("BANKER 8")
        assert "🔴 BANKER" in e
        assert "8" in p

    def test_ignora_fora_do_range(self):
        _, p = processar_filtro_digitado("0 13 5")
        assert p == ["5"]