"""Servidor WebSocket falso para testes: aceita uma conexão e segue um roteiro."""

from __future__ import annotations

import socket
import threading
from collections.abc import Callable

from lol_remoto.plataforma.websocket import chave_aceita


def quadro(opcode: int, dados: bytes, fim: bool = True) -> bytes:
    """Quadro do servidor (sem máscara)."""
    primeiro = (0x80 if fim else 0) | opcode
    tamanho = len(dados)
    if tamanho < 126:
        return bytes([primeiro, tamanho]) + dados
    if tamanho < 1 << 16:
        return bytes([primeiro, 126]) + tamanho.to_bytes(2, "big") + dados
    return bytes([primeiro, 127]) + tamanho.to_bytes(8, "big") + dados


def resposta_101(chave: str, protocolo: str = "wamp") -> bytes:
    return (
        "HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
        f"Sec-WebSocket-Accept: {chave_aceita(chave)}\r\n"
        f"Sec-WebSocket-Protocol: {protocolo}\r\n\r\n"
    ).encode()


class LadoServidor:
    def __init__(self, conexao: socket.socket, sobra: bytes) -> None:
        self.conexao = conexao
        self._buffer = bytearray(sobra)

    def enviar(self, dados: bytes) -> None:
        self.conexao.sendall(dados)

    def _ler(self, n: int) -> bytes:
        while len(self._buffer) < n:
            pedaco = self.conexao.recv(65536)
            if not pedaco:
                raise ConnectionError("cliente fechou")
            self._buffer += pedaco
        dados = bytes(self._buffer[:n])
        del self._buffer[:n]
        return dados

    def ler_quadro(self) -> tuple[int, bytes]:
        """Lê um quadro do cliente, conferindo que veio mascarado. Retorna (opcode, dados)."""
        b0, b1 = self._ler(2)
        assert b1 & 0x80, "o cliente deve mascarar os quadros"
        tamanho = b1 & 0x7F
        if tamanho == 126:
            tamanho = int.from_bytes(self._ler(2), "big")
        elif tamanho == 127:
            tamanho = int.from_bytes(self._ler(8), "big")
        mascara = self._ler(4)
        dados = bytes(b ^ mascara[i % 4] for i, b in enumerate(self._ler(tamanho)))
        return b0 & 0x0F, dados


class ServidorWsFalso:
    def __init__(
        self,
        roteiro: Callable[[LadoServidor], None],
        handshake: Callable[[str], bytes] = resposta_101,
    ) -> None:
        self._roteiro = roteiro
        self._handshake = handshake
        self._socket = socket.create_server(("127.0.0.1", 0))
        self.porta = self._socket.getsockname()[1]
        self.pedido: dict[str, str] = {}
        self.linha_pedido = ""
        self.erro: BaseException | None = None
        self._thread = threading.Thread(target=self._rodar, daemon=True)
        self._thread.start()

    def _rodar(self) -> None:
        try:
            conexao, _ = self._socket.accept()
            with conexao:
                recebido = b""
                while b"\r\n\r\n" not in recebido:
                    recebido += conexao.recv(4096)
                cabecalho, sobra = recebido.split(b"\r\n\r\n", 1)
                self.linha_pedido, *linhas = cabecalho.decode().split("\r\n")
                for linha in linhas:
                    nome, _, valor = linha.partition(":")
                    self.pedido[nome.strip().lower()] = valor.strip()
                conexao.sendall(self._handshake(self.pedido["sec-websocket-key"]))
                self._roteiro(LadoServidor(conexao, sobra))
        except BaseException as erro:  # noqa: BLE001 - repassado ao teste em `encerrar`
            self.erro = erro
        finally:
            self._socket.close()

    def encerrar(self) -> None:
        self._thread.join(timeout=5)
        if self.erro:
            raise self.erro
