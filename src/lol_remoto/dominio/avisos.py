"""Quando avisar o celular: regras puras sobre a passagem de um momento do cliente para outro.

Quem decide *se* o aviso vira notificação (modo ausente) é `servicos/notificacoes.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.selecao import Selecao, TipoAcao


@dataclass(frozen=True)
class Momento:
    """O que se sabe do cliente num instante."""

    fase: Fase
    selecao: Selecao | None = None


class TipoAviso(StrEnum):
    PARTIDA_ENCONTRADA = "partida_encontrada"
    PARTIDA_RECUSADA = "partida_recusada"  # alguém recusou; você voltou para a fila
    SUA_VEZ_BANIR = "sua_vez_banir"
    SUA_VEZ_ESCOLHER = "sua_vez_escolher"
    DODGE = "dodge"  # alguém saiu da seleção; você voltou para a fila
    SELECAO_CANCELADA = "selecao_cancelada"  # a seleção acabou sem voltar para a fila
    CARREGANDO = "carregando"


@dataclass(frozen=True)
class Aviso:
    tipo: TipoAviso
    acao_id: int | None = None  # só nos avisos de "sua vez"
    segundos: int | None = None  # tempo restante para agir, quando se sabe


def _aviso_de_fase(anterior: Fase, atual: Fase) -> Aviso | None:
    if atual is Fase.PARTIDA_ENCONTRADA:
        return Aviso(TipoAviso.PARTIDA_ENCONTRADA)
    if anterior is Fase.PARTIDA_ENCONTRADA and atual is Fase.FILA:
        return Aviso(TipoAviso.PARTIDA_RECUSADA)
    if anterior is Fase.SELECAO and atual is Fase.FILA:
        return Aviso(TipoAviso.DODGE)
    if anterior is Fase.SELECAO and atual in (Fase.LOBBY, Fase.NENHUMA):
        return Aviso(TipoAviso.SELECAO_CANCELADA)
    # Às vezes o cliente pula o GameStart e vai direto para InProgress.
    if atual is Fase.CARREGANDO or (anterior is Fase.SELECAO and atual is Fase.EM_PARTIDA):
        return Aviso(TipoAviso.CARREGANDO)
    return None


def _aviso_de_vez(anterior: Selecao | None, atual: Selecao | None) -> Aviso | None:
    """Avisa uma vez por ação: quando a minha ação em andamento muda."""
    vez = atual.minha_vez if atual else None
    if vez is None:
        return None
    vez_anterior = anterior.minha_vez if anterior else None
    if vez_anterior is not None and vez_anterior.id == vez.id:
        return None
    tipo = TipoAviso.SUA_VEZ_BANIR if vez.tipo is TipoAcao.BAN else TipoAviso.SUA_VEZ_ESCOLHER
    segundos = None if atual.timer.infinito else round(atual.timer.ms_restantes / 1000)
    return Aviso(tipo, acao_id=vez.id, segundos=segundos)


def avisos(anterior: Momento, atual: Momento) -> list[Aviso]:
    """Avisos gerados ao passar de `anterior` para `atual` (normalmente zero ou um)."""
    resultado = []
    if anterior.fase is not atual.fase:
        aviso = _aviso_de_fase(anterior.fase, atual.fase)
        if aviso:
            resultado.append(aviso)
    if atual.fase is Fase.SELECAO:
        selecao_anterior = anterior.selecao if anterior.fase is Fase.SELECAO else None
        aviso = _aviso_de_vez(selecao_anterior, atual.selecao)
        if aviso:
            resultado.append(aviso)
    return resultado
