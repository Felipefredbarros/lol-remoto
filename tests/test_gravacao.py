import json
import threading

from lol_remoto.gravacao import gravar
from lol_remoto.plataforma.lcu import FASE, READY_CHECK, SESSAO_SELECAO
from lol_remoto.plataforma.lcu_falsa import LcuFalsa


def _lockfile(pasta):
    (pasta / "lockfile").write_text("LeagueClient:1:49637:senha:https", encoding="utf-8")


def _linhas(arquivo):
    return [json.loads(linha) for linha in arquivo.read_text(encoding="utf-8").splitlines()]


def test_grava_estado_inicial_e_eventos_ate_a_partida_carregar(tmp_path):
    _lockfile(tmp_path)
    lcu = LcuFalsa({FASE: "Matchmaking"})
    lcu.emitir(FASE, "ReadyCheck")
    lcu.emitir(SESSAO_SELECAO, {"myTeam": []})
    lcu.emitir(FASE, "GameStart")
    lcu.emitir(FASE, "InProgress")  # não deve ser gravado: parou antes

    arquivo = gravar(
        tmp_path, tmp_path / "gravacoes", conectar=lambda c: lcu, escrever=lambda m: None
    )

    linhas = _linhas(arquivo)
    assert [(linha["tipo"], linha["uri"]) for linha in linhas[:3]] == [
        ("GET", FASE),
        ("GET", SESSAO_SELECAO),
        ("GET", READY_CHECK),
    ]
    assert [linha["dados"] for linha in linhas[3:]] == ["ReadyCheck", {"myTeam": []}, "GameStart"]
    assert all("t" in linha for linha in linhas)


def test_cliente_fechando_encerra_a_gravacao(tmp_path):
    _lockfile(tmp_path)
    lcu = LcuFalsa()
    lcu.emitir(FASE, "Lobby")
    lcu.desconectar()
    mensagens = []
    arquivo = gravar(tmp_path, tmp_path, conectar=lambda c: lcu, escrever=mensagens.append)
    assert len(_linhas(arquivo)) == 4
    assert any("encerrada" in m for m in mensagens)


def test_parar_enquanto_espera_o_cliente(tmp_path):
    parar = threading.Event()
    parar.set()
    assert gravar(tmp_path, tmp_path, parar=parar, escrever=lambda m: None) is None
