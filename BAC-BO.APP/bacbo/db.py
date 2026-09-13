"""Persistência SQLite (padrões, ranking, rodadas, contexto)."""
import json
import sqlite3
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


class Database:
    def __init__(self, path: str = "bacbo.db") -> None:
        self.path = path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS padroes (
                    nome        TEXT PRIMARY KEY,
                    padrao_json TEXT NOT NULL,
                    sugestao    TEXT NOT NULL,
                    ativo       INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS ranking (
                    padrao TEXT PRIMARY KEY,
                    wins   INTEGER DEFAULT 0,
                    total  INTEGER DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS rodadas (
                    uuid        TEXT PRIMARY KEY,
                    mesa_id     TEXT NOT NULL,
                    cor         TEXT NOT NULL,
                    ponto       INTEGER,
                    ts_servidor TEXT,
                    ts_local    TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_rodadas_mesa
                    ON rodadas(mesa_id, ts_servidor);
                CREATE TABLE IF NOT EXISTS estatisticas_contexto (
                    padrao      TEXT,
                    hora        INTEGER,
                    dia_semana  INTEGER,
                    wins        INTEGER DEFAULT 0,
                    total       INTEGER DEFAULT 0,
                    PRIMARY KEY (padrao, hora, dia_semana)
                );
            """)
            self._conn.commit()

    # ---------- padrões ----------
    def carregar_padroes(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT nome, padrao_json, sugestao, ativo FROM padroes"
            ).fetchall()
        return {
            r["nome"]: {
                "padrao": json.loads(r["padrao_json"]),
                "sugestao": r["sugestao"],
                "ativo": bool(r["ativo"]),
            }
            for r in rows
        }

    def salvar_padrao(self, nome: str, padrao: list, sugestao: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO padroes (nome, padrao_json, sugestao, ativo) "
                "VALUES (?, ?, ?, 1)",
                (nome, json.dumps(padrao, ensure_ascii=False), sugestao),
            )
            self._conn.commit()

    def remover_padrao(self, nome: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM padroes WHERE nome = ?", (nome,))
            self._conn.commit()

    # ---------- ranking ----------
    def carregar_ranking(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            rows = self._conn.execute("SELECT padrao, wins, total FROM ranking").fetchall()
        return {r["padrao"]: {"wins": r["wins"], "total": r["total"]} for r in rows}

    def atualizar_ranking(self, padrao: str, win: bool) -> None:
        with self._lock:
            self._conn.execute("""
                INSERT INTO ranking (padrao, wins, total) VALUES (?, ?, 1)
                ON CONFLICT(padrao) DO UPDATE SET
                    wins  = wins  + ?,
                    total = total + 1
            """, (padrao, 1 if win else 0, 1 if win else 0))
            self._conn.commit()

    # ---------- rodadas ----------
    def salvar_rodadas(self, mesa_id: str, rodadas: List[Dict[str, Any]]) -> int:
        novos = 0
        ts_local = datetime.now().isoformat()
        with self._lock:
            for r in rodadas:
                cur = self._conn.execute(
                    "INSERT OR IGNORE INTO rodadas "
                    "(uuid, mesa_id, cor, ponto, ts_servidor, ts_local) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (r["uuid"], mesa_id, r["cor"], r.get("ponto"),
                     r.get("ts_servidor", ""), ts_local),
                )
                novos += cur.rowcount
            self._conn.commit()
        return novos

    def carregar_rodadas(
        self, mesa_id: str, limite: Optional[int] = None,
    ) -> List[Tuple[str, int]]:
        if limite:
            sql = (
                "SELECT cor, ponto FROM ("
                "  SELECT cor, ponto, rowid FROM rodadas "
                "  WHERE mesa_id = ? ORDER BY rowid DESC LIMIT ?"
                ") ORDER BY rowid ASC"
            )
            params: tuple = (mesa_id, limite)
        else:
            sql = "SELECT cor, ponto FROM rodadas WHERE mesa_id = ? ORDER BY rowid ASC"
            params = (mesa_id,)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [(r["cor"], r["ponto"]) for r in rows]

    def total_rodadas(self, mesa_id: Optional[str] = None) -> int:
        with self._lock:
            if mesa_id:
                return self._conn.execute(
                    "SELECT COUNT(*) FROM rodadas WHERE mesa_id = ?", (mesa_id,)
                ).fetchone()[0]
            return self._conn.execute("SELECT COUNT(*) FROM rodadas").fetchone()[0]

    # ---------- contexto ----------
    def registrar_contexto(
        self, padrao: str, hora: int, dia_semana: int, win: bool,
    ) -> None:
        with self._lock:
            self._conn.execute("""
                INSERT INTO estatisticas_contexto (padrao, hora, dia_semana, wins, total)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(padrao, hora, dia_semana) DO UPDATE SET
                    wins  = wins  + ?,
                    total = total + 1
            """, (padrao, hora, dia_semana, 1 if win else 0, 1 if win else 0))
            self._conn.commit()

    def carregar_contexto(self, padrao: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM estatisticas_contexto"
        params: tuple = ()
        if padrao:
            sql += " WHERE padrao = ?"
            params = (padrao,)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()