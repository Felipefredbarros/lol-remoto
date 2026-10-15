"""Ponto de entrada: `python -m lol_remoto`. Monta as dependências e inicia o app."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lol_remoto import __version__, comandos, config, trocar_pin
from lol_remoto.app import App
from lol_remoto.plataforma.ativos_reais import AtivosDoClienteReal
from lol_remoto.plataforma.lcu_simulada import LcuSimulada
from lol_remoto.plataforma.lockfile import PASTA_PADRAO, Credenciais

log = logging.getLogger("lol_remoto")


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
        "--simular",
        action="store_true",
        help="usa um cliente do LoL simulado (fila, partida encontrada e seleção com bots)",
    )
    parser.add_argument(
        "--trocar-pin", action="store_true", help="define um novo PIN e sai (não inicia o app)"
    )
    parser.add_argument(
        "--ausente",
        action="store_true",
        help="já inicia com o modo ausente ligado (normalmente se liga pela página)",
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
    parser.add_argument("--verbose", action="store_true", help="log detalhado")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser.parse_args(argv)


def _configurar_log(verbose: bool) -> Path:
    pasta = config.pasta_logs()
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / "lol-remoto.log"
    handlers: list[logging.Handler] = [
        RotatingFileHandler(arquivo, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    ]
    # Com pythonw.exe não existe console (sys.stderr é None).
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )
    return arquivo


def _executar_app(args: argparse.Namespace) -> int:
    arquivo_log = _configurar_log(args.verbose)
    log.info("LoL Remoto %s iniciando (log em %s)", __version__, arquivo_log)
    cfg = comandos.carregar_config(args.config)
    if cfg is None:
        log.error("Configuração inválida em %s", args.config)
        return 1
    if args.ausente:
        log.info("Modo ausente ligado desde o início (--ausente)")

    simulada = None
    extras = {}
    if args.simular:
        log.warning("Modo simulação: o cliente do LoL é falso (o real não é tocado)")
        cfg = config.para_simulacao(cfg)  # porta + 1: convive com o app instalado
        # As fotos vêm do cliente de verdade, se estiver aberto (só imagens, só GET).
        simulada = LcuSimulada(ativos=AtivosDoClienteReal(args.pasta_lol or Path(cfg.pasta_lol)))
        extras = {
            "conectar": lambda credenciais: simulada,
            "ler_credenciais": lambda: Credenciais(porta=1, senha="simulacao", protocolo="http"),
        }
    app = App(
        cfg,
        pasta_lol=args.pasta_lol or Path(cfg.pasta_lol),
        arquivo_sessoes=args.config.with_name(trocar_pin.ARQUIVO_SESSOES),
        pasta_icones=config.pasta_logs() / "icones",
        ausente=args.ausente,
        **extras,
    )
    if simulada is not None:
        simulada.iniciar()
    parar = threading.Event()
    try:
        return app.executar(parar)
    except KeyboardInterrupt:
        log.info("Encerrando")
        parar.set()
        if simulada is not None:
            simulada.encerrar()
        app.monitor.encerrar()
        app.notificacoes.encerrar()
        return 0


def main(argv: list[str] | None = None) -> int:
    args = _ler_argumentos(argv)
    if args.anonimizar:
        return comandos.anonimizar(*args.anonimizar)
    if args.gravar:
        return comandos.gravar(args.pasta_lol or PASTA_PADRAO, args.gravar)
    if args.testar_notificacao:
        return comandos.testar_notificacao(args.config)
    if args.trocar_pin:
        return trocar_pin.executar(args.config)
    return _executar_app(args)


if __name__ == "__main__":
    sys.exit(main())
