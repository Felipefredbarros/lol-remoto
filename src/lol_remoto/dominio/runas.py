"""Runas recomendadas pelo próprio cliente (`/lol-perks/v1/recommended-pages`) e a página
que o app grava. Formato conferido no cliente real (tests/fixtures/runas_recomendadas.json).
"""

from __future__ import annotations

from dataclasses import dataclass

NOME_PAGINA = "LoL Remoto"  # a página que o app pode sobrescrever (ADR 0009)
FLASH = 4
MAPA_SUMMONERS_RIFT = 11
MAPA_ARAM = 12


@dataclass(frozen=True)
class Recomendacao:
    indice: int  # 0, 1 ou 2, na ordem do cliente
    estilo_principal: int
    estilo_secundario: int
    runas: tuple[int, ...]  # a runa principal (keystone) primeiro
    principal: str  # nome da runa principal, ex.: "Eletrocutar"
    descricao: str  # ex.: "Dano de combo"
    feiticos: tuple[int, ...]  # já com o Flash no D


def _int(valor: object) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def flash_no_d(feiticos: tuple[int, ...]) -> tuple[int, ...]:
    """O Felipe usa o Flash no D: se a recomendação trouxer o Flash no F, inverte."""
    if len(feiticos) == 2 and feiticos[1] == FLASH:
        return (FLASH, feiticos[0])
    return feiticos


def recomendacoes_de(dados: object) -> list[Recomendacao]:
    """Converte a lista da LCU; recomendações malformadas são ignoradas."""
    resultado: list[Recomendacao] = []
    for indice, item in enumerate(dados if isinstance(dados, list) else []):
        if not isinstance(item, dict):
            continue
        principal, secundario = (
            _int(item.get("primaryPerkStyleId")),
            _int(item.get("secondaryPerkStyleId")),
        )
        perks = item.get("perks") if isinstance(item.get("perks"), list) else []
        runas = tuple(r for p in perks if isinstance(p, dict) and (r := _int(p.get("id"))))
        if principal is None or secundario is None or not runas:
            continue
        keystone = item.get("keystone") if isinstance(item.get("keystone"), dict) else {}
        feiticos = tuple(f for f in item.get("summonerSpellIds") or [] if _int(f) is not None)
        resultado.append(
            Recomendacao(
                indice=indice,
                estilo_principal=principal,
                estilo_secundario=secundario,
                runas=runas,
                principal=str(keystone.get("name") or ""),
                descricao=str(keystone.get("recommendationDescriptor") or ""),
                feiticos=flash_no_d(feiticos),
            )
        )
    return resultado


def posicao_lcu(posicao: str) -> str:
    """'middle' (sessão da seleção) → 'MIDDLE'; sem posição (ARAM, às cegas) → 'NONE'."""
    return posicao.upper() if posicao else "NONE"


def mapa(aram: bool) -> int:
    return MAPA_ARAM if aram else MAPA_SUMMONERS_RIFT


def eh_pagina_do_app(pagina: object) -> bool:
    if not isinstance(pagina, dict) or not isinstance(pagina.get("name"), str):
        return False
    return pagina["name"].strip().lower() == NOME_PAGINA.lower()


def corpo_pagina(recomendacao: Recomendacao, nome: str) -> dict:
    """Corpo de POST/PUT em /lol-perks/v1/pages; `current` já deixa a página selecionada."""
    return {
        "name": nome,
        "primaryStyleId": recomendacao.estilo_principal,
        "subStyleId": recomendacao.estilo_secundario,
        "selectedPerkIds": list(recomendacao.runas),
        "current": True,
    }
