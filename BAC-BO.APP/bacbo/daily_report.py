"""Resumo diário e envio automático às 23:59."""
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from .config import CoresTerminal, log_terminal

TZ_BR = ZoneInfo("America/Sao_Paulo")


def _agora() -> datetime:
    return datetime.now(TZ_BR)

def gerar_resumo_diario(db, data: datetime = None) -> Dict[str, Any]:
    """
    Gera resumo de um dia específico (padrão: hoje).

    Nota: como o ranking no SQLite só armazena wins/total, este resumo
    usa o histórico da sessão atual quando disponível.
    """
    if data is None:
        data = _agora()

    # Carrega ranking acumulado
    ranking = db.carregar_ranking()

    total_wins = sum(d.get("wins", 0) for d in ranking.values())
    total_geral = sum(d.get("total", 0) for d in ranking.values())
    total_loss = max(0, total_geral - total_wins)

    # TIE específico (padrões com "TIE" ou "tie" no nome)
    tie_padroes = {
        k: v for k, v in ranking.items() if "TIE" in k or "tie" in k
    }
    tie_wins = sum(d.get("wins", 0) for d in tie_padroes.values())
    tie_total = sum(d.get("total", 0) for d in tie_padroes.values())
    tie_loss = max(0, tie_total - tie_wins)

    # Top 5 padrões
    ranking_ordenado = sorted(
        ranking.items(),
        key=lambda x: (
            x[1].get("wins", 0) / x[1].get("total", 1)
            if x[1].get("total", 0) > 0 else 0
        ),
        reverse=True,
    )
    top5 = []
    for padrao, dados in ranking_ordenado[:5]:
        total_p = dados.get("total", 0)
        wins_p = dados.get("wins", 0)
        if total_p > 0:
            top5.append({
                "padrao": padrao,
                "wins": wins_p,
                "total": total_p,
                "assertividade": round(wins_p / total_p * 100, 1),
            })

    assertividade = (
        (total_wins / total_geral * 100) if total_geral > 0 else 0.0
    )
    tie_assertividade = (
        (tie_wins / tie_total * 100) if tie_total > 0 else 0.0
    )

    return {
        "data": data.strftime("%d/%m/%Y"),
        "total_entradas": total_geral,
        "total_wins": total_wins,
        "total_loss": total_loss,
        "assertividade": round(assertividade, 1),
        "tie_sinais": tie_total,
        "tie_greens": tie_wins,
        "tie_reds": tie_loss,
        "tie_assertividade": round(tie_assertividade, 1),
        "top_padroes": top5,
    }

def formatar_resumo_telegram(resumo: Dict[str, Any]) -> str:
    """Formata o resumo em mensagem bonita para o Telegram."""
    data = resumo["data"]
    total = resumo["total_entradas"]
    wins = resumo["total_wins"]
    loss = resumo["total_loss"]
    ass = resumo["assertividade"]

    tie_sinais = resumo["tie_sinais"]
    tie_greens = resumo["tie_greens"]
    tie_reds = resumo["tie_reds"]
    tie_ass = resumo["tie_assertividade"]

    top5 = resumo["top_padroes"]

    msg = (
        f"📊 *RESUMO DIÁRIO — {data}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 *ENTRADAS GERAIS:*\n"
        f"• Total de sinais: `{total}`\n"
        f"• ✅ GREENs: `{wins}`\n"
        f"• ❌ REDs: `{loss}`\n"
        f"• 🚀 Assertividade: `{ass}%`\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🟡 *ENTRADAS DE TIE:*\n"
        f"• Total de sinais: `{tie_sinais}`\n"
        f"• ✅ GREENs: `{tie_greens}`\n"
        f"• ❌ REDs: `{tie_reds}`\n"
        f"• 🚀 Assertividade: `{tie_ass}%`\n\n"
    )

    if top5:
        msg += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        msg += "🏆 *TOP 5 PADRÕES DO DIA:*\n"
        for i, p in enumerate(top5, 1):
            msg += (
                f"{i}. `{p['padrao']}`\n"
                f"   ➔ *{p['assertividade']}%* ({p['wins']}/{p['total']})\n\n"
            )

    msg += "━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"_Gerado em {_agora().strftime('%H:%M:%S')}_"

    return msg


def enviar_resumo_diario(db, notifier) -> bool:
    """Gera e envia o resumo diário. Retorna True se conseguiu."""
    try:
        resumo = gerar_resumo_diario(db)
        msg = formatar_resumo_telegram(resumo)
        return notifier.send(msg)
    except Exception as e:
        log_terminal(f"❌ Erro ao enviar resumo: {e}", CoresTerminal.VERMELHO)
        return False


class DailyReporterThread:
    """
    Thread que envia o resumo diário às 23:59 (horário de Brasília).
    Roda em background indefinidamente.
    """

    def __init__(self, db, notifier) -> None:
        self.db = db
        self.notifier = notifier
        self.stop_event = threading.Event()
        self.thread = None

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        log_terminal("📅 DailyReporter iniciado", CoresTerminal.CIANO)

    def stop(self) -> None:
        self.stop_event.set()

    def _loop(self) -> None:
        """Loop principal — verifica a cada minuto se é hora de enviar."""
        ultimo_envio = None

        while not self.stop_event.is_set():
            agora = _agora()

            # Verifica se já enviou hoje às 23:59
            precisa_enviar = (
                agora.hour == 23
                and agora.minute == 59
                and ultimo_envio != agora.date()
            )

            if precisa_enviar:
                log_terminal("📤 Enviando resumo diário...", CoresTerminal.CIANO)
                enviar_resumo_diario(self.db, self.notifier)
                ultimo_envio = agora.date()

            # Aguarda 30 segundos
            self.stop_event.wait(30)