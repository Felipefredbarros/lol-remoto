"""Lockfile do cliente do LoL: porta e senha da LCU, que mudam a cada abertura do cliente.

Formato: `nome:pid:porta:senha:protocolo` (ex.: `LeagueClient:11028:49637:<senha>:https`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

PASTA_PADRAO = Path(r"C:\Riot Games\League of Legends")


class LockfileInvalido(ValueError):
    """O lockfile existe, mas não tem o formato esperado."""


@dataclass(frozen=True)
class Credenciais:
    porta: int
    senha: str = field(repr=False)  # nunca aparece em logs nem em repr()
    protocolo: str = "https"
    pid: int = 0


def interpretar(texto: str) -> Credenciais:
    partes = texto.strip().split(":")
    if len(partes) != 5:
        raise LockfileInvalido("O lockfile deveria ter 5 campos separados por ':'.")
    _nome, pid, porta, senha, protocolo = partes
    if not (porta.isdigit() and 0 < int(porta) < 65536) or not senha:
        raise LockfileInvalido("Porta ou senha inválida no lockfile.")
    if protocolo not in ("http", "https"):
        raise LockfileInvalido(f"Protocolo desconhecido no lockfile: {protocolo!r}.")
    return Credenciais(
        porta=int(porta), senha=senha, protocolo=protocolo, pid=int(pid) if pid.isdigit() else 0
    )


def ler(pasta: Path = PASTA_PADRAO) -> Credenciais | None:
    """Credenciais da LCU, ou None se o cliente estiver fechado (sem lockfile)."""
    try:
        texto = (pasta / "lockfile").read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as erro:  # ex.: o cliente está recriando o arquivo
        log.debug("Não foi possível ler o lockfile: %s", erro)
        return None
    return interpretar(texto)
