"""Feitiços de invocador (`/lol-game-data/assets/v1/summoner-spells.json`): quais valem no
modo e como fica o par D/F quando você troca um deles (docs/decisoes/0010).
"""

from __future__ import annotations

from dataclasses import dataclass

FLASH = 4
SLOTS = ("d", "f")
PREFIXO_ICONE = "/lol-game-data/assets/"

# Reserva, se o cliente não mandar `gameModes`: os feitiços de cada modo em 10/2026.
_POR_MODO = {
    "CLASSIC": frozenset({1, 3, 4, 6, 7, 11, 12, 14, 21}),
    "ARAM": frozenset({1, 3, 4, 6, 7, 13, 14, 21, 32}),
}


class FeiticoIndisponivel(ValueError):
    """O feitiço não existe ou não vale neste modo."""


@dataclass(frozen=True)
class Feitico:
    id: int
    nome: str
    modos: frozenset[str] | None  # None quando o cliente não informa
    icone: str | None  # caminho na LCU, só dentro de /lol-game-data/assets/


def _int(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def feiticos_de(dados: object) -> list[Feitico]:
    """Converte a lista da LCU; itens malformados e sem nome são ignorados."""
    resultado = []
    for item in dados if isinstance(dados, list) else []:
        if not isinstance(item, dict):
            continue
        id_, nome = _int(item.get("id")), item.get("name")
        if id_ is None or id_ <= 0 or not isinstance(nome, str) or not nome:
            continue
        modos = item.get("gameModes")
        icone = item.get("iconPath")
        resultado.append(
            Feitico(
                id=id_,
                nome=nome,
                modos=frozenset(m for m in modos if isinstance(m, str))
                if isinstance(modos, list)
                else None,
                icone=icone if isinstance(icone, str) and icone.startswith(PREFIXO_ICONE) else None,
            )
        )
    return resultado


def disponiveis(feiticos: list[Feitico], aram: bool) -> list[Feitico]:
    """Os feitiços do modo (Summoner's Rift ou ARAM), em ordem alfabética."""
    modo = "ARAM" if aram else "CLASSIC"
    validos = [
        f for f in feiticos if (modo in f.modos if f.modos is not None else f.id in _POR_MODO[modo])
    ]
    return sorted(validos, key=lambda f: f.nome)


def trocar(atuais: tuple[int, int], slot: str, novo: int) -> tuple[int, int]:
    """Novo par (D, F). Escolher no D o que está no F troca os dois, como no cliente."""
    if slot not in SLOTS:
        raise FeiticoIndisponivel("Escolha o feitiço do D ou do F.")
    d, f = atuais
    if slot == "d":
        return (novo, d) if novo == f else (novo, f)
    return (f, novo) if novo == d else (d, novo)


def flash_no_d(feiticos: tuple[int, ...]) -> tuple[int, ...]:
    """O Felipe usa o Flash no D: se uma sugestão trouxer o Flash no F, inverte."""
    if len(feiticos) == 2 and feiticos[1] == FLASH:
        return (FLASH, feiticos[0])
    return feiticos
