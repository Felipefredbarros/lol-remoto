"""Texto, prioridade e emoji de cada aviso, como notificação do ntfy."""

from __future__ import annotations

from lol_remoto.dominio.avisos import Aviso, TipoAviso
from lol_remoto.dominio.campeoes import Catalogo
from lol_remoto.dominio.selecao import Selecao
from lol_remoto.plataforma.ntfy import PRIORIDADE_MAXIMA, Notificacao

_TEXTOS: dict[TipoAviso, tuple[str, str, int, str]] = {
    # tipo: (título, mensagem, prioridade, tag/emoji do ntfy)
    TipoAviso.PARTIDA_ENCONTRADA: (
        "Partida encontrada!",
        "Você tem uns 10 segundos para aceitar.",
        PRIORIDADE_MAXIMA,
        "rotating_light",
    ),
    TipoAviso.PARTIDA_RECUSADA: (
        "Partida recusada",
        "Alguém recusou. Você voltou para a fila.",
        4,
        "hourglass_flowing_sand",
    ),
    TipoAviso.NAO_ACEITOU: (
        "Você saiu da fila",
        "A partida não foi aceita a tempo. Entre na fila de novo quando voltar.",
        4,
        "x",
    ),
    TipoAviso.SAIU_DA_FILA: ("Você saiu da fila", "A partida foi recusada.", 4, "x"),
    TipoAviso.PLANEJAMENTO: ("Seleção começou", "", PRIORIDADE_MAXIMA, "crystal_ball"),
    TipoAviso.SUA_VEZ_BANIR: ("Sua vez de banir!", "", PRIORIDADE_MAXIMA, "no_entry"),
    TipoAviso.SUA_VEZ_ESCOLHER: ("Sua vez de escolher!", "", PRIORIDADE_MAXIMA, "crossed_swords"),
    TipoAviso.ARAM: ("ARAM", "", 4, "game_die"),
    TipoAviso.DODGE: ("Alguém deu dodge", "Você voltou para a fila.", 4, "warning"),
    TipoAviso.SELECAO_CANCELADA: (
        "Seleção cancelada",
        "A seleção de campeões acabou sem partida.",
        4,
        "x",
    ),
    TipoAviso.CARREGANDO: (
        "Partida carregando",
        "Volta pro PC! O modo ausente foi desligado.",
        PRIORIDADE_MAXIMA,
        "video_game",
    ),
}


def _tempo(aviso: Aviso) -> str | None:
    return f"{aviso.segundos} s restantes." if aviso.segundos is not None else None


def _mensagem(aviso: Aviso, selecao: Selecao | None, catalogo: Catalogo) -> str | None:
    """Mensagem montada na hora (com tempo e campeões), ou None para usar a fixa."""
    eu = selecao.eu if selecao else None
    if aviso.tipo is TipoAviso.PLANEJAMENTO:
        partes = ["Declare sua intenção de pick.", _tempo(aviso)]
    elif aviso.tipo in (TipoAviso.SUA_VEZ_BANIR, TipoAviso.SUA_VEZ_ESCOLHER):
        intencao = catalogo.nome(eu.intencao) if eu and eu.intencao else None
        partes = [_tempo(aviso)]
        if aviso.tipo is TipoAviso.SUA_VEZ_ESCOLHER and intencao:
            partes.append(f"Sua intenção: {intencao}.")
    elif aviso.tipo is TipoAviso.ARAM:
        nome = catalogo.nome(aviso.campeao or 0) or "um campeão"
        banco = len(selecao.banco) if selecao else 0
        partes = [f"Você está de {nome}.", f"{banco} no banco." if banco else None]
    else:
        return None
    return " ".join(p for p in [*partes, "Toque para abrir."] if p)


def montar(
    aviso: Aviso, selecao: Selecao | None, catalogo: Catalogo, link: str | None
) -> Notificacao:
    titulo, mensagem, prioridade, tag = _TEXTOS[aviso.tipo]
    return Notificacao(
        titulo,
        _mensagem(aviso, selecao, catalogo) or mensagem,
        prioridade=prioridade,
        tags=(tag,),
        link=link,
    )
