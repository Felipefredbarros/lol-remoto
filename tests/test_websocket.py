import contextlib
import threading

import pytest

from lol_remoto.plataforma.websocket import (
    BINARIO,
    CONTINUACAO,
    FECHAR,
    PING,
    PONG,
    TEXTO,
    ClienteWebSocket,
    ConexaoFechada,
    ErroWebSocket,
    chave_aceita,
)
from servidor_ws_falso import ServidorWsFalso, quadro


def _conectar(servidor, **kwargs):
    return ClienteWebSocket.conectar("127.0.0.1", servidor.porta, tempo_limite=5, **kwargs)


def test_chave_aceita_exemplo_da_rfc():
    assert chave_aceita("dGhlIHNhbXBsZSBub25jZQ==") == "s3pPLMBiTxaQ9kYGzzhZRbK+xOo="


def test_handshake_envia_protocolo_e_cabecalhos():
    servidor = ServidorWsFalso(lambda lado: None)
    cliente = _conectar(servidor, cabecalhos={"Authorization": "Basic abc"})
    cliente.fechar()
    servidor.encerrar()
    assert servidor.linha_pedido == "GET / HTTP/1.1"
    assert servidor.pedido["sec-websocket-protocol"] == "wamp"
    assert servidor.pedido["authorization"] == "Basic abc"
    assert servidor.pedido["host"] == f"127.0.0.1:{servidor.porta}"


def test_handshake_recusado():
    servidor = ServidorWsFalso(
        lambda lado: None,
        handshake=lambda chave: b"HTTP/1.1 401 Unauthorized\r\nContent-Length: 0\r\n\r\n",
    )
    with pytest.raises(ErroWebSocket, match="401"):
        _conectar(servidor)
    servidor.encerrar()


def test_handshake_com_accept_errado():
    def resposta(chave):
        return b"HTTP/1.1 101 Switching Protocols\r\nSec-WebSocket-Accept: errado\r\n\r\n"

    servidor = ServidorWsFalso(lambda lado: None, handshake=resposta)
    with pytest.raises(ErroWebSocket, match="Accept"):
        _conectar(servidor)
    servidor.encerrar()


@pytest.mark.parametrize("tamanho", [0, 5, 125, 126, 300, 65535, 65536, 200_000])
def test_recebe_mensagens_de_todos_os_tamanhos(tamanho):
    texto = "é" * (tamanho // 2) + "a" * (tamanho % 2)
    servidor = ServidorWsFalso(lambda lado: lado.enviar(quadro(TEXTO, texto.encode())))
    cliente = _conectar(servidor)
    assert cliente.receber() == texto
    cliente.fechar()
    servidor.encerrar()


def test_mensagem_logo_depois_do_handshake_no_mesmo_pacote():
    from servidor_ws_falso import resposta_101

    servidor = ServidorWsFalso(
        lambda lado: None,
        handshake=lambda chave: resposta_101(chave) + quadro(TEXTO, b'[0,"ola"]'),
    )
    cliente = _conectar(servidor)
    assert cliente.receber() == '[0,"ola"]'
    cliente.fechar()
    servidor.encerrar()


def test_fragmentada_com_ping_no_meio_responde_pong():
    pongs = []

    def roteiro(lado):
        lado.enviar(quadro(TEXTO, b"[8,", fim=False))
        lado.enviar(quadro(PING, b"oi?"))
        lado.enviar(quadro(CONTINUACAO, b'"evento",', fim=False))
        lado.enviar(quadro(CONTINUACAO, b"{}]"))
        pongs.append(lado.ler_quadro())

    servidor = ServidorWsFalso(roteiro)
    cliente = _conectar(servidor)
    assert cliente.receber() == '[8,"evento",{}]'
    servidor.encerrar()
    cliente.fechar()
    assert pongs == [(PONG, b"oi?")]


def test_ignora_pong_e_aceita_binario():
    def roteiro(lado):
        lado.enviar(quadro(PONG, b""))
        lado.enviar(quadro(BINARIO, b"bin"))

    servidor = ServidorWsFalso(roteiro)
    cliente = _conectar(servidor)
    assert cliente.receber() == "bin"
    cliente.fechar()
    servidor.encerrar()


@pytest.mark.parametrize("tamanho", [10, 126, 70_000])
def test_envia_texto_mascarado(tamanho):
    recebidos = []
    texto = "x" * tamanho
    servidor = ServidorWsFalso(lambda lado: recebidos.append(lado.ler_quadro()))
    cliente = _conectar(servidor)
    cliente.enviar_texto(texto)
    servidor.encerrar()
    cliente.fechar()
    assert recebidos == [(TEXTO, texto.encode())]


def test_fechamento_pelo_servidor():
    respostas = []

    def roteiro(lado):
        lado.enviar(quadro(FECHAR, b"\x03\xe8"))
        respostas.append(lado.ler_quadro())

    servidor = ServidorWsFalso(roteiro)
    cliente = _conectar(servidor)
    with pytest.raises(ConexaoFechada):
        cliente.receber()
    servidor.encerrar()
    cliente.fechar()
    assert respostas == [(FECHAR, b"\x03\xe8")]


def test_conexao_cai_sem_aviso():
    servidor = ServidorWsFalso(lambda lado: lado.conexao.close())
    cliente = _conectar(servidor)
    with pytest.raises(ConexaoFechada):
        cliente.receber()
    servidor.encerrar()


def test_quadro_grande_demais_e_recusado(monkeypatch):
    monkeypatch.setattr("lol_remoto.plataforma.websocket.TAMANHO_MAXIMO_MENSAGEM", 1000)
    servidor = ServidorWsFalso(lambda lado: lado.enviar(quadro(TEXTO, b"a" * 2000)))
    cliente = _conectar(servidor)
    with pytest.raises(ErroWebSocket, match="grande demais"):
        cliente.receber()
    cliente.fechar()
    servidor.encerrar()


def test_fechar_de_outra_thread_destrava_receber():
    pronto = threading.Event()

    def roteiro(lado):
        pronto.set()
        with contextlib.suppress(ConnectionError):
            lado.ler_quadro()  # espera o close do cliente

    servidor = ServidorWsFalso(roteiro)
    cliente = _conectar(servidor)
    pronto.wait(5)
    threading.Timer(0.2, cliente.fechar).start()
    with pytest.raises(ConexaoFechada):
        cliente.receber()
    servidor.encerrar()
