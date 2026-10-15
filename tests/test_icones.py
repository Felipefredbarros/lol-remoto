"""Ícones de campeões e feitiços: cache em disco e as fotos reais no `--simular`."""

import pytest

from lol_remoto.plataforma.ativos_reais import AtivosDoClienteReal
from lol_remoto.plataforma.lcu import ErroLcu
from lol_remoto.plataforma.lcu_falsa import LcuFalsa
from lol_remoto.plataforma.lcu_simulada import LcuSimulada
from lol_remoto.servicos.acoes import ClienteDesconectado
from lol_remoto.servicos.icones import ServicoIcones

AHRI = "/lol-game-data/assets/v1/champion-icons/103.png"
FLASH = "/lol-game-data/assets/DATA/Spells/Icons2D/Summoner_flash.png"


@pytest.fixture
def lcu():
    falsa = LcuFalsa()
    falsa.arquivos.update({AHRI: b"png-ahri", FLASH: b"png-flash"})
    return falsa


def test_cache_em_disco_serve_com_o_cliente_fechado(lcu, tmp_path):
    ServicoIcones(lambda: lcu, {4: FLASH}.get, pasta=tmp_path).icone(103)
    ServicoIcones(lambda: lcu, {4: FLASH}.get, pasta=tmp_path).icone_feitico(4)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["campeao-103.png", "feitico-4.png"]

    fechado = ServicoIcones(lambda: None, lambda _id: None, pasta=tmp_path)  # depois de reiniciar
    assert fechado.icone(103) == b"png-ahri"
    assert fechado.icone_feitico(4) == b"png-flash"
    with pytest.raises(ClienteDesconectado):
        fechado.icone(1)


def test_sem_pasta_so_memoria(lcu):
    servico = ServicoIcones(lambda: lcu)
    assert servico.icone(103) == b"png-ahri"
    lcu.arquivos.clear()
    assert servico.icone(103) == b"png-ahri"


def test_pasta_invalida_nao_atrapalha(lcu, tmp_path):
    arquivo = tmp_path / "nao-e-pasta"
    arquivo.write_text("x")
    assert ServicoIcones(lambda: lcu, pasta=arquivo).icone(103) == b"png-ahri"


@pytest.mark.parametrize("caminho", [None, "/lol-summoner/v1/current-summoner", "../x.png"])
def test_feitico_sem_caminho_valido(caminho, lcu):
    with pytest.raises(ValueError):
        ServicoIcones(lambda: lcu, lambda _id: caminho).icone_feitico(4)


# ---------- fotos reais no --simular ----------


def _lockfile(pasta):
    (pasta / "lockfile").write_text("LeagueClient:1:2:senha:https", encoding="utf-8")


def test_ativos_do_cliente_real_so_leem_arquivos_do_jogo(lcu, tmp_path):
    _lockfile(tmp_path)
    ativos = AtivosDoClienteReal(tmp_path, conectar=lambda credenciais: lcu)
    assert ativos(AHRI) == b"png-ahri"
    for caminho in ("/lol-summoner/v1/current-summoner", "/lol-game-data/assets/../../x"):
        with pytest.raises(ErroLcu):
            ativos(caminho)
    assert lcu.chamadas == []  # nada além de GET


def test_ativos_com_o_cliente_fechado(lcu, tmp_path):
    with pytest.raises(ErroLcu, match="fechado"):
        AtivosDoClienteReal(tmp_path, conectar=lambda credenciais: lcu)(AHRI)


def test_simulacao_pega_as_fotos_do_cliente_real(lcu):
    pedidos = []

    def ativos(caminho):
        pedidos.append(caminho)
        return lcu.get_bytes(caminho)

    assert LcuSimulada(ativos=ativos).get_bytes(FLASH) == b"png-flash"
    assert pedidos == [FLASH]
    with pytest.raises(ErroLcu):
        LcuSimulada().get_bytes(FLASH)  # sem fonte de imagens: a página mostra as iniciais


def test_feiticos_da_simulacao_tem_icone():
    feiticos = LcuSimulada().get("/lol-game-data/assets/v1/summoner-spells.json")
    assert all(f["iconPath"].startswith("/lol-game-data/assets/") for f in feiticos)
