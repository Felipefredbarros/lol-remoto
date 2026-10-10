"""O estado como a página do celular precisa: JSON pronto, com nomes e tempos calculados."""

from __future__ import annotations

from typing import Any

from lol_remoto.dominio.campeoes import SEM_CAMPEAO, Catalogo
from lol_remoto.dominio.fase import DESCRICOES, pode_agir
from lol_remoto.dominio.ready_check import DURACAO_SEGUNDOS
from lol_remoto.dominio.selecao import POSICOES, Jogador, Selecao
from lol_remoto.servicos.estado import Retrato


def _campeao(id_: int, catalogo: Catalogo) -> dict[str, Any] | None:
    if id_ == SEM_CAMPEAO:
        return None
    return {"id": id_, "nome": catalogo.nome(id_) or f"#{id_}"}


def _jogador(jogador: Jogador, selecao: Selecao, catalogo: Catalogo) -> dict[str, Any]:
    agindo = next((a for a in selecao.em_andamento if a.celula == jogador.celula), None)
    return {
        "celula": jogador.celula,
        "nome": jogador.nome,
        "posicao": POSICOES.get(jogador.posicao),
        "campeao": _campeao(jogador.campeao, catalogo),
        "intencao": _campeao(jogador.intencao, catalogo),
        "confirmado": selecao.confirmou(jogador.celula),
        "eu": jogador.celula == selecao.minha_celula,
        # No planejamento ninguém está agindo de verdade (ver Selecao.minha_vez).
        "agindo": agindo.tipo.value if agindo and not selecao.em_planejamento else None,
    }


def _selecao(selecao: Selecao, recebida_em: float, agora: float, catalogo: Catalogo) -> dict:
    restante = selecao.timer.ms_restantes / 1000 - (agora - recebida_em)
    vez = selecao.minha_vez
    return {
        "etapa": selecao.timer.etapa.value,
        "planejamento": selecao.em_planejamento,
        "segundos_restantes": None if selecao.timer.infinito else max(0, round(restante)),
        "minha_vez": {"id": vez.id, "tipo": vez.tipo.value, "campeao": vez.campeao}
        if vez
        else None,
        "aliados": [_jogador(j, selecao, catalogo) for j in selecao.aliados],
        "inimigos": [_jogador(j, selecao, catalogo) for j in selecao.inimigos],
        "bans": {
            "aliados": [_campeao(i, catalogo) for i in selecao.bans(aliados=True)],
            "inimigos": [_campeao(i, catalogo) for i in selecao.bans(aliados=False)],
        },
        "aram": selecao.eh_aram,
        "banco": [_campeao(i, catalogo) for i in selecao.banco if i != SEM_CAMPEAO],
        "rerolls": selecao.rerolls if selecao.pode_rerolar else 0,
    }


def visao(retrato: Retrato, catalogo: Catalogo, agora: float) -> dict[str, Any]:
    """`agora` é o relógio monotônico do `Estado`, para calcular os tempos restantes."""
    ready_check = None
    if retrato.ready_check is not None:
        decorridos = retrato.ready_check.segundos_decorridos + (
            agora - retrato.ready_check_recebido_em
        )
        ready_check = {
            "resposta": retrato.ready_check.resposta.value,
            "segundos_restantes": max(0, round(DURACAO_SEGUNDOS - decorridos)),
        }
    return {
        "versao": retrato.versao,
        "conectado": retrato.conectado,
        "fase": retrato.fase.value,
        "fase_descricao": DESCRICOES[retrato.fase] if retrato.conectado else "Cliente fechado",
        "pode_agir": retrato.conectado and pode_agir(retrato.fase),
        "ausente": retrato.ausente,
        "ready_check": ready_check,
        "selecao": (
            _selecao(retrato.selecao, retrato.selecao_recebida_em, agora, catalogo)
            if retrato.selecao is not None
            else None
        ),
    }
