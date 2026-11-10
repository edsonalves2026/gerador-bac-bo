"""Cliente alternativo para a API HistoricBet.

Esta API exige headers específicos e possivelmente cookies de sessão.
Configure os cookies em `bacbo/config.py` ou via variável de ambiente.
"""
import os
from typing import List, Tuple

import requests

from .config import CoresTerminal, log_terminal


class HistoricBetClient:
    """Cliente para a API pública da HistoricBet (fallback)."""

    BASE_URL = "https://api.historicbet.com/results"

    def __init__(self, session: requests.Session, timeout: int = 10) -> None:
        self.session = session
        self.timeout = timeout
        self._configurar_headers()

    def _configurar_headers(self) -> None:
        """Configura headers idênticos ao navegador."""
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Origin": "https://historic.com.br",
            "Referer": "https://historic.com.br/",
        })

        # Cookies de sessão (capturados do navegador)
        # Podem vir de variável de ambiente ou config
        cookies_str = os.getenv("HISTORICBET_COOKIES", "")
        if cookies_str:
            self.session.headers["Cookie"] = cookies_str

    def buscar_historico(
        self,
        mesa_id: str = "",       # HistoriBet usa mesa única (Bac Bo)
        timezone: str = "America/Sao_Paulo",   # não usado
        limite: int = 1000,
        usar_filter: bool = True,    # não usado
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        """
        Busca histórico da HistoricBet.

        A API retorna JSON com formato:
        {
          "data": [
            {
              "id": 4688151,
              "winner": "Banker" | "Player" | "Tie",
              "Score": 11,
              "Hora": "08:27:28",
              ...
            },
            ...
          ],
          "count": 1000
        }
        """
        url = (
            f"{self.BASE_URL}"
            f"?page=1"
            f"&limit={min(limite, 1000)}"
            f"&galeFilter=SG,G1,G2"
            f"&gameType=1"
            f"&full=true"
        )

        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                log_terminal(
                    f"❌ HistoricBet status {resp.status_code}",
                    CoresTerminal.VERMELHO,
                )
                return [], [], [], [], []

            dados = resp.json()
            if not isinstance(dados, dict) or "data" not in dados:
                log_terminal(
                    "❌ HistoricBet formato inesperado",
                    CoresTerminal.VERMELHO,
                )
                return [], [], [], [], []

        except Exception as e:
            log_terminal(
                f"❌ HistoricBet erro: {str(e)[:100]}",
                CoresTerminal.VERMELHO,
            )
            return [], [], [], [], []

        return self._parse(dados["data"])

    @staticmethod
    def _parse(
        dados: list,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        """
        Parseia a lista de resultados da HistoricBet.

        A API retorna em ordem DECRESCENTE (mais recente primeiro).
        Convertemos para CRESCENTE (mais antigo primeiro).
        """
        cores, uuids, pontos, compostos, exibicao = [], [], [], [], []

        for item in dados:
            winner = str(item.get("winner", "")).strip()
            uid = str(item.get("id", ""))
            score = item.get("Score", 0)
            hora = item.get("Hora", "")

            # Mapeia o nome da cor
            if winner.lower() in ("banker", "red"):
                cor = "🔴"
            elif winner.lower() in ("player", "blue"):
                cor = "🔵"
            elif winner.lower() in ("tie", "yellow", "empate"):
                cor = "🟡"
            else:
                continue

            if not uid:
                continue

            cores.append(cor)
            uuids.append(f"hb_{uid}")  # prefixo hb_ para diferenciar da Tipminer
            pontos.append(score)
            compostos.append(f"{cor} {score}")
            exibicao.append(f"{cor} ({score})")

        # Inverte para ordem cronológica crescente
        return (
            cores[::-1],
            uuids[::-1],
            pontos[::-1],
            compostos[::-1],
            exibicao[::-1],
        )