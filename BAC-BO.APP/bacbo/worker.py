"""Motor do robô — recebe client/notifier/db por injeção."""
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .analysis import analisar_multi_amostra, processar_filtro_digitado
from .config import BacBoConfig, CoresTerminal, log_terminal
from .risk import Banca, StopRules, sugerir_unidade
from .strategies import (
    aplicar_confluencia,
    sinal_espelho,
    sinal_ponto_regressao,
    sinal_streak_fade,
)


class BacBoWorker:
    MAX_LOGS = 100
    MAX_HISTORICO = 50
    MAX_CICLO = 500

    def __init__(self, client, notifier, db, config: Optional[BacBoConfig] = None) -> None:
        self.client = client
        self.notifier = notifier
        self.db = db
        self.config = config or BacBoConfig()

        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

        self.banca = Banca(
            inicial=self.config.banca_inicial,
            aposta_base=self.config.aposta_base,
            multiplicador_gale=self.config.multiplicador_gale,
        )
        self.stop_rules = StopRules(
            stop_loss_consecutivo=self.config.stop_loss_consecutivo,
            stop_drawdown_unidades=self.config.stop_drawdown_unidades,
            stop_win_sessao=self.config.stop_win_sessao,
            cooldown_apos_loss=self.config.cooldown_apos_loss,
            max_entradas_hora=self.config.max_entradas_hora,
        )
        self.timestamps_entradas: List[datetime] = []
        self.motivo_bloqueio: Optional[str] = None

        self.state: Dict[str, Any] = {
            "bot_rodando": False,
            "sinal_ativo": False,
            "sugestao_atual": None,
            "tentativa": 0,
            "ultimo_uuid_processado": None,
            "ultimo_uuid_sinal_enviado": None,
            "ultimo_uuid_resultado_verificado": None,
            "historico_sinais": [],
            "historico_ciclo": [],
            "log_eventos": [],
            "padrao_selecionado": None,
            "ranking_padroes": {},
            "PADROES_MANUAIS_COMPOSTOS": {},
            "sinal_meta": None,
        }
        self.state["PADROES_MANUAIS_COMPOSTOS"] = self.db.carregar_padroes()
        self.state["ranking_padroes"] = self.db.carregar_ranking()

    # ------------------------------------------------------------------ life
    def start(self) -> None:
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.state["bot_rodando"] = True
                return
            self.state["bot_rodando"] = True
            self.stop_event.clear()
            self.thread = threading.Thread(target=self._loop, daemon=True)
            self.thread.start()
        self._log("▶️ Motor iniciado.", CoresTerminal.VERDE)

    def stop(self) -> None:
        with self.lock:
            self.state["bot_rodando"] = False
            self.stop_event.set()
        self._log("⏸️ Motor pausado.", CoresTerminal.AMARELO)

    def update_config(self, **kwargs: Any) -> None:
        with self.lock:
            for k, v in kwargs.items():
                if hasattr(self.config, k):
                    setattr(self.config, k, v)

    def get_state(self) -> Dict[str, Any]:
        with self.lock:
            return {
                **self.state,
                "historico_sinais": list(self.state["historico_sinais"]),
                "historico_ciclo": list(self.state["historico_ciclo"]),
                "log_eventos": list(self.state["log_eventos"]),
                "ranking_padroes": {k: dict(v) for k, v in self.state["ranking_padroes"].items()},
                "PADROES_MANUAIS_COMPOSTOS": {
                    k: dict(v) for k, v in self.state["PADROES_MANUAIS_COMPOSTOS"].items()
                },
                "banca": {
                    "saldo": self.banca.saldo,
                    "inicial": self.banca.inicial,
                    "pico": self.banca.pico,
                    "drawdown_max": self.banca.drawdown_max,
                    "retorno_pct": self.banca.retorno_pct,
                },
                "motivo_bloqueio": self.motivo_bloqueio,
                "rodadas_persistidas": self.db.total_rodadas(self.config.mesa_id),
            }

    def _log(self, msg: str, cor: str = CoresTerminal.RESET) -> None:
        log_terminal(msg, cor)
        horario = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.state["log_eventos"].insert(0, f"[{horario}] {msg}")
            if len(self.state["log_eventos"]) > self.MAX_LOGS:
                self.state["log_eventos"].pop()

    # ------------------------------------------------------------- padrões
    def add_padrao(self, nome: str, padrao: List[str], sugestao: str) -> None:
        with self.lock:
            self.state["PADROES_MANUAIS_COMPOSTOS"][nome] = {
                "padrao": padrao, "sugestao": sugestao, "ativo": True,
            }
        self.db.salvar_padrao(nome, padrao, sugestao)
        self._log(f"📌 Padrão '{nome}' salvo.", CoresTerminal.VERDE)

    def remover_padrao(self, nome: str) -> None:
        with self.lock:
            self.state["PADROES_MANUAIS_COMPOSTOS"].pop(nome, None)
        self.db.remover_padrao(nome)
        self._log(f"🗑️ Padrão '{nome}' removido.", CoresTerminal.AMARELO)

    # --------------------------------------------------------------- loop
    def _loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._processar_rodada()
            except Exception as e:
                self._log(f"❌ Erro no loop: {str(e)[:120]}", CoresTerminal.VERMELHO)
            self.stop_event.wait(self.config.intervalo_verificacao)

    def _dentro_janela(self) -> bool:
        agora = datetime.now()
        if not self.config.operar_fim_de_semana and agora.weekday() >= 5:
            return False
        return self.config.hora_inicio <= agora.hour <= self.config.hora_fim

    def entradas_ultima_hora(self) -> int:
        corte = datetime.now() - timedelta(hours=1)
        self.timestamps_entradas = [t for t in self.timestamps_entradas if t >= corte]
        return len(self.timestamps_entradas)

    def _persistir_rodadas(self, mesa_id, uuids, cores, pontos) -> int:
        rodadas = [
            {"uuid": u, "cor": c, "ponto": p}
            for u, c, p in zip(uuids, cores, pontos)
        ]
        return self.db.salvar_rodadas(mesa_id, rodadas)

    def _processar_rodada(self) -> None:
        cores, uuids, pontos, compostos, exibicao = self.client.buscar_historico(
            mesa_id=self.config.mesa_id,
            timezone=self.config.timezone,
            limite=self.config.limite_rodadas,
        )
        if not uuids:
            return

        novos = self._persistir_rodadas(self.config.mesa_id, uuids, cores, pontos)
        if novos:
            self._log(f"💾 {novos} rodada(s) persistida(s)", CoresTerminal.CIANO)

        uuid_atual = uuids[-1]
        nova = uuid_atual != self.state["ultimo_uuid_processado"]
        if nova:
            with self.lock:
                self.state["ultimo_uuid_processado"] = uuid_atual
            self._log(f"Nova rodada: {exibicao[-1]}", CoresTerminal.AZUL)

        if not self.state["bot_rodando"] or not nova:
            return

        if self.state["sinal_ativo"]:
            self._verificar_resultado(cores[-1], pontos[-1], uuid_atual)

        if not self.state["sinal_ativo"]:
            if not self._dentro_janela():
                self.motivo_bloqueio = "⏱️ Fora da janela de operação"
                return
            motivo = self.stop_rules.avaliar(
                self.state["historico_sinais"], self.banca, self.entradas_ultima_hora(),
            )
            if motivo:
                if motivo != self.motivo_bloqueio:
                    self._log(motivo, CoresTerminal.VERMELHO)
                    self.notifier.send(f"🛑 *BLOQUEIO ATIVO*\n{motivo}")
                    self.motivo_bloqueio = motivo
                return
            if self.motivo_bloqueio:
                self.notifier.send("✅ *BOT LIBERADO* — condições normalizadas")
                self.motivo_bloqueio = None

            cooldown = self.stop_rules.precisa_cooldown(self.state["historico_sinais"])
            if cooldown > 0:
                self._log(f"⏳ Cooldown: {cooldown} rodada(s)", CoresTerminal.AMARELO)
                return

            self._buscar_e_enviar_sinal(cores, pontos, compostos, uuid_atual)

    def _detectar_sinais(self, cores, pontos, compostos) -> Optional[tuple]:
        candidatos: List[tuple] = []

        sug, p30, p50, desc = analisar_multi_amostra(
            cores, compostos,
            self.state["PADROES_MANUAIS_COMPOSTOS"],
            self.config.tamanho_padrao,
            self.config.sensibilidade_minima,
        )
        if sug:
            conf = max(p30, p50)
            candidatos.append((sug, conf, "principal", desc or ""))

        if self.config.usar_streak_fade:
            s = sinal_streak_fade(cores, self.config.streak_min)
            if s:
                candidatos.append(s)

        if self.config.usar_ponto_regressao:
            s = sinal_ponto_regressao(cores, pontos)
            if s:
                candidatos.append(s)

        if self.config.usar_espelho:
            s = sinal_espelho(cores)
            if s:
                candidatos.append(s)

        if not candidatos:
            return None

        if self.config.usar_confluencia and len(candidatos) >= 2:
            consolidado = aplicar_confluencia(candidatos, self.config.confluencia_min_ratio)
            if consolidado:
                return consolidado
            return None

        return max(candidatos, key=lambda x: x[1])

    def _buscar_e_enviar_sinal(self, cores, pontos, compostos, uuid_atual) -> None:
        sinal = self._detectar_sinais(cores, pontos, compostos)
        if not sinal:
            return
        if self.state["ultimo_uuid_sinal_enviado"] == uuid_atual:
            return

        sugestao, confianca, fonte, descricao = sinal
        nome = {"🔴": "🔴 BANKER", "🔵": "🔵 PLAYER", "🟡": "🟡 TIE"}[sugestao]
        unidade = sugerir_unidade(confianca, odd=self.config.odd_alvo) if self.config.usar_kelly else 1.0

        with self.lock:
            self.state["sinal_ativo"] = True
            self.state["sugestao_atual"] = sugestao
            self.state["tentativa"] = 1
            self.state["padrao_selecionado"] = descricao or fonte
            self.state["ultimo_uuid_sinal_enviado"] = uuid_atual
            self.state["ultimo_uuid_resultado_verificado"] = None
            self.state["sinal_meta"] = {
                "fonte": fonte, "confianca": confianca, "unidade": unidade,
            }
        self.timestamps_entradas.append(datetime.now())

        msg = (
            "🤖 *BAC BO PRO - SINAL VIP*\n\n"
            f"🎯 *ENTRADA:* {nome}\n"
            "🛡️ *PROTEÇÃO:* 🟡 TIE\n"
            f"🔄 *GESTÃO:* Até Gale {self.config.max_gale}\n\n"
            f"🔍 *FONTE:* `{fonte}`\n"
            f"📋 *PADRÃO:*\n`{descricao}`\n\n"
            f"📊 *Confiança:* `{confianca:.1f}%`\n"
            f"💰 *Unidade:* `{unidade:.2f}u`\n\n"
            f"💼 *Banca:* `{self.banca.saldo:.2f}u` "
            f"({self.banca.retorno_pct:+.1f}%)\n\n"
            f"{self._formatar_ranking_telegram()}\n\n"
            f"{self._obter_texto_placar()}"
        )
        if self.notifier.send(msg):
            self._log(f"SINAL: {nome} | {fonte} | conf={confianca:.1f}%", CoresTerminal.VERDE)

    def _verificar_resultado(self, resultado: str, ponto: Optional[int], uuid_atual: str) -> None:
        if uuid_atual == self.state["ultimo_uuid_sinal_enviado"]:
            return
        if uuid_atual == self.state["ultimo_uuid_resultado_verificado"]:
            return

        with self.lock:
            self.state["ultimo_uuid_resultado_verificado"] = uuid_atual

        esperado = self.state["sugestao_atual"]
        padrao_usado = self.state["padrao_selecionado"]
        acertou = resultado == esperado or resultado == "🟡"
        txt = f"{resultado} ({ponto})" if ponto is not None else resultado

        if acertou:
            if resultado == "🟡":
                tipo, header = "WIN_TIE", "🟡 *WIN_TIE (Proteção)*"
            elif self.state["tentativa"] == 1:
                tipo, header = "WIN", "✅ *WIN DIRETO!* 🎯"
            else:
                tipo, header = "WIN_G1", "✅ *WIN NO GALE 1!* 🎯"
            self._registrar_resultado(tipo, padrao_usado)
            self.notifier.send(f"{header}\nResultado: `{txt}`\n\n{self._obter_texto_placar()}")
            with self.lock:
                self.state["sinal_ativo"] = False
                self.state["padrao_selecionado"] = None

        elif self.state["tentativa"] == 1:
            with self.lock:
                self.state["tentativa"] = 2
            self.notifier.send(f"⚠️ *NÃO BATEU 1ª → GALE 1*\nMantém: {esperado}")

        else:
            self._registrar_resultado("LOSS", padrao_usado)
            self.notifier.send(
                f"❌ *LOSS CONFIRMADO*\nResultado: `{txt}`\n\n{self._obter_texto_placar()}"
            )
            with self.lock:
                self.state["sinal_ativo"] = False
                self.state["padrao_selecionado"] = None

    # ------------------------------------------------------------- ranking
    def _registrar_resultado(self, resultado: str, padrao: Optional[str]) -> None:
        with self.lock:
            self.state["historico_sinais"].append(resultado)
            if len(self.state["historico_sinais"]) > self.MAX_HISTORICO:
                self.state["historico_sinais"].pop(0)
            self.state["historico_ciclo"].append(resultado)
            if len(self.state["historico_ciclo"]) > self.MAX_CICLO:
                self.state["historico_ciclo"].pop(0)
            if padrao:
                d = self.state["ranking_padroes"].setdefault(padrao, {"wins": 0, "total": 0})
                d["total"] += 1
                if resultado in ("WIN", "WIN_G1", "WIN_TIE"):
                    d["wins"] += 1

        self.banca.registrar(resultado)

        if padrao:
            venceu = resultado in ("WIN", "WIN_G1", "WIN_TIE")
            self.db.atualizar_ranking(padrao, venceu)
            agora = datetime.now()
            self.db.registrar_contexto(padrao, agora.hour, agora.weekday(), venceu)

    def calcular_ranking(self) -> List[Dict[str, Any]]:
        min_ops = self.config.min_operacoes_ranking
        ranking = []
        for padrao, d in self.state["ranking_padroes"].items():
            if d["total"] >= min_ops:
                ass = (d["wins"] / d["total"]) * 100
                ranking.append({
                    "padrao": padrao, "acertos": d["wins"],
                    "total": d["total"], "assertividade": ass,
                })
        return sorted(ranking, key=lambda x: (x["assertividade"], x["total"]), reverse=True)

    def _formatar_ranking_telegram(self) -> str:
        r = self.calcular_ranking()
        if not r:
            return "🏆 *Ranking:* Aguardando amostragem mínima."
        linhas = ["🏆 *PADRÕES MAIS ASSERTIVOS:*"]
        for i, it in enumerate(r[:5], 1):
            linhas.append(
                f"{i}. `{it['padrao']}` → *{it['assertividade']:.1f}%* "
                f"({it['acertos']}/{it['total']})"
            )
        return "\n".join(linhas)

    def _obter_texto_placar(self) -> str:
        h = self.state["historico_sinais"]
        if not h:
            return "📊 *PLACAR:* Aguardando..."
        t = len(h)
        wd, wg, wt, ls = h.count("WIN"), h.count("WIN_G1"), h.count("WIN_TIE"), h.count("LOSS")
        ass = ((wd + wg + wt) / t * 100) if t else 0
        return (
            f"📊 *PLACAR ({t}):*\n"
            f"🎯 Win: `{wd}` | 🔄 G1: `{wg}` | 🟡 Tie: `{wt}` | ❌ Loss: `{ls}`\n"
            f"🚀 *Assertividade:* `{ass:.1f}%`\n"
            f"💼 *Banca:* `{self.banca.saldo:.2f}u` "
            f"({self.banca.retorno_pct:+.1f}%) | "
            f"DD máx: `{self.banca.drawdown_max:.2f}u`"
        )

    # --------------------------------------------------------- relatório
    def gerar_relatorio(self, limite_rodadas: int, texto_filtro: str) -> Tuple[bool, str]:
        entradas_f, pontos_f = processar_filtro_digitado(texto_filtro)
        cores, uuids, pontos, compostos, _ = self.client.buscar_historico(
            mesa_id=self.config.mesa_id,
            timezone=self.config.timezone,
            limite=self.config.limite_rodadas,
        )
        if not cores or len(cores) < 10:
            return False, "⚠️ Histórico insuficiente."

        amostra_cores = cores[-limite_rodadas:]
        amostra_pontos = pontos[-limite_rodadas:]
        amostra_compostos = compostos[-limite_rodadas:]

        idx_tie = [i for i, c in enumerate(amostra_cores) if c == "🟡"]
        n_tie = len(idx_tie)
        if n_tie >= 2:
            gaps = [idx_tie[i] - idx_tie[i - 1] for i in range(1, n_tie)]
            media = sum(gaps) / len(gaps)
            txt_tie = (
                f"🟡 *TIE:* `{n_tie}x` | ⏱️ *Média:* a cada `{media:.1f}` rodadas "
                f"(~`{(media * 30) / 60:.1f}` min)"
            )
        elif n_tie == 1:
            txt_tie = "🟡 *TIE:* Apenas `1x`."
        else:
            txt_tie = f"🟡 *TIE:* Nenhum nas últimas `{len(amostra_cores)}` rodadas."

        contagem: Dict[str, Dict[str, Any]] = {}

        if pontos_f:
            pts = [int(p) for p in pontos_f]
            cores_alvo = []
            if "🔴 BANKER" in entradas_f:
                cores_alvo.append("🔴")
            if "🔵 PLAYER" in entradas_f:
                cores_alvo.append("🔵")
            if "🟡 TIE" in entradas_f:
                cores_alvo.append("🟡")
            if not cores_alvo:
                cores_alvo = ["🔴", "🔵", "🟡"]

            for i in range(len(amostra_cores) - 1):
                if amostra_pontos[i] not in pts or amostra_cores[i] not in cores_alvo:
                    continue
                chave = f"Mão Gatilho: {amostra_cores[i]} ({amostra_pontos[i]})"
                alvo = cores_alvo[0] if len(cores_alvo) == 1 else amostra_cores[i]
                nome_alvo = {"🔴": "🔴 BANKER", "🔵": "🔵 PLAYER", "🟡": "🟡 TIE"}[alvo]
                d = contagem.setdefault(
                    chave,
                    {"total": 0, "acertos_direto": 0, "acertos_gale": 0, "sugestao": nome_alvo},
                )
                d["total"] += 1
                r1 = amostra_cores[i + 1]
                if r1 == alvo or r1 == "🟡":
                    d["acertos_direto"] += 1
                elif i + 2 < len(amostra_cores):
                    r2 = amostra_cores[i + 2]
                    if r2 == alvo or r2 == "🟡":
                        d["acertos_gale"] += 1
        else:
            for i in range(self.config.tamanho_padrao, len(amostra_cores) - 1):
                s, _, _, p = analisar_multi_amostra(
                    amostra_cores[:i], amostra_compostos[:i],
                    self.state["PADROES_MANUAIS_COMPOSTOS"],
                    self.config.tamanho_padrao,
                    self.config.sensibilidade_minima,
                )
                if not s or not p:
                    continue
                nome = {"🔴": "🔴 BANKER", "🔵": "🔵 PLAYER", "🟡": "🟡 TIE"}[s]
                if entradas_f and nome not in entradas_f:
                    continue
                d = contagem.setdefault(
                    p, {"total": 0, "acertos_direto": 0, "acertos_gale": 0, "sugestao": nome}
                )
                d["total"] += 1
                r1 = amostra_cores[i]
                if r1 == s or r1 == "🟡":
                    d["acertos_direto"] += 1
                elif i + 1 < len(amostra_cores):
                    r2 = amostra_cores[i + 1]
                    if r2 == s or r2 == "🟡":
                        d["acertos_gale"] += 1

        if not contagem:
            return False, f"⚠️ Nenhum padrão atendeu aos critérios ('{texto_filtro}')."

        tot_s = sum(p["total"] for p in contagem.values())
        tot_d = sum(p["acertos_direto"] for p in contagem.values())
        tot_g = sum(p["acertos_gale"] for p in contagem.values())
        taxa = ((tot_d + tot_g) / tot_s * 100) if tot_s else 0.0
        filtro_txt = f"\n🎯 *Filtros:* `{texto_filtro}`" if texto_filtro else ""

        msg = (
            "📊 *RELATÓRIO DE ASSERTIVIDADE*\n"
            f"🆔 `{self.config.mesa_id[:8]}...` | 🔄 `{len(amostra_cores)}` rodadas{filtro_txt}\n"
            "-----------------------------------\n"
            f"{txt_tie}\n"
            "-----------------------------------\n"
            f"🎯 Ocorrências: `{tot_s}` | 🚀 Assertividade: `{taxa:.1f}%`\n"
            f"🎯 Win Direto: `{tot_d}` | 🔄 Win Gale 1: `{tot_g}`\n"
            "-----------------------------------\n"
            "🏆 *OCORRÊNCIAS:*\n"
        )
        ordenados = sorted(
            contagem.items(),
            key=lambda x: ((x[1]["acertos_direto"] + x[1]["acertos_gale"]) / x[1]["total"])
            if x[1]["total"] else 0,
            reverse=True,
        )
        for p, info in ordenados[:5]:
            tot = info["total"]
            ac = info["acertos_direto"] + info["acertos_gale"]
            t = (ac / tot * 100) if tot else 0.0
            msg += f"\n• `{p}`\n  ➔ Alvo: *{info['sugestao']}* | `{t:.1f}%` ({ac}/{tot})\n"
        msg += "\n⚠️ *Relatório estatístico gerado sob demanda.*"

        if self.notifier.send(msg):
            return True, "✅ Relatório enviado!"
        return False, "❌ Falha ao enviar."