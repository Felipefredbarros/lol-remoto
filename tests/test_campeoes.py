import pytest

from lol_remoto.dominio.campeoes import Campeao, Catalogo, normalizar

# Trecho no formato de /lol-game-data/assets/v1/champion-summary.json (pt_BR).
RESUMO = [
    {"id": -1, "name": "Nenhum", "alias": "None"},
    {"id": 1, "name": "Annie", "alias": "Annie"},
    {"id": 34, "name": "Anivia", "alias": "Anivia"},
    {"id": 41, "name": "Gangplank", "alias": "Gangplank"},
    {"id": 145, "name": "Kai'Sa", "alias": "Kaisa"},
    {"id": 136, "name": "Aurelion Sol", "alias": "AurelionSol"},
    {"id": 102, "name": "Shyvana", "alias": "Shyvana"},
    {"id": 22, "name": "Ashe", "alias": "Ashe"},
]


@pytest.fixture
def catalogo():
    return Catalogo.de_json(RESUMO)


def test_ignora_nenhum_e_entradas_quebradas():
    catalogo = Catalogo.de_json(
        [*RESUMO, "lixo", {"id": True, "name": "x"}, {"id": 999}, {"id": 0, "name": "Zero"}]
    )
    assert len(catalogo) == 7
    assert -1 not in catalogo
    assert 999 not in catalogo


def test_json_que_nao_e_lista_vira_catalogo_vazio():
    assert len(Catalogo.de_json({"erro": 1})) == 0


def test_nome(catalogo):
    assert catalogo.nome(145) == "Kai'Sa"
    assert catalogo.nome(0) is None
    assert catalogo.nome(12345) is None


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Kai'Sa", "kaisa"),
        ("Aurelion Sol", "aurelionsol"),
        ("Nunu & Willump", "nunuwillump"),
        ("Jarvan IV", "jarvaniv"),
        ("Ámbar", "ambar"),
    ],
)
def test_normalizar(texto, esperado):
    assert normalizar(texto) == esperado


def test_busca_sem_acento_pontuacao_ou_maiusculas(catalogo):
    assert catalogo.buscar("KAISA") == [Campeao(145, "Kai'Sa")]
    assert catalogo.buscar("aurelion s") == [Campeao(136, "Aurelion Sol")]


def test_busca_poe_quem_comeca_com_o_texto_primeiro(catalogo):
    nomes = [c.nome for c in catalogo.buscar("an")]
    assert nomes == ["Anivia", "Annie", "Gangplank", "Shyvana"]


def test_busca_vazia_lista_todos_em_ordem(catalogo):
    nomes = [c.nome for c in catalogo.buscar()]
    assert nomes == sorted(nomes, key=normalizar)
    assert len(nomes) == 7


def test_variantes_com_o_mesmo_nome_aparecem_uma_vez():
    # O cliente real (out/2026) traz "Jade_Annie" (60001) com o nome "Annie".
    catalogo = Catalogo.de_json([*RESUMO, {"id": 60001, "name": "Annie", "alias": "Jade_Annie"}])
    assert catalogo.buscar("annie") == [Campeao(1, "Annie")]
    assert catalogo.nome(60001) == "Annie"
    assert catalogo.buscar("annie", permitidos=[60001]) == [Campeao(60001, "Annie")]


def test_busca_so_entre_permitidos(catalogo):
    assert [c.id for c in catalogo.buscar("a", permitidos=[22, 41, 9999])] == [22, 41]
