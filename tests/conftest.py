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
