"""Fases do cliente (`/lol-gameflow/v1/gameflow-phase`) e a trava "nada dentro da partida"."""

from __future__ import annotations

from enum import StrEnum


class Fase(StrEnum):
    """Valores exatamente como a LCU envia."""

    NENHUMA = "None"
    LOBBY = "Lobby"
    FILA = "Matchmaking"
    TORNEIO = "CheckedIntoTournament"
    PARTIDA_ENCONTRADA = "ReadyCheck"
    SELECAO = "ChampSelect"
    CARREGANDO = "GameStart"
    FALHA_AO_INICIAR = "FailedToLaunch"
    EM_PARTIDA = "InProgress"
    RECONECTAR = "Reconnect"
    AGUARDANDO_ESTATISTICAS = "WaitingForStats"
    PRE_FIM_DE_JOGO = "PreEndOfGame"
    FIM_DE_JOGO = "EndOfGame"
    ERRO = "TerminatedInError"
    DESCONHECIDA = "?"


# As únicas fases em que o app pode agir no cliente (ver docs/decisoes/0002).
FASES_COM_ACAO = frozenset({Fase.PARTIDA_ENCONTRADA, Fase.SELECAO})

DESCRICOES = {
    Fase.NENHUMA: "Cliente aberto",
    Fase.LOBBY: "No lobby",
    Fase.FILA: "Na fila",
    Fase.TORNEIO: "Inscrito no torneio",
    Fase.PARTIDA_ENCONTRADA: "Partida encontrada!",
    Fase.SELECAO: "Seleção de campeões",
    Fase.CARREGANDO: "Partida carregando",
    Fase.FALHA_AO_INICIAR: "Falha ao iniciar a partida",
    Fase.EM_PARTIDA: "Em partida",
    Fase.RECONECTAR: "Reconectar à partida",
    Fase.AGUARDANDO_ESTATISTICAS: "Aguardando estatísticas",
    Fase.PRE_FIM_DE_JOGO: "Fim de jogo",
    Fase.FIM_DE_JOGO: "Fim de jogo",
    Fase.ERRO: "Erro no cliente",
    Fase.DESCONHECIDA: "Fase desconhecida",
}


class ForaDeFase(RuntimeError):
    """Pediram uma ação numa fase em que o app não pode agir."""


def fase_de(valor: object) -> Fase:
    """Converte o texto da LCU; valores novos (de patches futuros) viram `DESCONHECIDA`."""
    try:
        return Fase(valor)
    except ValueError:
        return Fase.DESCONHECIDA


def pode_agir(fase: Fase) -> bool:
    return fase in FASES_COM_ACAO


def exigir_fase(atual: Fase, *permitidas: Fase) -> None:
    """Levanta `ForaDeFase` se `atual` não estiver em `permitidas` ou não permitir ações.

    A segunda condição garante a regra mesmo que alguém passe uma fase de partida aqui.
    """
    if atual not in permitidas or not pode_agir(atual):
        raise ForaDeFase(f"Ação indisponível agora ({DESCRICOES[atual]}).")
