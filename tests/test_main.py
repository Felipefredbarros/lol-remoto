import json

from lol_remoto import __main__ as principal
from lol_remoto.plataforma.ntfy import ErroNotificacao


class _NotificadorCapturado:
    enviadas = []
    falhar = False

    def __init__(self, servidor, topico, token=None):
        self.topico = topico

    def enviar(self, notificacao):
        if self.falhar:
            raise ErroNotificacao("falhou")
        self.enviadas.append((self.topico, notificacao))


def test_testar_notificacao_cria_config_e_envia(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(principal, "NotificadorNtfy", _NotificadorCapturado)
    _NotificadorCapturado.enviadas = []
    caminho = tmp_path / "config.json"

    assert principal.main(["--config", str(caminho), "--testar-notificacao"]) == 0

    topico = json.loads(caminho.read_text(encoding="utf-8"))["ntfy_topico"]
    saida = capsys.readouterr().out
    assert "Seu PIN:" in saida and topico in saida
    assert _NotificadorCapturado.enviadas[0][0] == topico


def test_testar_notificacao_com_falha(tmp_path, monkeypatch):
    monkeypatch.setattr(principal, "NotificadorNtfy", _NotificadorCapturado)
    monkeypatch.setattr(_NotificadorCapturado, "falhar", True)
    assert principal.main(["--config", str(tmp_path / "c.json"), "--testar-notificacao"]) == 1


def test_config_invalida(tmp_path, capsys):
    caminho = tmp_path / "config.json"
    caminho.write_text("[]", encoding="utf-8")
    assert principal.main(["--config", str(caminho), "--testar-notificacao"]) == 1
    assert "inválida" in capsys.readouterr().err


def test_anonimizar(tmp_path):
    entrada, saida = tmp_path / "e.jsonl", tmp_path / "s.jsonl"
    entrada.write_text(json.dumps({"dados": {"gameName": "Fulano"}}) + "\n", encoding="utf-8")
    assert principal.main(["--anonimizar", str(entrada), str(saida)]) == 0
    assert "Fulano" not in saida.read_text(encoding="utf-8")
