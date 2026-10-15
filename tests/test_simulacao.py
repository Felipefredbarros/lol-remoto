"""O `--simular` de ponta a ponta: LCU simulada (acelerada) + monitor + notificações + ações."""

import threading
import time
from pathlib import Path

import pytest

from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.selecao import TipoAcao
from lol_remoto.plataforma.lcu_simulada import LcuSimulada
from lol_remoto.plataforma.lockfile import Credenciais
from lol_remoto.plataforma.ntfy import NotificadorFalso
from lol_remoto.servicos.acoes import ServicoAcoes
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.feiticos import ServicoFeiticos
from lol_remoto.servicos.monitor import Monitor
from lol_remoto.servicos.notificacoes import ServicoNotificacoes
from lol_remoto.servicos.runas import ServicoRunas

ESCALA = 0.02  # 1 s simulado = 20 ms


class _Partida:
    def __init__(self, aceitar=True, ciclo=0):
        self.lcu = LcuSimulada(escala=ESCALA, semente=7)
        self.lcu.ciclos = ciclo  # o ciclo 2 tem dodge
        self.estado = Estado(ausente=True)
        self.notificador = NotificadorFalso()
        self.notificacoes = ServicoNotificacoes(self.estado, self.notificador)
        self.monitor = Monitor(
            self.estado,
            Path("."),
            conectar=lambda credenciais: self.lcu,
            intervalo=0.01,
            ler_credenciais=lambda: Credenciais(porta=1, senha="x", protocolo="http"),
        )
        self.acoes = ServicoAcoes(self.estado, lambda: self.monitor.lcu)
        self.runas = ServicoRunas(self.estado, lambda: self.monitor.lcu)
        self.feiticos = ServicoFeiticos(self.estado, lambda: self.monitor.lcu)
        self.feito: set = set()
        self.erros: list[Exception] = []
        self.inicio_das_etapas: dict[str, float] = {}
        self._aceitar = aceitar
        self.estado.assinar(self._jogar)
        threading.Thread(target=self.monitor.executar, daemon=True).start()
        self.lcu.iniciar()

    def _jogar(self, anterior, atual):
        """Jogador automático: faz pela API de serviços o que você faria pela página."""
        try:
            if self._aceitar and atual.momento.partida_encontrada and "aceitar" not in self.feito:
                self.feito.add("aceitar")
                self.acoes.aceitar()
            selecao = atual.selecao
            if selecao is None or atual.fase is not Fase.SELECAO:
                return
            self.inicio_das_etapas.setdefault(selecao.timer.etapa.value, time.monotonic())
            if selecao.em_planejamento and "intencao" not in self.feito:
                self.feito.add("intencao")
                self.acoes.marcar(103)
            vez = selecao.minha_vez
            if vez and vez.id not in self.feito:
                self.feito.add(vez.id)
                self.acoes.confirmar(157 if vez.tipo is TipoAcao.BAN else 103)
            if selecao.eu and selecao.eu.campeao and "runas" not in self.feito:
                self.feito.add("runas")
                self.runas.aplicar(0)
                self.feiticos.trocar("f", 12)  # Teleporte no F (o D continua Flash)
        except Exception as erro:  # noqa: BLE001 - conferido no teste
            self.erros.append(erro)

    def esperar(self, condicao, tempo=20.0):
        fim = time.monotonic() + tempo
        while not condicao():
            assert time.monotonic() < fim, "a simulação não chegou lá a tempo"
            time.sleep(0.02)

    def titulos(self):
        self.notificacoes.aguardar_envios()
        return [n.titulo for n in self.notificador.enviadas]

    def encerrar(self):
        self.lcu.encerrar()
        self.monitor.encerrar()
        self.notificacoes.encerrar()


@pytest.fixture
def criar():
    partidas = []

    def fabrica(**kwargs):
        partidas.append(_Partida(**kwargs))
        return partidas[-1]

    yield fabrica
    for partida in partidas:
        partida.encerrar()


def test_ciclo_completo_pela_fila(criar):
    p = criar()
    p.esperar(lambda: p.estado.atual.fase is Fase.EM_PARTIDA)
    assert p.erros == []
    assert p.titulos() == [
        "Partida encontrada!",
        "Seleção começou",
        "Sua vez de banir!",
        "Sua vez de escolher!",
        "Partida carregando",
    ]
    chamadas = [(metodo, caminho) for metodo, caminho, _ in p.lcu.chamadas]
    assert ("POST", "/lol-matchmaking/v1/ready-check/accept") in chamadas
    assert ("PATCH", "/lol-champ-select/v1/session/actions/15") in chamadas  # meu pick
    assert ("PUT", "/lol-perks/v1/pages/1") in chamadas  # runas na "LoL Remoto"
    feiticos = [c for c in p.lcu.chamadas if c[1].endswith("/my-selection")]
    assert feiticos == [("PATCH", "/lol-champ-select/v1/session/my-selection",
                         {"spell1Id": 4, "spell2Id": 12})]  # fmt: skip


def test_planejamento_dura_o_tempo_todo_mesmo_declarando_intencao(criar):
    # Bug encontrado no teste manual: marcar a intenção encerrava o planejamento na hora.
    p = criar()
    p.esperar(lambda: "BAN_PICK" in p.inicio_das_etapas)
    assert "intencao" in p.feito
    duracao = p.inicio_das_etapas["BAN_PICK"] - p.inicio_das_etapas["PLANNING"]
    assert duracao >= 0.8 * 10 * ESCALA


def test_dodge_na_finalizacao(criar):
    p = criar(ciclo=2)
    p.esperar(lambda: "Alguém deu dodge" in p.titulos())
    assert p.erros == []


def test_sem_aceitar_sai_da_fila(criar):
    p = criar(aceitar=False)
    p.esperar(lambda: "Você saiu da fila" in p.titulos())
    assert p.titulos()[:2] == ["Partida encontrada!", "Você saiu da fila"]
