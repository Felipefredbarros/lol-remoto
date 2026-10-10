import json

import pytest

from lol_remoto.anonimizador import (
    AnonimizacaoIncompleta,
    Anonimizador,
    anonimizar_arquivo,
)


def test_troca_nomes_e_ids_de_forma_consistente():
    anonimizar = Anonimizador()
    dados = {
        "myTeam": [
            {"gameName": "Fulano", "tagLine": "BR1", "puuid": "abc-123", "summonerId": 987654},
            {"gameName": "Ciclano", "tagLine": "XYZ", "puuid": "def-456", "summonerId": 123456},
        ],
        "localPlayer": {"gameName": "Fulano", "puuid": "abc-123"},
        "championId": 103,
    }
    resultado = anonimizar(dados)
    assert resultado["myTeam"][0] == {
        "gameName": "Jogador1",
        "tagLine": "TESTE",
        "puuid": "puuid-1",
        "summonerId": 1,
    }
    assert resultado["myTeam"][1]["gameName"] == "Jogador2"
    assert resultado["localPlayer"] == {"gameName": "Jogador1", "puuid": "puuid-1"}
    assert resultado["championId"] == 103


def test_remove_segredos_do_chat_e_tokens():
    dados = {
        "chatDetails": {"multiUserChatPassword": "x", "mucJwtDto": {"jwt": "eyJ..."}},
        "authToken": "t",
        "timer": {"phase": "BAN_PICK"},
    }
    resultado = Anonimizador()(dados)
    assert resultado["chatDetails"] == "<removido>"
    assert resultado["authToken"] == "<removido>"
    assert resultado["timer"] == {"phase": "BAN_PICK"}


def test_vazio_continua_vazio_e_formato_estranho_e_removido():
    resultado = Anonimizador()({"gameName": "", "summonerId": 0, "puuid": {"x": 1}})
    assert resultado == {"gameName": "", "summonerId": 0, "puuid": "<removido>"}


def test_arquivo_jsonl(tmp_path):
    entrada = tmp_path / "gravacao.jsonl"
    linhas = [
        {"t": 0, "tipo": "GET", "uri": "/x", "dados": {"gameName": "Fulano"}},
        {"t": 1, "tipo": "Update", "uri": "/x", "dados": {"gameName": "Fulano"}},
    ]
    entrada.write_text("\n".join(json.dumps(linha) for linha in linhas) + "\n\n")
    saida = tmp_path / "fixtures" / "gravacao.jsonl"
    assert anonimizar_arquivo(entrada, saida) == 2
    texto = saida.read_text(encoding="utf-8")
    assert "Fulano" not in texto
    assert json.loads(texto.splitlines()[1])["dados"] == {"gameName": "Jogador1"}


def test_nao_grava_se_um_nome_vazar_por_campo_desconhecido(tmp_path):
    entrada = tmp_path / "gravacao.jsonl"
    dados = {"gameName": "Fulano", "campoNovoDoPatch": "mensagem para Fulano"}
    entrada.write_text(json.dumps({"dados": dados}) + "\n")
    saida = tmp_path / "saida.jsonl"
    with pytest.raises(AnonimizacaoIncompleta):
        anonimizar_arquivo(entrada, saida)
    assert not saida.exists()
