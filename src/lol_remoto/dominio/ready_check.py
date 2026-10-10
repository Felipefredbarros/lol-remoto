"""Partida encontrada (`/lol-matchmaking/v1/ready-check`): estado e a sua resposta."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DURACAO_SEGUNDOS = 10  # o cliente dá cerca de 10 s para aceitar


class Resposta(StrEnum):
    NENHUMA = "None"
    ACEITA = "Accepted"
    RECUSADA = "Declined"


@dataclass(frozen=True)
class ReadyCheck:
    em_andamento: bool
    resposta: Resposta
    segundos_decorridos: float


def ready_check_de(dados: object) -> ReadyCheck | None:
    """None quando não há partida encontrada (a LCU devolve 404 ou um objeto vazio)."""
    if not isinstance(dados, dict) or "state" not in dados:
        return None
    try:
        resposta = Resposta(dados.get("playerResponse"))
    except ValueError:
        resposta = Resposta.NENHUMA
    decorridos = dados.get("timer")
    if isinstance(decorridos, bool) or not isinstance(decorridos, int | float):
        decorridos = 0.0
    return ReadyCheck(
        em_andamento=dados["state"] == "InProgress",
        resposta=resposta,
        segundos_decorridos=float(decorridos),
    )
