import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from lol_remoto.plataforma.ntfy import (
    BotaoHttp,
    ErroNotificacao,
    Notificacao,
    NotificadorFalso,
    NotificadorNtfy,
    corpo_ntfy,
)

TOPICO = "lolremoto-topico-secreto-123"


def test_corpo_minimo():
    corpo = corpo_ntfy(TOPICO, Notificacao("Título", "Mensagem"))
    assert corpo == {"topic": TOPICO, "title": "Título", "message": "Mensagem", "priority": 3}


def test_corpo_com_link_tags_e_botoes():
    notificacao = Notificacao(
        "Partida encontrada!",
        "Aceitar?",
        prioridade=5,
        tags=("rotating_light",),
        link="http://100.64.0.1:8766/",
        botoes=(
            BotaoHttp("Aceitar", "http://100.64.0.1:8766/api/ready-check/aceitar", {"token": "t"}),
        ),
    )
    corpo = corpo_ntfy(TOPICO, notificacao)
    assert corpo["priority"] == 5
    assert corpo["tags"] == ["rotating_light"]
    assert corpo["click"] == "http://100.64.0.1:8766/"
    assert corpo["actions"] == [
        {
            "action": "http",
            "label": "Aceitar",
            "url": "http://100.64.0.1:8766/api/ready-check/aceitar",
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": '{"token": "t"}',
            "clear": True,
        }
    ]


@pytest.mark.parametrize(("pedida", "enviada"), [(0, 1), (9, 5), (4, 4)])
def test_prioridade_fica_entre_1_e_5(pedida, enviada):
    assert corpo_ntfy(TOPICO, Notificacao("t", "m", prioridade=pedida))["priority"] == enviada


class _ServidorNtfy:
    def __init__(self, status=200):
        self.pedidos = []
        dono = self

        class Manipulador(BaseHTTPRequestHandler):
            def do_POST(self):
                corpo = self.rfile.read(int(self.headers["Content-Length"]))
                dono.pedidos.append((self.path, dict(self.headers), json.loads(corpo)))
                self.send_response(status)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        self.http = ThreadingHTTPServer(("127.0.0.1", 0), Manipulador)
        self.url = f"http://127.0.0.1:{self.http.server_address[1]}"
        threading.Thread(
            target=self.http.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()

    def encerrar(self):
        self.http.shutdown()
        self.http.server_close()


def test_publica_json_na_raiz_do_servidor():
    servidor = _ServidorNtfy()
    NotificadorNtfy(servidor.url + "/", TOPICO).enviar(Notificacao("Oi", "Teste"))
    servidor.encerrar()
    caminho, cabecalhos, corpo = servidor.pedidos[0]
    assert caminho == "/"
    assert cabecalhos["Content-Type"] == "application/json"
    assert "Authorization" not in cabecalhos
    assert corpo["topic"] == TOPICO


def test_token_de_acesso_vai_no_cabecalho():
    servidor = _ServidorNtfy()
    NotificadorNtfy(servidor.url, TOPICO, token="tk_abc").enviar(Notificacao("Oi", "Teste"))
    servidor.encerrar()
    assert servidor.pedidos[0][1]["Authorization"] == "Bearer tk_abc"


def test_recusa_vira_erro_sem_mostrar_o_topico():
    servidor = _ServidorNtfy(status=403)
    with pytest.raises(ErroNotificacao, match="403") as erro:
        NotificadorNtfy(servidor.url, TOPICO).enviar(Notificacao("Oi", "Teste"))
    servidor.encerrar()
    assert TOPICO not in str(erro.value)


def test_servidor_inacessivel_vira_erro():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        porta = s.getsockname()[1]
    notificador = NotificadorNtfy(f"http://127.0.0.1:{porta}", TOPICO, tempo_limite=0.3)
    with pytest.raises(ErroNotificacao, match="inacessível") as erro:
        notificador.enviar(Notificacao("Oi", "Teste"))
    assert TOPICO not in str(erro.value)


def test_notificador_falso():
    falso = NotificadorFalso()
    falso.enviar(Notificacao("Oi", "Teste"))
    assert [n.titulo for n in falso.enviadas] == ["Oi"]
    with pytest.raises(ErroNotificacao):
        NotificadorFalso(falhar=True).enviar(Notificacao("Oi", "Teste"))
