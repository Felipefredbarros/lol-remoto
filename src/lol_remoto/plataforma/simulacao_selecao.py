"""Uma escolha alternada simulada: guarda a sessão, faz os bots agirem e publica cada mudança.

Usada pela `LcuSimulada`; você é a célula 2 (meio) e age pela página.
"""

from __future__ import annotations

import copy
import random
import threading
import time
from collections.abc import Callable
from typing import Any

from lol_remoto.plataforma import simulacao as sim
from lol_remoto.plataforma.lcu import ErroLcu


class SelecaoSimulada:
    def __init__(
        self,
        publicar: Callable[[dict[str, Any] | None], None],
        fase: Callable[[str], None],
        esperar: Callable[..., None],
        parar: threading.Event,
        sorteio: random.Random,
        escala: float,
    ) -> None:
        self._publicar_dados = publicar
        self._fase = fase
        self._esperar = esperar
        self._parar = parar
        self._sorteio = sorteio
        self._escala = escala
        self._trava = threading.RLock()
        self._sessao: dict[str, Any] | None = None
        self._fim_da_etapa = 0.0  # relógio monotônico

    # ---------- o que vem da página ----------

    def _usados(self, exceto_celula: int | None = None) -> set[int]:
        """Banidos e travados (como o cliente real, que não deixa repetir no draft)."""
        return {
            a["championId"]
            for a in sim.acoes(self._sessao or {"actions": []})
            if a["completed"] and a["championId"] > 0 and a["actorCellId"] != exceto_celula
        }

    def disponiveis(self) -> list[int]:
        """O que a LCU responderia em pickable/bannable-champion-ids agora."""
        with self._trava:
            usados = self._usados(exceto_celula=sim.MINHA_CELULA)
            return [c for c in sim.CAMPEOES if c not in usados]

    def minha_acao(self, id_: int, corpo: dict[str, Any]) -> None:
        with self._trava:
            sessao = self._sessao or {"actions": []}
            acao = next((a for a in sim.acoes(sessao) if a["id"] == id_), None)
            if acao is None or acao["actorCellId"] != sim.MINHA_CELULA or acao["completed"]:
                raise ErroLcu("Ação inválida na simulação.", 400)
            campeao = corpo.get("championId", acao["championId"])
            if campeao in self._usados(exceto_celula=sim.MINHA_CELULA):
                raise ErroLcu("Campeão banido ou já escolhido (simulação).", 400)
            acao["championId"] = campeao
            eu = sim.jogador(self._sessao, sim.MINHA_CELULA)
            if self._sessao["timer"]["phase"] == "PLANNING":
                eu["championPickIntent"] = campeao
            elif acao["type"] == "pick":
                eu["championId"] = campeao
            if corpo.get("completed"):
                acao.update(completed=True, isInProgress=False)
            self._publicar()

    def feiticos(self, corpo: dict[str, Any]) -> None:
        with self._trava:
            if self._sessao is None:
                raise ErroLcu("Fora da seleção.", 400)
            eu = sim.jogador(self._sessao, sim.MINHA_CELULA)
            eu.update({k: v for k, v in corpo.items() if k in ("spell1Id", "spell2Id")})
            self._publicar()

    # ---------- roteiro ----------

    def _publicar(self) -> None:
        if self._sessao is not None:
            restante = max(0.0, (self._fim_da_etapa - time.monotonic()) / self._escala)
            self._sessao["timer"]["adjustedTimeLeftInPhase"] = int(restante * 1000)
            self._publicar_dados(copy.deepcopy(self._sessao))

    def _etapa(self, nome: str, segundos: float) -> None:
        with self._trava:
            self._sessao["timer"]["phase"] = nome
            self._fim_da_etapa = time.monotonic() + segundos * self._escala
            self._publicar()

    def _concluir(self, acao: dict[str, Any], sortear: bool = True) -> None:
        if acao["championId"] == 0 and sortear:
            usados = self._usados() | {a["championId"] for a in sim.acoes(self._sessao)}
            acao["championId"] = self._sorteio.choice([c for c in sim.CAMPEOES if c not in usados])
        acao.update(completed=True, isInProgress=False)
        if acao["type"] == "pick":
            sim.jogador(self._sessao, acao["actorCellId"])["championId"] = acao["championId"]
        self._publicar()

    def _turno(self, ids: tuple[int, ...], segundos: float) -> None:
        """Abre as ações `ids`; os bots agem em 2–5 s; você tem até o fim do tempo."""
        with self._trava:
            turno = [a for a in sim.acoes(self._sessao) if a["id"] in ids]
            for acao in turno:
                acao["isInProgress"] = True
        self._etapa("BAN_PICK", segundos)
        prazos = {a["id"]: self._sorteio.uniform(2, 5) for a in turno}
        decorrido = 0.0
        while decorrido < segundos and not self._parar.is_set():
            with self._trava:
                for acao in turno:
                    eh_bot = acao["actorCellId"] != sim.MINHA_CELULA
                    if not acao["completed"] and eh_bot and decorrido >= prazos[acao["id"]]:
                        self._concluir(acao)
                if all(a["completed"] for a in turno):
                    return
            self._esperar(0.5, acordavel=True)  # reage logo quando você confirma
            decorrido += 0.5
        with self._trava:  # tempo esgotado: o cliente trava o que estiver marcado
            for acao in turno:
                if not acao["completed"]:
                    self._concluir(acao, sortear=acao["type"] == "pick")

    def rodar(self, dodge: bool) -> bool:
        """Planejamento, bans e picks. Retorna False se alguém deu dodge na finalização."""
        with self._trava:
            self._sessao = sim.sessao_inicial()
        self._etapa("PLANNING", 10)
        self._fase("ChampSelect")
        self._esperar(10)
        self._turno(tuple(range(1, 11)), 20)  # bans simultâneos
        with self._trava:
            for acao in sim.acoes(self._sessao):
                if acao["id"] == sim.ACAO_REVELAR_BANS:
                    acao["completed"] = True
        for ids in sim.TURNOS_DE_PICK:
            self._turno(ids, 20)
        self._etapa("FINALIZATION", 8)
        self._esperar(4 if dodge else 8)
        if not dodge:
            self._etapa("GAME_STARTING", 0)
        with self._trava:
            self._sessao = None
        return not dodge
