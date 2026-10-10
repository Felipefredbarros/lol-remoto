"""Transforma avisos do domínio em notificações push, só com o modo ausente ligado.

O envio roda numa thread própria: uma rede lenta não atrasa a leitura dos eventos da LCU.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import replace

from lol_remoto.dominio.avisos import Aviso, TipoAviso, avisos
from lol_remoto.dominio.fase import Fase
from lol_remoto.plataforma.ntfy import BotaoHttp, ErroNotificacao, Notificacao, Notificador
from lol_remoto.servicos import mensagens
from lol_remoto.servicos.estado import Estado, Retrato
from lol_remoto.servicos.tokens import ServicoTokens

log = logging.getLogger(__name__)


class ServicoNotificacoes:
    def __init__(
        self,
        estado: Estado,
        notificador: Notificador,
        endereco: Callable[[], str | None] = lambda: None,
        tokens: ServicoTokens | None = None,
    ) -> None:
        """`endereco` dá a URL da página no celular, se conhecida. Com ela e `tokens`, a
        partida encontrada ganha os botões Aceitar/Recusar (docs/decisoes/0005).
        """
        self._estado = estado
        self._notificador = notificador
        self._endereco = endereco
        self._tokens = tokens
        self._fila: queue.Queue[Notificacao | None] = queue.Queue()
        self._thread = threading.Thread(target=self._enviar_em_ordem, name="ntfy", daemon=True)
        self._thread.start()
        estado.assinar(self._ao_mudar)

    def _ao_mudar(self, anterior: Retrato, atual: Retrato) -> None:
        if self._tokens and atual.fase is not Fase.PARTIDA_ENCONTRADA:
            self._tokens.invalidar_todos()  # botões de uma partida que já passou
        if atual.ausente and not anterior.ausente:
            self._enfileirar(
                Notificacao(
                    "Modo ausente ligado",
                    "Vou te avisar quando a fila estourar ou for sua vez.",
                    prioridade=2,
                    tags=("bell",),
                    link=self._endereco(),
                )
            )
        # Só transições vistas com o cliente conectado: conectar no meio de uma seleção ou
        # o cliente fechar não são "dodge" nem "seleção cancelada".
        if not (anterior.conectado and atual.conectado):
            return
        for aviso in avisos(anterior.momento, atual.momento):
            log.info("Aviso: %s", aviso.tipo.value)
            if atual.ausente:
                self._enfileirar(self.montar(aviso, atual))
            if aviso.tipo is TipoAviso.CARREGANDO and atual.ausente:
                self._estado.definir_ausente(False)  # dentro da partida, nada de push

    def montar(self, aviso: Aviso, retrato: Retrato) -> Notificacao:
        endereco = self._endereco()
        notificacao = mensagens.montar(aviso, retrato.selecao, self._estado.catalogo, endereco)
        if aviso.tipo is TipoAviso.PARTIDA_ENCONTRADA and endereco and self._tokens:
            token = self._tokens.gerar()  # o mesmo vale para os dois botões, uma vez só
            notificacao = replace(
                notificacao,
                botoes=(
                    BotaoHttp("Aceitar", f"{endereco}api/ready-check/aceitar", {"token": token}),
                    BotaoHttp("Recusar", f"{endereco}api/ready-check/recusar", {"token": token}),
                ),
            )
        return notificacao

    def _enfileirar(self, notificacao: Notificacao) -> None:
        self._fila.put(notificacao)

    def _enviar_em_ordem(self) -> None:
        while True:
            notificacao = self._fila.get()
            try:
                if notificacao is None:
                    return
                self._notificador.enviar(notificacao)
            except ErroNotificacao as erro:
                log.warning("Notificação não enviada (%s): %s", notificacao.titulo, erro)
            except Exception:  # a thread de envio não pode morrer
                log.exception("Erro inesperado ao enviar notificação")
            finally:
                self._fila.task_done()

    def aguardar_envios(self) -> None:
        """Bloqueia até a fila esvaziar (testes e encerramento)."""
        self._fila.join()

    def encerrar(self) -> None:
        self._fila.put(None)
        self._thread.join(timeout=5)
