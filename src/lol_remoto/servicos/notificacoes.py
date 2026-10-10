"""Transforma avisos do domínio em notificações push, só com o modo ausente ligado.

O envio roda numa thread própria: uma rede lenta não atrasa a leitura dos eventos da LCU.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

from lol_remoto.dominio.avisos import Aviso, TipoAviso, avisos
from lol_remoto.plataforma.ntfy import (
    PRIORIDADE_MAXIMA,
    ErroNotificacao,
    Notificacao,
    Notificador,
)
from lol_remoto.servicos.estado import Estado, Retrato

log = logging.getLogger(__name__)

_TEXTOS: dict[TipoAviso, tuple[str, str, int, str]] = {
    # tipo: (título, mensagem, prioridade, tag/emoji do ntfy)
    TipoAviso.PARTIDA_ENCONTRADA: (
        "Partida encontrada!",
        "Você tem uns 10 segundos para aceitar.",
        PRIORIDADE_MAXIMA,
        "rotating_light",
    ),
    TipoAviso.PARTIDA_RECUSADA: (
        "Partida recusada",
        "Alguém recusou. Você voltou para a fila.",
        4,
        "hourglass_flowing_sand",
    ),
    TipoAviso.SUA_VEZ_BANIR: ("Sua vez de banir!", "", PRIORIDADE_MAXIMA, "no_entry"),
    TipoAviso.SUA_VEZ_ESCOLHER: ("Sua vez de escolher!", "", PRIORIDADE_MAXIMA, "crossed_swords"),
    TipoAviso.DODGE: ("Alguém deu dodge", "Você voltou para a fila.", 4, "warning"),
    TipoAviso.SELECAO_CANCELADA: (
        "Seleção cancelada",
        "A seleção de campeões acabou sem partida.",
        4,
        "x",
    ),
    TipoAviso.CARREGANDO: (
        "Partida carregando",
        "Volta pro PC! O modo ausente foi desligado.",
        PRIORIDADE_MAXIMA,
        "video_game",
    ),
}


class ServicoNotificacoes:
    def __init__(
        self,
        estado: Estado,
        notificador: Notificador,
        endereco: Callable[[], str | None] = lambda: None,
    ) -> None:
        """`endereco` dá a URL da página no celular (link da notificação), se conhecida."""
        self._estado = estado
        self._notificador = notificador
        self._endereco = endereco
        self._fila: queue.Queue[Notificacao | None] = queue.Queue()
        self._thread = threading.Thread(target=self._enviar_em_ordem, name="ntfy", daemon=True)
        self._thread.start()
        estado.assinar(self._ao_mudar)

    def _ao_mudar(self, anterior: Retrato, atual: Retrato) -> None:
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
        titulo, mensagem, prioridade, tag = _TEXTOS[aviso.tipo]
        if aviso.tipo in (TipoAviso.SUA_VEZ_BANIR, TipoAviso.SUA_VEZ_ESCOLHER):
            mensagem = self._mensagem_da_vez(aviso, retrato)
        return Notificacao(
            titulo, mensagem, prioridade=prioridade, tags=(tag,), link=self._endereco()
        )

    def _mensagem_da_vez(self, aviso: Aviso, retrato: Retrato) -> str:
        partes = []
        if aviso.segundos is not None:
            partes.append(f"{aviso.segundos} s restantes.")
        eu = retrato.selecao.eu if retrato.selecao else None
        intencao = self._estado.catalogo.nome(eu.intencao) if eu and eu.intencao else None
        if aviso.tipo is TipoAviso.SUA_VEZ_ESCOLHER and intencao:
            partes.append(f"Sua intenção: {intencao}.")
        partes.append("Toque para abrir.")
        return " ".join(partes)

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
