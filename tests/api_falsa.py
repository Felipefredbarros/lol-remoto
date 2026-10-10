"""Monta o servidor HTTP de verdade em 127.0.0.1, com LCU e notificador falsos."""

from __future__ import annotations

import http.client
import json
import threading

from lol_remoto.api.servidor import criar_servidor
from lol_remoto.api.sse import CanalSse
from lol_remoto.api.tipos import Dependencias
from lol_remoto.api.visao import visao
from lol_remoto.dominio.campeoes import Catalogo
from lol_remoto.dominio.pin import gerar_hash
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.plataforma.ntfy import NotificadorFalso
from lol_remoto.servicos.acoes import BANIVEIS, PICKAVEIS, ServicoAcoes
from lol_remoto.servicos.autenticacao import ServicoAutenticacao
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.icones import ServicoIcones
from lol_remoto.servicos.runas import ServicoRunas
from lol_remoto.servicos.sessoes import ServicoSessoes
from lol_remoto.servicos.tokens import ServicoTokens

PIN = "12345678"
TEMPO_LIMITE_TESTE = 1  # segundos (o padrão do servidor é maior)


class ApiFalsa:
    def __init__(self, maximo_sse: int = 4, heartbeat: float = 15.0) -> None:
        self.lcu: LcuFalsa | None = LcuFalsa(
            {PICKAVEIS: [103, 121, 412], BANIVEIS: [103, 121, 157]}
        )
        self.lcu.arquivos["/lol-game-data/assets/v1/champion-icons/103.png"] = b"\x89PNG-ahri"
        self.estado = Estado()
        self.estado.catalogo = Catalogo.de_json(
            [
                {"id": 103, "name": "Ahri"},
                {"id": 121, "name": "Kha'Zix"},
                {"id": 157, "name": "Yasuo"},
                {"id": 412, "name": "Thresh"},
            ]
        )
        self.notificador = NotificadorFalso()
        self.tokens = ServicoTokens()
        self.deps = Dependencias(
            estado=self.estado,
            acoes=ServicoAcoes(self.estado, lambda: self.lcu),
            autenticacao=ServicoAutenticacao(gerar_hash(PIN, iteracoes=1_000), max_erros=2),
            sessoes=ServicoSessoes(None),
            tokens=self.tokens,
            notificador=self.notificador,
            runas=ServicoRunas(self.estado, lambda: self.lcu),
        )
        self.canal = CanalSse(
            self.estado,
            lambda: visao(self.estado.atual, self.estado.catalogo, self.estado.agora()),
            maximo=maximo_sse,
            heartbeat=heartbeat,
        )
        self.servidor = criar_servidor(
            "127.0.0.1",
            0,
            self.deps,
            self.canal,
            ServicoIcones(lambda: self.lcu),
            tempo_limite=TEMPO_LIMITE_TESTE,
        )
        self.porta = self.servidor.server_address[1]
        self.url = f"http://127.0.0.1:{self.porta}"
        threading.Thread(
            target=self.servidor.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        ).start()

    def encerrar(self) -> None:
        self.servidor.shutdown()
        self.servidor.server_close()

    def requisitar(self, metodo, caminho, corpo=None, cookie=None, cabecalhos=None, bruto=None):
        """Devolve (status, cabeçalhos, corpo_bytes)."""
        conexao = http.client.HTTPConnection("127.0.0.1", self.porta, timeout=5)
        todos = {"Content-Type": "application/json"} if metodo == "POST" else {}
        if cookie:
            todos["Cookie"] = f"lolremoto_sessao={cookie}"
        todos.update(cabecalhos or {})
        dados = bruto if bruto is not None else (None if corpo is None else json.dumps(corpo))
        if metodo == "POST" and dados is None:
            dados = "{}"
        conexao.request(metodo, caminho, body=dados, headers=todos)
        resposta = conexao.getresponse()
        resultado = (resposta.status, resposta.headers, resposta.read())
        conexao.close()
        return resultado

    def json(self, metodo, caminho, corpo=None, cookie=None, cabecalhos=None):
        status, _, conteudo = self.requisitar(metodo, caminho, corpo, cookie, cabecalhos)
        return status, json.loads(conteudo)

    def entrar(self) -> str:
        status, cabecalhos, _ = self.requisitar("POST", "/api/entrar", {"pin": PIN})
        assert status == 200
        return cabecalhos["Set-Cookie"].split(";")[0].split("=", 1)[1]
