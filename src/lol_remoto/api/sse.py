"""Server-Sent Events: manda o estado ao celular a cada mudança (docs/decisoes/0007)."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Callable
from typing import Any

from lol_remoto.servicos.estado import Estado

log = logging.getLogger(__name__)

MAXIMO_CONEXOES = 4
INTERVALO_HEARTBEAT = 15.0  # segundos; também detecta conexões mortas


class CanalSse:
    def __init__(
        self,
        estado: Estado,
        montar: Callable[[], dict[str, Any]],
        maximo: int = MAXIMO_CONEXOES,
        heartbeat: float = INTERVALO_HEARTBEAT,
    ) -> None:
        """`montar` devolve o JSON do estado atual (a mesma visão de /api/estado)."""
        self._estado = estado
        self._montar = montar
        self._maximo = maximo
        self._heartbeat = heartbeat
        self._conexoes: list[threading.Event] = []
        self._trava = threading.Lock()

    @property
    def conexoes(self) -> int:
        with self._trava:
            return len(self._conexoes)

    def transmitir(self, escrever: Callable[[bytes], None]) -> None:
        """Bloqueia escrevendo eventos até o cliente sair ou a conexão ser substituída."""
        encerrar = threading.Event()
        with self._trava:
            self._conexoes.append(encerrar)
            while len(self._conexoes) > self._maximo:
                self._conexoes.pop(0).set()  # a mais antiga sai
        versao = None
        try:
            escrever(b"retry: 3000\n\n")  # o navegador reconecta em 3 s se cair
            while not encerrar.is_set():
                if versao is None:
                    atual = self._estado.atual
                else:
                    atual = self._estado.esperar_mudanca(versao, self._heartbeat)
                if atual.versao != versao:
                    versao = atual.versao
                    dados = json.dumps(self._montar(), ensure_ascii=False)
                    escrever(f"data: {dados}\n\n".encode())
                else:
                    escrever(b": ping\n\n")
        except OSError:
            pass  # o celular fechou a página ou perdeu a conexão
        finally:
            with self._trava:
                if encerrar in self._conexoes:
                    self._conexoes.remove(encerrar)
