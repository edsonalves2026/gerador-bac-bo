"""Configurações, cores de terminal, logs e sessão HTTP."""

from dataclasses import dataclass
from datetime import datetime

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class CoresTerminal:
    AZUL = "\033[94m"
    VERDE = "\033[92m"
    VERMELHO = "\033[91m"
    AMARELO = "\033[93m"
    CIANO = "\033[96m"
    RESET = "\033[0m"


def log_terminal(mensagem: str, cor: str = CoresTerminal.RESET) -> str:
    horario = datetime.now().strftime("%H:%M:%S")
    linha = f"{cor}[{horario}] {mensagem}{CoresTerminal.RESET}"
    print(linha, flush=True)
    return linha


@dataclass
class BacBoConfig:
    # Mesa / API
    mesa_id: str = "cc71e81d-8b56-4868-91c7-7224be543dce"
    timezone: str = "America/Sao_Paulo"
    limite_rodadas: int = 300   # ← era 200 — agora 300 (meio entre 200-500)
    timeout_api: int = 10
    timeout_telegram: int = 5

    # API Fallback
    usar_api_fallback: bool = True
    max_falhas_antes_de_trocar: int = 3
    url_api_fallback: str = "https://api.historicbet.com/results"

    # Cookies da HistoricBet (capturados do navegador)
    historicbet_cookies: str = ""

    # Loop
    intervalo_verificacao: int = 8

    # Estratégia base
    tamanho_padrao: int = 3
    sensibilidade_minima: float = 65.0
    min_operacoes_ranking: int = 4
    max_gale: int = 1

    # Estratégias extras
    usar_streak_fade: bool = True
    streak_min: int = 4
    usar_ponto_regressao: bool = True
    usar_espelho: bool = False
    usar_confluencia: bool = False
    confluencia_min_ratio: float = 0.66

    # =========================================================================
    # NOVOS DETECTORES (Etapa 2 - ainda com default False para segurança)
    # =========================================================================
    usar_sanduiche: bool = False
    usar_repeticao_numerica: bool = False
    usar_ciclo_curto: bool = False
    usar_zona_tie: bool = False
    usar_forca_lado: bool = False
    usar_tie_intervalo: bool = True

    # =========================================================================
    # PRIORIZAÇÃO POR CONFIANÇA (Etapa 1)
    # =========================================================================
    confianca_minima_sinal: float = 70.0
    priorizar_alta_confianca: bool = True

    # Risco
    banca_inicial: float = 100.0
    aposta_base: float = 1.0
    multiplicador_gale: float = 2.0
    usar_kelly: bool = True
    kelly_fracao: float = 0.25
    odd_alvo: float = 1.95

    # Stop rules
    stop_loss_consecutivo: int = 3
    stop_drawdown_unidades: float = 5.0
    stop_win_sessao: float = 10.0
    cooldown_apos_loss: int = 2
    max_entradas_hora: int = 20
    usar_gestao_risco: bool = False

    # Janela operacional
    hora_inicio: int = 10
    hora_fim: int = 23
    operar_fim_de_semana: bool = True


def build_http_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
    )
    return session