"""Identidade estável de pendência para o ciclo de decisão.

Um caso é "o mesmo problema" entre execuções. Não serve posição de linha, horário de
execução, nem o `id_saida` quando ele pode mudar (por exemplo, um `RM-NEG-PC-...` muda
se a Ponte reemitir o relatório). O caso é identificado por campos de negócio: tipo da
pendência, CNPJ/EC envolvido, referência de origem e competência.

Além da chave, cada caso tem uma composição (conjunto de operações/refs envolvidas,
quando a pendência é agregada). Se a composição muda entre execuções, registramos um
evento para que a decisão anterior seja reavaliada em vez de aplicada em silêncio.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass

import pandas as pd

_SO_DIGITOS = re.compile(r"\D+")


def _norm_cnpj(valor: object) -> str:
    """CNPJ só dígitos, 14 posições; devolve string vazia quando não houver."""
    s = _SO_DIGITOS.sub("", str(valor or ""))
    return s.zfill(14) if s else ""


def _norm_ref(valor: object) -> str:
    return str(valor or "").strip()


@dataclass(frozen=True)
class Caso:
    """Representação de um caso de negócio, independente da execução."""

    caso_hash: str
    tipo: str
    cnpj: str
    ref: str
    competencia: str
    composicao: tuple[str, ...]  # refs das operações envolvidas (ordem canônica)

    @property
    def composicao_hash(self) -> str:
        base = "|".join(self.composicao)
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _hash_caso(tipo: str, cnpj: str, ref: str, competencia: str) -> str:
    base = f"{tipo}|{cnpj}|{ref}|{competencia}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]


def _composicao(rastro: pd.DataFrame, id_saida: str) -> tuple[str, ...]:
    """Refs do rastro vinculadas a um id_saida, em ordem canônica."""
    if rastro is None or rastro.empty:
        return ()
    linhas = rastro[rastro["id_saida"] == id_saida]
    if linhas.empty:
        return ()
    refs = linhas["ref_origem"].astype(str).unique().tolist()
    return tuple(sorted(refs))


def construir(pendencia: dict, rastro: pd.DataFrame, competencia: str) -> Caso:
    """Devolve o caso correspondente a uma linha de `pendencias.csv`.

    `cnpj` sai de ref_origem quando ela é CNPJ (14 dígitos). Para pendências por
    operação (ex.: `RM-NEG-PC-0926-0210`), o CNPJ fica em branco e o caso é
    identificado pelo tipo + ref + competência.
    """
    tipo = str(pendencia["tipo"])
    ref = _norm_ref(pendencia.get("ref_origem"))
    cnpj = _norm_cnpj(ref) if ref.isdigit() and len(ref) >= 11 else ""
    composicao = _composicao(rastro, str(pendencia["id_saida"]))
    return Caso(
        caso_hash=_hash_caso(tipo, cnpj, ref, competencia),
        tipo=tipo,
        cnpj=cnpj,
        ref=ref,
        competencia=competencia,
        composicao=composicao,
    )


def construir_lote(
    pendencias: pd.DataFrame, rastro: pd.DataFrame, competencia: str
) -> dict[str, Caso]:
    """Mapa `id_saida -> Caso` para todas as pendências de uma execução."""
    if pendencias is None or pendencias.empty:
        return {}
    saida: dict[str, Caso] = {}
    for linha in pendencias.to_dict("records"):
        saida[str(linha["id_saida"])] = construir(linha, rastro, competencia)
    return saida


def precedentes_semelhantes(caso: Caso, outros: Iterable[Caso]) -> list[Caso]:
    """Casos com o mesmo tipo mas identidade diferente (uso só como referência)."""
    saida = []
    for c in outros:
        if c.tipo == caso.tipo and c.caso_hash != caso.caso_hash:
            saida.append(c)
    return saida
