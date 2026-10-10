"""Aplica uma das runas recomendadas pelo cliente, com os feitiços, durante a seleção.

Grava na página "LoL Remoto" (ou cria uma, se houver espaço). Sobrescrever outra página
só com confirmação explícita (docs/decisoes/0009).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from lol_remoto.dominio.campeoes import SEM_CAMPEAO
from lol_remoto.dominio.fase import Fase, exigir_fase
from lol_remoto.dominio.runas import (
    NOME_PAGINA,
    Recomendacao,
    corpo_pagina,
    eh_pagina_do_app,
    mapa,
    posicao_lcu,
    recomendacoes_de,
)
from lol_remoto.plataforma.lcu import Lcu
from lol_remoto.servicos.acoes import AcaoIndisponivel, ClienteDesconectado
from lol_remoto.servicos.estado import Estado

log = logging.getLogger(__name__)

RECOMENDADAS = "/lol-perks/v1/recommended-pages/champion/{campeao}/position/{posicao}/map/{mapa}"
PAGINAS = "/lol-perks/v1/pages"
PAGINA = "/lol-perks/v1/pages/{id}"
PAGINA_ATUAL = "/lol-perks/v1/currentpage"
INVENTARIO = "/lol-perks/v1/inventory"
ESTILOS = "/lol-perks/v1/styles"
FEITICOS = "/lol-game-data/assets/v1/summoner-spells.json"
MINHA_SELECAO = "/lol-champ-select/v1/session/my-selection"


class SemPaginaLivre(RuntimeError):
    """Não há página "LoL Remoto" nem espaço para criar uma."""


class EscolhaInvalida(ValueError):
    """O índice da recomendação não existe."""


class ServicoRunas:
    def __init__(self, estado: Estado, obter_lcu: Callable[[], Lcu | None]) -> None:
        self._estado = estado
        self._obter_lcu = obter_lcu
        self._nomes: dict[str, dict[int, str]] = {}  # "estilos"/"feiticos" → id → nome

    def _lcu(self) -> Lcu:
        lcu = self._obter_lcu()
        if lcu is None:
            raise ClienteDesconectado("O cliente do LoL não está aberto.")
        return lcu

    def recomendacoes(self) -> list[Recomendacao]:
        """As recomendações do cliente para o meu campeão (marcado ou travado) e posição."""
        atual = self._estado.atual
        exigir_fase(atual.fase, Fase.SELECAO)
        eu = atual.selecao.eu if atual.selecao else None
        if eu is None or eu.campeao == SEM_CAMPEAO:
            raise AcaoIndisponivel("Escolha o campeão antes das runas.")
        caminho = RECOMENDADAS.format(
            campeao=eu.campeao, posicao=posicao_lcu(eu.posicao), mapa=mapa(atual.selecao.eh_aram)
        )
        return recomendacoes_de(self._lcu().get(caminho))

    def nomes(self, tipo: str) -> dict[int, str]:
        """Nomes dos estilos de runa ou dos feitiços (em cache depois da 1ª vez)."""
        if tipo not in self._nomes:
            caminho = ESTILOS if tipo == "estilos" else FEITICOS
            itens = self._lcu().get(caminho) or []
            self._nomes[tipo] = {
                i["id"]: str(i.get("name", "")) for i in itens if isinstance(i, dict) and "id" in i
            }
        return self._nomes[tipo]

    def _pagina_destino(self, lcu: Lcu, sobrescrever_atual: bool) -> dict[str, Any] | None:
        """A página a sobrescrever, ou None para criar uma nova."""
        paginas = lcu.get(PAGINAS) or []
        propria = next((p for p in paginas if eh_pagina_do_app(p) and p.get("isEditable")), None)
        if propria is not None:
            return propria
        if (lcu.get(INVENTARIO) or {}).get("canAddCustomPage"):
            return None
        atual = lcu.get(PAGINA_ATUAL)
        if sobrescrever_atual and isinstance(atual, dict) and atual.get("isEditable"):
            return atual
        raise SemPaginaLivre(
            f'Não há espaço para a página "{NOME_PAGINA}". Renomeie uma página para '
            f'"{NOME_PAGINA}" no cliente ou confirme sobrescrever a página atual.'
        )

    def aplicar(self, indice: object, sobrescrever_atual: bool = False) -> Recomendacao:
        recomendacoes = self.recomendacoes()  # confere fase e campeão
        if isinstance(indice, bool) or not isinstance(indice, int):
            raise EscolhaInvalida("Escolha uma das recomendações.")
        escolhida = next((r for r in recomendacoes if r.indice == indice), None)
        if escolhida is None:
            raise EscolhaInvalida("Essa recomendação não existe mais.")

        lcu = self._lcu()
        pagina = self._pagina_destino(lcu, sobrescrever_atual is True)
        if pagina is None:
            lcu.enviar("POST", PAGINAS, corpo_pagina(escolhida, NOME_PAGINA))
        else:
            lcu.enviar(
                "PUT", PAGINA.format(id=pagina["id"]), corpo_pagina(escolhida, pagina["name"])
            )
        if len(escolhida.feiticos) == 2:
            primeiro, segundo = escolhida.feiticos
            lcu.enviar("PATCH", MINHA_SELECAO, {"spell1Id": primeiro, "spell2Id": segundo})
        log.info("Runas aplicadas: %s (%s)", escolhida.principal, escolhida.descricao)
        return escolhida
