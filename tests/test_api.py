"""Testes de ponta a ponta: servidor de verdade em 127.0.0.1 com LCU e ntfy falsos."""

import http.client
import socket

import pytest

from api_falsa import PIN, TEMPO_LIMITE_TESTE, ApiFalsa
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.ready_check import ReadyCheck, Resposta
from lol_remoto.dominio.selecao import selecao_de

READY = ReadyCheck(em_andamento=True, resposta=Resposta.NENHUMA, segundos_decorridos=2.0)


@pytest.fixture
def api():
    a = ApiFalsa()
    yield a
    a.encerrar()


# ---------- login e sessão ----------


def test_sem_login_tudo_e_401(api):
    for metodo, caminho in [
        ("GET", "/api/estado"),
        ("GET", "/api/campeoes"),
        ("GET", "/api/eventos"),
        ("GET", "/api/campeoes/103.png"),
        ("POST", "/api/ausente"),
        ("POST", "/api/selecao/marcar"),
        ("POST", "/api/ready-check/aceitar"),
    ]:
        status, _, _ = api.requisitar(metodo, caminho)
        assert status == 401, caminho


def test_login_cria_cookie_seguro(api):
    status, cabecalhos, _ = api.requisitar("POST", "/api/entrar", {"pin": PIN})
    assert status == 200
    cookie = cabecalhos["Set-Cookie"]
    assert cookie.startswith("lolremoto_sessao=")
    for atributo in ("HttpOnly", "SameSite=Strict", "Path=/", "Max-Age=2592000"):
        assert atributo in cookie


def test_cookie_libera_o_estado(api):
    token = api.entrar()
    status, dados = api.json("GET", "/api/estado", cookie=token)
    assert status == 200
    assert dados["fase"] == "None"
    assert dados["conectado"] is False
    assert api.json("GET", "/api/estado", cookie="inventado")[0] == 401


def test_pin_errado_401_e_depois_429(api):
    assert api.json("POST", "/api/entrar", {"pin": "000000"})[0] == 401
    assert api.json("POST", "/api/entrar", {"pin": "000000"})[0] == 429
    assert api.json("POST", "/api/entrar", {"pin": PIN})[0] == 429  # bloqueado mesmo certo


def test_sair_encerra_a_sessao(api):
    token = api.entrar()
    status, cabecalhos, _ = api.requisitar("POST", "/api/sair", cookie=token)
    assert status == 200
    assert "Max-Age=0" in cabecalhos["Set-Cookie"]
    assert api.json("GET", "/api/estado", cookie=token)[0] == 401


# ---------- proteções (iguais ao desligador) ----------


@pytest.mark.parametrize("caminho", ["/", "/api/estado", "/api/eventos"])
def test_host_estranho_e_recusado(api, caminho):
    status, _, _ = api.requisitar("GET", caminho, cabecalhos={"Host": "evil.com"})
    assert status == 403


def test_origin_estranho_e_recusado(api):
    status, _, _ = api.requisitar(
        "POST", "/api/entrar", {"pin": PIN}, cabecalhos={"Origin": "http://evil.com"}
    )
    assert status == 403


def test_post_sem_json_e_recusado(api):
    status, _, _ = api.requisitar(
        "POST", "/api/entrar", {"pin": PIN}, cabecalhos={"Content-Type": "text/plain"}
    )
    assert status == 415


def test_json_invalido(api):
    status, _, _ = api.requisitar("POST", "/api/entrar", bruto="{nao e json")
    assert status == 400


@pytest.mark.parametrize("tamanho", ["abc", "-5"])
def test_content_length_invalido(api, tamanho):
    conexao = http.client.HTTPConnection("127.0.0.1", api.porta, timeout=5)
    conexao.putrequest("POST", "/api/entrar")
    conexao.putheader("Content-Type", "application/json")
    conexao.putheader("Content-Length", tamanho)
    conexao.endheaders()
    assert conexao.getresponse().status == 400
    conexao.close()


def test_conexao_parada_e_encerrada(api):
    with socket.create_connection(("127.0.0.1", api.porta), timeout=TEMPO_LIMITE_TESTE + 3) as s:
        assert s.recv(1) == b""


@pytest.mark.parametrize("caminho", ["/../config.py", "/..%2f__main__.py", "/nada.html"])
def test_nao_serve_arquivos_fora_da_pasta_web(api, caminho):
    assert api.requisitar("GET", caminho)[0] == 404


def test_rota_desconhecida(api):
    assert api.json("GET", "/api/nada", cookie=api.entrar())[0] == 404


# ---------- modo ausente e notificação de teste ----------


def test_modo_ausente(api):
    token = api.entrar()
    status, dados = api.json("POST", "/api/ausente", {"ativo": True}, cookie=token)
    assert status == 200 and dados["ausente"] is True
    assert api.json("POST", "/api/ausente", {"ativo": "sim"}, cookie=token)[0] == 400


def test_testar_notificacao(api):
    token = api.entrar()
    assert api.json("POST", "/api/testar-notificacao", cookie=token)[0] == 200
    assert api.notificador.enviadas[-1].titulo == "LoL Remoto"
    api.notificador.falhar = True
    assert api.json("POST", "/api/testar-notificacao", cookie=token)[0] == 502


# ---------- partida encontrada ----------


def test_aceitar_com_sessao(api):
    token = api.entrar()
    api.estado.atualizar(conectado=True, fase=Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    status, dados = api.json("POST", "/api/ready-check/aceitar", cookie=token)
    assert status == 200
    assert dados["ready_check"]["segundos_restantes"] in (7, 8)
    assert api.lcu.chamadas == [("POST", "/lol-matchmaking/v1/ready-check/accept", None)]


def test_botao_da_notificacao_aceita_com_token_uma_vez(api):
    api.estado.atualizar(conectado=True, fase=Fase.PARTIDA_ENCONTRADA, ready_check=READY)
    token = api.tokens.gerar()
    assert api.json("POST", "/api/ready-check/recusar", {"token": token})[0] == 200
    assert api.json("POST", "/api/ready-check/recusar", {"token": token})[0] == 401
    assert api.lcu.chamadas == [("POST", "/lol-matchmaking/v1/ready-check/decline", None)]


def test_token_nao_serve_para_outras_rotas(api, sessao_draft):
    api.estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    token = api.tokens.gerar()
    assert api.json("POST", "/api/selecao/marcar", {"token": token, "campeao": 103})[0] == 401
    assert api.json("GET", "/api/estado", cookie=token)[0] == 401
    assert api.lcu.chamadas == []


def test_nada_dentro_da_partida(api):
    token = api.entrar()
    api.estado.atualizar(conectado=True, fase=Fase.EM_PARTIDA)
    for caminho in (
        "/api/ready-check/aceitar",
        "/api/selecao/confirmar",
        "/api/selecao/aram/reroll",
    ):
        assert api.json("POST", caminho, {"campeao": 103}, cookie=token)[0] == 409
    assert api.lcu.chamadas == []


def test_cliente_fechado_503(api):
    token = api.entrar()
    api.estado.atualizar(fase=Fase.PARTIDA_ENCONTRADA)
    api.lcu = None
    assert api.json("POST", "/api/ready-check/aceitar", cookie=token)[0] == 503


# ---------- seleção ----------


def test_estado_da_selecao(api, sessao_draft):
    token = api.entrar()
    api.estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    _, dados = api.json("GET", "/api/estado", cookie=token)
    selecao = dados["selecao"]
    assert dados["pode_agir"] is True
    assert selecao["minha_vez"] == {"id": 15, "tipo": "pick", "campeao": 0}
    assert selecao["bans"]["aliados"][0] == {"id": 157, "nome": "Yasuo"}
    eu = next(j for j in selecao["aliados"] if j["eu"])
    assert eu["posicao"] == "Meio" and eu["intencao"] == {"id": 103, "nome": "Ahri"}


def test_lista_de_campeoes_para_pick_e_ban(api, sessao_draft):
    token = api.entrar()
    api.estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    _, dados = api.json("GET", "/api/campeoes?tipo=ban", cookie=token)
    assert [c["nome"] for c in dados["campeoes"]] == ["Ahri", "Kha'Zix", "Yasuo"]
    _, dados = api.json("GET", "/api/campeoes", cookie=token)
    assert dados["tipo"] == "pick"
    assert [c["nome"] for c in dados["campeoes"]] == ["Ahri", "Kha'Zix", "Thresh"]


def test_marcar_e_confirmar(api, sessao_draft):
    token = api.entrar()
    api.estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_draft))
    assert api.json("POST", "/api/selecao/marcar", {"campeao": 412}, cookie=token)[0] == 200
    assert api.json("POST", "/api/selecao/confirmar", {"campeao": 412}, cookie=token)[0] == 200
    assert api.json("POST", "/api/selecao/marcar", {"campeao": 157}, cookie=token)[0] == 400
    assert [c[2] for c in api.lcu.chamadas] == [
        {"championId": 412},
        {"championId": 412, "completed": True},
    ]


def test_aram(api, sessao_aram):
    token = api.entrar()
    api.estado.atualizar(conectado=True, fase=Fase.SELECAO, selecao=selecao_de(sessao_aram))
    assert api.json("POST", "/api/selecao/aram/reroll", cookie=token)[0] == 200
    assert api.json("POST", "/api/selecao/aram/trocar", {"campeao": 22}, cookie=token)[0] == 200
    assert api.json("POST", "/api/selecao/aram/trocar", {"campeao": 1}, cookie=token)[0] == 400


# ---------- ícones ----------


def test_icone(api):
    token = api.entrar()
    status, cabecalhos, conteudo = api.requisitar("GET", "/api/campeoes/103.png", cookie=token)
    assert status == 200
    assert cabecalhos["Content-Type"] == "image/png"
    assert conteudo == b"\x89PNG-ahri"
    assert api.requisitar("GET", "/api/campeoes/999.png", cookie=token)[0] == 404
    api.lcu = None  # cliente fechou: o ícone já está em cache
    assert api.requisitar("GET", "/api/campeoes/103.png", cookie=token)[0] == 200
