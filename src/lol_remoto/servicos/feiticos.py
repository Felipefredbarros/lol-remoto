"""Troca dos feitiços (D e F) durante a seleção, separada das runas (docs/decisoes/0010)."""

from __future__ import annotations

import logging
from collections.abc import Callable

from lol_remoto.dominio.fase import Fase, exigir_fase
from lol_remoto.dominio.feiticos import (
    Feitico,
    FeiticoIndisponivel,
    disponiveis,
    feiticos_de,
    trocar,
)
from lol_remoto.plataforma.lcu import Lcu
from lol_remoto.servicos.acoes import AcaoIndisponivel, ClienteDesconectado
from lol_remoto.servicos.estado import Estado

log = logging.getLogger(__name__)

LISTA = "/lol-game-data/assets/v1/summoner-spells.json"
MINHA_SELECAO = "/lol-champ-select/v1/session/my-selection"


class ServicoFeiticos:
    def __init__(self, estado: Estado, obter_lcu: Callable[[], Lcu | None]) -> None:
        self._estado = estado
        self._obter_lcu = obter_lcu

    def _lcu(self) -> Lcu:
        lcu = self._obter_lcu()
        if lcu is None:
            raise ClienteDesconectado("O cliente do LoL não está aberto.")
        return lcu

    def todos(self) -> list[Feitico]:
        """A lista que o monitor carregou ao conectar; se faltar, busca de novo."""
        if not self._estado.feiticos:
            self._estado.feiticos = feiticos_de(self._lcu().get(LISTA))
        return self._estado.feiticos

    def nomes(self) -> dict[int, str]:
        return {f.id: f.nome for f in self.todos()}

    def caminho_icone(self, id_: int) -> str | None:
        """Caminho do ícone na LCU; vem da lista do cliente, nunca do pedido."""
        return next((f.icone for f in self.todos() if f.id == id_), None)

    def lista(self) -> list[Feitico]:
        """Os feitiços que valem no modo da seleção atual."""
        atual = self._estado.atual
        exigir_fase(atual.fase, Fase.SELECAO)
        aram = atual.selecao.eh_aram if atual.selecao else False
        return disponiveis(self.todos(), aram)

    def trocar(self, slot: object, feitico: object) -> tuple[int, int]:
        """Põe `feitico` no D ou no F; devolve o novo par (D, F)."""
        atual = self._estado.atual
        exigir_fase(atual.fase, Fase.SELECAO)
        eu = atual.selecao.eu if atual.selecao else None
        if eu is None:
            raise AcaoIndisponivel("A seleção de campeões ainda está carregando.")
        if not isinstance(slot, str):
            raise FeiticoIndisponivel("Escolha o feitiço do D ou do F.")
        validos = {f.id for f in self.lista()}
        if isinstance(feitico, bool) or not isinstance(feitico, int) or feitico not in validos:
            raise FeiticoIndisponivel("Esse feitiço não está disponível neste modo.")
        d, f = trocar(eu.feiticos, slot.lower(), feitico)
        self._lcu().enviar("PATCH", MINHA_SELECAO, {"spell1Id": d, "spell2Id": f})
        log.info("Feitiços: %s (D) e %s (F)", d, f)
        return d, f
