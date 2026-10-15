"""Etapas da página sequencial (api/passos.py), inclusive numa ranqueada real gravada."""

import json

import pytest

from conftest import PASTA_FIXTURES
from lol_remoto.api.passos import passos
from lol_remoto.api.visao import visao
from lol_remoto.dominio.campeoes import Catalogo
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.selecao import selecao_de
from lol_remoto.servicos.estado import Retrato

CATALOGO = Catalogo.de_json(
    [{"id": 103, "name": "Ahri"}, {"id": 145, "name": "Kai'Sa"}, {"id": 36, "name": "Dr. Mundo"}]
)
FEITICOS = {4: "Flash", 14: "Incendiar", 21: "Barreira"}


def _passos(fase, selecao=None):
    return passos(Retrato(fase=fase, selecao=selecao), CATALOGO, FEITICOS)


def _resumo(lista):
    """Ex.: ["fila:feito", "partida:atual", ...]."""
    return [f"{p['id']}:{p['estado']}" for p in lista]


def _atual(lista):
    return next(p["id"] for p in lista if p["estado"] == "atual")


@pytest.mark.parametrize("fase", [Fase.NENHUMA, Fase.LOBBY, Fase.EM_PARTIDA, Fase.FIM_DE_JOGO])
def test_fora_do_caminho_nao_ha_etapas(fase):
    assert _passos(fase) == []


def test_antes_da_selecao():
    assert _resumo(_passos(Fase.FILA)) == [
        "fila:atual", "partida:pendente", "selecao:pendente", "carregando:pendente",
    ]  # fmt: skip
    partida = _passos(Fase.PARTIDA_ENCONTRADA)
    assert _atual(partida) == "partida" and partida[0]["estado"] == "feito"
    assert _atual(_passos(Fase.SELECAO)) == "selecao"  # sessão ainda não chegou
    assert _atual(_passos(Fase.CARREGANDO)) == "carregando"


def test_escolha_alternada_na_minha_vez_de_pick(sessao_draft):
    lista = _passos(Fase.SELECAO, selecao_de(sessao_draft))
    assert _resumo(lista) == [
        "fila:feito", "partida:feito", "intencao:feito", "ban:feito",
        "pick:atual", "runas:pendente", "carregando:pendente",
    ]  # fmt: skip
    resumos = {p["id"]: p["resumo"] for p in lista}
    assert resumos["partida"] == "aceita"
    assert resumos["intencao"] == "Ahri"
    assert resumos["ban"] == "sem ban"  # meu ban na fixture ficou vazio
    assert resumos["pick"] is None  # ainda não feito


def test_sem_bans_pula_intencao_e_ban(sessao_draft):
    for turno in sessao_draft["actions"]:
        turno[:] = [a for a in turno if a["type"] != "ban"]
    lista = _passos(Fase.SELECAO, selecao_de(sessao_draft))
    assert [p["id"] for p in lista] == ["fila", "partida", "pick", "runas", "carregando"]


def test_aram_vai_direto_para_as_runas(sessao_aram):
    lista = _passos(Fase.SELECAO, selecao_de(sessao_aram))
    assert _resumo(lista) == [
        "fila:feito", "partida:feito", "campeao:feito", "runas:atual", "carregando:pendente",
    ]  # fmt: skip
    assert lista[2]["resumo"] == "Dr. Mundo"


def _sessoes_da_gravacao(nome):
    linhas = (PASTA_FIXTURES / "gravacoes" / nome).read_text(encoding="utf-8").splitlines()
    for linha in map(json.loads, linhas):
        if linha["uri"] == "/lol-champ-select/v1/session" and linha["dados"]:
            yield selecao_de(linha["dados"])


def test_ranqueada_real_segue_a_ordem_da_partida():
    vistas = []
    ultima = None
    for selecao in _sessoes_da_gravacao("ranqueada_solo.jsonl"):
        atual = _atual(_passos(Fase.SELECAO, selecao))
        if not vistas or vistas[-1] != atual:
            vistas.append(atual)
        ultima = selecao
    assert vistas == ["intencao", "ban", "pick", "runas"]
    no_ban = next(s for s in _sessoes_da_gravacao("ranqueada_solo.jsonl") if s.minha_vez)
    resumos = {p["id"]: p["resumo"] for p in _passos(Fase.SELECAO, no_ban)}
    assert resumos["intencao"] == "Kai'Sa"

    lista = _passos(Fase.CARREGANDO, ultima)
    resumos = {p["id"]: p["resumo"] for p in lista if p["estado"] == "feito"}
    assert resumos == {
        "fila": None,
        "partida": "aceita",
        "intencao": None,  # o cliente zera a intenção depois do pick
        "ban": "sem ban",  # o ban que passou em branco (grade vazia, corrigido em c7793f5)
        "pick": "Kai'Sa",
        "runas": "Flash + Barreira",
    }


def test_ordem_dos_picks_na_ranqueada_real():
    sessoes = list(_sessoes_da_gravacao("ranqueada_solo.jsonl"))
    retrato = Retrato(fase=Fase.SELECAO, selecao=sessoes[-1])
    ordem = visao(retrato, CATALOGO, 0.0)["selecao"]["ordem_picks"]
    assert len(ordem) == 10 and [p["ordem"] for p in ordem] == list(range(1, 11))
    assert all(p["estado"] == "feito" for p in ordem)
    eu = next(p for p in ordem if p["eu"])
    assert eu["campeao"] == {"id": 145, "nome": "Kai'Sa"} and eu["aliado"]
    # Ranqueada: o 1º pick é de um time e depois os turnos de dois alternam.
    assert [p["aliado"] for p in ordem[:3]] == [True, False, False]


def test_ordem_marca_quem_esta_escolhendo(sessao_draft):
    retrato = Retrato(fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    ordem = visao(retrato, CATALOGO, 0.0)["selecao"]["ordem_picks"]
    agindo = [p["celula"] for p in ordem if p["estado"] == "agindo"]
    assert agindo == [1, 2]  # turno de dois picks do meu time; o meu é a célula 2
    assert [p["estado"] for p in ordem[:3]] == ["feito", "feito", "feito"]
