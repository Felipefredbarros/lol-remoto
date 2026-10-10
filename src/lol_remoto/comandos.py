"""Comandos avulsos do console: `--gravar`, `--anonimizar` e `--testar-notificacao`."""

from __future__ import annotations

import sys
import threading
from pathlib import Path

from lol_remoto import anonimizador, config, gravacao
from lol_remoto.plataforma.ntfy import ErroNotificacao, Notificacao, NotificadorNtfy


def carregar_config(caminho: Path) -> config.Config | None:
    """Lê (ou cria) o config. Mostra o PIN gerado uma única vez, se houver console."""
    try:
        cfg, pin_gerado = config.carregar_ou_criar(caminho)
    except config.ConfigInvalida as erro:
        if sys.stderr is not None:
            print(f"Configuração inválida: {erro}", file=sys.stderr)
        return None
    if pin_gerado and sys.stdout is not None:
        print(f"Configuração criada em {caminho}.")
        print(f"Seu PIN: {pin_gerado}  (anote: só o hash fica guardado)")
    return cfg


def gravar(pasta_lol: Path, destino: Path) -> int:
    # Roda em outra thread: no Windows, Ctrl+C não interrompe um recv() bloqueado.
    parar = threading.Event()
    gravador = threading.Thread(
        target=gravacao.gravar, args=(pasta_lol, destino), kwargs={"parar": parar}, daemon=True
    )
    gravador.start()
    try:
        while gravador.is_alive():
            gravador.join(0.5)
    except KeyboardInterrupt:
        print("\nParando...")
        parar.set()
        gravador.join(5)
    return 0


def anonimizar(entrada: Path, saida: Path) -> int:
    try:
        linhas = anonimizador.anonimizar_arquivo(entrada, saida)
    except anonimizador.AnonimizacaoIncompleta as erro:
        print(f"Nada foi gravado: {erro}", file=sys.stderr)
        return 1
    print(f"{linhas} linhas anonimizadas em {saida}")
    return 0


def testar_notificacao(caminho_config: Path) -> int:
    cfg = carregar_config(caminho_config)
    if cfg is None:
        return 1
    print(f"No app ntfy do celular, assine o tópico: {cfg.ntfy_topico}")
    print(f"(servidor: {cfg.ntfy_servidor})")
    notificador = NotificadorNtfy(cfg.ntfy_servidor, cfg.ntfy_topico, cfg.ntfy_token)
    try:
        notificador.enviar(
            Notificacao(
                titulo="LoL Remoto",
                mensagem="Teste: se você está vendo isto, as notificações funcionam.",
                tags=("white_check_mark",),
            )
        )
    except ErroNotificacao as erro:
        print(f"Falhou: {erro}", file=sys.stderr)
        return 1
    print("Notificação de teste enviada.")
    return 0
