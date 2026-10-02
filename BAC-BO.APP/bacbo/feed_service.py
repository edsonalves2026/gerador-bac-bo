"""Feed de sinais ao vivo — eventos cronológicos estilo chat."""
import threading
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo


# =============================================================================
# TIMEZONE
# =============================================================================
TZ_BR = ZoneInfo("America/Sao_Paulo")


def _agora() -> datetime:
    """Retorna datetime no fuso de Brasília (funciona em Cloud UTC)."""
    return datetime.now(TZ_BR)


# =============================================================================
# TIPOS DE EVENTO
# =============================================================================
class Evento:
    ENTRADA = "entrada"
    RESULTADO = "resultado"
    BLOQUEIO = "bloqueio"
    INFO = "info"


# =============================================================================
# ESTRUTURA DE UM EVENTO DO FEED
# =============================================================================
@dataclass
class FeedEvent:
    tipo: str                         # "entrada" | "resultado" | "bloqueio" | "info"
    titulo: str                       # ex: "ENTRADA DETECTADA!"
    corpo: str                        # ex: "Faça a entrada no 🔵 Azul ou Tie"
    subtitulo: str = ""               # ex: "Empate = GREEN · Até 1 gale"
    cor: str = ""                     # "verde" | "vermelho" | "amarelo" | "azul" | "cinza"
    icone: str = ""                   # emoji ou classe
    ts: str = ""                      # HH:MM
    ts_full: str = ""                 # ISO

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =============================================================================
# SERVIÇO DE FEED (thread-safe)
# =============================================================================
class FeedService:
    MAX_EVENTOS = 100

    def __init__(self, db=None) -> None:
        self.db = db
        self._lock = threading.RLock()
        self._eventos: List[FeedEvent] = []

    # -------------------------------------------------------------- público
    def push(self, evento: FeedEvent) -> None:
        with self._lock:
            self._eventos.insert(0, evento)
            if len(self._eventos) > self.MAX_EVENTOS:
                self._eventos.pop()

        # Persistência opcional
        if self.db:
            try:
                self.db.salvar_evento_feed(evento.to_dict())
            except Exception:
                pass

    def push_entrada(self, sugestao: str, gale_max: int, fonte: str = "") -> None:
        """Atalho para evento de entrada."""
        nome = {"🔴": "Vermelho", "🔵": "Azul", "🟡": "Tie"}.get(sugestao, "—")
        agora = _agora()
        self.push(FeedEvent(
            tipo=Evento.ENTRADA,
            titulo="ENTRADA DETECTADA!",
            corpo=f"Faça a entrada no {sugestao} {nome} ou Tie 🟡",
            subtitulo=f"Empate = GREEN · Até {gale_max} gale",
            cor="amarelo",
            icone="⚠️",
            ts=agora.strftime("%H:%M"),
            ts_full=agora.isoformat(),
        ))

    def push_resultado(self, tipo_win: str) -> None:
        """Atalho para evento de resultado (WIN/GALE/LOSS)."""
        mapa = {
            "WIN": ("GREEN!", "verde", "✅"),
            "WIN_G1": ("GREEN no Gale 1!", "verde", "✅"),
            "WIN_TIE": ("GREEN protegido (Tie)", "verde", "🟡"),
            "LOSS": ("RED — Não bateu", "vermelho", "❌"),
        }
        titulo, cor, icone = mapa.get(tipo_win, ("Resultado", "cinza", "•"))
        agora = _agora()
        self.push(FeedEvent(
            tipo=Evento.RESULTADO,
            titulo="Resultado",
            corpo=titulo,
            subtitulo=(
                "Aguardando próximo padrão..."
                if "LOSS" not in tipo_win
                else "Aguardando novo sinal"
            ),
            cor=cor,
            icone=icone,
            ts=agora.strftime("%H:%M"),
            ts_full=agora.isoformat(),
        ))

    def push_bloqueio(self, motivo: str) -> None:
        agora = _agora()
        self.push(FeedEvent(
            tipo=Evento.BLOQUEIO,
            titulo="BOT BLOQUEADO",
            corpo=motivo,
            subtitulo="Operação suspensa temporariamente",
            cor="vermelho",
            icone="🛑",
            ts=agora.strftime("%H:%M"),
            ts_full=agora.isoformat(),
        ))

    def push_info(self, msg: str) -> None:
        agora = _agora()
        self.push(FeedEvent(
            tipo=Evento.INFO,
            titulo="Sistema",
            corpo=msg,
            cor="cinza",
            icone="ℹ️",
            ts=agora.strftime("%H:%M"),
            ts_full=agora.isoformat(),
        ))

    def eventos(self, limite: Optional[int] = None) -> List[FeedEvent]:
        with self._lock:
            evts = list(self._eventos)
        return evts[:limite] if limite else evts

    def limpar(self) -> None:
        with self._lock:
            self._eventos.clear()
