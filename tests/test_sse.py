import http.client
import json
import threading

import pytest

from api_falsa import ApiFalsa
from lol_remoto.api.sse import CanalSse
from lol_remoto.dominio.fase import Fase
from lol_remoto.servicos.estado import Estado


def _abrir(api, token):
    conexao = http.client.HTTPConnection("127.0.0.1", api.porta, timeout=5)
    conexao.request("GET", "/api/eventos", headers={"Cookie": f"lolremoto_sessao={token}"})
    resposta = conexao.getresponse()
    return conexao, resposta


def _proximo_evento(resposta):
    """Lê linhas até um evento `data:` completo."""
    while True:
        linha = resposta.fp.readline().decode()
        if linha == "":
            raise ConnectionError("stream encerrado")
        if linha.startswith("data: "):
            return json.loads(linha[6:])


@pytest.fixture
def api():
    a = ApiFalsa()
    yield a
    a.encerrar()


def test_stream_manda_o_estado_e_cada_mudanca(api):
    conexao, resposta = _abrir(api, api.entrar())
    assert resposta.status == 200
    assert resposta.headers["Content-Type"].startswith("text/event-stream")
    assert _proximo_evento(resposta)["fase"] == "None"
    api.estado.atualizar(conectado=True, fase=Fase.FILA)
    evento = _proximo_evento(resposta)
    assert evento["fase"] == "Matchmaking" and evento["fase_descricao"] == "Na fila"
    conexao.close()


def test_stream_exige_sessao(api):
    conexao, resposta = _abrir(api, "inventado")
    assert resposta.status == 401
    conexao.close()


def test_limite_de_conexoes_derruba_a_mais_antiga():
    estado = Estado()
    canal = CanalSse(estado, lambda: {"versao": estado.atual.versao}, maximo=1, heartbeat=0.05)
    primeira_escrita = threading.Event()
    escritas_primeira = []

    def primeira(dados):
        escritas_primeira.append(dados)
        primeira_escrita.set()

    t1 = threading.Thread(target=canal.transmitir, args=(primeira,), daemon=True)
    t1.start()
    primeira_escrita.wait(2)

    def segunda(dados):
        raise BrokenPipeError  # o segundo cliente cai logo; só queremos que ele entre

    canal.transmitir(segunda)
    t1.join(2)
    assert not t1.is_alive()  # a primeira foi encerrada pela segunda
    assert canal.conexoes == 0


def test_heartbeat_sem_mudancas():
    estado = Estado()
    canal = CanalSse(estado, lambda: {}, heartbeat=0.02)
    escritas = []

    def escrever(dados):
        escritas.append(dados)
        if len(escritas) >= 4:
            raise ConnectionResetError

    canal.transmitir(escrever)
    assert escritas[0] == b"retry: 3000\n\n"
    assert escritas[1].startswith(b"data: ")
    assert escritas[2] == b": ping\n\n"
