"""Anonimiza gravações da LCU antes de virarem fixtures num repositório público.

Troca nomes, tags e identificadores por valores falsos consistentes (o mesmo jogador vira
sempre o mesmo "JogadorN") e remove por completo senhas, tokens e dados do chat.
Comando: `python -m lol_remoto --anonimizar ENTRADA.jsonl SAIDA.jsonl`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Chaves removidas inteiras (o valor vira "<removido>"), comparadas em minúsculas por trecho.
_TRECHOS_SECRETOS = ("password", "jwt", "token", "chat", "secret")

# Chaves trocadas por pseudônimos.
_TEXTOS = {
    "gamename": "Jogador",
    "summonername": "Jogador",
    "displayname": "Jogador",
    "internalname": "jogador",
    "playeralias": "Jogador",
    "tagline": "TESTE",
    "puuid": "puuid-",
    "obfuscatedpuuid": "opuuid-",
    "sessao": "sessao-",
}
_NUMEROS = ("summonerid", "accountid", "obfuscatedsummonerid", "playerid", "gameid")


class Anonimizador:
    def __init__(self) -> None:
        self._pseudonimos: dict[tuple[str, Any], Any] = {}
        self.originais: set[str] = set()  # valores sensíveis vistos, para a conferência final

    def _pseudonimo(self, chave: str, valor: Any) -> Any:
        if not isinstance(valor, str | int) or isinstance(valor, bool):
            return "<removido>"  # formato inesperado: não arrisca
        if valor in ("", 0):
            return valor  # vazio continua vazio (ex.: nome escondido pelo cliente)
        if isinstance(valor, str) and len(valor) >= 4:
            self.originais.add(valor)
        if (chave, valor) not in self._pseudonimos:
            numero = sum(1 for c, _ in self._pseudonimos if c == chave) + 1
            if chave in _NUMEROS:
                novo: Any = numero
            elif chave == "tagline":
                novo = _TEXTOS[chave]
            else:
                novo = f"{_TEXTOS[chave]}{numero}"
            self._pseudonimos[chave, valor] = novo
        return self._pseudonimos[chave, valor]

    def __call__(self, dados: Any) -> Any:
        if isinstance(dados, list):
            return [self(item) for item in dados]
        if not isinstance(dados, dict):
            return dados
        resultado = {}
        for chave, valor in dados.items():
            minuscula = chave.lower()
            if any(trecho in minuscula for trecho in _TRECHOS_SECRETOS):
                resultado[chave] = "<removido>"
            elif minuscula in _TEXTOS or minuscula in _NUMEROS:
                resultado[chave] = self._pseudonimo(minuscula, valor)
            elif minuscula == "id" and isinstance(valor, str):
                resultado[chave] = self._pseudonimo("sessao", valor)  # UUID da seleção
            else:
                resultado[chave] = self(valor)
        return resultado


class AnonimizacaoIncompleta(RuntimeError):
    """Algum valor sensível original ainda aparece na saída."""


def anonimizar_arquivo(entrada: Path, saida: Path) -> int:
    """Anonimiza uma gravação JSONL. Retorna quantas linhas foram gravadas.

    Confere no final que nenhum nome/identificador original sobrou no texto (por exemplo,
    dentro de um campo que não conhecíamos) e, se sobrou, não grava nada.
    """
    anonimizar = Anonimizador()
    linhas = [
        json.dumps(anonimizar(json.loads(linha)), ensure_ascii=False)
        for linha in entrada.read_text(encoding="utf-8").splitlines()
        if linha.strip()
    ]
    texto = "\n".join(linhas) + "\n"
    vazados = sorted(v for v in anonimizar.originais if v in texto)
    if vazados:
        raise AnonimizacaoIncompleta(
            f"{len(vazados)} valor(es) sensível(is) continuam na saída; revise o anonimizador."
        )
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(texto, encoding="utf-8")
    return len(linhas)
