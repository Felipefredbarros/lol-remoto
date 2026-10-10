import copy
from dataclasses import replace

import pytest

from lol_remoto.dominio.avisos import Aviso, Momento, TipoAviso, avisos
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.ready_check import ReadyCheck, Resposta
from lol_remoto.dominio.selecao import selecao_de


def _tipos(anterior, atual):
    return [a.tipo for a in avisos(anterior, atual)]


@pytest.mark.parametrize(
    ("de", "para", "esperado"),
    [
        (Fase.SELECAO, Fase.FILA, [TipoAviso.DODGE]),
        (Fase.SELECAO, Fase.LOBBY, [TipoAviso.SELECAO_CANCELADA]),
        (Fase.SELECAO, Fase.NENHUMA, [TipoAviso.SELECAO_CANCELADA]),
        (Fase.SELECAO, Fase.CARREGANDO, [TipoAviso.CARREGANDO]),
        (Fase.SELECAO, Fase.EM_PARTIDA, [TipoAviso.CARREGANDO]),
        # Sem aviso (a partida encontrada depende dos dados de ready check; ver abaixo):
        (Fase.FILA, Fase.PARTIDA_ENCONTRADA, []),
        (Fase.PARTIDA_ENCONTRADA, Fase.FILA, []),
        (Fase.LOBBY, Fase.FILA, []),
        (Fase.FILA, Fase.LOBBY, []),
        (Fase.PARTIDA_ENCONTRADA, Fase.SELECAO, []),
        (Fase.CARREGANDO, Fase.EM_PARTIDA, []),
        (Fase.RECONECTAR, Fase.EM_PARTIDA, []),
        (Fase.EM_PARTIDA, Fase.FIM_DE_JOGO, []),
        (Fase.FIM_DE_JOGO, Fase.LOBBY, []),
        (Fase.FILA, Fase.FILA, []),
    ],
)
def test_avisos_de_mudanca_de_fase(de, para, esperado):
    assert _tipos(Momento(de), Momento(para)) == esperado


READY = ReadyCheck(em_andamento=True, resposta=Resposta.NENHUMA, segundos_decorridos=1.0)


def test_partida_encontrada_com_dados_de_ready_check():
    fila = Momento(Fase.FILA)
    so_fase = Momento(Fase.PARTIDA_ENCONTRADA)
    com_dados = Momento(Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    assert _tipos(fila, com_dados) == [TipoAviso.PARTIDA_ENCONTRADA]
    # Os dados podem chegar depois do evento de fase.
    assert _tipos(fila, so_fase) == []
    assert _tipos(so_fase, com_dados) == [TipoAviso.PARTIDA_ENCONTRADA]
    # Uma vez só, mesmo com o timer do ready check andando.
    depois = Momento(Fase.PARTIDA_ENCONTRADA, ready_check=replace(READY, segundos_decorridos=4))
    assert avisos(com_dados, depois) == []


def test_partida_personalizada_nao_e_partida_encontrada():
    # Gravação real: Matchmaking → ReadyCheck → ChampSelect em ms, sem dados de ready check.
    assert _tipos(Momento(Fase.FILA), Momento(Fase.PARTIDA_ENCONTRADA)) == []
    assert _tipos(Momento(Fase.PARTIDA_ENCONTRADA), Momento(Fase.SELECAO)) == []


@pytest.mark.parametrize(
    ("resposta", "para", "esperado"),
    [
        (Resposta.NENHUMA, Fase.FILA, TipoAviso.PARTIDA_RECUSADA),
        (Resposta.ACEITA, Fase.FILA, TipoAviso.PARTIDA_RECUSADA),
        (Resposta.NENHUMA, Fase.LOBBY, TipoAviso.NAO_ACEITOU),
        (Resposta.NENHUMA, Fase.NENHUMA, TipoAviso.NAO_ACEITOU),
        (Resposta.RECUSADA, Fase.LOBBY, TipoAviso.SAIU_DA_FILA),
        (Resposta.ACEITA, Fase.LOBBY, TipoAviso.SAIU_DA_FILA),
    ],
)
def test_fim_da_partida_encontrada(resposta, para, esperado):
    anterior = Momento(Fase.PARTIDA_ENCONTRADA, ready_check=replace(READY, resposta=resposta))
    assert _tipos(anterior, Momento(para)) == [esperado]


def test_partida_encontrada_que_vira_selecao_nao_avisa_saida():
    anterior = Momento(Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    assert _tipos(anterior, Momento(Fase.SELECAO)) == []


def test_sua_vez_de_escolher_ao_entrar_na_selecao(sessao_draft):
    selecao = selecao_de(sessao_draft)
    resultado = avisos(Momento(Fase.PARTIDA_ENCONTRADA), Momento(Fase.SELECAO, selecao))
    assert resultado == [Aviso(TipoAviso.SUA_VEZ_ESCOLHER, acao_id=15, segundos=27)]


def test_sua_vez_avisa_uma_vez_por_acao(sessao_draft):
    antes = Momento(Fase.SELECAO, selecao_de(sessao_draft))
    # Mesma ação, só o timer andou: não repete o aviso.
    sessao_draft["timer"]["adjustedTimeLeftInPhase"] = 12000
    depois = Momento(Fase.SELECAO, selecao_de(sessao_draft))
    assert avisos(antes, depois) == []


def test_sua_vez_de_banir_depois_de_nao_ser_sua_vez(sessao_draft):
    sem_vez = copy.deepcopy(sessao_draft)
    for turno in sem_vez["actions"]:
        for acao in turno:
            acao["isInProgress"] = False
    ban = sessao_draft["actions"][0][2]  # ban da célula 2 (eu)
    ban.update(completed=False, isInProgress=True)
    sessao_draft["actions"][4][1]["isInProgress"] = False

    resultado = avisos(
        Momento(Fase.SELECAO, selecao_de(sem_vez)), Momento(Fase.SELECAO, selecao_de(sessao_draft))
    )
    assert [(a.tipo, a.acao_id) for a in resultado] == [(TipoAviso.SUA_VEZ_BANIR, 3)]


def test_timer_infinito_nao_informa_segundos(sessao_draft):
    sessao_draft["timer"]["isInfinite"] = True
    resultado = avisos(Momento(Fase.LOBBY), Momento(Fase.SELECAO, selecao_de(sessao_draft)))
    assert resultado[0].segundos is None


def test_aram_avisa_o_campeao_e_nao_a_vez(sessao_aram):
    selecao = selecao_de(sessao_aram)
    resultado = avisos(Momento(Fase.PARTIDA_ENCONTRADA), Momento(Fase.SELECAO, selecao))
    assert resultado == [Aviso(TipoAviso.ARAM, segundos=61, campeao=36)]


def test_aram_avisa_quando_o_campeao_chega_e_nao_no_reroll(sessao_aram):
    sem_campeao = copy.deepcopy(sessao_aram)
    sem_campeao["myTeam"][2]["championId"] = 0
    sem_campeao["actions"] = [[{"id": 0, "actorCellId": 7, "type": "pick", "isInProgress": True}]]
    antes = Momento(Fase.SELECAO, selecao_de(sem_campeao))
    assert avisos(Momento(Fase.FILA), antes) == []  # nada de "sua vez" no ARAM
    depois = Momento(Fase.SELECAO, selecao_de(sessao_aram))
    assert _tipos(antes, depois) == [TipoAviso.ARAM]
    sessao_aram["myTeam"][2]["championId"] = 22  # reroll
    assert avisos(depois, Momento(Fase.SELECAO, selecao_de(sessao_aram))) == []


def test_planejamento_avisa_intencao_e_nao_o_ban(sessao_draft):
    # Gravação real: no planejamento o primeiro ban já vem "em andamento".
    for turno in sessao_draft["actions"]:
        for acao in turno:
            acao.update(completed=False, isInProgress=False, championId=0)
    sessao_draft["actions"][0][2]["isInProgress"] = True  # meu ban
    sessao_draft["timer"].update(phase="PLANNING", adjustedTimeLeftInPhase=24000)
    planejamento = Momento(Fase.SELECAO, selecao_de(sessao_draft))
    assert avisos(Momento(Fase.FILA), planejamento) == [Aviso(TipoAviso.PLANEJAMENTO, segundos=24)]

    sessao_draft["timer"].update(phase="BAN_PICK", adjustedTimeLeftInPhase=30000)
    bans = Momento(Fase.SELECAO, selecao_de(sessao_draft))
    assert avisos(planejamento, bans) == [Aviso(TipoAviso.SUA_VEZ_BANIR, acao_id=3, segundos=30)]


def test_selecao_sem_dados_nao_quebra():
    assert avisos(Momento(Fase.PARTIDA_ENCONTRADA), Momento(Fase.SELECAO)) == []
