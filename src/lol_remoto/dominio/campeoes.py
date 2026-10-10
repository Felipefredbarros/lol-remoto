"""Catálogo de campeões (`/lol-game-data/assets/v1/champion-summary.json`) e busca por nome."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

SEM_CAMPEAO = 0


@dataclass(frozen=True)
class Campeao:
    id: int
    nome: str


def normalizar(texto: str) -> str:
    """Minúsculas, sem acento e só letras/números: "Kai'Sa" e "kaisa" ficam iguais."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sem_acento.lower() if c.isalnum())


class Catalogo:
    def __init__(self, campeoes: Iterable[Campeao]) -> None:
        self._por_id = {c.id: c for c in campeoes}

    @classmethod
    def de_json(cls, dados: object) -> Catalogo:
        """Lê a lista da LCU; ignora o item "Nenhum" (id -1) e entradas malformadas."""
        if not isinstance(dados, list):
            return cls([])
        campeoes = []
        for item in dados:
            if not isinstance(item, dict):
                continue
            id_, nome = item.get("id"), item.get("name")
            if isinstance(id_, int) and not isinstance(id_, bool) and id_ > 0 and nome:
                campeoes.append(Campeao(id_, str(nome)))
        return cls(campeoes)

    def __len__(self) -> int:
        return len(self._por_id)

    def __contains__(self, id_: object) -> bool:
        return id_ in self._por_id

    def nome(self, id_: int) -> str | None:
        """Nome do campeão, ou None para "nenhum" (0) e ids desconhecidos."""
        campeao = self._por_id.get(id_)
        return campeao.nome if campeao else None

    def buscar(self, texto: str = "", permitidos: Iterable[int] | None = None) -> list[Campeao]:
        """Campeões cujo nome contém `texto`; os que começam com ele vêm primeiro.

        Ex.: "an" → Anivia, Annie, ... e depois Gangplank, Shyvana... `permitidos` limita
        aos ids disponíveis no momento (pickable/bannable).

        O cliente tem variantes de modos especiais com o mesmo nome (ex.: "Jade_Annie",
        id 60001); a busca mostra um campeão por nome, o de menor id.
        """
        alvo = normalizar(texto)
        ids = self._por_id.keys() if permitidos is None else set(permitidos)
        por_nome: dict[str, Campeao] = {}
        for campeao in sorted(
            (self._por_id[i] for i in ids if i in self._por_id), key=lambda c: c.id
        ):
            chave = normalizar(campeao.nome)
            if alvo in chave:
                por_nome.setdefault(chave, campeao)
        return sorted(
            por_nome.values(),
            key=lambda c: (not normalizar(c.nome).startswith(alvo), normalizar(c.nome)),
        )
