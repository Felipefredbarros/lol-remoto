import pytest

from lol_remoto.plataforma.lcu import FASE, ErroLcu, Evento
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.plataforma.websocket import ConexaoFechada


def test_get_devolve_copia_e_none_quando_nao_existe():
    lcu = LcuFalsa({FASE: "Lobby", "/lista": [1, 2]})
    assert lcu.get(FASE) == "Lobby"
    lcu.get("/lista").append(3)
    assert lcu.get("/lista") == [1, 2]
    assert lcu.get("/nada") is None


def test_enviar_registra_chamadas_e_pode_falhar():
    lcu = LcuFalsa()
    lcu.erros["POST", "/b"] = ErroLcu("recusado", 500)
    lcu.enviar("POST", "/a", {"x": 1})
    with pytest.raises(ErroLcu):
        lcu.enviar("POST", "/b")
    assert lcu.chamadas == [("POST", "/a", {"x": 1}), ("POST", "/b", None)]


def test_emitir_atualiza_o_get_e_entrega_o_evento():
    lcu = LcuFalsa()
    lcu.emitir(FASE, "Matchmaking")
    lcu.emitir("/lol-matchmaking/v1/ready-check", None, tipo="Delete")
    eventos = lcu.eventos([FASE])
    assert next(eventos) == Evento(FASE, "Update", "Matchmaking")
    assert next(eventos).tipo == "Delete"
    assert lcu.get(FASE) == "Matchmaking"
    assert lcu.assinados == [FASE]


def test_desconectar_encerra_os_eventos():
    lcu = LcuFalsa()
    lcu.desconectar()
    with pytest.raises(ConexaoFechada):
        next(lcu.eventos([FASE]))
