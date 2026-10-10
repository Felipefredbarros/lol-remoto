import pytest

from lol_remoto.plataforma.lockfile import Credenciais, LockfileInvalido, interpretar, ler

EXEMPLO = "LeagueClient:11028:49637:SenhaSecreta123:https"


def test_interpreta_o_formato_do_cliente():
    assert interpretar(EXEMPLO) == Credenciais(
        porta=49637, senha="SenhaSecreta123", protocolo="https", pid=11028
    )


def test_senha_nao_aparece_no_repr():
    assert "SenhaSecreta123" not in repr(interpretar(EXEMPLO))


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "LeagueClient:1:2:3",
        "LeagueClient:1:porta:senha:https",
        "LeagueClient:1:70000:senha:https",
        "LeagueClient:1:49637::https",
        "LeagueClient:1:49637:senha:ftp",
    ],
)
def test_formatos_invalidos(texto):
    with pytest.raises(LockfileInvalido):
        interpretar(texto)


def test_sem_lockfile_o_cliente_esta_fechado(tmp_path):
    assert ler(tmp_path) is None


def test_le_o_arquivo_da_pasta(tmp_path):
    (tmp_path / "lockfile").write_text(EXEMPLO + "\n", encoding="utf-8")
    assert ler(tmp_path).porta == 49637
