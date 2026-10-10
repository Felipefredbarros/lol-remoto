import pytest

from lol_remoto.servicos.tokens import ServicoTokens


class _Relogio:
    def __init__(self):
        self.agora = 50.0

    def __call__(self):
        return self.agora


def test_uso_unico():
    tokens = ServicoTokens()
    token = tokens.gerar()
    assert tokens.consumir(token)
    assert not tokens.consumir(token)


def test_expira():
    relogio = _Relogio()
    tokens = ServicoTokens(validade=15, relogio=relogio)
    token = tokens.gerar()
    relogio.agora += 16
    assert not tokens.consumir(token)


def test_invalidar_todos():
    tokens = ServicoTokens()
    token = tokens.gerar()
    tokens.invalidar_todos()
    assert not tokens.consumir(token)


@pytest.mark.parametrize("token", [None, "", 123, ["x"], "inventado"])
def test_tokens_invalidos(token):
    tokens = ServicoTokens()
    tokens.gerar()
    assert not tokens.consumir(token)


def test_tokens_diferentes_a_cada_partida():
    tokens = ServicoTokens()
    assert tokens.gerar() != tokens.gerar()
