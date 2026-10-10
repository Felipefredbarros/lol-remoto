"""Ícones dos campeões, buscados na LCU e guardados em memória.

Servir pelo próprio PC mantém a CSP `default-src 'self'` e não depende de internet.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from lol_remoto.plataforma.lcu import Lcu
from lol_remoto.servicos.acoes import CampeaoIndisponivel, ClienteDesconectado

CAMINHO = "/lol-game-data/assets/v1/champion-icons/{id}.png"
LIMITE_CACHE = 400  # ~30 KB cada; cabe o catálogo inteiro


class ServicoIcones:
    def __init__(self, obter_lcu: Callable[[], Lcu | None]) -> None:
        self._obter_lcu = obter_lcu
        self._cache: dict[int, bytes] = {}
        self._trava = threading.Lock()

    def icone(self, campeao: int) -> bytes:
        if campeao <= 0:
            raise CampeaoIndisponivel("Campeão inválido.")
        with self._trava:
            if campeao in self._cache:
                return self._cache[campeao]
        lcu = self._obter_lcu()
        if lcu is None:
            raise ClienteDesconectado("O cliente do LoL não está aberto.")
        dados = lcu.get_bytes(CAMINHO.format(id=campeao))
        with self._trava:
            if len(self._cache) < LIMITE_CACHE:
                self._cache[campeao] = dados
        return dados
