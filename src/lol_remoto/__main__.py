"""Ponto de entrada: `python -m lol_remoto`. Monta as dependências e inicia o app."""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from lol_remoto import __version__, anonimizador, config, gravacao
from lol_remoto.plataforma.lockfile import PASTA_PADRAO
from lol_remoto.plataforma.ntfy import ErroNotificacao, Notificacao, NotificadorNtfy


def _ler_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lol_remoto", description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        default=config.pasta_config() / "config.json",
        help="caminho do config.json (padrão: %%APPDATA%%\\LolRemoto\\config.json)",
    )
    parser.add_argument(
        "--pasta-lol", type=Path, help="pasta do LoL, onde fica o lockfile (padrão: a do config)"
    )
    parser.add_argument(
        "--testar-notificacao",
        action="store_true",
        help="manda uma notificação de teste para o celular e sai",
    )
    parser.add_argument(
        "--gravar",
        type=Path,
        metavar="PASTA",
        help="grava os eventos reais da LCU em PASTA (só escuta) e sai",
    )
    parser.add_argument(
        "--anonimizar",
        type=Path,
        nargs=2,
        metavar=("ENTRADA", "SAIDA"),
        help="anonimiza uma gravação para virar fixture e sai",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def _gravar(pasta_lol: Path, destino: Path) -> int:
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


def _anonimizar(entrada: Path, saida: Path) -> int:
    try:
        linhas = anonimizador.anonimizar_arquivo(entrada, saida)
    except anonimizador.AnonimizacaoIncompleta as erro:
        print(f"Nada foi gravado: {erro}", file=sys.stderr)
        return 1
    print(f"{linhas} linhas anonimizadas em {saida}")
    return 0


def _carregar_config(caminho: Path) -> config.Config | None:
    try:
        cfg, pin_gerado = config.carregar_ou_criar(caminho)
    except config.ConfigInvalida as erro:
        print(f"Configuração inválida: {erro}", file=sys.stderr)
        return None
    if pin_gerado and sys.stdout is not None:
        print(f"Configuração criada em {caminho}.")
        print(f"Seu PIN: {pin_gerado}  (anote: só o hash fica guardado)")
    return cfg


def _testar_notificacao(caminho_config: Path) -> int:
    cfg = _carregar_config(caminho_config)
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


def main(argv: list[str] | None = None) -> int:
    args = _ler_argumentos(argv)
    if args.anonimizar:
        return _anonimizar(*args.anonimizar)
    if args.gravar:
        return _gravar(args.pasta_lol or PASTA_PADRAO, args.gravar)
    if args.testar_notificacao:
        return _testar_notificacao(args.config)
    print("O servidor ainda não foi implementado (ver docs/roteiro.md).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
