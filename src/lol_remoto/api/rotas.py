"""Registro das rotas da API JSON e tradução de exceções em status HTTP.

Independente do servidor HTTP: recebe método, caminho, corpo e um `Pedido`; devolve
`Resposta`. Para adicionar uma rota: escreva a função em `rotas_painel.py` ou
`rotas_cliente.py` e registre-a em `ROTAS`. Exceções novas vão em `_STATUS_POR_ERRO`.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from lol_remoto.api import rotas_cliente, rotas_painel
from lol_remoto.api.tipos import (
    Dependencias,
    NaoAutenticado,
    Pedido,
    RequisicaoInvalida,
    Resposta,
    Rota,
)
from lol_remoto.dominio.fase import ForaDeFase
from lol_remoto.dominio.feiticos import FeiticoIndisponivel
from lol_remoto.plataforma.lcu import ErroLcu
from lol_remoto.plataforma.ntfy import ErroNotificacao
from lol_remoto.servicos.acoes import AcaoIndisponivel, CampeaoIndisponivel, ClienteDesconectado
from lol_remoto.servicos.autenticacao import AcessoBloqueado, PinIncorreto
from lol_remoto.servicos.runas import EscolhaInvalida, SemPaginaLivre

log = logging.getLogger(__name__)

ROTAS: dict[tuple[str, str], Rota] = {
    ("POST", "/api/entrar"): rotas_painel.entrar,
    ("POST", "/api/sair"): rotas_painel.sair,
    ("GET", "/api/estado"): rotas_painel.estado,
    ("GET", "/api/campeoes"): rotas_painel.campeoes,
    ("POST", "/api/ausente"): rotas_painel.ausente,
    ("POST", "/api/testar-notificacao"): rotas_painel.testar_notificacao,
    ("POST", "/api/ready-check/aceitar"): rotas_cliente.aceitar,
    ("POST", "/api/ready-check/recusar"): rotas_cliente.recusar,
    ("POST", "/api/selecao/marcar"): rotas_cliente.marcar,
    ("POST", "/api/selecao/confirmar"): rotas_cliente.confirmar,
    ("POST", "/api/selecao/aram/reroll"): rotas_cliente.rerolar,
    ("POST", "/api/selecao/aram/trocar"): rotas_cliente.trocar_do_banco,
    ("GET", "/api/runas"): rotas_cliente.runas,
    ("POST", "/api/runas/aplicar"): rotas_cliente.aplicar_runas,
    ("GET", "/api/feiticos"): rotas_cliente.feiticos,
    ("POST", "/api/feiticos"): rotas_cliente.trocar_feitico,
}

_STATUS_POR_ERRO: dict[type[Exception], int] = {
    RequisicaoInvalida: 400,
    CampeaoIndisponivel: 400,
    EscolhaInvalida: 400,
    FeiticoIndisponivel: 400,
    NaoAutenticado: 401,
    PinIncorreto: 401,
    ForaDeFase: 409,
    AcaoIndisponivel: 409,
    SemPaginaLivre: 409,
    AcessoBloqueado: 429,
    ErroLcu: 502,
    ErroNotificacao: 502,
    ClienteDesconectado: 503,
}


def ler_corpo(corpo: bytes) -> dict[str, Any]:
    if not corpo:
        return {}
    try:
        dados = json.loads(corpo)
    except (json.JSONDecodeError, UnicodeDecodeError) as erro:
        raise RequisicaoInvalida("O corpo da requisição não é um JSON válido.") from erro
    if not isinstance(dados, dict):
        raise RequisicaoInvalida("O corpo da requisição deve ser um objeto JSON.")
    return dados


def tratar(metodo: str, caminho: str, corpo: bytes, pedido: Pedido, deps: Dependencias) -> Resposta:
    """`pedido` chega sem corpo; o corpo bruto é lido aqui (JSON inválido vira 400)."""
    rota = ROTAS.get((metodo, caminho))
    if rota is None:
        return Resposta(404, {"erro": "Rota não encontrada."})
    try:
        completo = Pedido(ler_corpo(corpo), pedido.origem, pedido.sessao, pedido.consulta)
        return rota(deps, completo)
    except tuple(_STATUS_POR_ERRO) as erro:
        status = next(s for tipo, s in _STATUS_POR_ERRO.items() if isinstance(erro, tipo))
        if status >= 500:
            log.warning("%s %s falhou: %s", metodo, caminho, erro)
        # "codigo" deixa a página distinguir erros com o mesmo status (ex.: 409).
        return Resposta(status, {"erro": str(erro), "codigo": type(erro).__name__})
    except Exception:
        log.exception("Erro inesperado em %s %s", metodo, caminho)
        return Resposta(500, {"erro": "Erro interno no servidor."})
