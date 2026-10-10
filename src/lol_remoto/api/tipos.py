"""Tipos da API: pedido, resposta, dependências e erros comuns às rotas."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lol_remoto.api.visao import visao
from lol_remoto.plataforma.ntfy import Notificador
from lol_remoto.servicos.acoes import ServicoAcoes
from lol_remoto.servicos.autenticacao import ServicoAutenticacao
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.sessoes import ServicoSessoes
from lol_remoto.servicos.tokens import ServicoTokens

COOKIE = "lolremoto_sessao"  # com prefixo: cookies não são separados por porta (ADR 0006)


class RequisicaoInvalida(ValueError):
    """O corpo da requisição não é um JSON de objeto, ou falta um campo."""


class NaoAutenticado(PermissionError):
    """Sem sessão válida (ou token de uso único)."""


@dataclass(frozen=True)
class Pedido:
    corpo: dict[str, Any] = field(default_factory=dict)
    origem: str = ""  # IP de quem pediu
    sessao: str | None = None  # token do cookie
    consulta: dict[str, str] = field(default_factory=dict)  # ?chave=valor


@dataclass(frozen=True)
class Resposta:
    status: int
    dados: dict[str, Any]
    cabecalhos: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Dependencias:
    estado: Estado
    acoes: ServicoAcoes
    autenticacao: ServicoAutenticacao
    sessoes: ServicoSessoes
    tokens: ServicoTokens
    notificador: Notificador


Rota = Callable[[Dependencias, Pedido], Resposta]


def exigir_sessao(deps: Dependencias, pedido: Pedido) -> None:
    if not deps.sessoes.valida(pedido.sessao):
        raise NaoAutenticado("Entre com o PIN.")


def resposta_estado(deps: Dependencias) -> Resposta:
    """A maioria das rotas devolve o estado atualizado, igual ao de /api/estado."""
    return Resposta(200, visao(deps.estado.atual, deps.estado.catalogo, deps.estado.agora()))
