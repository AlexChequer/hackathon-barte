"""01 - Relatório de comissões da adquirente Orbe (CSV ; com decimal vírgula)."""

from pathlib import Path

import pandas as pd

from tarvo import parse

MONEY_COLS = ["valor_bruto", "valor_taxa", "valor_liquido"]
HEADER_LINES = 1


def load_orbe(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
    return raw.assign(
        linha_origem=raw.index + HEADER_LINES + 1,
        data_movimento=raw["data_movimento"].map(parse.br_date),
        data_venda_original=raw["data_venda_original"].map(parse.br_date),
        qtd_parcelas=pd.to_numeric(raw["qtd_parcelas"], errors="coerce").astype("Int64"),
        taxa_aplicada=raw["taxa_aplicada_pct"].map(lambda v: parse.br_decimal(v) / 100),
        **{col: raw[col].map(parse.br_decimal) for col in MONEY_COLS},
    )
