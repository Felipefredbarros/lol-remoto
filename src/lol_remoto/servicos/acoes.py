"""Ações no cliente do LoL: aceitar/recusar a partida, marcar/confirmar campeão e ARAM.

Toda ação confere a fase antes (ver docs/decisoes/0002: nada dentro da partida) e parte
de um pedido seu; nada é feito automaticamente.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from lol_remoto.dominio.campeoes import SEM_CAMPEAO
from lol_remoto.dominio.fase import Fase, exigir_fase
from lol_remoto.dominio.selecao import Acao, Selecao, TipoAcao
from lol_remoto.plataforma.lcu import Lcu
from lol_remoto.servicos.estado import Estado

log = logging.getLogger(__name__)

ACEITAR = "/lol-matchmaking/v1/ready-check/accept"
RECUSAR = "/lol-matchmaking/v1/ready-check/decline"
ACAO = "/lol-champ-select/v1/session/actions/{id}"
PICKAVEIS = "/lol-champ-select/v1/pickable-champion-ids"
BANIVEIS = "/lol-champ-select/v1/bannable-champion-ids"
REROLL = "/lol-champ-select/v1/session/my-selection/reroll"
TROCAR_DO_BANCO = "/lol-champ-select/v1/session/bench/swap/{id}"


class ClienteDesconectado(RuntimeError):
    """O cliente do LoL não está aberto (ou ainda não conectou)."""


class AcaoIndisponivel(RuntimeError):
    """A ação não faz sentido agora (ex.: não é a sua vez)."""


class CampeaoIndisponivel(ValueError):
    """O campeão não pode ser escolhido/banido agora."""


class ServicoAcoes:
    def __init__(self, estado: Estado, obter_lcu: Callable[[], Lcu | None]) -> None:
        """`obter_lcu` devolve a conexão atual (normalmente `Monitor.lcu`)."""
        self._estado = estado
        self._obter_lcu = obter_lcu

    def _lcu(self) -> Lcu:
        lcu = self._obter_lcu()
        if lcu is None:
            raise ClienteDesconectado("O cliente do LoL não está aberto.")
        return lcu

    def _selecao(self) -> Selecao:
        atual = self._estado.atual
        exigir_fase(atual.fase, Fase.SELECAO)
        if atual.selecao is None:
            raise AcaoIndisponivel("A seleção de campeões ainda está carregando.")
        return atual.selecao

    # ---------- partida encontrada ----------

    def aceitar(self) -> None:
        exigir_fase(self._estado.atual.fase, Fase.PARTIDA_ENCONTRADA)
        self._lcu().enviar("POST", ACEITAR)
        log.info("Partida aceita")

    def recusar(self) -> None:
        exigir_fase(self._estado.atual.fase, Fase.PARTIDA_ENCONTRADA)
        self._lcu().enviar("POST", RECUSAR)
        log.info("Partida recusada")

    # ---------- seleção ----------

    def _acao_para_marcar(self, selecao: Selecao) -> Acao:
        """Na vez: a ação em andamento. No planejamento: o meu pick (vira intenção)."""
        if selecao.em_planejamento:
            pick = next(
                (
                    a
                    for a in selecao.acoes
                    if a.celula == selecao.minha_celula
                    and a.tipo is TipoAcao.PICK
                    and not a.concluida
                ),
                None,
            )
            if pick is None:
                raise AcaoIndisponivel("Não há pick para declarar intenção.")
            return pick
        if selecao.minha_vez is None:
            raise AcaoIndisponivel("Não é a sua vez.")
        return selecao.minha_vez

    def disponiveis(self, tipo: TipoAcao) -> list[int]:
        """Ids que o cliente aceita agora para ban ou pick, sem os banidos e os já travados.

        O app também tira os usados por conta própria: no `--simular` deu para escolher um
        banido, e não dá para confiar só na lista do cliente (numa ranqueada a de baníveis
        veio vazia; roteiro, etapa 8). Sem ela, no ban vale o catálogo, já que dá para banir
        qualquer campeão; o cliente recusa o que não puder.
        """
        atual = self._estado.atual
        exigir_fase(atual.fase, Fase.SELECAO)
        usados = atual.selecao.ja_usados() if atual.selecao else frozenset()
        ids = self._lcu().get(BANIVEIS if tipo is TipoAcao.BAN else PICKAVEIS)
        validos = [i for i in ids or [] if isinstance(i, int) and not isinstance(i, bool)]
        if not validos and tipo is TipoAcao.BAN:
            log.warning("O cliente não informou os campeões baníveis; usando o catálogo")
            validos = [c.id for c in self._estado.catalogo.buscar()]
        return [i for i in validos if i not in usados]

    def _validar_campeao(self, campeao: object, tipo: TipoAcao) -> int:
        if isinstance(campeao, bool) or not isinstance(campeao, int) or campeao <= 0:
            raise CampeaoIndisponivel("Escolha um campeão.")
        if campeao not in self.disponiveis(tipo):
            raise CampeaoIndisponivel("Esse campeão não está disponível agora.")
        return campeao

    def marcar(self, campeao: object) -> None:
        """Marca (hover) o campeão na ação atual, ou declara a intenção no planejamento."""
        selecao = self._selecao()
        acao = self._acao_para_marcar(selecao)
        id_campeao = self._validar_campeao(campeao, acao.tipo)
        self._lcu().enviar("PATCH", ACAO.format(id=acao.id), {"championId": id_campeao})
        log.info("Campeão %s marcado (%s)", id_campeao, acao.tipo.value)

    def confirmar(self, campeao: object = None) -> None:
        """Trava o ban/pick. Com `campeao`, marca e confirma de uma vez."""
        selecao = self._selecao()
        if selecao.em_planejamento:
            raise AcaoIndisponivel("No planejamento só dá para declarar intenção.")
        acao = self._acao_para_marcar(selecao)
        if campeao is not None:
            id_campeao = self._validar_campeao(campeao, acao.tipo)
        elif acao.campeao != SEM_CAMPEAO:
            id_campeao = acao.campeao
        else:
            raise AcaoIndisponivel("Marque um campeão antes de confirmar.")
        # PATCH com "completed": o caminho usado pelas ferramentas da comunidade, e manda
        # o campeão junto (sem depender do hover). A confirmar numa fila real (roteiro, etapa 8).
        self._lcu().enviar(
            "PATCH", ACAO.format(id=acao.id), {"championId": id_campeao, "completed": True}
        )
        log.info("Campeão %s confirmado (%s)", id_campeao, acao.tipo.value)

    # ---------- ARAM ----------

    def _selecao_aram(self) -> Selecao:
        selecao = self._selecao()
        if not selecao.eh_aram:
            raise AcaoIndisponivel("Isso só existe no ARAM.")
        return selecao

    def rerolar(self) -> None:
        selecao = self._selecao_aram()
        if not selecao.pode_rerolar or selecao.rerolls <= 0:
            raise AcaoIndisponivel("Sem rerolls disponíveis.")
        self._lcu().enviar("POST", REROLL)
        log.info("Reroll pedido")

    def trocar_do_banco(self, campeao: object) -> None:
        selecao = self._selecao_aram()
        if isinstance(campeao, bool) or campeao not in selecao.banco:
            raise CampeaoIndisponivel("Esse campeão não está no banco.")
        self._lcu().enviar("POST", TROCAR_DO_BANCO.format(id=campeao))
        log.info("Troca com o banco: %s", campeao)
