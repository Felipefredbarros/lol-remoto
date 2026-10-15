"""Etapas da partida para a página sequencial: fila → partida → intenção → ban → pick →
runas → carregando. Só lê o `Retrato`; a página desenha a barra e o histórico com isso.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from lol_remoto.dominio.campeoes import SEM_CAMPEAO, Catalogo
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.selecao import Acao, Selecao, TipoAcao
from lol_remoto.servicos.estado import Retrato

NOMES = {
    "fila": "Fila",
    "partida": "Partida",
    "selecao": "Seleção",
    "intencao": "Intenção",
    "ban": "Ban",
    "pick": "Pick",
    "campeao": "Campeão",
    "runas": "Runas",
    "carregando": "Carregando",
}
_ANTES_DA_SELECAO = ["fila", "partida", "selecao", "carregando"]


def _minha(selecao: Selecao, tipo: TipoAcao) -> Acao | None:
    return next(
        (a for a in selecao.acoes if a.tipo is tipo and a.celula == selecao.minha_celula), None
    )


def _ids(selecao: Selecao) -> list[str]:
    """ARAM: o campeão é sorteado. Com ban (escolha alternada): intenção e ban antes do pick."""
    if selecao.eh_aram:
        meio = ["campeao"]
    elif _minha(selecao, TipoAcao.BAN):
        meio = ["intencao", "ban", "pick"]
    else:
        meio = ["pick"]
    return ["fila", "partida", *meio, "runas", "carregando"]


def _atual_na_selecao(selecao: Selecao) -> str:
    if selecao.eh_aram:
        return "runas"
    ban, pick = _minha(selecao, TipoAcao.BAN), _minha(selecao, TipoAcao.PICK)
    if ban and selecao.em_planejamento:
        return "intencao"
    if ban and not ban.concluida:
        return "ban"
    if pick and not pick.concluida:
        return "pick"
    return "runas"


def _nome(id_: int, catalogo: Catalogo) -> str | None:
    return None if id_ in (SEM_CAMPEAO, -1) else (catalogo.nome(id_) or f"#{id_}")


def _resumo(
    passo: str, selecao: Selecao | None, catalogo: Catalogo, feiticos: Mapping[int, str]
) -> str | None:
    eu = selecao.eu if selecao else None
    if passo == "partida":
        return "aceita"
    if selecao is None or eu is None:
        return None
    if passo == "intencao":
        # O cliente zera a intenção uns segundos depois do pick (ranqueada real, 10/2026):
        # aí não dá mais para saber qual era, e "nenhuma" seria falso.
        if eu.intencao == SEM_CAMPEAO and selecao.confirmou(eu.celula):
            return None
        return _nome(eu.intencao, catalogo) or "nenhuma"
    if passo == "ban":
        ban = _minha(selecao, TipoAcao.BAN)
        return (_nome(ban.campeao, catalogo) if ban else None) or "sem ban"
    if passo in ("pick", "campeao"):
        return _nome(eu.campeao, catalogo)
    if passo == "runas":
        nomes = [feiticos.get(f, f"#{f}") for f in eu.feiticos if f > 0]
        return " + ".join(nomes) or None
    return None


def passos(
    retrato: Retrato, catalogo: Catalogo, feiticos: Mapping[int, str]
) -> list[dict[str, Any]]:
    """Lista vazia fora do caminho fila → carregamento (lobby, em partida, fim de jogo...)."""
    selecao = retrato.selecao
    if retrato.fase is Fase.FILA:
        ids, atual = _ANTES_DA_SELECAO, "fila"
    elif retrato.fase is Fase.PARTIDA_ENCONTRADA:
        ids, atual = _ANTES_DA_SELECAO, "partida"
    elif retrato.fase is Fase.SELECAO and selecao is None:
        ids, atual = _ANTES_DA_SELECAO, "selecao"
    elif retrato.fase is Fase.SELECAO and selecao is not None:
        ids, atual = _ids(selecao), _atual_na_selecao(selecao)
    elif retrato.fase is Fase.CARREGANDO:
        ids = _ids(selecao) if selecao else _ANTES_DA_SELECAO
        atual = "carregando"
    else:
        return []

    posicao = ids.index(atual)
    resultado = []
    for i, id_ in enumerate(ids):
        estado = "feito" if i < posicao else "atual" if i == posicao else "pendente"
        resumo = _resumo(id_, selecao, catalogo, feiticos) if estado == "feito" else None
        resultado.append({"id": id_, "nome": NOMES[id_], "estado": estado, "resumo": resumo})
    return resultado
