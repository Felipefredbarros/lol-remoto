"""Cliente WebSocket mínimo (RFC 6455), só com a biblioteca padrão.

Feito para falar com a LCU (ver docs/decisoes/0003-runtime-sem-dependencias.md): mensagens
de texto, quadros fragmentados, ping/pong e close. Não suporta extensões (compressão).
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import os
import socket
import ssl
import threading

_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"  # constante da RFC 6455
TAMANHO_MAXIMO_MENSAGEM = 16 * 1024 * 1024
_FIM_CABECALHO = b"\r\n\r\n"

CONTINUACAO, TEXTO, BINARIO, FECHAR, PING, PONG = 0x0, 0x1, 0x2, 0x8, 0x9, 0xA


class ErroWebSocket(OSError):
    """Falha no handshake ou no protocolo."""


class ConexaoFechada(ErroWebSocket):
    """O outro lado fechou a conexão (ou ela caiu)."""


def chave_aceita(chave: str) -> str:
    """Valor esperado em `Sec-WebSocket-Accept` para a `Sec-WebSocket-Key` enviada."""
    return base64.b64encode(hashlib.sha1((chave + _GUID).encode()).digest()).decode()


def _mascarar(dados: bytes, mascara: bytes) -> bytes:
    repetida = (mascara * (len(dados) // 4 + 1))[: len(dados)]
    resultado = int.from_bytes(dados, "big") ^ int.from_bytes(repetida, "big")
    return resultado.to_bytes(len(dados), "big")


class ClienteWebSocket:
    def __init__(self, conexao: socket.socket, sobra: bytes = b"") -> None:
        """Use `conectar`. `sobra` são bytes já lidos depois do cabeçalho do handshake."""
        self._conexao = conexao
        self._buffer = bytearray(sobra)
        self._trava_envio = threading.Lock()
        self._fechado = False

    @classmethod
    def conectar(
        cls,
        host: str,
        porta: int,
        caminho: str = "/",
        cabecalhos: dict[str, str] | None = None,
        contexto_ssl: ssl.SSLContext | None = None,
        protocolo: str | None = "wamp",
        tempo_limite: float = 10,
    ) -> ClienteWebSocket:
        conexao = socket.create_connection((host, porta), timeout=tempo_limite)
        try:
            if contexto_ssl is not None:
                conexao = contexto_ssl.wrap_socket(conexao, server_hostname=host)
            sobra = cls._handshake(conexao, f"{host}:{porta}", caminho, cabecalhos, protocolo)
        except BaseException:
            conexao.close()
            raise
        conexao.settimeout(None)  # depois do handshake, espera eventos sem limite
        return cls(conexao, sobra)

    @staticmethod
    def _handshake(conexao, host, caminho, cabecalhos, protocolo) -> bytes:
        chave = base64.b64encode(os.urandom(16)).decode()
        linhas = [
            f"GET {caminho} HTTP/1.1",
            f"Host: {host}",
            "Upgrade: websocket",
            "Connection: Upgrade",
            f"Sec-WebSocket-Key: {chave}",
            "Sec-WebSocket-Version: 13",
        ]
        if protocolo:
            linhas.append(f"Sec-WebSocket-Protocol: {protocolo}")
        linhas += [f"{nome}: {valor}" for nome, valor in (cabecalhos or {}).items()]
        conexao.sendall(("\r\n".join(linhas) + "\r\n\r\n").encode())

        recebido = b""
        while _FIM_CABECALHO not in recebido:
            pedaco = conexao.recv(4096)
            if not pedaco:
                raise ErroWebSocket("Conexão fechada durante o handshake.")
            recebido += pedaco
            if len(recebido) > 64 * 1024:
                raise ErroWebSocket("Resposta do handshake grande demais.")
        cabecalho, sobra = recebido.split(_FIM_CABECALHO, 1)
        status, *resto = cabecalho.decode("latin-1").split("\r\n")
        if status.split(" ")[1:2] != ["101"]:
            raise ErroWebSocket(f"Handshake recusado: {status}")
        campos = {n.strip().lower(): v.strip() for n, _, v in (r.partition(":") for r in resto)}
        if campos.get("sec-websocket-accept") != chave_aceita(chave):
            raise ErroWebSocket("Sec-WebSocket-Accept inválido.")
        return sobra

    # ---------- envio ----------

    def enviar_texto(self, texto: str) -> None:
        self._enviar_quadro(TEXTO, texto.encode())

    def _enviar_quadro(self, opcode: int, dados: bytes) -> None:
        tamanho = len(dados)
        if tamanho < 126:
            cabecalho = bytes([0x80 | opcode, 0x80 | tamanho])
        elif tamanho < 1 << 16:
            cabecalho = bytes([0x80 | opcode, 0x80 | 126]) + tamanho.to_bytes(2, "big")
        else:
            cabecalho = bytes([0x80 | opcode, 0x80 | 127]) + tamanho.to_bytes(8, "big")
        mascara = os.urandom(4)  # o cliente sempre mascara (RFC 6455, 5.3)
        with self._trava_envio:
            try:
                self._conexao.sendall(cabecalho + mascara + _mascarar(dados, mascara))
            except OSError as erro:
                raise ConexaoFechada(f"Falha ao enviar: {erro}") from erro

    # ---------- recebimento ----------

    def _ler(self, quantidade: int) -> bytes:
        while len(self._buffer) < quantidade:
            try:
                pedaco = self._conexao.recv(max(4096, quantidade - len(self._buffer)))
            except OSError as erro:
                raise ConexaoFechada(f"Conexão interrompida: {erro}") from erro
            if not pedaco:
                raise ConexaoFechada("O servidor fechou a conexão.")
            self._buffer += pedaco
        dados = bytes(self._buffer[:quantidade])
        del self._buffer[:quantidade]
        return dados

    def _ler_quadro(self) -> tuple[bool, int, bytes]:
        b0, b1 = self._ler(2)
        tamanho = b1 & 0x7F
        if tamanho == 126:
            tamanho = int.from_bytes(self._ler(2), "big")
        elif tamanho == 127:
            tamanho = int.from_bytes(self._ler(8), "big")
        if tamanho > TAMANHO_MAXIMO_MENSAGEM:
            raise ErroWebSocket(f"Quadro grande demais ({tamanho} bytes).")
        mascara = self._ler(4) if b1 & 0x80 else None
        dados = self._ler(tamanho)
        return bool(b0 & 0x80), b0 & 0x0F, _mascarar(dados, mascara) if mascara else dados

    def receber(self) -> str:
        """Bloqueia até chegar uma mensagem de texto completa. Responde pings sozinho."""
        partes: list[bytes] = []
        while True:
            fim, opcode, dados = self._ler_quadro()
            if opcode == PING:
                self._enviar_quadro(PONG, dados)
            elif opcode == FECHAR:
                self._responder_fechamento(dados)
                raise ConexaoFechada("O servidor encerrou o WebSocket.")
            elif opcode in (TEXTO, BINARIO, CONTINUACAO):
                partes.append(dados)
                if sum(map(len, partes)) > TAMANHO_MAXIMO_MENSAGEM:
                    raise ErroWebSocket("Mensagem grande demais.")
                if fim:
                    return b"".join(partes).decode("utf-8", errors="replace")
            # PONG e opcodes desconhecidos são ignorados.

    def _responder_fechamento(self, dados: bytes) -> None:
        if not self._fechado:
            self._fechado = True
            with contextlib.suppress(ConexaoFechada):
                self._enviar_quadro(FECHAR, dados[:2])

    def fechar(self) -> None:
        """Encerra a conexão. Pode ser chamado de outra thread para destravar `receber`."""
        self._responder_fechamento(b"\x03\xe8")  # 1000 = fechamento normal
        with contextlib.suppress(OSError):
            self._conexao.shutdown(socket.SHUT_RDWR)
        self._conexao.close()
