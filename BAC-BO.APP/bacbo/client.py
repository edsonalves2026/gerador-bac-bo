"""Cliente HTTP da API Tipminer com paginação automática."""
import time
import uuid
from typing import List, Tuple

import requests

from .config import CoresTerminal, log_terminal


class TipminerClient:
    """Cliente para a API pública do Tipminer (Bac Bo)."""

    BASE_URL = "https://api.core.public.tipminer.com/v1/bac-bo/rounds"
    MAX_POR_PAGINA = 200      # limite que a API respeita por chamada
    MAX_PAGINAS = 10          # segurança: até 2000 rodadas

    def __init__(self, session: requests.Session, timeout: int = 10) -> None:
        self.session = session
        self.timeout = timeout

    # ------------------------------------------------------------------ API
    def buscar_historico(
        self,
        mesa_id: str,
        timezone: str = "America/Sao_Paulo",
        limite: int = 200,
        usar_filter: bool = True,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
        """
        Busca histórico da mesa. Se `limite > 200`, faz paginação automática
        usando o `instant` da rodada mais antiga como cursor (`before=`).

        Retorna listas em ordem CRONOLÓGICA CRESCENTE (mais antiga primeiro).
        """
        tz_encoded = timezone.replace("/", "%2F")
        todas_rodadas: List[dict] = []
        cursor_ts: str | None = None

        paginas = 0
        while paginas < self.MAX_PAGINAS:
            cb = uuid.uuid4()
            ts = int(time.time() * 1000)
            extra = "&subject=filter" if usar_filter else ""
            cursor_param = f"&before={cursor_ts}" if cursor_ts else ""

            url = (
                f"{self.BASE_URL}/{mesa_id}/history"
                f"?timezone={tz_encoded}"
                f"{extra}"
                f"&limit={self.MAX_POR_PAGINA}"
                f"{cursor_param}"
                f"&t={ts}"
                f"&_cb={cb}"
            )

            try:
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code != 200:
                    log_terminal(
                        f"❌ API status {resp.status_code} (pág {paginas+1})",
                        CoresTerminal.VERMELHO,
                    )
                    break
                dados = resp.json()
                if not isinstance(dados, list) or not dados:
                    break
            except Exception as e:
                log_terminal(
                    f"❌ API erro: {str(e)[:100]}", CoresTerminal.VERMELHO
                )
                break

            # Filtra rodadas novas (evita duplicatas entre páginas)
            uuids_existentes = {r.get("uuid") for r in todas_rodadas}
            novas = [r for r in dados if r.get("uuid") not in uuids_existentes]

            if not novas:
                # Página só trouxe duplicatas → acabou o histórico
                break

            todas_rodadas.extend(novas)
            paginas += 1

            # Já atingiu o limite pedido?
            if len(todas_rodadas) >= limite:
                break

            # Se a página veio incompleta, não há mais dados
            if len(dados) < self.MAX_POR_PAGINA:
                break

            # Cursor para a próxima página: `instant` da rodada MAIS ANTIGA
            # (última da lista, já que a API retorna decrescente por data)
            cursor_ts = dados[-1].get("instant")
            if not cursor_ts:
                break

        # Trunca no limite pedido
        todas_rodadas = todas_rodadas[:limite]

        # Reordena do mais antigo para o mais novo
        todas_rodadas.sort(key=lambda x: x.get("instant", ""))

        # Parseia
        return self._parse(todas_rodadas)

    # ---------------------------------------------------------------- parser
    @staticmethod
    def _parse(
        dados: list,
    ) -> Tuple[List[str], List[str], List[int], List[str], List[str]]:
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

        return cores, uuids, pontos, compostos, exibicao