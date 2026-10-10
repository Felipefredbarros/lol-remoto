"""Cliente da LCU (API local do cliente do LoL): REST por HTTPS e eventos por WebSocket.

O TLS é verificado contra o certificado raiz da Riot (docs/decisoes/0004).
"""

from __future__ import annotations

import base64
import json
import logging
import ssl
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from lol_remoto.plataforma.lockfile import Credenciais
from lol_remoto.plataforma.websocket import ClienteWebSocket

log = logging.getLogger(__name__)

CERTIFICADO_RIOT = Path(__file__).with_name("riotgames.pem")

# Caminhos usados pelo app.
FASE = "/lol-gameflow/v1/gameflow-phase"
SESSAO_SELECAO = "/lol-champ-select/v1/session"
READY_CHECK = "/lol-matchmaking/v1/ready-check"
EVENTOS_ASSINADOS = (FASE, SESSAO_SELECAO, READY_CHECK)

_MENSAGEM_EVENTO = 8  # tipo WAMP "EVENT"; 0 é a boas-vindas, ignorada


class ErroLcu(RuntimeError):
    """A LCU recusou o pedido ou não está acessível."""

    def __init__(self, mensagem: str, status: int | None = None) -> None:
        super().__init__(mensagem)
        self.status = status


@dataclass(frozen=True)
class Evento:
    uri: str
    tipo: str  # "Create", "Update" ou "Delete"
    dados: Any


class Lcu(Protocol):
    def get(self, caminho: str) -> Any:
        """JSON da resposta, ou None se o recurso não existe agora (404)."""

    def enviar(self, metodo: str, caminho: str, corpo: Any = None) -> Any:
        """POST/PATCH/PUT/DELETE. Levanta `ErroLcu` se a LCU recusar."""

    def get_bytes(self, caminho: str) -> bytes:
        """Conteúdo binário (ex.: ícone de campeão)."""

    def eventos(self, caminhos: Iterable[str]) -> Iterator[Evento]:
        """Assina os caminhos e produz eventos até a conexão cair (`ConexaoFechada`)."""

    def fechar(self) -> None:
        """Encerra a conexão de eventos (destrava `eventos` em outra thread)."""


def contexto_tls() -> ssl.SSLContext:
    contexto = ssl.create_default_context(cafile=str(CERTIFICADO_RIOT))
    # O certificado da Riot não tem Authority Key Identifier; o Python 3.13+ recusa isso por
    # padrão. Cadeia, validade e nome (127.0.0.1) continuam verificados.
    contexto.verify_flags &= ~ssl.VERIFY_X509_STRICT
    return contexto


def nome_do_evento(caminho: str) -> str:
    """'/lol-gameflow/v1/gameflow-phase' → 'OnJsonApiEvent_lol-gameflow_v1_gameflow-phase'."""
    return "OnJsonApiEvent" + caminho.replace("/", "_")


def evento_de(mensagem: str) -> Evento | None:
    """Interpreta uma mensagem WAMP; None para o que não for evento da API."""
    try:
        dados = json.loads(mensagem)
    except json.JSONDecodeError:
        return None
    if not (isinstance(dados, list) and len(dados) >= 3 and dados[0] == _MENSAGEM_EVENTO):
        return None
    corpo = dados[2]
    if not isinstance(corpo, dict) or not isinstance(corpo.get("uri"), str):
        return None
    return Evento(uri=corpo["uri"], tipo=str(corpo.get("eventType", "")), dados=corpo.get("data"))


class LcuHttp:
    HOST = "127.0.0.1"

    def __init__(
        self,
        credenciais: Credenciais,
        contexto: ssl.SSLContext | None = None,
        tempo_limite: float = 5,
    ) -> None:
        self._credenciais = credenciais
        self._tls = credenciais.protocolo == "https"
        self._contexto = (contexto or contexto_tls()) if self._tls else None
        self._tempo_limite = tempo_limite
        self._base = f"{credenciais.protocolo}://{self.HOST}:{credenciais.porta}"
        senha = base64.b64encode(f"riot:{credenciais.senha}".encode()).decode()
        self._autorizacao = f"Basic {senha}"
        self._ws: ClienteWebSocket | None = None

    def _requisitar(self, metodo: str, caminho: str, corpo: Any = None) -> tuple[int, bytes]:
        dados = None if corpo is None else json.dumps(corpo).encode()
        cabecalhos = {"Authorization": self._autorizacao, "Accept": "application/json"}
        if dados is not None:
            cabecalhos["Content-Type"] = "application/json"
        pedido = urllib.request.Request(
            self._base + caminho, data=dados, method=metodo, headers=cabecalhos
        )
        try:
            with urllib.request.urlopen(
                pedido, context=self._contexto, timeout=self._tempo_limite
            ) as resposta:
                return resposta.status, resposta.read()
        except urllib.error.HTTPError as erro:
            return erro.code, erro.read()
        except (urllib.error.URLError, OSError) as erro:
            motivo = getattr(erro, "reason", erro)
            raise ErroLcu(f"Cliente do LoL indisponível: {motivo}") from erro

    @staticmethod
    def _json(conteudo: bytes) -> Any:
        try:
            return json.loads(conteudo) if conteudo else None
        except json.JSONDecodeError as erro:
            raise ErroLcu("A LCU respondeu algo que não é JSON.") from erro

    @classmethod
    def _erro(cls, metodo: str, caminho: str, status: int, conteudo: bytes) -> ErroLcu:
        try:
            mensagem = cls._json(conteudo).get("message")
        except (ErroLcu, AttributeError):
            mensagem = None
        return ErroLcu(f"{metodo} {caminho} → {status}: {mensagem or 'erro na LCU'}", status)

    def get(self, caminho: str) -> Any:
        status, conteudo = self._requisitar("GET", caminho)
        if status == 404:
            return None
        if not 200 <= status < 300:
            raise self._erro("GET", caminho, status, conteudo)
        return self._json(conteudo)

    def enviar(self, metodo: str, caminho: str, corpo: Any = None) -> Any:
        status, conteudo = self._requisitar(metodo, caminho, corpo)
        if not 200 <= status < 300:
            raise self._erro(metodo, caminho, status, conteudo)
        return self._json(conteudo)

    def get_bytes(self, caminho: str) -> bytes:
        status, conteudo = self._requisitar("GET", caminho)
        if not 200 <= status < 300:
            raise ErroLcu(f"GET {caminho} → {status}", status)
        return conteudo

    def eventos(self, caminhos: Iterable[str]) -> Iterator[Evento]:
        self._ws = ClienteWebSocket.conectar(
            self.HOST,
            self._credenciais.porta,
            cabecalhos={"Authorization": self._autorizacao},
            contexto_ssl=self._contexto,
            tempo_limite=self._tempo_limite,
        )
        for caminho in caminhos:
            self._ws.enviar_texto(json.dumps([5, nome_do_evento(caminho)]))
        while True:
            evento = evento_de(self._ws.receber())
            if evento is not None:
                yield evento

    def fechar(self) -> None:
        if self._ws is not None:
            self._ws.fechar()
