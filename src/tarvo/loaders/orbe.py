"""01 - Relatório de comissões da adquirente Orbe (CSV ; com decimal vírgula)."""

from pathlib import Path

import pandas as pd

from tarvo import parse
from tarvo.loaders.layout import exigir

MONEY_COLS = ["valor_bruto", "valor_taxa", "valor_liquido"]
HEADER_LINES = 1
COLUNAS = ["id_transacao", "data_movimento", "cod_estabelecimento", "nome_estabelecimento", "tipo_lancamento",
           "modalidade", "qtd_parcelas", "valor_bruto", "taxa_aplicada_pct", "valor_taxa", "valor_liquido",
           "id_referencia", "data_venda_original"]


def load_orbe(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
    exigir(path, raw.columns, COLUNAS)
    return raw.assign(
        linha_origem=raw.index + HEADER_LINES + 1,
        data_movimento=raw["data_movimento"].map(parse.br_date),
        data_venda_original=raw["data_venda_original"].map(parse.br_date),
        qtd_parcelas=pd.to_numeric(raw["qtd_parcelas"], errors="coerce").astype("Int64"),
        taxa_aplicada=raw["taxa_aplicada_pct"].map(lambda v: parse.br_decimal(v) / 100),
        **{col: raw[col].map(parse.br_decimal) for col in MONEY_COLS},
    )
