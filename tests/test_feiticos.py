"""Feitiços separados das runas (ADR 0010): lista do modo, troca D/F e a trava de fase."""

import pytest

from conftest import carregar_fixture
from lol_remoto.dominio.fase import Fase, ForaDeFase
from lol_remoto.dominio.feiticos import (
    FeiticoIndisponivel,
    disponiveis,
    feiticos_de,
    flash_no_d,
    trocar,
)
from lol_remoto.dominio.selecao import selecao_de
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.servicos.acoes import ClienteDesconectado
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.feiticos import LISTA, MINHA_SELECAO, ServicoFeiticos

LISTA_REAL = carregar_fixture("feiticos.json")

# ---------- domínio ----------


def test_leitura_ignora_lixo_e_icone_fora_dos_assets():
    feiticos = feiticos_de(
        [
            {"id": 4, "name": "Flash", "gameModes": ["CLASSIC"], "iconPath": "/x/../../etc"},
            {"id": "5", "name": "Texto"},
            {"id": 6, "name": ""},
            {"id": True, "name": "Bool"},
            "lixo",
        ]
    )
    assert [(f.id, f.nome, f.icone) for f in feiticos] == [(4, "Flash", None)]
    assert feiticos_de(None) == []


def test_feiticos_do_rift_e_do_aram():
    todos = feiticos_de(LISTA_REAL)
    rift = [f.nome for f in disponiveis(todos, aram=False)]
    aram = [f.nome for f in disponiveis(todos, aram=True)]
    assert rift == [
        "Barreira", "Curar", "Exaustão", "Fantasma", "Flash", "Golpear", "Incendiar",
        "Purificar", "Teleporte",
    ]  # fmt: skip
    assert "Clareza" in aram and "Marcar" in aram
    assert "Golpear" not in aram and "Teleporte" not in aram
    assert "Ao Rei!" not in rift + aram and "Espaço reservado" not in rift + aram


def test_sem_game_modes_usa_a_lista_de_reserva():
    todos = feiticos_de([{"id": 11, "name": "Golpear"}, {"id": 13, "name": "Clareza"}])
    assert [f.id for f in disponiveis(todos, aram=False)] == [11]
    assert [f.id for f in disponiveis(todos, aram=True)] == [13]


@pytest.mark.parametrize(
    ("atuais", "slot", "novo", "esperado"),
    [
        ((4, 14), "f", 12, (4, 12)),  # troca só o F
        ((4, 14), "d", 6, (6, 14)),  # troca só o D
        ((4, 14), "d", 14, (14, 4)),  # o do F vai para o D: os dois trocam
        ((4, 14), "f", 4, (14, 4)),  # o do D vai para o F: os dois trocam
        ((4, 14), "d", 4, (4, 14)),  # o mesmo: nada muda
        ((0, 0), "d", 4, (4, 0)),
    ],
)
def test_trocar(atuais, slot, novo, esperado):
    assert trocar(atuais, slot, novo) == esperado


def test_slot_invalido():
    with pytest.raises(FeiticoIndisponivel):
        trocar((4, 14), "q", 6)


@pytest.mark.parametrize(
    ("entrada", "saida"),
    [((4, 14), (4, 14)), ((14, 4), (4, 14)), ((7, 21), (7, 21)), ((), ()), ((4,), (4,))],
)
def test_flash_no_d(entrada, saida):
    assert flash_no_d(entrada) == saida


# ---------- serviço ----------


@pytest.fixture
def lcu():
    return LcuFalsa({LISTA: LISTA_REAL})


def _estado(sessao, fase=Fase.SELECAO):
    estado = Estado()
    estado.atualizar(conectado=True, fase=fase, selecao=selecao_de(sessao))
    return estado


def test_trocar_o_f_manda_o_par_para_o_cliente(lcu, sessao_draft):
    servico = ServicoFeiticos(_estado(sessao_draft), lambda: lcu)  # eu: Flash + Incendiar
    assert servico.trocar("f", 12) == (4, 12)
    assert lcu.chamadas == [("PATCH", MINHA_SELECAO, {"spell1Id": 4, "spell2Id": 12})]


def test_flash_para_o_f_troca_os_dois(lcu, sessao_draft):
    servico = ServicoFeiticos(_estado(sessao_draft), lambda: lcu)
    servico.trocar("F", 4)  # maiúscula também vale
    assert lcu.chamadas[-1][2] == {"spell1Id": 14, "spell2Id": 4}


@pytest.mark.parametrize("feitico", [13, 999, "4", None, True])
def test_feitico_fora_do_modo_ou_invalido(feitico, lcu, sessao_draft):
    servico = ServicoFeiticos(_estado(sessao_draft), lambda: lcu)
    with pytest.raises(FeiticoIndisponivel):
        servico.trocar("d", feitico)  # 13 = Clareza, só no ARAM
    assert lcu.chamadas == []


@pytest.mark.parametrize("slot", [None, 1, "x"])
def test_slot_invalido_no_servico(slot, lcu, sessao_draft):
    with pytest.raises(FeiticoIndisponivel):
        ServicoFeiticos(_estado(sessao_draft), lambda: lcu).trocar(slot, 4)
    assert lcu.chamadas == []


def test_aram_oferece_clareza(lcu, sessao_aram):
    servico = ServicoFeiticos(_estado(sessao_aram), lambda: lcu)
    assert 13 in [f.id for f in servico.lista()]
    servico.trocar("f", 13)
    assert lcu.chamadas[-1][2]["spell2Id"] == 13


@pytest.mark.parametrize("fase", [Fase.FILA, Fase.PARTIDA_ENCONTRADA, Fase.EM_PARTIDA])
def test_nada_fora_da_selecao(fase, lcu, sessao_draft):
    """Regra 1: dentro da partida (ou antes da seleção) os feitiços não mudam."""
    servico = ServicoFeiticos(_estado(sessao_draft, fase), lambda: lcu)
    with pytest.raises(ForaDeFase):
        servico.trocar("f", 12)
    with pytest.raises(ForaDeFase):
        servico.lista()
    assert lcu.chamadas == []


def test_usa_a_lista_carregada_pelo_monitor(sessao_draft):
    estado = _estado(sessao_draft)
    estado.feiticos = feiticos_de(LISTA_REAL)
    servico = ServicoFeiticos(estado, lambda: None)  # sem precisar do cliente
    assert servico.nomes()[4] == "Flash"
    assert servico.caminho_icone(4).endswith("Summoner_flash.png")
    assert servico.caminho_icone(999) is None


def test_cliente_fechado(sessao_draft):
    with pytest.raises(ClienteDesconectado):
        ServicoFeiticos(_estado(sessao_draft), lambda: None).lista()
