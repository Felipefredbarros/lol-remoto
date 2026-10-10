import pytest

from conftest import carregar_fixture
from lol_remoto.dominio.fase import Fase, ForaDeFase
from lol_remoto.dominio.runas import (
    corpo_pagina,
    eh_pagina_do_app,
    flash_no_d,
    mapa,
    posicao_lcu,
    recomendacoes_de,
)
from lol_remoto.dominio.selecao import selecao_de
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.servicos.acoes import AcaoIndisponivel, ClienteDesconectado
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.runas import (
    INVENTARIO,
    PAGINA_ATUAL,
    PAGINAS,
    EscolhaInvalida,
    SemPaginaLivre,
    ServicoRunas,
)

REAL = carregar_fixture("runas_recomendadas.json")
AHRI = "/lol-perks/v1/recommended-pages/champion/103/position/MIDDLE/map/11"
SORAKA_ARAM = "/lol-perks/v1/recommended-pages/champion/36/position/NONE/map/12"


# ---------- domínio ----------


def test_recomendacoes_reais_da_ahri():
    recomendacoes = recomendacoes_de(REAL["ahri_meio_sr"])
    assert len(recomendacoes) == 3
    primeira = recomendacoes[0]
    assert (primeira.principal, primeira.descricao) == ("Eletrocutar", "Dano de combo")
    assert (primeira.estilo_principal, primeira.estilo_secundario) == (8100, 8200)
    assert primeira.runas == (8112, 8139, 8140, 8106, 8226, 8210, 5005, 5008, 5001)
    assert primeira.feiticos == (4, 14)  # Flash já estava no D


def test_aram_real_vem_com_flash_no_f_e_o_app_inverte():
    recomendacoes = recomendacoes_de(REAL["soraka_aram"])
    assert REAL["soraka_aram"][0]["summonerSpellIds"] == [13, 4]
    assert all(r.feiticos == (4, 13) for r in recomendacoes)


@pytest.mark.parametrize(
    ("entrada", "saida"),
    [((4, 14), (4, 14)), ((14, 4), (4, 14)), ((7, 21), (7, 21)), ((), ()), ((4,), (4,))],
)
def test_flash_no_d(entrada, saida):
    assert flash_no_d(entrada) == saida


def test_recomendacoes_malformadas_sao_ignoradas():
    dados = [None, {"perks": []}, {"primaryPerkStyleId": 1, "secondaryPerkStyleId": 2}, "x"]
    assert recomendacoes_de(dados) == []
    assert recomendacoes_de({"erro": 1}) == []


def test_posicao_mapa_e_pagina():
    assert posicao_lcu("middle") == "MIDDLE"
    assert posicao_lcu("") == "NONE"
    assert (mapa(aram=False), mapa(aram=True)) == (11, 12)
    assert eh_pagina_do_app({"name": "  lol remoto "})
    assert not eh_pagina_do_app({"name": "Minha"}) and not eh_pagina_do_app(None)
    corpo = corpo_pagina(recomendacoes_de(REAL["ahri_meio_sr"])[0], "LoL Remoto")
    assert corpo == {
        "name": "LoL Remoto",
        "primaryStyleId": 8100,
        "subStyleId": 8200,
        "selectedPerkIds": [8112, 8139, 8140, 8106, 8226, 8210, 5005, 5008, 5001],
        "current": True,
    }


# ---------- serviço ----------

PAGINA_DO_APP = {"id": 538483650, "name": "LoL Remoto", "isEditable": True}
OUTRA = {"id": 1, "name": "Minha página", "isEditable": True}


@pytest.fixture
def lcu():
    return LcuFalsa(
        {
            AHRI: REAL["ahri_meio_sr"],
            SORAKA_ARAM: REAL["soraka_aram"],
            PAGINAS: [OUTRA, PAGINA_DO_APP],
            INVENTARIO: {"canAddCustomPage": False},
            PAGINA_ATUAL: OUTRA,
        }
    )


@pytest.fixture
def estado(sessao_draft):
    sessao_draft["myTeam"][2]["championId"] = 103  # eu (meio) com a Ahri
    e = Estado()
    e.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    return e


def test_aplicar_grava_na_pagina_lol_remoto_e_poe_os_feiticos(estado, lcu):
    escolhida = ServicoRunas(estado, lambda: lcu).aplicar(2)
    assert escolhida.principal == "Toque Ígneo"
    assert lcu.chamadas == [
        (
            "PUT",
            "/lol-perks/v1/pages/538483650",
            {
                "name": "LoL Remoto",
                "primaryStyleId": 8200,
                "subStyleId": 8100,
                "selectedPerkIds": [8992, 8226, 8210, 8237, 8139, 8106, 5005, 5008, 5001],
                "current": True,
            },
        ),
        ("PATCH", "/lol-champ-select/v1/session/my-selection", {"spell1Id": 4, "spell2Id": 14}),
    ]


def test_sem_pagina_do_app_mas_com_espaco_cria_uma(estado, lcu):
    lcu.respostas[PAGINAS] = [OUTRA]
    lcu.respostas[INVENTARIO] = {"canAddCustomPage": True}
    ServicoRunas(estado, lambda: lcu).aplicar(0)
    metodo, caminho, corpo = lcu.chamadas[0]
    assert (metodo, caminho, corpo["name"]) == ("POST", "/lol-perks/v1/pages", "LoL Remoto")


def test_sem_espaco_pede_confirmacao_e_nao_mexe_em_nada(estado, lcu):
    lcu.respostas[PAGINAS] = [OUTRA]
    servico = ServicoRunas(estado, lambda: lcu)
    with pytest.raises(SemPaginaLivre, match="Renomeie"):
        servico.aplicar(0)
    assert lcu.chamadas == []
    servico.aplicar(0, sobrescrever_atual=True)
    assert lcu.chamadas[0][:2] == ("PUT", "/lol-perks/v1/pages/1")
    assert lcu.chamadas[0][2]["name"] == "Minha página"  # mantém o nome da página dele


def test_aram_usa_o_mapa_do_aram_e_inverte_o_flash(lcu, sessao_aram):
    estado = Estado()
    estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_aram))
    ServicoRunas(estado, lambda: lcu).aplicar(0)  # meu campeão no ARAM: 36
    assert lcu.chamadas[-1][2] == {"spell1Id": 4, "spell2Id": 13}


@pytest.mark.parametrize("indice", [3, -1, None, True, "0"])
def test_indice_invalido(estado, lcu, indice):
    with pytest.raises(EscolhaInvalida):
        ServicoRunas(estado, lambda: lcu).aplicar(indice)
    assert lcu.chamadas == []


def test_sem_campeao_ainda(lcu, sessao_draft):
    estado = Estado()
    estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    with pytest.raises(AcaoIndisponivel, match="campeão"):
        ServicoRunas(estado, lambda: lcu).recomendacoes()


@pytest.mark.parametrize("fase", [Fase.FILA, Fase.PARTIDA_ENCONTRADA, Fase.EM_PARTIDA])
def test_so_na_selecao(fase, lcu, sessao_draft):
    estado = Estado()
    estado.atualizar(fase=fase, selecao=selecao_de(sessao_draft))
    with pytest.raises(ForaDeFase):
        ServicoRunas(estado, lambda: lcu).aplicar(0)
    assert lcu.chamadas == []


def test_cliente_fechado(estado):
    with pytest.raises(ClienteDesconectado):
        ServicoRunas(estado, lambda: None).recomendacoes()


def test_nomes_de_estilos_e_feiticos_ficam_em_cache(estado, lcu):
    lcu.respostas["/lol-perks/v1/styles"] = [{"id": 8100, "name": "Dominação"}]
    servico = ServicoRunas(estado, lambda: lcu)
    assert servico.nomes("estilos") == {8100: "Dominação"}
    lcu.respostas["/lol-perks/v1/styles"] = []
    assert servico.nomes("estilos") == {8100: "Dominação"}
