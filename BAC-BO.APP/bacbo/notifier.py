"""Envio de mensagens para o Telegram."""
import requests

from .config import CoresTerminal, build_http_session, log_terminal


class TelegramNotifier:
    MAX_LEN = 4000

    def __init__(
        self,
        token: str,
        chat_id: str,
        session: requests.Session = None,
        timeout: int = 5,
    ):
        self.token = token
        self.chat_id = chat_id
        self.session = session or build_http_session()
        self.timeout = timeout

    def send(self, texto: str) -> bool:
        if not texto or not self.token or not self.chat_id:
            return False

        if len(texto) > self.MAX_LEN:
            texto = texto[: self.MAX_LEN - 100] + "\n\n⚠️ _(mensagem truncada)_"

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": texto,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return True
        except Exception as e:
            log_terminal(f"❌ Falha no Telegram: {str(e)[:80]}", CoresTerminal.VERMELHO)
            return False