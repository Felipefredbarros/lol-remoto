"""Configuração do usuário, guardada fora do repositório.

Local padrão: %APPDATA%\\LolRemoto\\config.json. Guarda só o hash do PIN; o tópico do ntfy
é secreto (quem o conhece lê as notificações) e por isso também nunca vai para o log.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from lol_remoto.dominio.pin import gerar_hash, gerar_pin, hash_valido, validar_pin
from lol_remoto.plataforma.lockfile import PASTA_PADRAO

PORTA_PADRAO = 8766  # a 8765 é do desligador
NTFY_PADRAO = "https://ntfy.sh"
_TOPICO_VALIDO = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


class ConfigInvalida(ValueError):
    """O arquivo de configuração tem valores que não podem ser usados."""


@dataclass(frozen=True)
class Config:
    pin_hash: str
    ntfy_topico: str
    porta: int = PORTA_PADRAO
    ntfy_servidor: str = NTFY_PADRAO
    ntfy_token: str | None = None  # token de acesso, se o tópico for protegido
    pasta_lol: str = str(PASTA_PADRAO)
    # URL que o celular usa para chegar ao PC (botões da notificação). Vazio = IP do Tailscale.
    endereco_publico: str | None = None

    def __repr__(self) -> str:  # nunca mostra o tópico nem o token
        return f"Config(porta={self.porta}, ntfy_servidor={self.ntfy_servidor!r}, ...)"


def pasta_config() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "LolRemoto"


def pasta_logs() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "LolRemoto"


def gerar_topico() -> str:
    return "lolremoto-" + secrets.token_urlsafe(18)  # 24 caracteres aleatórios


def _validar_porta(porta: object) -> int:
    if isinstance(porta, bool) or not isinstance(porta, int) or not 1024 <= porta <= 65535:
        raise ConfigInvalida("A porta deve ser um número entre 1024 e 65535.")
    return porta


def _texto_opcional(dados: dict, chave: str) -> str | None:
    valor = dados.get(chave)
    if valor is not None and not isinstance(valor, str):
        raise ConfigInvalida(f"'{chave}' deve ser um texto.")
    return valor or None


def _url(valor: str | None, chave: str) -> str | None:
    if valor is not None and not valor.startswith(("http://", "https://")):
        raise ConfigInvalida(f"'{chave}' deve começar com http:// ou https://.")
    return valor


def validar(dados: object) -> Config:
    if not isinstance(dados, dict):
        raise ConfigInvalida("O arquivo de configuração deve conter um objeto JSON.")
    if not hash_valido(dados.get("pin_hash")):
        raise ConfigInvalida("PIN ausente ou inválido. Rode `py -m lol_remoto --trocar-pin`.")
    topico = dados.get("ntfy_topico")
    if not (isinstance(topico, str) and _TOPICO_VALIDO.match(topico)):
        raise ConfigInvalida("'ntfy_topico' deve ter de 16 a 64 letras, números, '-' ou '_'.")
    return Config(
        pin_hash=dados["pin_hash"],
        ntfy_topico=topico,
        porta=_validar_porta(dados.get("porta", PORTA_PADRAO)),
        ntfy_servidor=_url(_texto_opcional(dados, "ntfy_servidor"), "ntfy_servidor") or NTFY_PADRAO,
        ntfy_token=_texto_opcional(dados, "ntfy_token"),
        pasta_lol=_texto_opcional(dados, "pasta_lol") or str(PASTA_PADRAO),
        endereco_publico=_url(_texto_opcional(dados, "endereco_publico"), "endereco_publico"),
    )


def salvar(config: Config, caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(asdict(config), indent=2) + "\n", encoding="utf-8")


def carregar(caminho: Path) -> Config:
    try:
        return validar(json.loads(caminho.read_text(encoding="utf-8")))
    except json.JSONDecodeError as erro:
        raise ConfigInvalida(f"{caminho} não é um JSON válido: {erro}") from erro


def carregar_ou_criar(caminho: Path) -> tuple[Config, str | None]:
    """Lê a configuração; se não existir, cria uma com PIN e tópico aleatórios.

    Retorna (config, pin_gerado). `pin_gerado` só vem preenchido quando o arquivo
    acabou de ser criado, para ser mostrado uma única vez.
    """
    if caminho.exists():
        return carregar(caminho), None
    pin = gerar_pin()
    config = Config(pin_hash=gerar_hash(pin), ntfy_topico=gerar_topico())
    salvar(config, caminho)
    return config, pin


def para_simulacao(config: Config) -> Config:
    """O `--simular` usa a porta seguinte, para rodar junto com o app instalado (ADR 0011)."""
    return replace(config, porta=_validar_porta(config.porta + 1))


def trocar_pin(caminho: Path, novo_pin: str) -> Config:
    """Grava o hash de `novo_pin`, mantendo o resto. Cria o arquivo se não existir."""
    novo_hash = gerar_hash(validar_pin(novo_pin))
    if caminho.exists():
        config = replace(carregar(caminho), pin_hash=novo_hash)
    else:
        config = Config(pin_hash=novo_hash, ntfy_topico=gerar_topico())
    salvar(config, caminho)
    return config
