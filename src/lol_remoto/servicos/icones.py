"""Ícones dos campeões e dos feitiços, buscados na LCU e guardados em memória.

Servir pelo próprio PC mantém a CSP `default-src 'self'` e não depende de internet. Com
`pasta`, as imagens também ficam em disco (a pasta `icones`, ao lado do log): carregam rápido
depois de reiniciar e aparecem no `--simular` mesmo com o cliente fechado.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from lol_remoto.dominio.feiticos import PREFIXO_ICONE, FeiticoIndisponivel
from lol_remoto.plataforma.lcu import Lcu
from lol_remoto.servicos.acoes import CampeaoIndisponivel, ClienteDesconectado

log = logging.getLogger(__name__)

CAMINHO = "/lol-game-data/assets/v1/champion-icons/{id}.png"
LIMITE_CACHE = 450  # ~30 KB cada; cabe o catálogo inteiro e os feitiços


class ServicoIcones:
    def __init__(
        self,
        obter_lcu: Callable[[], Lcu | None],
        caminho_feitico: Callable[[int], str | None] = lambda _id: None,
        pasta: Path | None = None,
    ) -> None:
        """`caminho_feitico` dá o `iconPath` de um feitiço (normalmente `ServicoFeiticos`)."""
        self._obter_lcu = obter_lcu
        self._caminho_feitico = caminho_feitico
        self._pasta = pasta
        self._cache: dict[tuple[str, int], bytes] = {}
        self._trava = threading.Lock()

    def icone(self, campeao: int) -> bytes:
        if campeao <= 0:
            raise CampeaoIndisponivel("Campeão inválido.")
        return self._buscar(("campeao", campeao), lambda: CAMINHO.format(id=campeao))

    def icone_feitico(self, feitico: int) -> bytes:
        def caminho() -> str:
            encontrado = self._caminho_feitico(feitico)
            if not encontrado or not encontrado.startswith(PREFIXO_ICONE):
                raise FeiticoIndisponivel("Feitiço sem ícone.")
            return encontrado

        return self._buscar(("feitico", feitico), caminho)

    def _buscar(self, chave: tuple[str, int], caminho: Callable[[], str]) -> bytes:
        with self._trava:
            if chave in self._cache:
                return self._cache[chave]
        arquivo = self._pasta / f"{chave[0]}-{chave[1]}.png" if self._pasta else None
        if arquivo is not None and arquivo.is_file():
            dados = arquivo.read_bytes()
        else:
            lcu = self._obter_lcu()
            if lcu is None:
                raise ClienteDesconectado("O cliente do LoL não está aberto.")
            dados = lcu.get_bytes(caminho())
            if arquivo is not None:
                self._gravar(arquivo, dados)
        with self._trava:
            if len(self._cache) < LIMITE_CACHE:
                self._cache[chave] = dados
        return dados

    @staticmethod
    def _gravar(arquivo: Path, dados: bytes) -> None:
        try:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_bytes(dados)
        except OSError as erro:  # o cache em disco é só um extra
            log.debug("Não foi possível guardar %s: %s", arquivo.name, erro)
