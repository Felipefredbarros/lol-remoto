import threading
import time

import pytest

from lol_remoto.dominio.fase import Fase
from lol_remoto.plataforma.lcu import FASE, READY_CHECK, SESSAO_SELECAO, ErroLcu
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.monitor import CATALOGO, Monitor

READY = {"state": "InProgress", "playerResponse": "None", "timer": 1.0}


def esperar(condicao, tempo=3.0):
    fim = time.monotonic() + tempo
    while time.monotonic() < fim:
        if condicao():
            return
        time.sleep(0.01)
    raise AssertionError("a condição não aconteceu a tempo")


def _lockfile(pasta, texto="LeagueClient:1:49637:senha:https"):
    (pasta / "lockfile").write_text(texto, encoding="utf-8")


class _Cenario:
    """Monitor rodando numa thread, com uma LcuFalsa nova a cada conexão."""

    def __init__(self, pasta, respostas=None):
        self.estado = Estado()
        self.conexoes: list[LcuFalsa] = []
        self.respostas = respostas or {FASE: "Lobby"}

        def conectar(credenciais):
            lcu = LcuFalsa(self.respostas)
            self.conexoes.append(lcu)
            return lcu

        self.monitor = Monitor(self.estado, pasta, conectar=conectar, intervalo=0.02)
        self.thread = threading.Thread(target=self.monitor.executar, daemon=True)
        self.thread.start()

    @property
    def lcu(self) -> LcuFalsa:
        return self.conexoes[-1]

    def encerrar(self):
        self.monitor.encerrar()
        self.thread.join(timeout=3)
        assert not self.thread.is_alive()


@pytest.fixture
def cenario(tmp_path):
    _lockfile(tmp_path)
    c = _Cenario(tmp_path, {FASE: "Lobby", CATALOGO: [{"id": 103, "name": "Ahri"}]})
    esperar(lambda: c.estado.atual.conectado)
    yield c
    c.encerrar()


def test_espera_o_cliente_abrir(tmp_path):
    c = _Cenario(tmp_path)
    time.sleep(0.1)
    assert c.conexoes == [] and not c.estado.atual.conectado
    _lockfile(tmp_path)
    esperar(lambda: c.estado.atual.conectado)
    assert c.estado.atual.fase is Fase.LOBBY
    c.encerrar()


def test_lockfile_invalido_nao_derruba(tmp_path):
    _lockfile(tmp_path, "lixo")
    c = _Cenario(tmp_path)
    time.sleep(0.1)
    assert c.thread.is_alive() and c.conexoes == []
    c.encerrar()


def test_estado_inicial_e_assinaturas(cenario):
    assert cenario.lcu.assinados == [FASE, SESSAO_SELECAO, READY_CHECK]
    assert cenario.estado.catalogo.nome(103) == "Ahri"


def test_fila_ate_a_partida_carregar(cenario, sessao_draft):
    lcu, estado = cenario.lcu, cenario.estado
    lcu.emitir(FASE, "Matchmaking")
    lcu.emitir(READY_CHECK, READY)
    lcu.emitir(FASE, "ReadyCheck")
    esperar(lambda: estado.atual.fase is Fase.PARTIDA_ENCONTRADA and estado.atual.ready_check)

    lcu.emitir(SESSAO_SELECAO, sessao_draft)  # a sessão costuma chegar antes da fase
    lcu.emitir(FASE, "ChampSelect")
    esperar(lambda: estado.atual.fase is Fase.SELECAO)
    assert estado.atual.selecao.minha_vez.id == 15
    assert estado.atual.ready_check is None

    lcu.emitir(FASE, "GameStart")
    esperar(lambda: estado.atual.fase is Fase.CARREGANDO)
    assert estado.atual.selecao is None


def test_sessao_fora_da_selecao_e_ignorada(cenario, sessao_draft):
    cenario.lcu.emitir(SESSAO_SELECAO, sessao_draft)
    cenario.lcu.emitir(FASE, "Matchmaking")
    esperar(lambda: cenario.estado.atual.fase is Fase.FILA)
    assert cenario.estado.atual.selecao is None


def test_entrar_na_selecao_sem_sessao_busca_por_get(cenario, sessao_draft):
    cenario.lcu.respostas[SESSAO_SELECAO] = sessao_draft
    cenario.lcu.emitir(FASE, "ChampSelect")
    esperar(lambda: cenario.estado.atual.selecao is not None)


def test_sessao_apagada_e_sessao_invalida(cenario, sessao_draft):
    lcu, estado = cenario.lcu, cenario.estado
    lcu.emitir(FASE, "ChampSelect")
    lcu.emitir(SESSAO_SELECAO, sessao_draft)
    esperar(lambda: estado.atual.selecao is not None)
    lcu.emitir(SESSAO_SELECAO, None, tipo="Delete")
    esperar(lambda: estado.atual.selecao is None)
    lcu.emitir(SESSAO_SELECAO, {"formato": "novo"})
    lcu.emitir(FASE, "Lobby")
    esperar(lambda: estado.atual.fase is Fase.LOBBY)
    assert cenario.thread.is_alive()


def test_conecta_no_meio_da_selecao(tmp_path, sessao_draft):
    _lockfile(tmp_path)
    c = _Cenario(tmp_path, {FASE: "ChampSelect", SESSAO_SELECAO: sessao_draft})
    esperar(lambda: c.estado.atual.selecao is not None)
    assert c.estado.atual.fase is Fase.SELECAO
    c.encerrar()


def test_cliente_fecha_e_reabre(cenario):
    primeira = cenario.lcu
    primeira.emitir(FASE, "Matchmaking")
    esperar(lambda: cenario.estado.atual.fase is Fase.FILA)
    primeira.desconectar()
    esperar(lambda: len(cenario.conexoes) == 2 and cenario.estado.atual.conectado)
    assert cenario.estado.atual.fase is Fase.LOBBY


def test_erro_da_lcu_no_estado_inicial_reconecta(tmp_path, monkeypatch):
    falhas = []
    original = LcuFalsa.get

    def get_que_falha_uma_vez(self, caminho):
        if caminho == FASE and not falhas:
            falhas.append(1)
            raise ErroLcu("cliente ainda iniciando", 503)
        return original(self, caminho)

    monkeypatch.setattr(LcuFalsa, "get", get_que_falha_uma_vez)
    _lockfile(tmp_path)
    c = _Cenario(tmp_path)
    esperar(lambda: c.estado.atual.conectado)
    assert len(c.conexoes) == 2
    c.encerrar()
