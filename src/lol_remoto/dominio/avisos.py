"""Quando avisar o celular: regras puras sobre a passagem de um momento do cliente para outro.

Quem decide *se* o aviso vira notificação (modo ausente) é `servicos/notificacoes.py`.
As regras foram conferidas com gravações reais (tests/fixtures/gravacoes/).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from lol_remoto.dominio.campeoes import SEM_CAMPEAO
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.ready_check import ReadyCheck, Resposta
from lol_remoto.dominio.selecao import Selecao, TipoAcao


@dataclass(frozen=True)
class Momento:
    """O que se sabe do cliente num instante."""

    fase: Fase
    selecao: Selecao | None = None
    ready_check: ReadyCheck | None = None

    @property
    def partida_encontrada(self) -> bool:
        """Há uma partida esperando o seu aceite.

        A fase sozinha não basta: a partida personalizada passa por `ReadyCheck` em
        milissegundos, sem nada para aceitar e sem dados de ready check.
        """
        return (
            self.fase is Fase.PARTIDA_ENCONTRADA
            and self.ready_check is not None
            and self.ready_check.em_andamento
        )


class TipoAviso(StrEnum):
    PARTIDA_ENCONTRADA = "partida_encontrada"
    PARTIDA_RECUSADA = "partida_recusada"  # alguém recusou; você voltou para a fila
    NAO_ACEITOU = "nao_aceitou"  # o tempo acabou sem você aceitar; saiu da fila
    SAIU_DA_FILA = "saiu_da_fila"  # você recusou (ou o grupo); saiu da fila
    PLANEJAMENTO = "planejamento"  # seleção começou: declare a intenção de pick
    SUA_VEZ_BANIR = "sua_vez_banir"
    SUA_VEZ_ESCOLHER = "sua_vez_escolher"
    ARAM = "aram"  # recebeu o campeão do ARAM
    DODGE = "dodge"  # alguém saiu da seleção; você voltou para a fila
    SELECAO_CANCELADA = "selecao_cancelada"  # a seleção acabou sem voltar para a fila
    CARREGANDO = "carregando"


@dataclass(frozen=True)
class Aviso:
    tipo: TipoAviso
    acao_id: int | None = None  # só nos avisos de "sua vez"
    segundos: int | None = None  # tempo restante, quando se sabe
    campeao: int | None = None  # só no aviso do ARAM


def _segundos(selecao: Selecao) -> int | None:
    return None if selecao.timer.infinito else round(selecao.timer.ms_restantes / 1000)


def _aviso_de_fila(anterior: Momento, atual: Momento) -> Aviso | None:
    if atual.partida_encontrada and not anterior.partida_encontrada:
        return Aviso(TipoAviso.PARTIDA_ENCONTRADA)
    if not anterior.partida_encontrada or atual.fase is Fase.PARTIDA_ENCONTRADA:
        return None
    if atual.fase is Fase.FILA:
        return Aviso(TipoAviso.PARTIDA_RECUSADA)
    if atual.fase in (Fase.LOBBY, Fase.NENHUMA):
        resposta = anterior.ready_check.resposta if anterior.ready_check else None
        tipo = TipoAviso.NAO_ACEITOU if resposta is Resposta.NENHUMA else TipoAviso.SAIU_DA_FILA
        return Aviso(tipo)
    return None


def _aviso_de_fase(anterior: Fase, atual: Fase) -> Aviso | None:
    if anterior is Fase.SELECAO and atual is Fase.FILA:
        return Aviso(TipoAviso.DODGE)
    if anterior is Fase.SELECAO and atual in (Fase.LOBBY, Fase.NENHUMA):
        return Aviso(TipoAviso.SELECAO_CANCELADA)
    # Às vezes o cliente pula o GameStart e vai direto para InProgress.
    if atual is Fase.CARREGANDO or (anterior is Fase.SELECAO and atual is Fase.EM_PARTIDA):
        return Aviso(TipoAviso.CARREGANDO)
    return None


def _aviso_de_selecao(anterior: Selecao | None, atual: Selecao) -> Aviso | None:
    if atual.eh_aram:
        # No ARAM o campeão é sorteado: avisa quando ele chega, não a "vez".
        eu, eu_antes = atual.eu, anterior.eu if anterior else None
        campeao_antes = eu_antes.campeao if eu_antes else SEM_CAMPEAO
        if eu and eu.campeao != SEM_CAMPEAO and campeao_antes == SEM_CAMPEAO:
            return Aviso(TipoAviso.ARAM, campeao=eu.campeao, segundos=_segundos(atual))
        return None

    if atual.em_planejamento and not (anterior and anterior.em_planejamento):
        return Aviso(TipoAviso.PLANEJAMENTO, segundos=_segundos(atual))

    # Avisa uma vez por ação: quando a minha ação em andamento muda.
    vez = atual.minha_vez
    vez_anterior = anterior.minha_vez if anterior else None
    if vez is None or (vez_anterior is not None and vez_anterior.id == vez.id):
        return None
    tipo = TipoAviso.SUA_VEZ_BANIR if vez.tipo is TipoAcao.BAN else TipoAviso.SUA_VEZ_ESCOLHER
    return Aviso(tipo, acao_id=vez.id, segundos=_segundos(atual))


def avisos(anterior: Momento, atual: Momento) -> list[Aviso]:
    """Avisos gerados ao passar de `anterior` para `atual` (normalmente zero ou um)."""
    resultado = []
    aviso = _aviso_de_fila(anterior, atual)
    if aviso:
        resultado.append(aviso)
    if anterior.fase is not atual.fase:
        aviso = _aviso_de_fase(anterior.fase, atual.fase)
        if aviso:
            resultado.append(aviso)
    if atual.fase is Fase.SELECAO and atual.selecao is not None:
        # A sessão pode chegar antes do evento de fase; o que vale é a seleção anterior.
        selecao_anterior = anterior.selecao if anterior.fase is Fase.SELECAO else None
        aviso = _aviso_de_selecao(selecao_anterior, atual.selecao)
        if aviso:
            resultado.append(aviso)
    return resultado
