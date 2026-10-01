"""Serviço de análise — busca histórico amplo e mantém cache."""
import threading
import time
from typing import Any, Dict, List, Optional

from .patterns_analyzer import PatternsAnalyzer


class AnalysisService:
    """
    Responsável por:
      - buscar histórico amplo (500+ rodadas) na API
      - rodar PatternsAnalyzer
      - cachear por N segundos (evita re-análise a cada rerun Streamlit)
    """

    def __init__(self, client, ttl_segundos: int = 60) -> None:
        self.client = client
        self.ttl = ttl_segundos
        self._cache: Optional[Dict[str, Any]] = None
        self._cache_ts: float = 0.0
        self._lock = threading.RLock()

        def obter_analise(
        self,
        mesa_id: str,
        timezone: str,
        num_rodadas: int = 500,
        tamanho_cor: int = 4,
        min_ocorrencias: int = 4,
        min_taxa: float = 85.0,
        usar_gale: int = 2,
        forcar: bool = False,
    ) -> Dict[str, Any]:
        with self._lock:
            agora = time.time()
            if not forcar and self._cache and (agora - self._cache_ts) < self.ttl:
                cached = dict(self._cache)
                cached["cacheado"] = True
                return cached

            cores, uuids, pontos, _, _ = self.client.buscar_historico(
                mesa_id=mesa_id,
                timezone=timezone,
                limite=num_rodadas,
            )

            if len(cores) < tamanho_cor + 5:
                return {
                    "resultados": {"cores": [], "numeros": [], "sequencias": []},
                    "stats": None,
                    "total_rodadas": len(cores),
                    "timestamp": time.strftime("%H:%M:%S"),
                    "cacheado": False,
                    "erro": "Histórico insuficiente",
                }

            cores_uso = cores[-num_rodadas:]
            pontos_uso = pontos[-num_rodadas:]

            analyzer = PatternsAnalyzer(cores_uso, pontos_uso)
            resultados = analyzer.analisar_tudo(
                tamanho_cor=tamanho_cor,
                min_ocorrencias=min_ocorrencias,
                min_taxa=min_taxa,
                usar_gale=usar_gale,
            )

            # --- NOVO: painel de estatísticas ---
            from .stats_analyzer import StatsAnalyzer
            stats = StatsAnalyzer(cores_uso).calcular(gale=int(usar_gale))

            self._cache = {
                "resultados": resultados,
                "stats": stats,
                "total_rodadas": len(cores_uso),
                "timestamp": time.strftime("%H:%M:%S"),
                "cacheado": False,
            }
            self._cache_ts = agora
            return self._cache

    def invalidar(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_ts = 0.0
