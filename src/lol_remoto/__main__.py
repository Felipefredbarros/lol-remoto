"""Ponto de entrada: `python -m lol_remoto`. Monta as dependências e inicia o app."""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from lol_remoto import __version__, anonimizador, gravacao
from lol_remoto.plataforma.lockfile import PASTA_PADRAO


def _ler_argumentos(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lol_remoto", description=__doc__)
    parser.add_argument(
        "--pasta-lol", type=Path, default=PASTA_PADRAO, help="pasta do LoL (onde fica o lockfile)"
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


def main(argv: list[str] | None = None) -> int:
    args = _ler_argumentos(argv)
    if args.anonimizar:
        return _anonimizar(*args.anonimizar)
    if args.gravar:
        return _gravar(args.pasta_lol, args.gravar)
    print("O servidor ainda não foi implementado (ver docs/roteiro.md).", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
