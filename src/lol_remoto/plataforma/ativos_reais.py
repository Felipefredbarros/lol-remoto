"""Imagens do cliente do LoL de verdade para o `--simular` (fotos de campeões e feitiços).

Só GET em `/lol-game-data/assets/` (arquivos do jogo): nunca lê o estado da conta nem age
no cliente. Com o cliente fechado, a página mostra as iniciais (ou o cache em disco).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from lol_remoto.plataforma import lockfile
from lol_remoto.plataforma.lcu import ErroLcu, Lcu, LcuHttp
from lol_remoto.plataforma.lockfile import Credenciais

PREFIXO = "/lol-game-data/assets/"


class AtivosDoClienteReal:
    def __init__(self, pasta_lol: Path, conectar: Callable[[Credenciais], Lcu] = LcuHttp) -> None:
        self._pasta_lol = pasta_lol
        self._conectar = conectar

    def __call__(self, caminho: str) -> bytes:
        if not caminho.startswith(PREFIXO) or ".." in caminho:
            raise ErroLcu(f"GET {caminho} → só arquivos do jogo", 404)
        credenciais = lockfile.ler(self._pasta_lol)
        if credenciais is None:
            raise ErroLcu("O cliente do LoL está fechado: sem imagens.", 404)
        return self._conectar(credenciais).get_bytes(caminho)
