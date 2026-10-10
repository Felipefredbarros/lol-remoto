"""Servidor HTTP (biblioteca padrão): página web, API JSON, ícones e o stream SSE."""

from __future__ import annotations

import json
import logging
import re
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from lol_remoto.api import rotas
from lol_remoto.api.protecao import host_permitido, hosts_permitidos, origem_permitida
from lol_remoto.api.sse import CanalSse
from lol_remoto.api.tipos import COOKIE, Dependencias, Pedido, Resposta
from lol_remoto.servicos.icones import ServicoIcones

log = logging.getLogger(__name__)

PASTA_WEB = Path(__file__).resolve().parent.parent / "web"
TAMANHO_MAXIMO_CORPO = 4096
TEMPO_LIMITE_CONEXAO = 10  # segundos
_ICONE = re.compile(r"^/api/campeoes/(\d{1,6})\.png$")

_TIPOS = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/manifest+json; charset=utf-8",
    ".svg": "image/svg+xml",
}

_CABECALHOS_SEGURANCA = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'",
    "Cache-Control": "no-store",
}


def _arquivo_web(caminho: str) -> Path | None:
    """Resolve um caminho de URL para um arquivo de `web/`, sem permitir sair da pasta."""
    if not PASTA_WEB.is_dir():
        return None
    nome = "index.html" if caminho == "/" else caminho.lstrip("/")
    permitidos = {p.name: p for p in PASTA_WEB.iterdir() if p.is_file()}
    return permitidos.get(nome)


def criar_servidor(
    host: str,
    porta: int,
    deps: Dependencias,
    canal: CanalSse,
    icones: ServicoIcones,
    tempo_limite: float = TEMPO_LIMITE_CONEXAO,
) -> ThreadingHTTPServer:
    permitidos = hosts_permitidos(host)

    class Manipulador(BaseHTTPRequestHandler):
        server_version = "LolRemoto"
        sys_version = ""
        timeout = tempo_limite  # fecha conexões paradas

        def do_GET(self) -> None:
            self._atender("GET")

        def do_POST(self) -> None:
            self._atender("POST")

        def _sessao(self) -> str | None:
            try:
                biscoito = SimpleCookie(self.headers.get("Cookie") or "")
            except CookieError:
                return None
            return biscoito[COOKIE].value if COOKIE in biscoito else None

        def _atender(self, metodo: str) -> None:
            if not host_permitido(self.headers.get("Host"), permitidos):
                log.warning("Host recusado: %r", self.headers.get("Host"))
                self._enviar_json(Resposta(403, {"erro": "Host não permitido."}))
                return

            url = urlsplit(self.path)
            caminho = url.path
            pedido = Pedido(
                origem=self.client_address[0],
                sessao=self._sessao(),
                consulta=dict(parse_qsl(url.query)),
            )
            if metodo == "GET" and not caminho.startswith("/api/"):
                self._enviar_arquivo(caminho)
                return
            if metodo == "GET" and caminho == "/api/eventos":
                self._transmitir(pedido)
                return
            if metodo == "GET" and (icone := _ICONE.match(caminho)):
                self._enviar_icone(pedido, int(icone.group(1)))
                return
            if metodo == "POST":
                recusa = self._validar_post()
                if recusa:
                    self._enviar_json(recusa)
                    return

            try:
                tamanho = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                tamanho = -1
            if tamanho < 0:
                self._enviar_json(Resposta(400, {"erro": "Content-Length inválido."}))
                return
            if tamanho > TAMANHO_MAXIMO_CORPO:
                self._enviar_json(Resposta(413, {"erro": "Requisição grande demais."}))
                return
            corpo = self.rfile.read(tamanho) if tamanho > 0 else b""
            self._enviar_json(rotas.tratar(metodo, caminho, corpo, pedido, deps))

        def _validar_post(self) -> Resposta | None:
            if not origem_permitida(self.headers.get("Origin"), permitidos):
                log.warning("Origin recusado: %r", self.headers.get("Origin"))
                return Resposta(403, {"erro": "Origem não permitida."})
            if self.headers.get_content_type() != "application/json":
                return Resposta(415, {"erro": "Envie o corpo como application/json."})
            return None

        def _transmitir(self, pedido: Pedido) -> None:
            if not deps.sessoes.valida(pedido.sessao):
                self._enviar_json(Resposta(401, {"erro": "Entre com o PIN."}))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            for nome, valor in _CABECALHOS_SEGURANCA.items():
                self.send_header(nome, valor)
            self.end_headers()

            def escrever(dados: bytes) -> None:
                self.wfile.write(dados)
                self.wfile.flush()

            canal.transmitir(escrever)

        def _enviar_icone(self, pedido: Pedido, campeao: int) -> None:
            if not deps.sessoes.valida(pedido.sessao):
                self._enviar_json(Resposta(401, {"erro": "Entre com o PIN."}))
                return
            try:
                dados = icones.icone(campeao)
            except Exception as erro:  # cliente fechado, campeão inexistente...
                log.debug("Ícone %s indisponível: %s", campeao, erro)
                self._enviar_json(Resposta(404, {"erro": "Ícone indisponível."}))
                return
            self._enviar(200, "image/png", dados, {"Cache-Control": "private, max-age=86400"})

        def _enviar_arquivo(self, caminho: str) -> None:
            arquivo = _arquivo_web(caminho)
            if arquivo is None:
                self._enviar_json(Resposta(404, {"erro": "Página não encontrada."}))
                return
            tipo = _TIPOS.get(arquivo.suffix, "application/octet-stream")
            self._enviar(200, tipo, arquivo.read_bytes())

        def _enviar_json(self, resposta: Resposta) -> None:
            conteudo = json.dumps(resposta.dados, ensure_ascii=False).encode()
            extras = dict(resposta.cabecalhos)
            self._enviar(resposta.status, "application/json; charset=utf-8", conteudo, extras)

        def _enviar(
            self, status: int, tipo: str, conteudo: bytes, extras: dict[str, str] | None = None
        ) -> None:
            self.send_response(status)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(conteudo)))
            for nome, valor in {**_CABECALHOS_SEGURANCA, **(extras or {})}.items():
                self.send_header(nome, valor)
            self.end_headers()
            self.wfile.write(conteudo)

        def log_message(self, formato: str, *args: object) -> None:
            log.debug("%s - %s", self.client_address[0], formato % args)

    return ThreadingHTTPServer((host, porta), Manipulador)
