"""LCU em memória, para testes e para o `--simular`. Não fala com o cliente do LoL."""

from __future__ import annotations

import copy
import queue
import time
from collections.abc import Iterable, Iterator
from typing import Any

from lol_remoto.plataforma.lcu import ErroLcu, Evento
from lol_remoto.plataforma.websocket import ConexaoFechada


class LcuFalsa:
    def __init__(self, respostas: dict[str, Any] | None = None) -> None:
        self.respostas: dict[str, Any] = dict(respostas or {})  # GET caminho → JSON
        self.arquivos: dict[str, bytes] = {}  # GET binário (ícones)
        self.erros: dict[tuple[str, str], ErroLcu] = {}  # (método, caminho) → erro a levantar
        self.chamadas: list[tuple[str, str, Any]] = []  # tudo que não é GET
        self.assinados: list[str] = []
        self._fila: queue.Queue[Evento | None] = queue.Queue()

    # ---------- REST ----------

    def get(self, caminho: str) -> Any:
        if ("GET", caminho) in self.erros:
            raise self.erros["GET", caminho]
        return copy.deepcopy(self.respostas.get(caminho))

    def enviar(self, metodo: str, caminho: str, corpo: Any = None) -> Any:
        self.chamadas.append((metodo, caminho, copy.deepcopy(corpo)))
        if (metodo, caminho) in self.erros:
            raise self.erros[metodo, caminho]
        return None

    def get_bytes(self, caminho: str) -> bytes:
        if caminho not in self.arquivos:
            raise ErroLcu(f"GET {caminho} → 404", 404)
        return self.arquivos[caminho]

    # ---------- eventos ----------

    def emitir(self, uri: str, dados: Any, tipo: str = "Update") -> None:
        """Simula um evento da LCU; também atualiza o que o GET daquele caminho devolve."""
        if tipo == "Delete":
            self.respostas.pop(uri, None)
        else:
            self.respostas[uri] = copy.deepcopy(dados)
        self._fila.put(Evento(uri=uri, tipo=tipo, dados=copy.deepcopy(dados)))

    def desconectar(self) -> None:
        """Simula o cliente do LoL fechando."""
        self._fila.put(None)

    def eventos(self, caminhos: Iterable[str]) -> Iterator[Evento]:
        self.assinados = list(caminhos)  # como a LcuHttp: assina na hora da chamada
        return self._ler_eventos()

    def _ler_eventos(self) -> Iterator[Evento]:
        while True:
            evento = self._fila.get()
            if evento is None:
                self._fila.task_done()
                raise ConexaoFechada("LCU falsa desconectada.")
            yield evento
            self._fila.task_done()  # quem consome voltou: o evento anterior foi processado

    def aguardar_consumo(self, tempo_limite: float = 3.0) -> None:
        """Bloqueia até todos os eventos emitidos terem sido processados por quem os lê."""
        fim = time.monotonic() + tempo_limite
        with self._fila.all_tasks_done:
            while self._fila.unfinished_tasks:
                restante = fim - time.monotonic()
                if restante <= 0:
                    raise TimeoutError("Os eventos da LCU falsa não foram consumidos a tempo.")
                self._fila.all_tasks_done.wait(restante)

    def fechar(self) -> None:
        self.desconectar()
