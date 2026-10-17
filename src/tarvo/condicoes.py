"""Condições comerciais registradas fora da planilha de taxas (fonte única).

A planilha é o que a Orbe conhece. Uma condição comercial (ex.: isenção da Casa do Estudante, R6)
muda a taxa contratada sem mudar a planilha. O motor usa a condição vigente quando houver e
compara a cobrança da Orbe com a planilha para separar falha da Orbe de falha da Tarvo (R16.1).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "condicoes_comerciais.json"
COLUNAS_TAXA = ("debito", "credito_vista", "credito_2a6", "credito_7a12", "pix", "antecipacao")


@dataclass(frozen=True)
class Condicao:
    id: str
    cnpj: str
    taxas: dict[str, Decimal]
    inicio: dt.date
    fim: dt.date | None
    fonte: str
    aprovado_por: str
    descricao: str = ""

    def vale_em(self, data: dt.date) -> bool:
        return self.inicio <= data and (self.fim is None or data <= self.fim)


def _parse(item: dict) -> Condicao:
    taxas = {k: Decimal(str(v)) for k, v in item["taxas"].items()}
    desconhecidas = set(taxas) - set(COLUNAS_TAXA)
    if desconhecidas:
        raise ValueError(f"condição {item.get('id')}: modalidade desconhecida {sorted(desconhecidas)}")
    return Condicao(
        id=item["id"],
        cnpj=str(item["cnpj"]).zfill(14),
        taxas=taxas,
        inicio=dt.date.fromisoformat(item["inicio"]),
        fim=dt.date.fromisoformat(item["fim"]) if item.get("fim") else None,
        fonte=item["fonte"],
        aprovado_por=item["aprovado_por"],
        descricao=item.get("descricao", ""),
    )


def carregar(caminho: Path = CAMINHO_PADRAO) -> tuple[Condicao, ...]:
    """Lê o arquivo de condições. Arquivo ausente = nenhuma condição (não é erro)."""
    if not caminho.exists():
        return ()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return tuple(_parse(item) for item in dados.get("condicoes", []))


def vigente(condicoes: tuple[Condicao, ...], cnpj: str, data: dt.date, coluna: str) -> Condicao | None:
    """Condição que define a taxa de `coluna` para o CNPJ na data, ou None."""
    candidatas = [c for c in condicoes if c.cnpj == cnpj and coluna in c.taxas and c.vale_em(data)]
    return max(candidatas, key=lambda c: c.inicio) if candidatas else None


@dataclass(frozen=True)
class SinalResolvido:
    """Texto da planilha já analisado (ex.: renegociação que já está na própria planilha)."""

    cnpj: str
    texto: str
    decisao: str
    fonte: str


def carregar_sinais_resolvidos(caminho: Path = CAMINHO_PADRAO) -> tuple[SinalResolvido, ...]:
    if not caminho.exists():
        return ()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return tuple(
        SinalResolvido(str(i["cnpj"]).zfill(14), i["texto"].strip(), i["decisao"], i["fonte"])
        for i in dados.get("sinais_resolvidos", [])
    )
