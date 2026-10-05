"""Persistência de padrões e ranking — export/import para JSON."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional


def exportar_padroes(db, caminho: str = "padroes_export.json") -> Dict[str, Any]:
    """
    Exporta padrões + ranking + estatísticas de contexto para JSON.

    Retorna dict com metadados e caminho do arquivo.
    """
    try:
        padroes = db.carregar_padroes()
        ranking = db.carregar_ranking()
        contexto = db.carregar_contexto()
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}

    payload = {
        "versao": "1.0",
        "timestamp": datetime.now().isoformat(),
        "padroes": padroes,
        "ranking": ranking,
        "contexto": contexto,
    }

    try:
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        return {
            "sucesso": True,
            "caminho": caminho,
            "total_padroes": len(padroes),
            "total_ranking": len(ranking),
            "total_contexto": len(contexto),
        }
    except Exception as e:
        return {"sucesso": False, "erro": str(e)}


def importar_padroes(
    db,
    caminho: str,
    sobrescrever: bool = False,
) -> Dict[str, Any]:
    """
    Importa padrões + ranking + contexto de um JSON.

    Se `sobrescrever=True`, apaga os existentes antes.
    Se `sobrescrever=False`, mescla (padrões existentes têm prioridade).
    """
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception as e:
        return {"sucesso": False, "erro": f"Falha ao ler arquivo: {e}"}

    # Valida estrutura
    if not isinstance(payload, dict) or "padroes" not in payload:
        return {"sucesso": False, "erro": "Formato inválido do JSON"}

    padroes_import = payload.get("padroes", {})
    ranking_import = payload.get("ranking", {})
    contexto_import = payload.get("contexto", [])

    importados = {"padroes": 0, "ranking": 0, "contexto": 0}

    # Importa padrões
    for nome, item in padroes_import.items():
        try:
            padrao = item.get("padrao", [])
            sugestao = item.get("sugestao", "🔴")
            db.salvar_padrao(nome, padrao, sugestao)
            importados["padroes"] += 1
        except Exception:
            continue

    # Importa ranking (mescla com o atual)
    for padrao, dados in ranking_import.items():
        wins = dados.get("wins", 0)
        total = dados.get("total", 0)
        if total > 0:
            # Faz N atualizações para reconstruir o ranking
            atual = db.carregar_ranking().get(padrao, {"wins": 0, "total": 0})
            delta_wins = max(0, wins - atual.get("wins", 0))
            delta_total = max(0, total - atual.get("total", 0))
            if delta_total > 0:
                for i in range(delta_total):
                    db.atualizar_ranking(padrao, i < delta_wins)
                importados["ranking"] += 1

    # Importa contexto (mescla)
    for item in contexto_import:
        try:
            padrao = item.get("padrao", "")
            hora = item.get("hora", 0)
            dia_semana = item.get("dia_semana", 0)
            wins = item.get("wins", 0)
            total = item.get("total", 0)
            for i in range(total):
                db.registrar_contexto(padrao, hora, dia_semana, i < wins)
            importados["contexto"] += 1
        except Exception:
            continue

    return {
        "sucesso": True,
        "importados": importados,
    }