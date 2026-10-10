"""Utilidades compartilhadas pelos testes."""

import json
from pathlib import Path

import pytest

PASTA_FIXTURES = Path(__file__).parent / "fixtures"


def carregar_fixture(nome: str):
    return json.loads((PASTA_FIXTURES / nome).read_text(encoding="utf-8"))


@pytest.fixture
def sessao_draft():
    return carregar_fixture("selecao_draft.json")


@pytest.fixture
def sessao_aram():
    return carregar_fixture("selecao_aram.json")


@pytest.fixture(autouse=True)
def hash_rapido(monkeypatch):
    """O config gera hashes com 600 mil iterações; nos testes, 1.000 bastam."""
    from lol_remoto import config
    from lol_remoto.dominio.pin import gerar_hash

    monkeypatch.setattr(config, "gerar_hash", lambda pin: gerar_hash(pin, iteracoes=1_000))
