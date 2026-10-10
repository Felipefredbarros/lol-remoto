import pytest

from lol_remoto.dominio.fase import Fase, ForaDeFase
from lol_remoto.dominio.selecao import TipoAcao, selecao_de
from lol_remoto.plataforma.lcu import ErroLcu
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.servicos.acoes import (
    BANIVEIS,
    PICKAVEIS,
    AcaoIndisponivel,
    CampeaoIndisponivel,
    ClienteDesconectado,
    ServicoAcoes,
)
from lol_remoto.servicos.estado import Estado


@pytest.fixture
def lcu():
    return LcuFalsa({PICKAVEIS: [1, 103, 121, 412], BANIVEIS: [1, 103, 121, 157]})


@pytest.fixture
def estado():
    return Estado()


@pytest.fixture
def acoes(estado, lcu):
    return ServicoAcoes(estado, lambda: lcu)


def _na_selecao(estado, sessao):
    estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao))


# ---------- trava de fase (ADR 0002) ----------

FASES_SEM_ACAO = [f for f in Fase if f not in (Fase.PARTIDA_ENCONTRADA, Fase.SELECAO)]


@pytest.mark.parametrize("fase", FASES_SEM_ACAO)
def test_nenhuma_acao_fora_da_fila_e_da_selecao(fase, estado, acoes, lcu, sessao_draft):
    estado.atualizar(fase=fase, selecao=selecao_de(sessao_draft))
    for acao in (
        acoes.aceitar,
        acoes.recusar,
        lambda: acoes.marcar(103),
        lambda: acoes.confirmar(103),
        acoes.rerolar,
        lambda: acoes.trocar_do_banco(22),
        lambda: acoes.disponiveis(TipoAcao.PICK),
    ):
        with pytest.raises(ForaDeFase):
            acao()
    assert lcu.chamadas == []


def test_aceitar_e_recusar_so_na_partida_encontrada(estado, acoes, lcu):
    estado.atualizar(fase=Fase.PARTIDA_ENCONTRADA)
    acoes.aceitar()
    acoes.recusar()
    assert lcu.chamadas == [
        ("POST", "/lol-matchmaking/v1/ready-check/accept", None),
        ("POST", "/lol-matchmaking/v1/ready-check/decline", None),
    ]
    estado.atualizar(fase=Fase.SELECAO)
    with pytest.raises(ForaDeFase):
        acoes.aceitar()


def test_cliente_fechado(estado):
    estado.atualizar(fase=Fase.PARTIDA_ENCONTRADA)
    with pytest.raises(ClienteDesconectado):
        ServicoAcoes(estado, lambda: None).aceitar()


def test_erro_da_lcu_e_repassado(estado, acoes, lcu):
    estado.atualizar(fase=Fase.PARTIDA_ENCONTRADA)
    lcu.erros["POST", "/lol-matchmaking/v1/ready-check/accept"] = ErroLcu("expirou", 500)
    with pytest.raises(ErroLcu):
        acoes.aceitar()


# ---------- marcar e confirmar ----------


def test_marcar_na_minha_vez(estado, acoes, lcu, sessao_draft):
    _na_selecao(estado, sessao_draft)  # minha vez: pick 15
    acoes.marcar(103)
    assert lcu.chamadas == [
        ("PATCH", "/lol-champ-select/v1/session/actions/15", {"championId": 103})
    ]


def test_confirmar_o_campeao_marcado(estado, acoes, lcu, sessao_draft):
    sessao_draft["actions"][4][1]["championId"] = 103  # já marcado
    _na_selecao(estado, sessao_draft)
    acoes.confirmar()
    assert lcu.chamadas == [
        ("PATCH", "/lol-champ-select/v1/session/actions/15", {"championId": 103, "completed": True})
    ]


def test_confirmar_com_campeao_marca_e_trava(estado, acoes, lcu, sessao_draft):
    _na_selecao(estado, sessao_draft)
    acoes.confirmar(412)
    assert lcu.chamadas[0][2] == {"championId": 412, "completed": True}


def test_confirmar_sem_nada_marcado(estado, acoes, sessao_draft):
    _na_selecao(estado, sessao_draft)
    with pytest.raises(AcaoIndisponivel, match="Marque"):
        acoes.confirmar()


@pytest.mark.parametrize("campeao", [None, 0, -1, True, "103", 999])
def test_campeao_invalido_ou_indisponivel(campeao, estado, acoes, lcu, sessao_draft):
    _na_selecao(estado, sessao_draft)
    with pytest.raises(CampeaoIndisponivel):
        acoes.marcar(campeao)
    assert lcu.chamadas == []


def test_ban_usa_a_lista_de_baniveis(estado, acoes, lcu, sessao_draft):
    for turno in sessao_draft["actions"]:
        for acao in turno:
            acao["isInProgress"] = False
    sessao_draft["actions"][0][2].update(isInProgress=True, completed=False)  # meu ban (id 3)
    _na_selecao(estado, sessao_draft)
    with pytest.raises(CampeaoIndisponivel):
        acoes.marcar(412)  # pickável, mas não banível
    acoes.confirmar(157)
    assert lcu.chamadas == [
        ("PATCH", "/lol-champ-select/v1/session/actions/3", {"championId": 157, "completed": True})
    ]


def test_nao_e_minha_vez(estado, acoes, sessao_draft):
    for turno in sessao_draft["actions"]:
        for acao in turno:
            acao["isInProgress"] = False
    _na_selecao(estado, sessao_draft)
    with pytest.raises(AcaoIndisponivel, match="vez"):
        acoes.marcar(103)


def test_planejamento_declara_intencao_no_meu_pick(estado, acoes, lcu, sessao_draft):
    sessao_draft["timer"]["phase"] = "PLANNING"
    _na_selecao(estado, sessao_draft)
    acoes.marcar(103)
    assert lcu.chamadas == [
        ("PATCH", "/lol-champ-select/v1/session/actions/15", {"championId": 103})
    ]
    with pytest.raises(AcaoIndisponivel, match="planejamento"):
        acoes.confirmar(103)


def test_selecao_ainda_carregando(estado, acoes):
    estado.atualizar(fase=Fase.SELECAO)
    with pytest.raises(AcaoIndisponivel, match="carregando"):
        acoes.marcar(103)


def test_disponiveis_ignora_lixo(estado, acoes, lcu):
    estado.atualizar(fase=Fase.SELECAO)
    lcu.respostas[PICKAVEIS] = [1, "2", True, 3]
    assert acoes.disponiveis(TipoAcao.PICK) == [1, 3]


# ---------- ARAM ----------


def test_reroll(estado, acoes, lcu, sessao_aram):
    _na_selecao(estado, sessao_aram)
    acoes.rerolar()
    assert lcu.chamadas == [("POST", "/lol-champ-select/v1/session/my-selection/reroll", None)]


def test_reroll_sem_rerolls(estado, acoes, sessao_aram):
    sessao_aram["rerollsRemaining"] = 0
    _na_selecao(estado, sessao_aram)
    with pytest.raises(AcaoIndisponivel, match="reroll"):
        acoes.rerolar()


def test_trocar_do_banco(estado, acoes, lcu, sessao_aram):
    _na_selecao(estado, sessao_aram)
    acoes.trocar_do_banco(53)
    assert lcu.chamadas == [("POST", "/lol-champ-select/v1/session/bench/swap/53", None)]
    with pytest.raises(CampeaoIndisponivel):
        acoes.trocar_do_banco(99)


def test_aram_fora_do_aram(estado, acoes, sessao_draft):
    _na_selecao(estado, sessao_draft)
    with pytest.raises(AcaoIndisponivel, match="ARAM"):
        acoes.rerolar()
