import pytest

from lol_remoto.dominio.selecao import Etapa, SelecaoInvalida, TipoAcao, selecao_de


def test_times_e_jogadores(sessao_draft):
    selecao = selecao_de(sessao_draft)
    assert [j.celula for j in selecao.aliados] == [0, 1, 2, 3, 4]
    assert [j.celula for j in selecao.inimigos] == [5, 6, 7, 8, 9]
    assert selecao.eu.posicao == "middle"
    assert selecao.eu.intencao == 103
    assert selecao.eu.nome == "Eu#TESTE"
    assert selecao.jogador(3).nome is None  # nome escondido pelo cliente
    assert selecao.jogador(6).campeao == 103
    assert selecao.jogador(42) is None


def test_ignora_acoes_que_nao_sao_ban_nem_pick(sessao_draft):
    selecao = selecao_de(sessao_draft)
    assert {a.tipo for a in selecao.acoes} == {TipoAcao.BAN, TipoAcao.PICK}
    assert 100 not in {a.id for a in selecao.acoes}


def test_bans_dos_dois_times_sem_os_pulados(sessao_draft):
    selecao = selecao_de(sessao_draft)
    assert selecao.bans(aliados=True) == (157, 238, 555, 84)
    assert selecao.bans(aliados=False) == (11, 17, 30, 99)


def test_minha_vez_e_acoes_em_andamento(sessao_draft):
    selecao = selecao_de(sessao_draft)
    assert [a.id for a in selecao.em_andamento] == [14, 15]
    assert selecao.minha_vez.id == 15
    assert selecao.minha_vez.tipo is TipoAcao.PICK


def test_confirmou(sessao_draft):
    selecao = selecao_de(sessao_draft)
    assert selecao.confirmou(0)
    assert not selecao.confirmou(1)  # só marcou (hover)
    assert selecao.confirmou(5)


def test_timer(sessao_draft):
    timer = selecao_de(sessao_draft).timer
    assert timer.etapa is Etapa.BANS_E_PICKS
    assert timer.ms_restantes == 27450
    assert not timer.infinito


def test_nao_e_aram(sessao_draft):
    selecao = selecao_de(sessao_draft)
    assert not selecao.eh_aram
    assert selecao.banco == ()


def test_aram(sessao_aram):
    selecao = selecao_de(sessao_aram)
    assert selecao.eh_aram
    assert selecao.eu.campeao == 36
    assert selecao.banco == (22, 53)
    assert selecao.pode_rerolar
    assert selecao.rerolls == 1
    assert selecao.minha_vez is None
    assert selecao.timer.etapa is Etapa.FINALIZACAO


def test_sem_minha_vez_quando_ninguem_esta_agindo(sessao_draft):
    for turno in sessao_draft["actions"]:
        for acao in turno:
            acao["isInProgress"] = False
    assert selecao_de(sessao_draft).minha_vez is None


def test_etapa_desconhecida_e_campos_estranhos(sessao_draft):
    sessao_draft["timer"]["phase"] = "ETAPA_NOVA"
    sessao_draft["myTeam"][0]["championId"] = True  # bool não pode virar o campeão 1
    sessao_draft["theirTeam"] = None
    sessao_draft["actions"] = [[{"type": "pick"}], "lixo", [None]]
    selecao = selecao_de(sessao_draft)
    assert selecao.timer.etapa is Etapa.DESCONHECIDA
    assert selecao.aliados[0].campeao == 0
    assert selecao.inimigos == ()
    assert len(selecao.acoes) == 1 and selecao.acoes[0].id == -1


@pytest.mark.parametrize("dados", [None, [], "texto", {}, {"myTeam": "x"}, {"myTeam": [1]}])
def test_formato_invalido(dados):
    with pytest.raises(SelecaoInvalida):
        selecao_de(dados)
