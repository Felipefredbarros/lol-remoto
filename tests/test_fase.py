import pytest

from lol_remoto.dominio.fase import DESCRICOES, Fase, ForaDeFase, exigir_fase, fase_de, pode_agir


def test_converte_texto_da_lcu():
    assert fase_de("ChampSelect") is Fase.SELECAO
    assert fase_de("None") is Fase.NENHUMA


@pytest.mark.parametrize("valor", ["FaseNovaDeUmPatch", None, 3, ""])
def test_valor_desconhecido_vira_desconhecida(valor):
    assert fase_de(valor) is Fase.DESCONHECIDA


def test_toda_fase_tem_descricao():
    assert set(DESCRICOES) == set(Fase)


@pytest.mark.parametrize("fase", [Fase.PARTIDA_ENCONTRADA, Fase.SELECAO])
def test_pode_agir_na_fila_e_na_selecao(fase):
    assert pode_agir(fase)


@pytest.mark.parametrize(
    "fase", [f for f in Fase if f not in (Fase.PARTIDA_ENCONTRADA, Fase.SELECAO)]
)
def test_nao_pode_agir_em_nenhuma_outra_fase(fase):
    # Regra central do projeto: nada dentro da partida (ADR 0002).
    assert not pode_agir(fase)
    with pytest.raises(ForaDeFase):
        exigir_fase(fase, fase)


def test_exigir_fase_aceita_a_fase_certa():
    exigir_fase(Fase.SELECAO, Fase.SELECAO)


def test_exigir_fase_recusa_fase_diferente():
    with pytest.raises(ForaDeFase, match="Partida encontrada"):
        exigir_fase(Fase.PARTIDA_ENCONTRADA, Fase.SELECAO)
