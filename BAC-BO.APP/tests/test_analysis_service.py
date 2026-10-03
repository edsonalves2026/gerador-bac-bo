from unittest.mock import MagicMock
from bacbo.analysis_service import AnalysisService


def _fake_client(cores, pontos, uuids=None):
    c = MagicMock()
    uuids = uuids or [f"u{i}" for i in range(len(cores))]
    c.buscar_historico.return_value = (
        list(cores),
        list(uuids),
        list(pontos),
        [f"{c} {p}" for c, p in zip(cores, pontos)],
        [f"{c} ({p})" for c, p in zip(cores, pontos)],
    )
    return c


def test_retorna_dados_com_historico_suficiente():
    # 🔴🔵🔵🔵 se repete; próximo sempre 🔵
    cores = (["🔴", "🔵", "🔵", "🔵", "🔵"] * 40)[:200]
    pontos = [7] * len(cores)
    service = AnalysisService(_fake_client(cores, pontos), ttl_segundos=60)
    out = service.obter_analise(
        mesa_id="m1",
        timezone="America/Sao_Paulo",
        num_rodadas=500,
        tamanho_cor=4,
        min_ocorrencias=4,
        min_taxa=80.0,
        usar_gale=2,
    )
    assert out["total_rodadas"] == len(cores)
    assert "cores" in out["resultados"]
    assert "numeros" in out["resultados"]
    assert "sequencias" in out["resultados"]


def test_historico_insuficiente():
    cores = ["🔴", "🔵"]
    pontos = [7, 8]
    service = AnalysisService(_fake_client(cores, pontos))
    out = service.obter_analise(
        mesa_id="m1",
        timezone="UTC",
        num_rodadas=500,
        tamanho_cor=4,
        min_ocorrencias=4,
        min_taxa=80.0,
        usar_gale=2,
    )
    assert out.get("erro") == "Histórico insuficiente"


def test_cache_funciona():
    cores = (["🔴", "🔵", "🔵", "🔵", "🔵"] * 40)[:200]
    pontos = [7] * len(cores)
    client = _fake_client(cores, pontos)
    service = AnalysisService(client, ttl_segundos=300)

    service.obter_analise("m1", "UTC", 500, 4, 4, 80.0, 2)
    service.obter_analise("m1", "UTC", 500, 4, 4, 80.0, 2)

    # 2ª chamada deve ter usado cache
    assert client.buscar_historico.call_count == 1


def test_forcar_invalida_cache():
    cores = (["🔴", "🔵", "🔵", "🔵", "🔵"] * 40)[:200]
    pontos = [7] * len(cores)
    client = _fake_client(cores, pontos)
    service = AnalysisService(client, ttl_segundos=300)

    service.obter_analise("m1", "UTC", 500, 4, 4, 80.0, 2)
    service.obter_analise("m1", "UTC", 500, 4, 4, 80.0, 2, forcar=True)
    assert client.buscar_historico.call_count == 2
