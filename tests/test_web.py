"""Checagens estáticas da página (sem navegador): IDs, importações, CSP e segurança."""

import re

import pytest

from api_falsa import ApiFalsa
from lol_remoto.api.servidor import PASTA_WEB
from lol_remoto.api.visao import visao
from lol_remoto.dominio.campeoes import Catalogo
from lol_remoto.dominio.fase import Fase
from lol_remoto.dominio.ready_check import ReadyCheck, Resposta
from lol_remoto.dominio.selecao import selecao_de
from lol_remoto.servicos.estado import Estado

HTML = (PASTA_WEB / "index.html").read_text(encoding="utf-8")
SCRIPTS = {p.name: p.read_text(encoding="utf-8") for p in PASTA_WEB.glob("*.js")}


def test_todo_id_usado_no_js_existe_no_html():
    ids_html = set(re.findall(r'id="([^"]+)"', HTML))
    for nome, codigo in SCRIPTS.items():
        for usado in re.findall(r'el\("([^"]+)"\)', codigo):
            assert usado in ids_html, f"{nome} usa #{usado}, que não existe no HTML"


def test_importacoes_apontam_para_arquivos_e_nomes_que_existem():
    for nome, codigo in SCRIPTS.items():
        for nomes, arquivo in re.findall(r'import \{([^}]+)\} from "\./([^"]+)"', codigo):
            assert arquivo in SCRIPTS, f"{nome} importa {arquivo}, que não existe"
            for importado in (n.strip() for n in nomes.split(",")):
                exportado = rf"export (async )?(function|const|class|let) {importado}\b"
                assert re.search(exportado, SCRIPTS[arquivo]), f"{arquivo} não exporta {importado}"
        for apelido, arquivo in re.findall(r'import \* as (\w+) from "\./([^"]+)"', codigo):
            assert arquivo in SCRIPTS
            for funcao in set(re.findall(rf"\b{apelido}\.(\w+)\(", codigo)):
                exportado = rf"export (async )?function {funcao}\b"
                assert re.search(exportado, SCRIPTS[arquivo]), f"{arquivo} não exporta {funcao}"


@pytest.mark.parametrize(
    "perigoso", ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("]
)
def test_js_nao_monta_html_a_partir_de_texto(perigoso):
    # Nomes de jogadores vêm do cliente do LoL: só textContent.
    for nome, codigo in SCRIPTS.items():
        assert perigoso not in codigo, f"{nome} usa {perigoso}"


def test_html_respeita_a_csp():
    # default-src 'self': nada de script/estilo inline nem recursos de fora.
    assert "<style" not in HTML
    assert ' style="' not in HTML
    assert re.findall(r"<script[^>]*>", HTML) == ['<script type="module" src="app.js">']
    assert "http://" not in HTML and "https://" not in HTML


def test_visao_tem_os_campos_que_a_pagina_usa(sessao_draft):
    estado = Estado()
    estado.catalogo = Catalogo.de_json([{"id": 103, "name": "Ahri"}])
    estado.atualizar(
        conectado=True,
        fase=Fase.SELECAO,
        selecao=selecao_de(sessao_draft),
        ready_check=ReadyCheck(True, Resposta.NENHUMA, 1.0),
    )
    dados = visao(estado.atual, estado.catalogo, estado.agora())
    topo = {"versao", "fase", "fase_descricao", "ausente", "ready_check", "selecao", "passos"}
    assert topo <= set(dados)
    assert {"id", "nome", "estado", "resumo"} <= set(dados["passos"][0])  # etapas.js
    assert {"resposta", "segundos_restantes"} <= set(dados["ready_check"])
    selecao = dados["selecao"]
    esperados = {"aram", "etapa", "planejamento", "segundos_restantes", "minha_vez", "bans"}
    assert esperados | {"aliados", "inimigos", "ordem_picks"} <= set(selecao)
    pick = selecao["ordem_picks"][0]  # ordem.js
    assert {"ordem", "aliado", "eu", "nome", "posicao", "campeao", "intencao", "estado"} <= set(
        pick
    )
    assert {"aliados", "inimigos"} == set(selecao["bans"])
    campos = {"eu", "nome", "posicao", "campeao", "intencao", "confirmado", "agindo", "feiticos"}
    assert campos <= set(selecao["aliados"][0])
    eu = next(j for j in selecao["aliados"] if j["eu"])
    assert set(eu["feiticos"]) == {"d", "f"}  # feiticos.js lê feiticos.d e feiticos.f


@pytest.fixture
def api():
    a = ApiFalsa()
    yield a
    a.encerrar()


def test_pagina_e_arquivos_sao_servidos_sem_login(api):
    status, cabecalhos, corpo = api.requisitar("GET", "/")
    assert status == 200 and cabecalhos["Content-Type"].startswith("text/html")
    assert b"LoL Remoto" in corpo
    for nome in [*SCRIPTS, "estilo.css", "manifest.json", "icone.svg"]:
        status, cabecalhos, _ = api.requisitar("GET", "/" + nome)
        assert status == 200, nome
    status, cabecalhos, _ = api.requisitar("GET", "/app.js")
    assert cabecalhos["Content-Type"].startswith("text/javascript")
    assert "default-src 'self'" in cabecalhos["Content-Security-Policy"]
