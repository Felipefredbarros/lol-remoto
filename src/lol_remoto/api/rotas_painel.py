"""Rotas do painel: login, estado, modo ausente, lista de campeões e teste de notificação."""

from __future__ import annotations

import logging

from lol_remoto.api.tipos import (
    COOKIE,
    Dependencias,
    Pedido,
    RequisicaoInvalida,
    Resposta,
    exigir_sessao,
    resposta_estado,
)
from lol_remoto.dominio.selecao import TipoAcao
from lol_remoto.plataforma.ntfy import Notificacao

log = logging.getLogger(__name__)


def _cookie(token: str, segundos: int) -> tuple[tuple[str, str], ...]:
    valor = f"{COOKIE}={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age={segundos}"
    return (("Set-Cookie", valor),)


def entrar(deps: Dependencias, pedido: Pedido) -> Resposta:
    deps.autenticacao.verificar(pedido.corpo.get("pin"), pedido.origem)
    log.info("Login vindo de %s", pedido.origem)
    token = deps.sessoes.criar()
    estado = resposta_estado(deps)
    return Resposta(200, estado.dados, _cookie(token, deps.sessoes.segundos_de_validade))


def sair(deps: Dependencias, pedido: Pedido) -> Resposta:
    deps.sessoes.encerrar(pedido.sessao)
    return Resposta(200, {"ok": True}, _cookie("", 0))


def estado(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    return resposta_estado(deps)


def campeoes(deps: Dependencias, pedido: Pedido) -> Resposta:
    """Campeões disponíveis agora para ban ou pick (?tipo=ban|pick), em ordem alfabética."""
    exigir_sessao(deps, pedido)
    tipo = TipoAcao.BAN if pedido.consulta.get("tipo") == "ban" else TipoAcao.PICK
    lista = deps.estado.catalogo.buscar(permitidos=deps.acoes.disponiveis(tipo))
    log.info("Grade de %s: %d campeões", tipo.value, len(lista))  # diagnóstico do ban vazio
    return Resposta(
        200, {"tipo": tipo.value, "campeoes": [{"id": c.id, "nome": c.nome} for c in lista]}
    )


def ausente(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    ativo = pedido.corpo.get("ativo")
    if not isinstance(ativo, bool):
        raise RequisicaoInvalida("Envie 'ativo' como true ou false.")
    deps.estado.definir_ausente(ativo)
    return resposta_estado(deps)


def testar_notificacao(deps: Dependencias, pedido: Pedido) -> Resposta:
    exigir_sessao(deps, pedido)
    deps.notificador.enviar(
        Notificacao("LoL Remoto", "Teste: as notificações estão chegando.", tags=("bell",))
    )
    return Resposta(200, {"ok": True})
