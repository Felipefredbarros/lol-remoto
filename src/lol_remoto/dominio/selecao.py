"""Sessão da seleção de campeões (`/lol-champ-select/v1/session`) convertida em objetos.

O formato é o da LCU (API não oficial). Campos secundários ausentes viram valores neutros,
para que um patch que remova algo pequeno não derrube a tela inteira.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from lol_remoto.dominio.campeoes import SEM_CAMPEAO

POSICOES = {
    "top": "Topo",
    "jungle": "Selva",
    "middle": "Meio",
    "bottom": "Atirador",
    "utility": "Suporte",
}


class SelecaoInvalida(ValueError):
    """O JSON da sessão não tem o formato esperado."""


class TipoAcao(StrEnum):
    BAN = "ban"
    PICK = "pick"


_TIPOS = frozenset(t.value for t in TipoAcao)


class Etapa(StrEnum):
    PLANEJAMENTO = "PLANNING"
    BANS_E_PICKS = "BAN_PICK"
    FINALIZACAO = "FINALIZATION"
    INICIANDO = "GAME_STARTING"
    DESCONHECIDA = "?"


@dataclass(frozen=True)
class Jogador:
    celula: int
    aliado: bool
    posicao: str  # "top", "jungle"... ou "" quando não há posição (ARAM, às cegas)
    campeao: int  # marcado ou confirmado; 0 = nenhum
    intencao: int  # intenção declarada no planejamento; 0 = nenhuma
    nome: str | None  # None quando o cliente esconde o nome


@dataclass(frozen=True)
class Acao:
    id: int
    celula: int
    tipo: TipoAcao
    campeao: int
    concluida: bool
    em_andamento: bool
    aliada: bool


@dataclass(frozen=True)
class Timer:
    etapa: Etapa
    ms_restantes: int  # no momento em que a sessão foi recebida
    infinito: bool


@dataclass(frozen=True)
class Selecao:
    minha_celula: int
    aliados: tuple[Jogador, ...]
    inimigos: tuple[Jogador, ...]
    acoes: tuple[Acao, ...]
    timer: Timer
    banco: tuple[int, ...] = ()  # ARAM: campeões disponíveis para troca
    banco_ativo: bool = False
    rerolls: int = 0
    pode_rerolar: bool = False

    @property
    def eh_aram(self) -> bool:
        return self.banco_ativo

    @property
    def eu(self) -> Jogador | None:
        return self.jogador(self.minha_celula)

    def jogador(self, celula: int) -> Jogador | None:
        return next((j for j in (*self.aliados, *self.inimigos) if j.celula == celula), None)

    @property
    def em_andamento(self) -> tuple[Acao, ...]:
        """Ações acontecendo agora (nos bans simultâneos, são várias)."""
        return tuple(a for a in self.acoes if a.em_andamento and not a.concluida)

    @property
    def em_planejamento(self) -> bool:
        """Etapa de declarar a intenção de pick (escolha alternada), antes dos bans."""
        return self.timer.etapa is Etapa.PLANEJAMENTO

    @property
    def minha_vez(self) -> Acao | None:
        """A minha ação em andamento, se for a minha vez de banir ou escolher.

        No planejamento o cliente já marca o primeiro ban como "em andamento", mas ainda
        não dá para banir (gravação real, out/2026); por isso ali não é a minha vez.
        """
        if self.em_planejamento:
            return None
        return next((a for a in self.em_andamento if a.celula == self.minha_celula), None)

    def bans(self, aliados: bool) -> tuple[int, ...]:
        return tuple(
            a.campeao
            for a in self.acoes
            if a.tipo is TipoAcao.BAN
            and a.concluida
            and a.aliada == aliados
            and a.campeao != SEM_CAMPEAO
        )

    def confirmou(self, celula: int) -> bool:
        """True se o jogador já travou o campeão."""
        return any(
            a.tipo is TipoAcao.PICK and a.concluida and a.celula == celula for a in self.acoes
        )


# ---------- conversão do JSON ----------


def _int(dados: dict[str, Any], chave: str, padrao: int = 0) -> int:
    valor = dados.get(chave, padrao)
    # bool é subclasse de int; `true` não deve virar o campeão 1.
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else padrao


def _jogador(dados: object, aliado: bool) -> Jogador:
    if not isinstance(dados, dict):
        raise SelecaoInvalida("Jogador com formato inesperado.")
    nome = dados.get("gameName") or None
    tag = dados.get("tagLine")
    return Jogador(
        celula=_int(dados, "cellId", -1),
        aliado=aliado,
        posicao=str(dados.get("assignedPosition") or "").lower(),
        campeao=_int(dados, "championId"),
        intencao=_int(dados, "championPickIntent"),
        nome=f"{nome}#{tag}" if nome and tag else nome,
    )


def _acoes(turnos: object) -> tuple[Acao, ...]:
    """`actions` é uma lista de turnos, cada turno uma lista de ações. Só ban/pick interessam."""
    if not isinstance(turnos, list):
        return ()
    acoes = []
    for turno in turnos:
        for item in turno if isinstance(turno, list) else ():
            if not isinstance(item, dict) or item.get("type") not in _TIPOS:
                continue
            acoes.append(
                Acao(
                    id=_int(item, "id", -1),
                    celula=_int(item, "actorCellId", -1),
                    tipo=TipoAcao(item["type"]),
                    campeao=_int(item, "championId"),
                    concluida=bool(item.get("completed")),
                    em_andamento=bool(item.get("isInProgress")),
                    aliada=bool(item.get("isAllyAction")),
                )
            )
    return tuple(acoes)


def _timer(dados: object) -> Timer:
    dados = dados if isinstance(dados, dict) else {}
    try:
        etapa = Etapa(dados.get("phase"))
    except ValueError:
        etapa = Etapa.DESCONHECIDA
    return Timer(
        etapa=etapa,
        ms_restantes=max(0, _int(dados, "adjustedTimeLeftInPhase")),
        infinito=bool(dados.get("isInfinite")),
    )


def selecao_de(dados: object) -> Selecao:
    """Converte o JSON da LCU. Levanta `SelecaoInvalida` se o essencial estiver faltando."""
    if not isinstance(dados, dict):
        raise SelecaoInvalida("A sessão da seleção deve ser um objeto JSON.")
    if not isinstance(dados.get("myTeam"), list):
        raise SelecaoInvalida("A sessão da seleção não tem o time ('myTeam').")
    inimigos = dados.get("theirTeam")
    inimigos = inimigos if isinstance(inimigos, list) else []
    banco = dados.get("benchChampions")
    banco = banco if isinstance(banco, list) else []
    return Selecao(
        minha_celula=_int(dados, "localPlayerCellId", -1),
        aliados=tuple(_jogador(j, aliado=True) for j in dados["myTeam"]),
        inimigos=tuple(_jogador(j, aliado=False) for j in inimigos),
        acoes=_acoes(dados.get("actions")),
        timer=_timer(dados.get("timer")),
        banco=tuple(_int(c, "championId") for c in banco if isinstance(c, dict)),
        banco_ativo=bool(dados.get("benchEnabled")),
        rerolls=_int(dados, "rerollsRemaining"),
        pode_rerolar=bool(dados.get("allowRerolling")),
    )
