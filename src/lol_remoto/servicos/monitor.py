"""Mantém o `Estado` em dia com o cliente do LoL: espera o lockfile, conecta, assina os
eventos e reconecta quando o cliente fecha e abre de novo.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lol_remoto.dominio.campeoes import Catalogo
from lol_remoto.dominio.fase import Fase, fase_de
from lol_remoto.dominio.ready_check import ready_check_de
from lol_remoto.dominio.selecao import Selecao, SelecaoInvalida, selecao_de
from lol_remoto.plataforma import lockfile
from lol_remoto.plataforma.lcu import (
    EVENTOS_ASSINADOS,
    FASE,
    READY_CHECK,
    SESSAO_SELECAO,
    ErroLcu,
    Evento,
    Lcu,
    LcuHttp,
)
from lol_remoto.plataforma.lockfile import Credenciais, LockfileInvalido
from lol_remoto.servicos.estado import Estado

log = logging.getLogger(__name__)

CATALOGO = "/lol-game-data/assets/v1/champion-summary.json"
INTERVALO_LOCKFILE = 3.0  # segundos

# Fases em que a sessão da seleção interessa (ela pode chegar antes do evento de fase).
_FASES_COM_SELECAO = (Fase.PARTIDA_ENCONTRADA, Fase.SELECAO)


class Monitor:
    def __init__(
        self,
        estado: Estado,
        pasta_lol: Path,
        conectar: Callable[[Credenciais], Lcu] = LcuHttp,
        intervalo: float = INTERVALO_LOCKFILE,
        ler_credenciais: Callable[[], Credenciais | None] | None = None,
    ) -> None:
        """`ler_credenciais` substitui a leitura do lockfile (usado no `--simular`)."""
        self._estado = estado
        self._pasta_lol = pasta_lol
        self._ler_credenciais = ler_credenciais or (lambda: lockfile.ler(pasta_lol))
        self._conectar = conectar
        self._intervalo = intervalo
        self._parar = threading.Event()
        self._lcu: Lcu | None = None

    @property
    def lcu(self) -> Lcu | None:
        """Conexão atual com o cliente (None se ele estiver fechado). Usada pelas ações."""
        return self._lcu

    def encerrar(self) -> None:
        self._parar.set()
        lcu = self._lcu
        if lcu is not None:
            lcu.fechar()

    def executar(self) -> None:
        """Laço principal; rode numa thread própria. Termina com `encerrar()`."""
        avisou = False
        while not self._parar.is_set():
            try:
                credenciais = self._ler_credenciais()
            except LockfileInvalido as erro:
                log.warning("Lockfile inválido: %s", erro)
                credenciais = None
            if credenciais is None:
                if not avisou:
                    log.info("Esperando o cliente do LoL abrir (%s)", self._pasta_lol)
                    avisou = True
            else:
                avisou = False
                self._ouvir(self._conectar(credenciais))
            self._parar.wait(self._intervalo)

    def _ouvir(self, lcu: Lcu) -> None:
        try:
            eventos = lcu.eventos(EVENTOS_ASSINADOS)  # assina antes de ler o estado inicial
            self._lcu = lcu
            if self._parar.is_set():  # encerrar() pode ter vindo antes de self._lcu existir
                return
            self._carregar_estado_inicial(lcu)
            log.info("Conectado ao cliente do LoL")
            for evento in eventos:
                self._aplicar(lcu, evento)
        except (ErroLcu, OSError) as erro:  # OSError inclui ConexaoFechada
            if not self._parar.is_set():
                log.info("Conexão com o cliente do LoL encerrada: %s", erro)
        finally:
            self._lcu = None
            lcu.fechar()
            self._estado.atualizar(
                conectado=False, fase=Fase.NENHUMA, selecao=None, ready_check=None
            )

    def _carregar_estado_inicial(self, lcu: Lcu) -> None:
        try:
            self._estado.catalogo = Catalogo.de_json(lcu.get(CATALOGO))
        except ErroLcu as erro:
            log.warning("Não foi possível carregar os campeões: %s", erro)
        fase = fase_de(lcu.get(FASE))
        selecao = self._ler_selecao(lcu.get(SESSAO_SELECAO)) if fase is Fase.SELECAO else None
        ready_check = (
            ready_check_de(lcu.get(READY_CHECK)) if fase is Fase.PARTIDA_ENCONTRADA else None
        )
        log.info("Fase: %s", fase.value)
        self._estado.atualizar(conectado=True, fase=fase, selecao=selecao, ready_check=ready_check)

    @staticmethod
    def _ler_selecao(dados: Any) -> Selecao | None:
        if dados is None:
            return None
        try:
            return selecao_de(dados)
        except SelecaoInvalida as erro:
            log.warning("Sessão da seleção em formato inesperado: %s", erro)
            return None

    def _aplicar(self, lcu: Lcu, evento: Evento) -> None:
        apagado = evento.tipo == "Delete"
        if evento.uri == FASE:
            fase = fase_de(evento.dados)
            log.info("Fase: %s", evento.dados)
            mudancas: dict[str, Any] = {"fase": fase}
            if fase is not Fase.SELECAO:
                mudancas["selecao"] = None
            elif self._estado.atual.selecao is None:
                mudancas["selecao"] = self._ler_selecao(lcu.get(SESSAO_SELECAO))
            if fase is not Fase.PARTIDA_ENCONTRADA:
                mudancas["ready_check"] = None
            elif self._estado.atual.ready_check is None:
                # Na fila de verdade há dados de ready check; na personalizada, não (404).
                mudancas["ready_check"] = ready_check_de(lcu.get(READY_CHECK))
        elif evento.uri == SESSAO_SELECAO:
            if self._estado.atual.fase not in _FASES_COM_SELECAO:
                return  # sobra de uma seleção que já acabou
            mudancas = {"selecao": None if apagado else self._ler_selecao(evento.dados)}
        elif evento.uri == READY_CHECK:
            if apagado and self._estado.atual.fase is Fase.PARTIDA_ENCONTRADA:
                # Guarda a última resposta até a fase mudar (é ela que diz se você saiu da
                # fila sem aceitar); a mudança de fase limpa o ready check logo depois.
                return
            mudancas = {"ready_check": None if apagado else ready_check_de(evento.dados)}
        else:
            return
        self._estado.atualizar(**mudancas)
