"""Gerenciador de clientes — fallback automático entre APIs."""
import threading
from datetime import datetime
from typing import List, Optional, Tuple

from .client import TipminerClient
from .client_historicbet import HistoricBetClient
from .config import CoresTerminal, log_terminal


class ClientManager:
    """
    Gerencia múltiplos clientes HTTP com fallback automático.

    - Tenta a API primária (Tipminer) primeiro
    - Se falhar N vezes seguidas, troca para a fallback (HistoricBet)
    - Se a fallback também falhar, volta para a primária
    - Registra estatísticas de cada API
    """

    def __init__(
        self,
        tipminer: TipminerClient,
        historicbet: HistoricBetClient,
        max_falhas_antes_de_trocar: int = 3,
    ) -> None:
        self.tipminer = tipminer
        self.historicbet = historicbet
        self.max_falhas = max_falhas_antes_de_trocar

        self.lock = threading.RLock()
        self.api_ativa = "tipminer"   # "tipminer" ou "historicbet"

        # Estatísticas
        self.stats = {
            "tipminer": {"sucessos": 0, "falhas": 0, "falhas_consecutivas": 0},
            "historicbet": {"sucessos": 0, "falhas": 0, "falhas_consecutivas": 0},
        }

        # Timestamp da última troca
        self.ultima_troca: Optional[datetime] = None

    # ---------------------------------------------------------------- público
    def buscar_historico(self, **kwargs) -> Tuple[list, list, list, list, list]:
        """
        Busca histórico usando o cliente ativo.
        Se falhar, registra e tenta o outro automaticamente.
        """
        with self.lock:
            api_principal = self.api_ativa
            api_fallback = (
                "historicbet" if api_principal == "tipminer" else "tipminer"
            )

        # 1) Tenta a API ativa
        cores, uuids, pontos, compostos, exibicao = self._chamar_api(
            api_principal, **kwargs
        )

        if cores:
            with self.lock:
                self.stats[api_principal]["sucessos"] += 1
                self.stats[api_principal]["falhas_consecutivas"] = 0
            return cores, uuids, pontos, compostos, exibicao

        # 2) Falhou — registra
        with self.lock:
            self.stats[api_principal]["falhas"] += 1
            self.stats[api_principal]["falhas_consecutivas"] += 1
            falhas_seguidas = self.stats[api_principal]["falhas_consecutivas"]

        self._log_stats()

        # 3) Se passou do limite, tenta a fallback
        if falhas_seguidas >= self.max_falhas:
            log_terminal(
                f"⚠️ API '{api_principal}' falhou {falhas_seguidas}x. "
                f"Trocando para '{api_fallback}'...",
                CoresTerminal.AMARELO,
            )

            cores, uuids, pontos, compostos, exibicao = self._chamar_api(
                api_fallback, **kwargs
            )

            if cores:
                # Sucesso na fallback — registra
                with self.lock:
                    self.stats[api_fallback]["sucessos"] += 1
                    self.stats[api_fallback]["falhas_consecutivas"] = 0
                    self.api_ativa = api_fallback
                    self.ultima_troca = datetime.now()

                log_terminal(
                    f"✅ Trocado para '{api_fallback}' com sucesso!",
                    CoresTerminal.VERDE,
                )
                return cores, uuids, pontos, compostos, exibicao

            # Fallback também falhou
            with self.lock:
                self.stats[api_fallback]["falhas"] += 1
                self.stats[api_fallback]["falhas_consecutivas"] += 1

            log_terminal(
                f"❌ Ambas as APIs falharam!",
                CoresTerminal.VERMELHO,
            )

        return [], [], [], [], []

    def _chamar_api(self, api: str, **kwargs) -> Tuple[list, list, list, list, list]:
        """Chama o cliente específico."""
        try:
            if api == "tipminer":
                return self.tipminer.buscar_historico(
                    mesa_id=kwargs.get("mesa_id", ""),
                    timezone=kwargs.get("timezone", "America/Sao_Paulo"),
                    limite=kwargs.get("limite", 300),
                )
            elif api == "historicbet":
                return self.historicbet.buscar_historico(
                    limite=kwargs.get("limite", 1000),
                )
            else:
                return [], [], [], [], []
        except Exception as e:
            log_terminal(
                f"❌ Erro ao chamar {api}: {str(e)[:100]}",
                CoresTerminal.VERMELHO,
            )
            return [], [], [], [], []

    def _log_stats(self) -> None:
        """Loga estatísticas das APIs."""
        with self.lock:
            t = self.stats["tipminer"]
            h = self.stats["historicbet"]

        log_terminal(
            f"📊 Tipminer: {t['sucessos']}✓ / {t['falhas']}✗ | "
            f"HistoricBet: {h['sucessos']}✓ / {h['falhas']}✗",
            CoresTerminal.CIANO,
        )

    # ------------------------------------------------------------ diagnóstico
    def get_stats(self) -> dict:
        """Retorna estatísticas para o dashboard."""
        with self.lock:
            return {
                "api_ativa": self.api_ativa,
                "tipminer": dict(self.stats["tipminer"]),
                "historicbet": dict(self.stats["historicbet"]),
                "ultima_troca": (
                    self.ultima_troca.isoformat() if self.ultima_troca else None
                ),
            }

    def forcar_api(self, api: str) -> bool:
        """Força uma API específica (útil para testes)."""
        if api not in ("tipminer", "historicbet"):
            return False
        with self.lock:
            self.api_ativa = api
            self.ultima_troca = datetime.now()
        log_terminal(f"🔧 API forçada para '{api}'", CoresTerminal.CIANO)
        return True