"""Cliente HTTP da API Tipminer."""
import uuid
from typing import List, Tuple
import requests

from .config import CoresTerminal, log_terminal


class TipminerClient:
    def __init__(self, session: requests.Session, timeout: int = 10) -> None:
        self.session = session
        self.timeout = timeout

    def buscar_historico(
        self,
        mesa_id: str,
        timezone: str = "America/Sao_Paulo",
        limite: int = 200,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        url = (
            f"https://api.core.public.tipminer.com/v1/bac-bo/rounds/{mesa_id}/history"
            f"?limit={limite}&timezone={timezone.replace('/', '%2F')}&_cb={uuid.uuid4()}"
        )
        try:
            resp = self.session.get(url, timeout=self.timeout)
            if resp.status_code != 200:
                return [], [], [], [], []
            dados = resp.json()
            if not isinstance(dados, list):
                return [], [], [], [], []
        except Exception as e:
            log_terminal(f"❌ API erro: {str(e)[:100]}", CoresTerminal.VERMELHO)
            return [], [], [], [], []

        return self._parse(dados)

    @staticmethod
    def _parse(dados: list) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        cores, uuids, pontos, compostos, exibicao = [], [], [], [], []
        for item in dados:
            tipo = str(item.get("type", "")).upper()
            uuid_r = item.get("uuid", "")
            ponto = item.get("result", 0)

            if "BANKER" in tipo or "RED" in tipo:
                cor = "🔴"
            elif "PLAYER" in tipo or "BLUE" in tipo:
                cor = "🔵"
            elif "TIE" in tipo or "YELLOW" in tipo:
                cor = "🟡"
            else:
                continue

            if not uuid_r:
                continue

            cores.append(cor)
            uuids.append(uuid_r)
            pontos.append(ponto)
            compostos.append(f"{cor} {ponto}")
            exibicao.append(f"{cor} ({ponto})")

        return cores[::-1], uuids[::-1], pontos[::-1], compostos[::-1], exibicao[::-1]