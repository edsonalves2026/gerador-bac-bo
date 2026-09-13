def test_schema_inicial_vazio(memory_db):
    assert memory_db.carregar_padroes() == {}
    assert memory_db.carregar_ranking() == {}


def test_salvar_e_carregar_padrao(memory_db):
    memory_db.salvar_padrao("p1", ["🔴", "🔵"], "🔴")
    p = memory_db.carregar_padroes()
    assert p["p1"]["padrao"] == ["🔴", "🔵"]
    assert p["p1"]["sugestao"] == "🔴"
    assert p["p1"]["ativo"] is True


def test_remover_padrao(memory_db):
    memory_db.salvar_padrao("p1", ["🔴"], "🔴")
    memory_db.remover_padrao("p1")
    assert memory_db.carregar_padroes() == {}


def test_ranking_upsert(memory_db):
    memory_db.atualizar_ranking("p1", True)
    memory_db.atualizar_ranking("p1", True)
    memory_db.atualizar_ranking("p1", False)
    r = memory_db.carregar_ranking()
    assert r["p1"] == {"wins": 2, "total": 3}


def test_salvar_rodadas(memory_db):
    rodadas = [
        {"uuid": "u1", "cor": "🔴", "ponto": 8},
        {"uuid": "u2", "cor": "🔵", "ponto": 10},
        {"uuid": "u1", "cor": "🔴", "ponto": 8},   # duplicada
    ]
    novos = memory_db.salvar_rodadas("m1", rodadas)
    assert novos == 2
    assert memory_db.total_rodadas("m1") == 2


def test_carregar_rodadas_em_ordem(memory_db):
    memory_db.salvar_rodadas("m1", [
        {"uuid": "u1", "cor": "🔴", "ponto": 8},
        {"uuid": "u2", "cor": "🔵", "ponto": 10},
    ])
    rows = memory_db.carregar_rodadas("m1")
    assert rows == [("🔴", 8), ("🔵", 10)]


def test_contexto_upsert(memory_db):
    memory_db.registrar_contexto("p1", 14, 2, True)
    memory_db.registrar_contexto("p1", 14, 2, True)
    memory_db.registrar_contexto("p1", 14, 2, False)
    ctx = memory_db.carregar_contexto("p1")
    assert len(ctx) == 1
    assert ctx[0]["wins"] == 2
    assert ctx[0]["total"] == 3