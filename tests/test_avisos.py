import copy

import pytest

from lol_remoto.dominio.avisos import Aviso, Momento, TipoAviso, avisos
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.selecao import selecao_de


def _tipos(anterior, atual):
    return [a.tipo for a in avisos(anterior, atual)]


@pytest.mark.parametrize(
    ("de", "para", "esperado"),
    [
        (Fase.FILA, Fase.PARTIDA_ENCONTRADA, [TipoAviso.PARTIDA_ENCONTRADA]),
        (Fase.NENHUMA, Fase.PARTIDA_ENCONTRADA, [TipoAviso.PARTIDA_ENCONTRADA]),
        (Fase.PARTIDA_ENCONTRADA, Fase.FILA, [TipoAviso.PARTIDA_RECUSADA]),
        (Fase.SELECAO, Fase.FILA, [TipoAviso.DODGE]),
        (Fase.SELECAO, Fase.LOBBY, [TipoAviso.SELECAO_CANCELADA]),
        (Fase.SELECAO, Fase.NENHUMA, [TipoAviso.SELECAO_CANCELADA]),
        (Fase.SELECAO, Fase.CARREGANDO, [TipoAviso.CARREGANDO]),
        (Fase.SELECAO, Fase.EM_PARTIDA, [TipoAviso.CARREGANDO]),
        # Sem aviso:
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


def test_partida_encontrada_avisa_uma_vez_so():
    momento = Momento(Fase.PARTIDA_ENCONTRADA)
    assert avisos(momento, momento) == []


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


def test_aram_nao_tem_aviso_de_vez(sessao_aram):
    selecao = selecao_de(sessao_aram)
    assert avisos(Momento(Fase.PARTIDA_ENCONTRADA), Momento(Fase.SELECAO, selecao)) == []


def test_selecao_sem_dados_nao_quebra():
    assert avisos(Momento(Fase.PARTIDA_ENCONTRADA), Momento(Fase.SELECAO)) == []
