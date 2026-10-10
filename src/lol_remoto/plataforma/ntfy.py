"""Notificações push pelo ntfy (https://ntfy.sh), com botões de ação `http`.

Ver docs/decisoes/0005: o tópico é secreto, então nunca aparece em logs nem em mensagens
de erro.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)

PRIORIDADE_MINIMA, PRIORIDADE_PADRAO, PRIORIDADE_MAXIMA = 1, 3, 5


class ErroNotificacao(RuntimeError):
    """O servidor do ntfy não aceitou a notificação ou não está acessível."""


@dataclass(frozen=True)
class BotaoHttp:
    """Botão que faz o app do ntfy enviar um POST JSON a partir do celular."""

    rotulo: str
    url: str
    corpo: dict[str, Any]


@dataclass(frozen=True)
class Notificacao:
    titulo: str
    mensagem: str
    prioridade: int = PRIORIDADE_PADRAO
    tags: tuple[str, ...] = ()  # emojis do ntfy, ex.: "rotating_light"
    link: str | None = None  # abre ao tocar na notificação
    botoes: tuple[BotaoHttp, ...] = ()


class Notificador(Protocol):
    def enviar(self, notificacao: Notificacao) -> None:
        """Publica a notificação. Levanta `ErroNotificacao` se falhar."""


def corpo_ntfy(topico: str, notificacao: Notificacao) -> dict[str, Any]:
    """JSON de publicação do ntfy (POST na raiz do servidor)."""
    corpo: dict[str, Any] = {
        "topic": topico,
        "title": notificacao.titulo,
        "message": notificacao.mensagem,
        "priority": max(PRIORIDADE_MINIMA, min(PRIORIDADE_MAXIMA, notificacao.prioridade)),
    }
    if notificacao.tags:
        corpo["tags"] = list(notificacao.tags)
    if notificacao.link:
        corpo["click"] = notificacao.link
    if notificacao.botoes:
        corpo["actions"] = [
            {
                "action": "http",
                "label": botao.rotulo,
                "url": botao.url,
                "method": "POST",
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(botao.corpo),
                "clear": True,  # some a notificação depois do toque
            }
            for botao in notificacao.botoes
        ]
    return corpo


class NotificadorNtfy:
    def __init__(
        self, servidor: str, topico: str, token: str | None = None, tempo_limite: float = 5
    ) -> None:
        self._servidor = servidor.rstrip("/")
        self._topico = topico
        self._token = token
        self._tempo_limite = tempo_limite

    def enviar(self, notificacao: Notificacao) -> None:
        cabecalhos = {"Content-Type": "application/json"}
        if self._token:
            cabecalhos["Authorization"] = f"Bearer {self._token}"
        pedido = urllib.request.Request(
            self._servidor + "/",
            data=json.dumps(corpo_ntfy(self._topico, notificacao)).encode(),
            headers=cabecalhos,
            method="POST",
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self._tempo_limite) as resposta:
                resposta.read()
        except urllib.error.HTTPError as erro:
            raise ErroNotificacao(f"O ntfy ({self._servidor}) recusou: HTTP {erro.code}") from None
        except (urllib.error.URLError, OSError) as erro:
            motivo = getattr(erro, "reason", erro)
            raise ErroNotificacao(f"ntfy ({self._servidor}) inacessível: {motivo}") from None
        log.info("Notificação enviada: %s", notificacao.titulo)


class NotificadorFalso:
    """Guarda as notificações em vez de enviá-las (testes e `--simular` sem ntfy)."""

    def __init__(self, falhar: bool = False) -> None:
        self.enviadas: list[Notificacao] = []
        self.falhar = falhar

    def enviar(self, notificacao: Notificacao) -> None:
        if self.falhar:
            raise ErroNotificacao("Falha simulada.")
        self.enviadas.append(notificacao)
        log.info("[simulação] Notificação: %s — %s", notificacao.titulo, notificacao.mensagem)
