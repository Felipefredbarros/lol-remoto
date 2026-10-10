"""Ponto de entrada: `python -m lol_remoto`. Monta as dependências e inicia o app."""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from lol_remoto import __version__, comandos, config, trocar_pin
from lol_remoto.plataforma.lockfile import PASTA_PADRAO
from lol_remoto.plataforma.ntfy import NotificadorNtfy
from lol_remoto.plataforma.rede import descobrir_ip_tailscale
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.monitor import Monitor
from lol_remoto.servicos.notificacoes import ServicoNotificacoes

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


class _Endereco:
    """URL da página para o celular. O IP do Tailscale é descoberto uma vez, em segundo plano."""

    def __init__(self, fixo: str | None, porta: int) -> None:
        self._fixo = fixo
        self._porta = porta
        self._ip: str | None = None
        if not fixo:
            threading.Thread(target=self._descobrir, daemon=True).start()

    def _descobrir(self) -> None:
        self._ip = descobrir_ip_tailscale()

    def __call__(self) -> str | None:
        if self._fixo:
            return self._fixo.rstrip("/") + "/"
        return f"http://{self._ip}:{self._porta}/" if self._ip else None


def _executar_app(args: argparse.Namespace) -> int:
    arquivo_log = _configurar_log(args.verbose)
    log.info("LoL Remoto %s iniciando (log em %s)", __version__, arquivo_log)
    cfg = comandos.carregar_config(args.config)
    if cfg is None:
        log.error("Configuração inválida em %s", args.config)
        return 1

    estado = Estado(ausente=args.ausente)
    notificacoes = ServicoNotificacoes(
        estado,
        NotificadorNtfy(cfg.ntfy_servidor, cfg.ntfy_topico, cfg.ntfy_token),
        endereco=_Endereco(cfg.endereco_publico, cfg.porta),
    )
    monitor = Monitor(estado, args.pasta_lol or Path(cfg.pasta_lol))
    if args.ausente:
        log.info("Modo ausente ligado desde o início (--ausente)")

    threading.Thread(target=monitor.executar, name="monitor", daemon=True).start()
    parar = threading.Event()
    try:
        # Espera com timeout para o Ctrl+C funcionar no Windows.
        while not parar.wait(1):
            pass
    except KeyboardInterrupt:
        log.info("Encerrando")
    monitor.encerrar()
    notificacoes.encerrar()
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
