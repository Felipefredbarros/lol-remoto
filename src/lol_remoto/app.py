"""Composição do app: monta estado, monitor, notificações e servidores HTTP, e os executa.

Só aqui (e no `__main__`) se escolhem implementações concretas; o `--simular` troca a LCU
e o notificador sem mudar mais nada.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from pathlib import Path

from lol_remoto.api.servidor import criar_servidor
from lol_remoto.api.sse import CanalSse
from lol_remoto.api.tipos import Dependencias
from lol_remoto.api.visao import visao
from lol_remoto.config import Config
from lol_remoto.plataforma.lcu import Lcu, LcuHttp
from lol_remoto.plataforma.lockfile import Credenciais
from lol_remoto.plataforma.ntfy import Notificador, NotificadorNtfy
from lol_remoto.plataforma.rede import descobrir_ip_tailscale
from lol_remoto.servicos.acoes import ServicoAcoes
from lol_remoto.servicos.autenticacao import ServicoAutenticacao
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.icones import ServicoIcones
from lol_remoto.servicos.monitor import Monitor
from lol_remoto.servicos.notificacoes import ServicoNotificacoes
from lol_remoto.servicos.runas import ServicoRunas
from lol_remoto.servicos.sessoes import ServicoSessoes
from lol_remoto.servicos.tokens import ServicoTokens

log = logging.getLogger("lol_remoto")

INTERVALO_BUSCA_TAILSCALE = 15  # segundos


class App:
    def __init__(
        self,
        cfg: Config,
        pasta_lol: Path,
        arquivo_sessoes: Path | None,
        ausente: bool = False,
        conectar: Callable[[Credenciais], Lcu] = LcuHttp,
        notificador: Notificador | None = None,
    ) -> None:
        self._cfg = cfg
        self._ip_tailscale: str | None = None
        self.estado = Estado(ausente=ausente)
        self.monitor = Monitor(self.estado, pasta_lol, conectar=conectar)
        self.notificador = notificador or NotificadorNtfy(
            cfg.ntfy_servidor, cfg.ntfy_topico, cfg.ntfy_token
        )
        tokens = ServicoTokens()
        self.notificacoes = ServicoNotificacoes(
            self.estado, self.notificador, endereco=self.endereco, tokens=tokens
        )
        self.deps = Dependencias(
            estado=self.estado,
            acoes=ServicoAcoes(self.estado, lambda: self.monitor.lcu),
            autenticacao=ServicoAutenticacao(cfg.pin_hash),
            sessoes=ServicoSessoes(arquivo_sessoes),
            tokens=tokens,
            notificador=self.notificador,
            runas=ServicoRunas(self.estado, lambda: self.monitor.lcu),
        )
        self._icones = ServicoIcones(lambda: self.monitor.lcu)
        self._canal = CanalSse(
            self.estado, lambda: visao(self.estado.atual, self.estado.catalogo, self.estado.agora())
        )

    def endereco(self) -> str | None:
        """URL da página para o celular (link e botões da notificação)."""
        if self._cfg.endereco_publico:
            return self._cfg.endereco_publico.rstrip("/") + "/"
        if self._ip_tailscale:
            return f"http://{self._ip_tailscale}:{self._cfg.porta}/"
        return None

    def servir(self, host: str) -> None:
        servidor = criar_servidor(host, self._cfg.porta, self.deps, self._canal, self._icones)
        threading.Thread(target=servidor.serve_forever, name=f"http-{host}", daemon=True).start()
        log.info("Ouvindo em http://%s:%s", host, self._cfg.porta)

    def _aguardar_tailscale(self, parar: threading.Event) -> None:
        """Fica tentando achar o IP do Tailscale (ele pode subir depois do Windows)."""
        avisou = False
        while not parar.is_set():
            ip = descobrir_ip_tailscale()
            if ip:
                self._ip_tailscale = ip
                try:
                    self.servir(ip)
                except OSError as erro:
                    log.error("Não foi possível ouvir em %s:%s: %s", ip, self._cfg.porta, erro)
                return
            if not avisou:
                log.warning(
                    "Tailscale não encontrado; tentando a cada %ss", INTERVALO_BUSCA_TAILSCALE
                )
                avisou = True
            parar.wait(INTERVALO_BUSCA_TAILSCALE)

    def executar(self, parar: threading.Event) -> int:
        """Roda até `parar` ser acionado. Retorna o código de saída."""
        try:
            self.servir("127.0.0.1")
        except OSError as erro:
            log.error(
                "Não foi possível usar a porta %s (já está rodando?): %s", self._cfg.porta, erro
            )
            return 1
        threading.Thread(target=self.monitor.executar, name="monitor", daemon=True).start()
        threading.Thread(
            target=self._aguardar_tailscale, args=(parar,), name="tailscale", daemon=True
        ).start()
        # Espera com timeout para o Ctrl+C funcionar no Windows.
        while not parar.wait(1):
            pass
        self.monitor.encerrar()
        self.notificacoes.encerrar()
        return 0
