"""Dados da simulação (`--simular`): campeões, runas e a sessão de uma escolha alternada.

O formato imita o da LCU real (ver tests/fixtures/gravacoes/), com 10 jogadores; você
é a célula 2, no meio.
"""

from __future__ import annotations

from typing import Any

MINHA_CELULA = 2
POSICOES = ["top", "jungle", "middle", "bottom", "utility"]

CAMPEOES = {
    1: "Annie", 11: "Master Yi", 17: "Teemo", 22: "Ashe", 25: "Morgana", 32: "Amumu",
    51: "Caitlyn", 53: "Blitzcrank", 64: "Lee Sin", 84: "Akali", 86: "Garen", 89: "Leona",
    99: "Lux", 103: "Ahri", 104: "Graves", 117: "Lulu", 119: "Draven", 121: "Kha'Zix",
    141: "Kayn", 145: "Kai'Sa", 157: "Yasuo", 222: "Jinx", 236: "Lucian", 238: "Zed",
    245: "Ekko", 266: "Aatrox", 412: "Thresh", 497: "Rakan", 498: "Xayah", 777: "Yone",
}  # fmt: skip

ESTILOS = {8000: "Precisão", 8100: "Dominação", 8200: "Feitiçaria", 8300: "Inspiração",
           8400: "Determinação"}  # fmt: skip
FEITICOS = {1: "Purificar", 3: "Exaustão", 4: "Flash", 6: "Fantasma", 7: "Curar", 11: "Golpear",
            12: "Teleporte", 13: "Clareza", 14: "Incendiar", 21: "Barreira"}  # fmt: skip
_SO_NO_RIFT, _SO_NO_ARAM = {11, 12}, {13}


def feiticos() -> list[dict[str, Any]]:
    """A lista de feitiços no formato da LCU, com os modos (sem ícones na simulação)."""
    return [
        {
            "id": i,
            "name": n,
            "gameModes": [m for m, fora in (("CLASSIC", _SO_NO_ARAM), ("ARAM", _SO_NO_RIFT))
                          if i not in fora],
        }
        for i, n in FEITICOS.items()
    ]  # fmt: skip


def _recomendacao(principal, nome, descricao, secundario, runas, feiticos) -> dict[str, Any]:
    return {
        "primaryPerkStyleId": principal,
        "secondaryPerkStyleId": secundario,
        "summonerSpellIds": feiticos,
        "keystone": {"id": runas[0], "name": nome, "recommendationDescriptor": descricao},
        "perks": [{"id": r} for r in runas],
    }


# As mesmas 3 recomendações para qualquer campeão, marcadas como exemplo na página
# (no cliente real elas dependem do campeão e da posição).
RUNAS_RECOMENDADAS = [
    _recomendacao(8100, "Eletrocutar", "Exemplo da simulação", 8200,
                  [8112, 8139, 8140, 8106, 8226, 8210, 5005, 5008, 5001], [4, 14]),
    _recomendacao(8100, "Eletrocutar", "Exemplo da simulação", 8300,
                  [8112, 8139, 8140, 8106, 8345, 8347, 5005, 5008, 5001], [4, 14]),
    _recomendacao(8200, "Invocar Aery", "Exemplo da simulação", 8000,
                  [8214, 8226, 8210, 8237, 9111, 8014, 5005, 5008, 5001], [12, 4]),
]  # fmt: skip

# Ordem dos picks na escolha alternada: ids das ações por turno.
TURNOS_DE_PICK = [(11,), (12, 13), (14, 15), (16, 17), (18, 19), (20,)]
ACAO_REVELAR_BANS = 100


def _jogador(celula: int) -> dict[str, Any]:
    aliado = celula < 5
    eu = celula == MINHA_CELULA
    escondido = celula == 3  # um aliado com nome escondido, como nas ranqueadas
    nome = "Você" if eu else (f"Aliado{celula + 1}" if aliado and not escondido else "")
    return {
        "cellId": celula,
        "team": 1 if aliado else 2,
        "assignedPosition": POSICOES[celula] if aliado else "",
        "championId": 0,
        "championPickIntent": 0,
        "gameName": nome,
        "tagLine": "SIM" if nome else "",
        "spell1Id": 4,
        "spell2Id": 14,
    }


def _acao(id_: int, celula: int, tipo: str) -> dict[str, Any]:
    return {
        "id": id_,
        "actorCellId": celula,
        "championId": 0,
        "completed": False,
        "isAllyAction": celula < 5,
        "isInProgress": False,
        "type": tipo,
    }


def sessao_inicial() -> dict[str, Any]:
    """Sessão no começo do planejamento: os 10 bans já "em andamento", como na fila real."""
    bans = [_acao(celula + 1, celula, "ban") for celula in range(10)]
    for ban in bans:
        ban["isInProgress"] = True
    turnos: list[list[dict[str, Any]]] = [bans, [_acao(ACAO_REVELAR_BANS, -1, "ten_bans_reveal")]]
    celulas_por_pick = {11: 0, 12: 5, 13: 6, 14: 1, 15: 2, 16: 7, 17: 8, 18: 3, 19: 4, 20: 9}
    for turno in TURNOS_DE_PICK:
        turnos.append([_acao(id_, celulas_por_pick[id_], "pick") for id_ in turno])
    return {
        "localPlayerCellId": MINHA_CELULA,
        "isCustomGame": False,
        "queueId": 400,
        "benchEnabled": False,
        "benchChampions": [],
        "allowRerolling": False,
        "rerollsRemaining": 0,
        "myTeam": [_jogador(c) for c in range(5)],
        "theirTeam": [_jogador(c) for c in range(5, 10)],
        "actions": turnos,
        "timer": {"phase": "PLANNING", "adjustedTimeLeftInPhase": 0, "isInfinite": False},
    }


def acoes(sessao: dict[str, Any]) -> list[dict[str, Any]]:
    return [acao for turno in sessao["actions"] for acao in turno]


def jogador(sessao: dict[str, Any], celula: int) -> dict[str, Any]:
    return next(j for j in sessao["myTeam"] + sessao["theirTeam"] if j["cellId"] == celula)
