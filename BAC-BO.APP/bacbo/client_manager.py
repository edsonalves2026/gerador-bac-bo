"""Gerenciador de clientes — fallback automático entre APIs."""
import threading
from datetime import datetime
from typing import List, Optional, Tuple

from .client import TipminerClient
from .client_historicbet import HistoricBetClient
from .client_iadados import IadadosClient
from .config import CoresTerminal, log_terminal


class ClientManager:
    """
    Gerencia múltiplos clientes HTTP com fallback automático.

    Ordem: Tipminer → HistoricBet → iadados
    Se um falhar N vezes seguidas, tenta o próximo.
    """

    def __init__(
        self,
        tipminer: TipminerClient,
        historicbet: HistoricBetClient = None,
        iadados: IadadosClient = None,
        max_falhas_antes_de_trocar: int = 3,
    ) -> None:
        self.tipminer = tipminer
        self.historicbet = historicbet
        self.iadados = iadados
        self.max_falhas = max_falhas_antes_de_trocar

        self.lock = threading.RLock()

        # Lista de APIs disponíveis (em ordem de prioridade)
        self.apis = ["tipminer"]
        if historicbet:
            self.apis.append("historicbet")
        if iadados:
            self.apis.append("iadados")

        self.api_ativa = "tipminer"

        # Estatísticas
        self.stats = {
            api: {"sucessos": 0, "falhas": 0, "falhas_consecutivas": 0}
            for api in self.apis
        }

        self.ultima_troca: Optional[datetime] = None

    # ---------------------------------------------------------------- público
    def buscar_historico(self, **kwargs) -> Tuple[list, list, list, list, list]:
        """
        Busca histórico usando o cliente ativo.
        Se falhar N vezes, tenta a próxima API na lista.
        """
        with self.lock:
            idx_atual = self.apis.index(self.api_ativa)

        # 1) Tenta a API ativa
        cores, uuids, pontos, compostos, exibicao = self._chamar_api(
            self.api_ativa, **kwargs
        )

        if cores:
            with self.lock:
                self.stats[self.api_ativa]["sucessos"] += 1
                self.stats[self.api_ativa]["falhas_consecutivas"] = 0
            return cores, uuids, pontos, compostos, exibicao

        # 2) Falhou — registra
        with self.lock:
            self.stats[self.api_ativa]["falhas"] += 1
            self.stats[self.api_ativa]["falhas_consecutivas"] += 1
            falhas_seguidas = self.stats[self.api_ativa]["falhas_consecutivas"]

        self._log_stats()

        # 3) Se passou do limite, tenta as outras APIs
        if falhas_seguidas >= self.max_falhas:
            # Tenta as APIs na ordem, começando pela próxima
            for offset in range(1, len(self.apis)):
                proxima_idx = (idx_atual + offset) % len(self.apis)
                proxima_api = self.apis[proxima_idx]

                log_terminal(
                    f"⚠️ API '{self.api_ativa}' falhou {falhas_seguidas}x. "
                    f"Trocando para '{proxima_api}'...",
                    CoresTerminal.AMARELO,
                )

                cores, uuids, pontos, compostos, exibicao = self._chamar_api(
                    proxima_api, **kwargs
                )

                if cores:
                    with self.lock:
                        self.stats[proxima_api]["sucessos"] += 1
                        self.stats[proxima_api]["falhas_consecutivas"] = 0
                        self.api_ativa = proxima_api
                        self.ultima_troca = datetime.now()

                    log_terminal(
                        f"✅ Trocado para '{proxima_api}' com sucesso!",
                        CoresTerminal.VERDE,
                    )
                    return cores, uuids, pontos, compostos, exibicao

                with self.lock:
                    self.stats[proxima_api]["falhas"] += 1
                    self.stats[proxima_api]["falhas_consecutivas"] += 1

            log_terminal(
                "❌ Todas as APIs falharam!",
                CoresTerminal.VERMELHO,
            )

        return [], [], [], [], []

    def _chamar_api(self, api: str, **kwargs) -> Tuple[list, list, list, list, list]:
        """Chama o cliente específico."""
        try:
            if api == "tipminer" and self.tipminer:
                return self.tipminer.buscar_historico(
                    mesa_id=kwargs.get("mesa_id", ""),
                    timezone=kwargs.get("timezone", "America/Sao_Paulo"),
                    limite=kwargs.get("limite", 300),
                )
            elif api == "historicbet" and self.historicbet:
                return self.historicbet.buscar_historico(
                    limite=kwargs.get("limite", 1000),
                )
            elif api == "iadados" and self.iadados:
                return self.iadados.buscar_historico(
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
            partes = []
            for api in self.apis:
                s = self.stats[api]
                partes.append(f"{api.capitalize()}: {s['sucessos']}✓ / {s['falhas']}✗")
            msg = " | ".join(partes)

        log_terminal(f"📊 {msg}", CoresTerminal.CIANO)

    # ------------------------------------------------------------ diagnóstico
    def get_stats(self) -> dict:
        """Retorna estatísticas para o dashboard."""
        with self.lock:
            return {
                "api_ativa": self.api_ativa,
                "apis_disponiveis": list(self.apis),
                "tipminer": dict(self.stats.get("tipminer", {})),
                "historicbet": dict(self.stats.get("historicbet", {})),
                "iadados": dict(self.stats.get("iadados", {})),
                "ultima_troca": (
                    self.ultima_troca.isoformat() if self.ultima_troca else None
                ),
            }

    def forcar_api(self, api: str) -> bool:
        """Força uma API específica."""
        if api not in self.apis:
            return False
        with self.lock:
            self.api_ativa = api
            self.ultima_troca = datetime.now()
        log_terminal(f"🔧 API forçada para '{api}'", CoresTerminal.CIANO)
        return True