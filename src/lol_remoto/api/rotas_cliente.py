"""Rotas que agem no cliente do LoL: partida encontrada, ban/pick, ARAM, runas e feitiços.

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


def runas(deps: Dependencias, pedido: Pedido) -> Resposta:
    """As 3 runas recomendadas pelo cliente para o meu campeão, com nomes para a página."""
    exigir_sessao(deps, pedido)
    recomendacoes = deps.runas.recomendacoes()
    estilos = deps.runas.estilos()
    feiticos = deps.feiticos.nomes()
    return Resposta(
        200,
        {
            "recomendacoes": [
                {
                    "indice": r.indice,
                    "principal": r.principal,
                    "descricao": r.descricao,
                    "estilos": f"{estilos.get(r.estilo_principal, '?')} + "
                    f"{estilos.get(r.estilo_secundario, '?')}",
                    "feiticos": [feiticos.get(f, f"#{f}") for f in r.feiticos],
                }
                for r in recomendacoes
            ]
        },
    )


def aplicar_runas(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    escolhida = deps.runas.aplicar(
        pedido.corpo.get("indice"),
        sobrescrever_atual=pedido.corpo.get("sobrescrever_atual") is True,
    )
    return Resposta(200, {"aplicada": escolhida.principal})


def feiticos(deps: Dependencias, pedido: Pedido) -> Resposta:
    """Os feitiços que valem no modo da seleção atual (os atuais vêm no estado)."""
    exigir_sessao(deps, pedido)
    lista = deps.feiticos.lista()
    return Resposta(200, {"disponiveis": [{"id": f.id, "nome": f.nome} for f in lista]})


def trocar_feitico(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    deps.feiticos.trocar(pedido.corpo.get("slot"), pedido.corpo.get("feitico"))
    return resposta_estado(deps)
