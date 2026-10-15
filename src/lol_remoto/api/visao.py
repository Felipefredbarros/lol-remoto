"""O estado como a página do celular precisa: JSON pronto, com nomes e tempos calculados."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lol_remoto.api.passos import passos
from lol_remoto.dominio.campeoes import SEM_CAMPEAO, Catalogo
from lol_remoto.dominio.fase import DESCRICOES, pode_agir
from lol_remoto.dominio.ready_check import DURACAO_SEGUNDOS
from lol_remoto.dominio.selecao import POSICOES, Jogador, Selecao, TipoAcao
from lol_remoto.servicos.estado import Estado, Retrato


def _campeao(id_: int, catalogo: Catalogo) -> dict[str, Any] | None:
    if id_ == SEM_CAMPEAO:
        return None
    return {"id": id_, "nome": catalogo.nome(id_) or f"#{id_}"}


def _feitico(id_: int, nomes: Mapping[int, str]) -> dict[str, Any] | None:
    return {"id": id_, "nome": nomes.get(id_, f"#{id_}")} if id_ > 0 else None


def _jogador(
    jogador: Jogador, selecao: Selecao, catalogo: Catalogo, feiticos: Mapping[int, str]
) -> dict[str, Any]:
    agindo = next((a for a in selecao.em_andamento if a.celula == jogador.celula), None)
    eu = jogador.celula == selecao.minha_celula
    d, f = jogador.feiticos
    return {
        "celula": jogador.celula,
        "nome": jogador.nome,
        "posicao": POSICOES.get(jogador.posicao),
        "campeao": _campeao(jogador.campeao, catalogo),
        "intencao": _campeao(jogador.intencao, catalogo),
        "confirmado": selecao.confirmou(jogador.celula),
        "eu": eu,
        # Só os seus feitiços: são os que a página deixa trocar (ADR 0010).
        "feiticos": {"d": _feitico(d, feiticos), "f": _feitico(f, feiticos)} if eu else None,
        # No planejamento ninguém está agindo de verdade (ver Selecao.minha_vez).
        "agindo": agindo.tipo.value if agindo and not selecao.em_planejamento else None,
    }


def _ordem_picks(selecao: Selecao, catalogo: Catalogo) -> list[dict[str, Any]]:
    """Os picks dos dois times na ordem dos turnos (picks do mesmo turno ficam lado a lado)."""
    ordem = []
    picks = [a for a in selecao.acoes if a.tipo is TipoAcao.PICK]
    for numero, acao in enumerate(picks, start=1):
        jogador = selecao.jogador(acao.celula)
        if acao.concluida:
            estado = "feito"
        elif acao.em_andamento and not selecao.em_planejamento:
            estado = "agindo"
        else:
            estado = "aguardando"
        ordem.append(
            {
                "ordem": numero,
                "celula": acao.celula,
                "aliado": acao.aliada,
                "eu": acao.celula == selecao.minha_celula,
                "nome": jogador.nome if jogador else None,
                "posicao": POSICOES.get(jogador.posicao) if jogador else None,
                "campeao": _campeao(acao.campeao, catalogo),
                "intencao": _campeao(jogador.intencao, catalogo) if jogador else None,
                "estado": estado,
            }
        )
    return ordem


def _selecao(
    selecao: Selecao,
    recebida_em: float,
    agora: float,
    catalogo: Catalogo,
    feiticos: Mapping[int, str],
) -> dict:
    restante = selecao.timer.ms_restantes / 1000 - (agora - recebida_em)
    vez = selecao.minha_vez
    return {
        "etapa": selecao.timer.etapa.value,
        "planejamento": selecao.em_planejamento,
        "segundos_restantes": None if selecao.timer.infinito else max(0, round(restante)),
        "minha_vez": {"id": vez.id, "tipo": vez.tipo.value, "campeao": vez.campeao}
        if vez
        else None,
        "ordem_picks": _ordem_picks(selecao, catalogo),
        "aliados": [_jogador(j, selecao, catalogo, feiticos) for j in selecao.aliados],
        "inimigos": [_jogador(j, selecao, catalogo, feiticos) for j in selecao.inimigos],
        "bans": {
            "aliados": [_campeao(i, catalogo) for i in selecao.bans(aliados=True)],
            "inimigos": [_campeao(i, catalogo) for i in selecao.bans(aliados=False)],
        },
        "aram": selecao.eh_aram,
        "banco": [_campeao(i, catalogo) for i in selecao.banco if i != SEM_CAMPEAO],
        "rerolls": selecao.rerolls if selecao.pode_rerolar else 0,
    }


def visao_de(estado: Estado) -> dict[str, Any]:
    """O estado atual como a página recebe (em /api/estado, nas ações e no SSE)."""
    nomes = {f.id: f.nome for f in estado.feiticos}
    return visao(estado.atual, estado.catalogo, estado.agora(), nomes)


def visao(
    retrato: Retrato,
    catalogo: Catalogo,
    agora: float,
    feiticos: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    """`agora` é o relógio monotônico do `Estado`, para calcular os tempos restantes.
    `feiticos` dá os nomes dos feitiços (id → nome)."""
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
        "passos": passos(retrato, catalogo, feiticos or {}),
        "selecao": (
            _selecao(retrato.selecao, retrato.selecao_recebida_em, agora, catalogo, feiticos or {})
            if retrato.selecao is not None
            else None
        ),
    }
