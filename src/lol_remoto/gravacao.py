"""Comando `python -m lol_remoto --gravar PASTA`: grava os eventos reais da LCU em JSONL.

Serve para criar fixtures realistas (depois de anonimizadas, ver `anonimizador.py`). Só
escuta: não faz nenhuma ação no cliente. Para sozinho quando a partida começa a carregar.
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from lol_remoto.dominio.fase import Fase, fase_de
from lol_remoto.plataforma import lockfile
from lol_remoto.plataforma.lcu import EVENTOS_ASSINADOS, FASE, ErroLcu, Lcu, LcuHttp
from lol_remoto.plataforma.lockfile import Credenciais
from lol_remoto.plataforma.websocket import ConexaoFechada

INTERVALO_LOCKFILE = 3  # segundos
_FASES_FINAIS = (Fase.CARREGANDO, Fase.EM_PARTIDA)


def _aguardar_credenciais(
    pasta_lol: Path, parar: threading.Event, escrever: Callable[[str], None]
) -> Credenciais | None:
    avisou = False
    while not parar.is_set():
        credenciais = lockfile.ler(pasta_lol)
        if credenciais:
            return credenciais
        if not avisou:
            escrever(f"Esperando o cliente do LoL abrir (lockfile em {pasta_lol})...")
            avisou = True
        parar.wait(INTERVALO_LOCKFILE)
    return None


def gravar(
    pasta_lol: Path,
    destino: Path,
    conectar: Callable[[Credenciais], Lcu] = LcuHttp,
    parar: threading.Event | None = None,
    escrever: Callable[[str], None] = print,
    relogio: Callable[[], float] = time.monotonic,
) -> Path | None:
    """Grava até a partida carregar, o cliente fechar ou `parar` ser acionado."""
    parar = parar or threading.Event()
    credenciais = _aguardar_credenciais(pasta_lol, parar, escrever)
    if credenciais is None:
        return None

    lcu = conectar(credenciais)
    parar_conexao = threading.Thread(target=lambda: (parar.wait(), lcu.fechar()), daemon=True)
    parar_conexao.start()

    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / f"gravacao-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    inicio = relogio()
    total = 0
    with arquivo.open("w", encoding="utf-8") as saida:

        def registrar(tipo: str, uri: str, dados: Any) -> None:
            nonlocal total
            linha = {"t": round(relogio() - inicio, 3), "tipo": tipo, "uri": uri, "dados": dados}
            saida.write(json.dumps(linha, ensure_ascii=False) + "\n")
            saida.flush()
            total += 1

        escrever(f"Gravando em {arquivo}. Entre na fila; Ctrl+C para parar.")
        try:
            for caminho in EVENTOS_ASSINADOS:  # estado inicial
                registrar("GET", caminho, lcu.get(caminho))
            for evento in lcu.eventos(EVENTOS_ASSINADOS):
                registrar(evento.tipo, evento.uri, evento.dados)
                if evento.uri == FASE:
                    escrever(f"Fase: {evento.dados}")
                    if fase_de(evento.dados) in _FASES_FINAIS:
                        escrever("Partida carregando: gravação encerrada.")
                        break
        except (ConexaoFechada, ErroLcu) as erro:
            if not parar.is_set():
                escrever(f"Conexão com o cliente encerrada: {erro}")
        finally:
            parar.set()  # libera a thread que fecha a conexão
    escrever(f"{total} eventos gravados em {arquivo}")
    return arquivo
