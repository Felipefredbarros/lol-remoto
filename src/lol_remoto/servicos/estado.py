"""Estado atual do cliente do LoL e do app: o ponto de encontro entre monitor, API e avisos.

O monitor escreve; a API, o SSE e as notificações leem. Cada mudança gera um `Retrato`
novo (imutável) com `versao` maior, e os ouvintes recebem o par (anterior, novo).
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, replace

from lol_remoto.dominio.avisos import Momento
from lol_remoto.dominio.campeoes import Catalogo
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.ready_check import ReadyCheck
from lol_remoto.dominio.selecao import Selecao

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Retrato:
    versao: int = 0
    conectado: bool = False  # conectado ao cliente do LoL
    fase: Fase = Fase.NENHUMA
    selecao: Selecao | None = None
    selecao_recebida_em: float = 0.0  # relógio monotônico; base para o timer
    ready_check: ReadyCheck | None = None
    ready_check_recebido_em: float = 0.0
    ausente: bool = False  # modo ausente: as notificações só saem com ele ligado

    @property
    def momento(self) -> Momento:
        return Momento(self.fase, self.selecao, self.ready_check)


Ouvinte = Callable[[Retrato, Retrato], None]


class Estado:
    def __init__(self, ausente: bool = False, relogio: Callable[[], float] = time.monotonic):
        self._retrato = Retrato(ausente=ausente)
        self._condicao = threading.Condition()
        self._ouvintes: list[Ouvinte] = []
        self._relogio = relogio
        self.catalogo = Catalogo([])  # recarregado a cada conexão com o cliente

    @property
    def atual(self) -> Retrato:
        with self._condicao:
            return self._retrato

    def agora(self) -> float:
        return self._relogio()

    def assinar(self, ouvinte: Ouvinte) -> None:
        self._ouvintes.append(ouvinte)

    def atualizar(self, **mudancas: object) -> Retrato:
        """Aplica as mudanças e avisa os ouvintes. Sem mudança real, não faz nada."""
        with self._condicao:
            anterior = self._retrato
            if "selecao" in mudancas:
                mudancas.setdefault("selecao_recebida_em", self._relogio())
            if "ready_check" in mudancas:
                mudancas.setdefault("ready_check_recebido_em", self._relogio())
            candidato = replace(anterior, **mudancas)  # type: ignore[arg-type]
            if _iguais(candidato, anterior):
                return anterior
            novo = replace(candidato, versao=anterior.versao + 1)
            self._retrato = novo
            self._condicao.notify_all()
        # Fora da trava: um ouvinte pode chamar `atualizar` de novo (ex.: desligar o modo
        # ausente quando a partida carrega).
        for ouvinte in list(self._ouvintes):
            try:
                ouvinte(anterior, novo)
            except Exception:
                log.exception("Erro num ouvinte do estado")
        return novo

    def definir_ausente(self, ativo: bool) -> Retrato:
        log.info("Modo ausente %s", "ligado" if ativo else "desligado")
        return self.atualizar(ausente=bool(ativo))

    def esperar_mudanca(self, versao_conhecida: int, tempo_limite: float) -> Retrato:
        """Bloqueia até a versão mudar ou o tempo acabar (usado pelo SSE)."""
        with self._condicao:
            self._condicao.wait_for(
                lambda: self._retrato.versao != versao_conhecida, timeout=tempo_limite
            )
            return self._retrato


def _iguais(a: Retrato, b: Retrato) -> bool:
    """Compara ignorando os instantes de recebimento (que mudam a cada chamada)."""
    ignorar = {"selecao_recebida_em": 0.0, "ready_check_recebido_em": 0.0}
    return replace(a, **ignorar) == replace(b, **ignorar)
