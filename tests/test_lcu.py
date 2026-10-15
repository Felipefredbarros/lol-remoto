import base64
import json
import socket
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from lol_remoto.plataforma.lcu import (
    FASE,
    SESSAO_SELECAO,
    ErroLcu,
    Evento,
    LcuHttp,
    contexto_tls,
    evento_de,
)
from lol_remoto.plataforma.lockfile import Credenciais
from lol_remoto.plataforma.websocket import TEXTO
from servidor_ws_falso import ServidorWsFalso, quadro

SENHA = "senha-de-teste"
AUTORIZACAO = "Basic " + base64.b64encode(f"riot:{SENHA}".encode()).decode()


# ---------- funções puras ----------


def test_evento_de_mensagem_wamp():
    mensagem = json.dumps(
        [8, "OnJsonApiEvent", {"data": "ChampSelect", "eventType": "Update", "uri": FASE}]
    )
    assert evento_de(mensagem) == Evento(uri=FASE, tipo="Update", dados="ChampSelect")


@pytest.mark.parametrize(
    "mensagem",
    [
        '[0,"f2d354b3",1,"WAMP-1.0-RiotRemoting"]',  # boas-vindas real da LCU
        "não é json",
        "{}",
        "[8]",
        '[8,"x","texto"]',
        '[8,"x",{"data":1}]',
    ],
)
def test_mensagens_que_nao_sao_evento_sao_ignoradas(mensagem):
    assert evento_de(mensagem) is None


def test_contexto_tls_verifica_certificado_e_nome():
    contexto = contexto_tls()
    assert contexto.verify_mode is ssl.CERT_REQUIRED
    assert contexto.check_hostname
    assert not contexto.verify_flags & ssl.VERIFY_X509_STRICT
    assert contexto.minimum_version >= ssl.TLSVersion.TLSv1_2  # nada de TLS 1.0/1.1
    assert any("LoL Game Engineering" in str(c.get("subject")) for c in contexto.get_ca_certs())


# ---------- REST contra um servidor HTTP local ----------


class _ServidorLcu:
    def __init__(self):
        self.rotas = {}  # (método, caminho) → (status, corpo, tipo)
        self.pedidos = []
        dono = self

        class Manipulador(BaseHTTPRequestHandler):
            def _responder(self):
                tamanho = int(self.headers.get("Content-Length") or 0)
                corpo = self.rfile.read(tamanho) if tamanho else b""
                dono.pedidos.append((self.command, self.path, dict(self.headers), corpo))
                status, conteudo, tipo = dono.rotas.get(
                    (self.command, self.path), (404, b'{"message":"nada"}', "application/json")
                )
                self.send_response(status)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(conteudo)))
                self.end_headers()
                self.wfile.write(conteudo)

            do_GET = do_POST = do_PATCH = _responder

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
        threading.Thread(
            target=self.http.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()
        self.lcu = LcuHttp(Credenciais(self.http.server_address[1], SENHA, "http"))


@pytest.fixture
def servidor():
    s = _ServidorLcu()
    yield s
    s.http.shutdown()
    s.http.server_close()


def test_get_com_autenticacao(servidor):
    servidor.rotas["GET", FASE] = (200, b'"Lobby"', "application/json")
    assert servidor.lcu.get(FASE) == "Lobby"
    _, _, cabecalhos, _ = servidor.pedidos[0]
    assert cabecalhos["Authorization"] == AUTORIZACAO


def test_get_404_vira_none(servidor):
    assert servidor.lcu.get("/lol-champ-select/v1/session") is None


def test_get_com_erro_traz_status_e_mensagem(servidor):
    servidor.rotas["GET", FASE] = (500, b'{"message":"quebrou"}', "application/json")
    with pytest.raises(ErroLcu, match="quebrou") as erro:
        servidor.lcu.get(FASE)
    assert erro.value.status == 500


def test_enviar_manda_json(servidor):
    caminho = "/lol-champ-select/v1/session/actions/15"
    servidor.rotas["PATCH", caminho] = (204, b"", "application/json")
    assert servidor.lcu.enviar("PATCH", caminho, {"championId": 103}) is None
    metodo, _, cabecalhos, corpo = servidor.pedidos[0]
    assert metodo == "PATCH"
    assert cabecalhos["Content-Type"] == "application/json"
    assert json.loads(corpo) == {"championId": 103}


def test_enviar_recusado_levanta_erro(servidor):
    with pytest.raises(ErroLcu) as erro:
        servidor.lcu.enviar("POST", "/lol-matchmaking/v1/ready-check/accept")
    assert erro.value.status == 404


def test_get_bytes(servidor):
    servidor.rotas["GET", "/icone.png"] = (200, b"\x89PNG", "image/png")
    assert servidor.lcu.get_bytes("/icone.png") == b"\x89PNG"
    with pytest.raises(ErroLcu):
        servidor.lcu.get_bytes("/nao-existe.png")


def test_cliente_fechado_levanta_erro():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]  # porta livre, ninguém ouvindo depois do with
    with pytest.raises(ErroLcu, match="indisponível"):
        LcuHttp(Credenciais(porta, SENHA, "http"), tempo_limite=0.3).get(FASE)


# ---------- eventos pelo WebSocket ----------


def test_eventos_assina_o_canal_geral_e_filtra_os_caminhos(servidor):
    assinaturas = []

    def evento(uri, dados):
        corpo = {"data": dados, "eventType": "Update", "uri": uri}
        return quadro(TEXTO, json.dumps([8, "OnJsonApiEvent", corpo]).encode())

    def roteiro(lado):
        assinaturas.append(json.loads(lado.ler_quadro()[1]))
        lado.enviar(quadro(TEXTO, b'[0,"sessao",1,"WAMP-1.0-RiotRemoting"]'))
        lado.enviar(evento("/lol-chat/v1/conversations", {"x": 1}))  # outro assunto
        lado.enviar(evento(SESSAO_SELECAO + "/timer", {"x": 2}))  # subcaminho
        lado.enviar(evento(FASE, "ReadyCheck"))
        lado.ler_quadro()  # espera o close

    ws = ServidorWsFalso(roteiro)
    lcu = LcuHttp(Credenciais(ws.porta, SENHA, "http"))
    eventos = lcu.eventos([FASE, SESSAO_SELECAO])
    assert next(eventos) == Evento(uri=FASE, tipo="Update", dados="ReadyCheck")
    lcu.fechar()
    ws.encerrar()
    assert ws.pedido["authorization"] == AUTORIZACAO
    assert assinaturas == [[5, "OnJsonApiEvent"]]
