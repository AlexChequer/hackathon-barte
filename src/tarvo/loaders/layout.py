"""Conferência de layout na entrada (R34: "prefiro que a solução avise o que quebre").

Cada loader diz de quais colunas precisa. Se faltar alguma, o arquivo não é usado e o
fechamento marca a frente como bloqueada, dizendo o arquivo, o que faltou e o que veio.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path


class LayoutInvalido(ValueError):
    def __init__(self, arquivo: Path, faltando: list[str], encontradas: Iterable[str]):
        self.arquivo = arquivo
        self.faltando = faltando
        encontradas = [str(c) for c in encontradas if c not in (None, "")]
        super().__init__(
            f"{arquivo.name} mudou de layout: falta {', '.join(repr(f) for f in faltando)}. "
            f"Veio: {', '.join(repr(c) for c in encontradas[:20]) or 'nada reconhecível'}."
        )


def exigir(arquivo: Path, encontradas: Iterable[str], esperadas: Iterable[str]) -> None:
    encontradas = list(encontradas)
    faltando = [c for c in esperadas if c not in encontradas]
    if faltando:
        raise LayoutInvalido(arquivo, faltando, encontradas)
