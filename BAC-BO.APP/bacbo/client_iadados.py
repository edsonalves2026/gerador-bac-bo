"""Cliente para a API iadados.com (sem autenticação Bearer).

Endpoint: https://iadados.com/php/bacbo_history_proxy.php
Só precisa do cookie PHPSESSID (que dura horas/dias).
"""
import os
from typing import List, Tuple

import requests

from .config import CoresTerminal, log_terminal


class IadadosClient:
    """Cliente para iadados.com — fallback simples e estável."""

    BASE_URL = "https://iadados.com/php/bacbo_history_proxy.php"

    def __init__(self, session: requests.Session, timeout: int = 10) -> None:
        self.session = session
        self.timeout = timeout
        self._configurar_headers()

    def _configurar_headers(self) -> None:
        """Headers base — imitam o navegador."""
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://iadados.com/index.php",
            "Origin": "https://iadados.com",
        })

        cookie = os.getenv("IADADOS_COOKIE", "")
        if cookie:
            self.session.headers["Cookie"] = cookie

    def buscar_historico(
        self,
        mesa_id: str = "",
        timezone: str = "America/Sao_Paulo",
        limite: int = 1000,
        usar_filter: bool = True,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        """Busca histórico da iadados.com."""
        url = (
            f"{self.BASE_URL}"
            f"?page=1"
            f"&limit={min(limite, 1000)}"
        )

        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                log_terminal(
                    f"❌ iadados status {resp.status_code}",
                    CoresTerminal.VERMELHO,
                )
                return [], [], [], [], []

            dados = resp.json()
            if not isinstance(dados, dict) or "data" not in dados:
                log_terminal(
                    "❌ iadados formato inesperado",
                    CoresTerminal.VERMELHO,
                )
                return [], [], [], [], []

        except Exception as e:
            log_terminal(
                f"❌ iadados erro: {str(e)[:100]}",
                CoresTerminal.VERMELHO,
            )
            return [], [], [], [], []

        return self._parse(dados["data"])

    @staticmethod
    def _parse(
        dados: list,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        """
        Parseia os resultados da iadados.com.

        IMPORTANTE: a API retorna em ordem DECRESCENTE (mais recente primeiro).
        Invertemos para o worker receber em ordem CRESCENTE (mais antigo primeiro).
        """
        cores, uuids, pontos, compostos, exibicao = [], [], [], [], []

        for item in dados:
            winner = str(item.get("winner", "")).strip()
            score = item.get("score", item.get("resultado", 0))
            hora = str(item.get("hora", "")).strip()

            if winner.lower() in ("banker", "red"):
                cor = "🔴"
            elif winner.lower() in ("player", "blue"):
                cor = "🔵"
            elif winner.lower() in ("tie", "yellow", "empate"):
                cor = "🟡"
            else:
                cor_letra = str(item.get("cor", "")).upper()
                if cor_letra == "V":
                    cor = "🔴"
                elif cor_letra == "A":
                    cor = "🔵"
                elif cor_letra in ("T", "E"):
                    cor = "🟡"
                else:
                    continue

            uid_final = f"iad_{hora}"

            cores.append(cor)
            uuids.append(uid_final)
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