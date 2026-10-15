"""Scripts de instalação (ADR 0011): conferências estáticas, sem executar nada no Windows."""

import re
from pathlib import Path

import pytest

PASTA = Path(__file__).resolve().parent.parent / "scripts"
SCRIPTS = sorted(PASTA.glob("*.ps1"))


def _texto(nome):
    return (PASTA / nome).read_text(encoding="utf-8")


def test_existem_os_tres_scripts():
    assert [s.name for s in SCRIPTS] == ["desinstalar.ps1", "instalar.ps1", "reiniciar.ps1"]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda s: s.name)
def test_so_ascii(script):
    """Regra 11: o PowerShell 5.1 lê arquivo sem BOM como ANSI e quebra os acentos."""
    script.read_bytes().decode("ascii")


@pytest.mark.parametrize("nome", ["instalar.ps1", "desinstalar.ps1"])
def test_pede_administrador(nome):
    assert _texto(nome).startswith("#Requires -RunAsAdministrator")


def test_reiniciar_nao_pede_administrador():
    assert "#Requires" not in _texto("reiniciar.ps1")


@pytest.mark.parametrize("nome", ["instalar.ps1", "desinstalar.ps1", "reiniciar.ps1"])
def test_mesmo_nome_de_tarefa(nome):
    assert '$NomeTarefa = "LoL Remoto"' in _texto(nome)


@pytest.mark.parametrize("nome", ["instalar.ps1", "desinstalar.ps1"])
def test_mesma_regra_de_firewall(nome):
    assert '$NomeRegra = "LoL Remoto (Tailscale)"' in _texto(nome)


def test_firewall_so_libera_o_tailscale():
    texto = _texto("instalar.ps1")
    assert '$RedeTailscale = "100.64.0.0/10"' in texto
    regra = re.search(r"New-NetFirewallRule.*?\| Out-Null", texto, re.DOTALL).group(0)
    assert "-RemoteAddress $RedeTailscale" in regra and "-Direction Inbound" in regra
    assert '@("$porta", "$portaSimulacao")' in regra  # o app e o --simular (porta + 1)


def test_tarefa_roda_sem_janela_e_sem_privilegio():
    texto = _texto("instalar.ps1")
    assert '-Execute $pythonw -Argument "-m lol_remoto"' in texto
    assert "-RunLevel Limited" in texto and "-AtLogOn" in texto


def test_pin_definido_antes_da_tarefa():
    """Sem config, o app criaria um PIN e o mostraria num console que não existe."""
    texto = _texto("instalar.ps1")
    assert texto.index("--trocar-pin") < texto.index("Register-ScheduledTask")
