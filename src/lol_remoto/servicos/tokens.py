"""Tokens de uso único dos botões Aceitar/Recusar da notificação (docs/decisoes/0005).

Cada token vale por poucos segundos, só uma vez e só para responder à partida encontrada.
Ficam só em memória.
"""

from __future__ import annotations

import hashlib
import secrets
import threading
import time
from collections.abc import Callable

VALIDADE_PADRAO = 15.0  # segundos; a partida encontrada dura uns 10


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class ServicoTokens:
    def __init__(
        self, validade: float = VALIDADE_PADRAO, relogio: Callable[[], float] = time.monotonic
    ) -> None:
        self._validade = validade
        self._relogio = relogio
        self._expira_em: dict[str, float] = {}
        self._trava = threading.Lock()

    def gerar(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._trava:
            agora = self._relogio()
            self._expira_em = {h: e for h, e in self._expira_em.items() if e > agora}
            self._expira_em[_hash(token)] = agora + self._validade
        return token

    def consumir(self, token: object) -> bool:
        """True se o token existe e ainda vale. Depois disso ele não vale mais."""
        if not isinstance(token, str) or not token:
            return False
        with self._trava:
            expira_em = self._expira_em.pop(_hash(token), None)
            return expira_em is not None and expira_em > self._relogio()

    def invalidar_todos(self) -> None:
        with self._trava:
            self._expira_em.clear()
