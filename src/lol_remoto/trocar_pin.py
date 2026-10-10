"""Comando `python -m lol_remoto --trocar-pin`: define um novo PIN pelo console.

Trocar o PIN também derruba todas as sessões (os celulares precisam entrar de novo).
"""

from __future__ import annotations

import getpass
from collections.abc import Callable
from pathlib import Path

from lol_remoto import config
from lol_remoto.dominio.pin import PIN_MINIMO, PinInvalido, gerar_pin, validar_pin

ARQUIVO_SESSOES = "sessoes.json"
DICA_REINICIAR = (
    "Se o LoL Remoto já estiver rodando, reinicie-o para usar o novo PIN:\n"
    '  Stop-ScheduledTask "LoL Remoto"; Start-ScheduledTask "LoL Remoto"'
)


def executar(
    caminho: Path,
    ler: Callable[[str], str] = getpass.getpass,
    escrever: Callable[[str], None] = print,
) -> int:
    """Pede o PIN (sem mostrar na tela), confirma e grava só o hash. Retorna o código de saída."""
    escrever(f"Novo PIN: só números, mínimo {PIN_MINIMO} dígitos. Deixe vazio para gerar um.")
    novo = ler("Novo PIN: ").strip()

    if not novo:
        novo = gerar_pin()
        escrever(f"\nPIN gerado: {novo}\nAnote agora: ele não fica salvo em texto em lugar nenhum.")
    else:
        try:
            validar_pin(novo)
        except PinInvalido as erro:
            escrever(str(erro))
            return 1
        if ler("Repita o PIN: ").strip() != novo:
            escrever("Os PINs não conferem. Nada foi alterado.")
            return 1

    try:
        config.trocar_pin(caminho, novo)
    except config.ConfigInvalida as erro:
        escrever(f"Configuração inválida, nada foi alterado: {erro}")
        return 1
    sessoes = caminho.with_name(ARQUIVO_SESSOES)
    if sessoes.exists():
        sessoes.unlink()
        escrever("Todas as sessões foram encerradas: entre de novo nos aparelhos.")
    escrever(f"\nPIN salvo em {caminho} (só o hash fica guardado).")
    escrever(DICA_REINICIAR)
    return 0
