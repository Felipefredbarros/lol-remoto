import pytest

from lol_remoto.dominio.ready_check import ReadyCheck, Resposta, ready_check_de


def test_partida_encontrada_sem_resposta():
    dados = {"state": "InProgress", "playerResponse": "None", "timer": 3.5, "declinerIds": []}
    assert ready_check_de(dados) == ReadyCheck(True, Resposta.NENHUMA, 3.5)


def test_aceita():
    dados = {"state": "InProgress", "playerResponse": "Accepted", "timer": 5}
    assert ready_check_de(dados).resposta is Resposta.ACEITA


def test_valores_estranhos_viram_neutros():
    dados = {"state": "EveryoneReady", "playerResponse": "Talvez", "timer": True}
    assert ready_check_de(dados) == ReadyCheck(False, Resposta.NENHUMA, 0.0)


@pytest.mark.parametrize("dados", [None, [], {}, {"timer": 1}])
def test_sem_partida_encontrada(dados):
    assert ready_check_de(dados) is None
