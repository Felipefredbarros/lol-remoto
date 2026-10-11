"""Reproduz gravações reais (anonimizadas) do cliente pelo monitor e confere as notificações.

As gravações ficam em tests/fixtures/gravacoes/ e foram feitas com `--gravar` em 10/2026.
Se um patch do LoL mudar o formato, grave de novo e compare.
"""

import json
import threading
import time

import pytest

from conftest import PASTA_FIXTURES
from lol_remoto.dominio.fase import Fase
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.plataforma.ntfy import NotificadorFalso
from lol_remoto.servicos.estado import Estado
from lol_remoto.servicos.monitor import Monitor
from lol_remoto.servicos.notificacoes import ServicoNotificacoes


def _esperar(condicao, tempo=3.0):
    fim = time.monotonic() + tempo
    while not condicao():
        assert time.monotonic() < fim, "a condição não aconteceu a tempo"
        time.sleep(0.01)


def reproduzir(nome, tmp_path):
    """Passa a gravação pelo monitor com o modo ausente ligado; devolve as notificações."""
    linhas = [
        json.loads(linha)
        for linha in (PASTA_FIXTURES / "gravacoes" / nome).read_text(encoding="utf-8").splitlines()
    ]
    iniciais = {x["uri"]: x["dados"] for x in linhas if x["tipo"] == "GET" and x["dados"]}
    (tmp_path / "lockfile").write_text("LeagueClient:1:2:senha:https", encoding="utf-8")

    estado = Estado(ausente=True)
    notificador = NotificadorFalso()
    servico = ServicoNotificacoes(estado, notificador)
    lcu = LcuFalsa(iniciais)
    monitor = Monitor(estado, tmp_path, conectar=lambda c: lcu, intervalo=0.01)
    thread = threading.Thread(target=monitor.executar, daemon=True)
    thread.start()
    _esperar(lambda: estado.atual.conectado)

    for linha in linhas:
        if linha["tipo"] != "GET":
            lcu.emitir(linha["uri"], linha["dados"], linha["tipo"])
            lcu.aguardar_consumo()  # um evento de cada vez, como no cliente real

    servico.aguardar_envios()
    fase_final = estado.atual.fase
    monitor.encerrar()
    thread.join(3)
    servico.encerrar()
    return fase_final, notificador.enviadas


def test_personalizada_escolha_alternada(tmp_path):
    fase_final, enviadas = reproduzir("personalizada_alternada.jsonl", tmp_path)
    assert fase_final is Fase.CARREGANDO
    assert [n.titulo for n in enviadas] == [
        "Seleção começou",  # planejamento: o ban "em andamento" ainda não é a vez
        "Sua vez de banir!",  # quando os bans começam de verdade
        "Sua vez de escolher!",
        "Partida carregando",
    ]
    assert enviadas[0].mensagem.startswith("Declare sua intenção de pick. 24 s")
    assert enviadas[1].mensagem.startswith("30 s restantes.")


def test_personalizada_aram(tmp_path):
    fase_final, enviadas = reproduzir("personalizada_aram.jsonl", tmp_path)
    assert fase_final is Fase.CARREGANDO
    # Sem "Partida encontrada!": a personalizada passa pelo ReadyCheck sem nada para aceitar.
    assert [n.titulo for n in enviadas] == ["ARAM", "Partida carregando"]
    assert "2 no banco" in enviadas[0].mensagem


@pytest.mark.parametrize("nome", [p.name for p in (PASTA_FIXTURES / "gravacoes").glob("*.jsonl")])
def test_gravacoes_estao_anonimizadas(nome):
    texto = (PASTA_FIXTURES / "gravacoes" / nome).read_text(encoding="utf-8")
    for linha in texto.splitlines():
        dados = json.loads(linha)["dados"]
        if isinstance(dados, dict) and "myTeam" in dados:
            for jogador in dados["myTeam"] + dados.get("theirTeam", []):
                assert jogador["gameName"] == "" or jogador["gameName"].startswith("Jogador")
                assert jogador.get("puuid", "") == "" or jogador["puuid"].startswith("puuid-")
            assert dados.get("chatDetails") == "<removido>"


def test_normal_alternada_pela_fila(tmp_path):
    fase_final, enviadas = reproduzir("normal_alternada.jsonl", tmp_path)
    assert fase_final is Fase.CARREGANDO
    assert [n.titulo for n in enviadas] == [
        "Partida encontrada!",
        "Seleção começou",
        "Sua vez de banir!",
        "Sua vez de escolher!",  # troca de ordem de pick: por 2 s foi o primeiro a escolher
        "Sua vez de escolher!",  # a vez de verdade
        "Partida carregando",
    ]
    assert enviadas[1].mensagem.startswith("Declare sua intenção de pick. 12 s")


def test_ranqueada_solo(tmp_path):
    # Mesmas notificações que chegaram no celular nessa partida (log de 11/10/2026).
    fase_final, enviadas = reproduzir("ranqueada_solo.jsonl", tmp_path)
    assert fase_final is Fase.CARREGANDO
    assert [n.titulo for n in enviadas] == [
        "Partida encontrada!",
        "Seleção começou",
        "Sua vez de banir!",
        "Sua vez de escolher!",
        "Partida carregando",
    ]


def test_dodge_na_finalizacao(tmp_path):
    # Gravação feita logo após o cliente abrir: sem eventos de ready check (ver lcu.py).
    fase_final, enviadas = reproduzir("normal_alternada_dodge.jsonl", tmp_path)
    assert fase_final is Fase.LOBBY
    assert [n.titulo for n in enviadas] == [
        "Seleção começou",
        "Sua vez de banir!",
        "Sua vez de escolher!",
        "Alguém deu dodge",
    ]
