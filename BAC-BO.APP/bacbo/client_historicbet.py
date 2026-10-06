"""Cliente HistoricBet com login automático e refresh de tokens."""
import os
import threading
import time
from typing import List, Optional, Tuple

import requests

from .config import CoresTerminal, log_terminal


class HistoricBetClient:
    """
    Cliente para a API pública da HistoricBet.

    Fluxo:
      1. Login com email + senha → recebe accessToken + refreshToken
      2. Usa accessToken para /results
      3. Renova accessToken quando expira (via login ou refresh)
    """

    BASE_URL = "https://api.historicbet.com"
    LOGIN_URL = f"{BASE_URL}/auth/login"
    RESULTS_URL = f"{BASE_URL}/results"

    def __init__(
        self,
        session: requests.Session,
        email: str = "",
        password: str = "",
        timeout: int = 10,
    ) -> None:
        self.session = session
        self.timeout = timeout
        self.email = email or os.getenv("HISTORICBET_EMAIL", "")
        self.password = password or os.getenv("HISTORICBET_PASSWORD", "")

        # Tokens (em memória)
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.access_token_exp: float = 0.0  # timestamp de expiração

        self._lock = threading.RLock()

        self._configurar_headers()

    # ---------------------------------------------------------------- headers
    def _configurar_headers(self) -> None:
        """Headers base do navegador."""
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Origin": "https://historic.com.br",
            "Referer": "https://historic.com.br/",
        })

    # ------------------------------------------------------------------ login
    def _fazer_login(self) -> bool:
        """Faz login e armazena os tokens."""
        if not self.email or not self.password:
            log_terminal(
                "❌ HistoricBet: credenciais não configuradas",
                CoresTerminal.VERMELHO,
            )
            return False

        payload = {"email": self.email, "password": self.password}

        try:
            resp = self.session.post(
                self.LOGIN_URL, json=payload, timeout=self.timeout
            )
            if resp.status_code != 200:
                log_terminal(
                    f"❌ HistoricBet login falhou: {resp.status_code}",
                    CoresTerminal.VERMELHO,
                )
                return False

            dados = resp.json()
            self.access_token = dados.get("accessToken")
            self.refresh_token = dados.get("refreshToken")

            if not self.access_token:
                log_terminal(
                    "❌ HistoricBet: accessToken não retornado",
                    CoresTerminal.VERMELHO,
                )
                return False

            # Decodifica o JWT para pegar a expiração
            try:
                import base64
                import json

                parts = self.access_token.split(".")
                if len(parts) == 3:
                    payload_b64 = parts[1]
                    # Corrige padding
                    payload_b64 += "=" * (-len(payload_b64) % 4)
                    payload_json = json.loads(
                        base64.urlsafe_b64decode(payload_b64)
                    )
                    self.access_token_exp = float(payload_json.get("exp", 0))
                else:
                    # Fallback: assume 15 min
                    self.access_token_exp = time.time() + 900
            except Exception:
                self.access_token_exp = time.time() + 900

            log_terminal(
                f"✅ HistoricBet: login OK (expira em "
                f"{int(self.access_token_exp - time.time())}s)",
                CoresTerminal.VERDE,
            )
            return True

        except Exception as e:
            log_terminal(
                f"❌ HistoricBet login exception: {str(e)[:100]}",
                CoresTerminal.VERMELHO,
            )
            return False

    def _garantir_token_valido(self) -> bool:
        """
        Verifica se o accessToken está válido.
        Se estiver expirado (ou perto de expirar), refaz login.
        """
        with self._lock:
            # Considera expirado se faltar menos de 60 segundos
            if (
                self.access_token
                and time.time() < (self.access_token_exp - 60)
            ):
                return True

            # Precisa renovar
            log_terminal(
                "🔄 HistoricBet: token expirado, refazendo login...",
                CoresTerminal.AMARELO,
            )
            return self._fazer_login()

    # ------------------------------------------------------------------ buscar
    def buscar_historico(
        self,
        mesa_id: str = "",
        timezone: str = "America/Sao_Paulo",
        limite: int = 1000,
        usar_filter: bool = True,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        """
        Busca histórico de rodadas da HistoricBet.

        Args:
            mesa_id: ignorado (a API usa uma mesa só)
            timezone: ignorado
            limite: máximo 1000 (limite da API)
            usar_filter: ignorado (sempre usa)

        Returns:
            (cores, uuids, pontos, compostos, exibicao) em ordem CRESCENTE.
        """
        # Garante token válido
        if not self._garantir_token_valido():
            return [], [], [], [], []

        url = (
            f"{self.RESULTS_URL}"
            f"?page=1"
            f"&limit={min(limite, 1000)}"
            f"&galeFilter=SG,G1,G2"
            f"&gameType=1"
            f"&full=true"
        )

        headers = {"Authorization": f"Bearer {self.access_token}"}

        try:
            resp = self.session.get(
                url, headers=headers, timeout=self.timeout
            )

            # Se 401/403, tenta refazer login uma vez
            if resp.status_code in (401, 403):
                log_terminal(
                    f"⚠️ HistoricBet: {resp.status_code} — "
                    f"tentando refazer login...",
                    CoresTerminal.AMARELO,
                )
                if not self._fazer_login():
                    return [], [], [], [], []
                headers["Authorization"] = f"Bearer {self.access_token}"
                resp = self.session.get(
                    url, headers=headers, timeout=self.timeout
                )

            if resp.status_code != 200:
                log_terminal(
                    f"❌ HistoricBet: status {resp.status_code}",
                    CoresTerminal.VERMELHO,
                )
                return [], [], [], [], []

            dados = resp.json()
            if not isinstance(dados, dict) or "data" not in dados:
                log_terminal(
                    "❌ HistoricBet: formato inesperado",
                    CoresTerminal.VERMELHO,
                )
                return [], [], [], [], []

            return self._parse(dados["data"])

        except Exception as e:
            log_terminal(
                f"❌ HistoricBet erro: {str(e)[:100]}",
                CoresTerminal.VERMELHO,
            )
            return [], [], [], [], []

    # ------------------------------------------------------------------ parser
    @staticmethod
    def _parse(
        dados: list,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        cores, uuids, pontos, compostos, exibicao = [], [], [], [], []

        for item in dados:
            winner = str(item.get("winner", "")).strip()
            uid = str(item.get("id", ""))
            score = item.get("Score", 0)

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
            uuids.append(f"hb_{uid}")  # prefixo para diferenciar
            pontos.append(score)
            compostos.append(f"{cor} {score}")
            exibicao.append(f"{cor} ({score})")

        # Inverte (mais recente primeiro → mais antigo primeiro)
        return (
            cores[::-1],
            uuids[::-1],
            pontos[::-1],
            compostos[::-1],
            exibicao[::-1],
        )