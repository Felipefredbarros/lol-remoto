import json

import pytest

from lol_remoto import config
from lol_remoto.config import Config, ConfigInvalida, carregar_ou_criar, trocar_pin, validar
from lol_remoto.dominio.pin import conferir, gerar_hash

HASH = gerar_hash("12345678", iteracoes=1_000)
TOPICO = "lolremoto-abcdefghijklmnopqrstuvwx"


def _valido(**extra):
    return {"pin_hash": HASH, "ntfy_topico": TOPICO, **extra}


def test_cria_com_pin_e_topico_aleatorios(tmp_path):
    caminho = tmp_path / "LolRemoto" / "config.json"
    cfg, pin = carregar_ou_criar(caminho)
    assert pin is not None and conferir(pin, cfg.pin_hash)
    assert cfg.ntfy_topico.startswith("lolremoto-") and len(cfg.ntfy_topico) == 34
    assert cfg.porta == 8766
    assert cfg.ntfy_servidor == "https://ntfy.sh"
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    assert pin not in json.dumps(dados)  # só o hash é salvo


def test_segunda_carga_nao_gera_pin(tmp_path):
    caminho = tmp_path / "config.json"
    primeira, _ = carregar_ou_criar(caminho)
    segunda, pin = carregar_ou_criar(caminho)
    assert pin is None
    assert segunda == primeira


def test_topicos_gerados_sao_diferentes():
    assert config.gerar_topico() != config.gerar_topico()


def test_valores_opcionais():
    cfg = validar(
        _valido(
            porta=9000,
            ntfy_servidor="https://ntfy.exemplo.com",
            ntfy_token="tk_1",
            pasta_lol=r"D:\Jogos\LoL",
            endereco_publico="http://meu-pc:8766",
        )
    )
    assert cfg == Config(
        pin_hash=HASH,
        ntfy_topico=TOPICO,
        porta=9000,
        ntfy_servidor="https://ntfy.exemplo.com",
        ntfy_token="tk_1",
        pasta_lol=r"D:\Jogos\LoL",
        endereco_publico="http://meu-pc:8766",
    )


def test_repr_nao_mostra_topico_nem_token():
    texto = repr(validar(_valido(ntfy_token="tk_segredo")))
    assert TOPICO not in texto and "tk_segredo" not in texto


@pytest.mark.parametrize(
    "dados",
    [
        [],
        {"ntfy_topico": TOPICO},
        {"pin_hash": HASH},
        _valido(ntfy_topico="curto"),
        _valido(ntfy_topico="tem espaço no meio do tópico"),
        _valido(porta=80),
        _valido(porta=True),
        _valido(ntfy_servidor="ftp://x"),
        _valido(endereco_publico="meu-pc:8766"),
        _valido(pasta_lol=123),
    ],
)
def test_invalidos(dados):
    with pytest.raises(ConfigInvalida):
        validar(dados)


def test_json_quebrado(tmp_path):
    caminho = tmp_path / "config.json"
    caminho.write_text("{nao é json", encoding="utf-8")
    with pytest.raises(ConfigInvalida):
        carregar_ou_criar(caminho)


def test_trocar_pin_mantem_o_resto(tmp_path):
    caminho = tmp_path / "config.json"
    config.salvar(validar(_valido(porta=9000)), caminho)
    cfg = trocar_pin(caminho, "87654321")
    assert conferir("87654321", cfg.pin_hash)
    assert cfg.porta == 9000 and cfg.ntfy_topico == TOPICO


def test_trocar_pin_sem_config_cria_um(tmp_path):
    cfg = trocar_pin(tmp_path / "config.json", "87654321")
    assert conferir("87654321", cfg.pin_hash)
    assert cfg.ntfy_topico.startswith("lolremoto-")


def test_simulacao_usa_a_porta_seguinte():
    """O --simular convive com o app instalado (ADR 0011): 8766 → 8767."""
    cfg = Config(pin_hash="x", ntfy_topico="t" * 16)
    assert config.para_simulacao(cfg).porta == cfg.porta + 1
    assert config.para_simulacao(cfg).ntfy_topico == cfg.ntfy_topico
    with pytest.raises(ConfigInvalida):
        config.para_simulacao(Config(pin_hash="x", ntfy_topico="t" * 16, porta=65535))
