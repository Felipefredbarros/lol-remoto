"""Cliente do LoL simulado (`--simular`): fila → partida encontrada → seleção → carregando.

Reage às ações da página (aceitar, marcar, confirmar, runas, feitiços); os outros 9
jogadores são bots. A cada 3 ciclos alguém dá dodge na finalização. `escala` acelera tudo
nos testes.
"""

from __future__ import annotations

import logging
import random
import re
import threading
from typing import Any

from lol_remoto.plataforma import simulacao as sim
from lol_remoto.plataforma.lcu import FASE, READY_CHECK, SESSAO_SELECAO
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.plataforma.simulacao_selecao import SelecaoSimulada

log = logging.getLogger(__name__)

_ACAO = re.compile(r"^/lol-champ-select/v1/session/actions/(\d+)$")


def _respostas_fixas() -> dict[str, Any]:
    ids = list(sim.CAMPEOES)
    respostas: dict[str, Any] = {
        FASE: "None",
        "/lol-game-data/assets/v1/champion-summary.json": [
            {"id": i, "name": n} for i, n in sim.CAMPEOES.items()
        ],
        "/lol-champ-select/v1/pickable-champion-ids": ids,
        "/lol-champ-select/v1/bannable-champion-ids": ids,
        "/lol-perks/v1/pages": [{"id": 1, "name": "LoL Remoto", "isEditable": True}],
        "/lol-perks/v1/styles": [{"id": i, "name": n} for i, n in sim.ESTILOS.items()],
        "/lol-game-data/assets/v1/summoner-spells.json": sim.feiticos(),
    }
    for campeao in ids:
        caminho = f"/lol-perks/v1/recommended-pages/champion/{campeao}/position/MIDDLE/map/11"
        respostas[caminho] = sim.RUNAS_RECOMENDADAS
    return respostas


class LcuSimulada(LcuFalsa):
    def __init__(self, escala: float = 1.0, semente: int | None = None) -> None:
        super().__init__(_respostas_fixas())
        self._escala = escala
        self._acordar = threading.Event()
        self._parar = threading.Event()
        self._trava = threading.Lock()
        self._resposta = "None"
        self.ciclos = 0
        self.selecao = SelecaoSimulada(
            publicar=self._publicar_sessao,
            fase=self._fase,
            esperar=self._esperar,
            parar=self._parar,
            sorteio=random.Random(semente),
            escala=escala,
        )

    def enviar(self, metodo: str, caminho: str, corpo: Any = None) -> Any:
        super().enviar(metodo, caminho, corpo)  # registra em `chamadas`
        if caminho.endswith("/ready-check/accept"):
            with self._trava:
                self._resposta = "Accepted"
        elif caminho.endswith("/ready-check/decline"):
            with self._trava:
                self._resposta = "Declined"
        elif (casou := _ACAO.match(caminho)) and metodo == "PATCH":
            self.selecao.minha_acao(int(casou.group(1)), corpo or {})
        elif caminho.endswith("/session/my-selection"):
            self.selecao.feiticos(corpo or {})
        self._acordar.set()
        return None

    # ---------- roteiro ----------

    def iniciar(self) -> None:
        threading.Thread(target=self._rodar, name="simulacao", daemon=True).start()

    def encerrar(self) -> None:
        self._parar.set()
        self._acordar.set()

    def _esperar(self, segundos: float, acordavel: bool = False) -> None:
        """Espera (na escala). `acordavel`: volta antes se a página fizer alguma ação."""
        if not acordavel:
            self._parar.wait(segundos * self._escala)
            return
        self._acordar.clear()
        self._acordar.wait(segundos * self._escala)

    def _fase(self, fase: str) -> None:
        log.info("[simulação] fase: %s", fase)
        self.emitir(FASE, fase)

    def _publicar_sessao(self, sessao: dict[str, Any] | None) -> None:
        if sessao is None:
            self.emitir(SESSAO_SELECAO, None, tipo="Delete")
        else:
            self.emitir(SESSAO_SELECAO, sessao)

    def _rodar(self) -> None:
        while not self._parar.is_set():
            self._fase("Lobby")
            self._esperar(3)
            self._fase("Matchmaking")
            self._esperar(6)
            if self._partida_encontrada():
                self._depois_da_selecao(self.selecao.rodar(dodge=self.ciclos % 3 == 2))
            self.ciclos += 1

    def _partida_encontrada(self) -> bool:
        """Partida encontrada por até 10 s; os outros 9 aceitam 2 s depois de você."""
        with self._trava:
            self._resposta = "None"
        self._fase("ReadyCheck")
        resposta, segundo = "None", 0
        for segundo in range(11):
            with self._trava:
                resposta = self._resposta
            estado = {"state": "InProgress", "playerResponse": resposta, "timer": float(segundo)}
            self.emitir(READY_CHECK, estado)
            if resposta == "Declined" or (resposta == "Accepted" and segundo >= 2):
                break
            self._esperar(1)
        if resposta == "Accepted":
            final = {"state": "EveryoneReady", "playerResponse": resposta, "timer": float(segundo)}
            self.emitir(READY_CHECK, final)
        self.emitir(READY_CHECK, None, tipo="Delete")
        return resposta == "Accepted"

    def _depois_da_selecao(self, partida: bool) -> None:
        self._publicar_sessao(None)
        if not partida:
            self._fase("Matchmaking")  # alguém deu dodge: de volta à fila
            self._esperar(3)
            return
        self._fase("GameStart")
        self._esperar(2)
        self._fase("InProgress")
        self._esperar(15)
        self._fase("EndOfGame")
        self._esperar(3)
