"""Rotas que agem no cliente do LoL: partida encontrada, ban/pick e ARAM.

A trava de fase ("nada dentro da partida") fica em `servicos/acoes.py`.
"""

from __future__ import annotations

from lol_remoto.api.tipos import (
    Dependencias,
    NaoAutenticado,
    Pedido,
    Resposta,
    exigir_sessao,
    resposta_estado,
)


def _sessao_ou_token(deps: Dependencias, pedido: Pedido) -> None:
    """Os botões da notificação não têm cookie: aceitam o token de uso único (ADR 0005)."""
    if deps.sessoes.valida(pedido.sessao) or deps.tokens.consumir(pedido.corpo.get("token")):
        return
    raise NaoAutenticado("Sessão ou token inválido (o botão da notificação vale uma vez).")


def aceitar(deps: Dependencias, pedido: Pedido) -> Resposta:
    _sessao_ou_token(deps, pedido)
    deps.acoes.aceitar()
    return resposta_estado(deps)


def recusar(deps: Dependencias, pedido: Pedido) -> Resposta:
    _sessao_ou_token(deps, pedido)
    deps.acoes.recusar()
    return resposta_estado(deps)


def marcar(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    deps.acoes.marcar(pedido.corpo.get("campeao"))
    return resposta_estado(deps)


def confirmar(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    deps.acoes.confirmar(pedido.corpo.get("campeao"))
    return resposta_estado(deps)


def rerolar(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    deps.acoes.rerolar()
    return resposta_estado(deps)


def trocar_do_banco(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    deps.acoes.trocar_do_banco(pedido.corpo.get("campeao"))
    return resposta_estado(deps)
