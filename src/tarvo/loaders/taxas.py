"""02 - Planilha de taxas contratadas (mantida à mão). Só a aba 'Taxas vigentes'."""

from pathlib import Path

import openpyxl
import pandas as pd

from tarvo import parse

SHEET = "Taxas vigentes"
HEADER_ROW = 5
COLUMNS = {
    "Lojista": "lojista",
    "CNPJ": "cnpj_raw",
    "EC Orbe": "ec_orbe",
    "Débito": "debito",
    "Crédito à vista": "credito_vista",
    "Créd. 2-6x": "credito_2a6",
    "Créd. 7-12x": "credito_7a12",
    "Pix": "pix",
    "Antecipação": "antecipacao",
    "Spread remessa": "spread_remessa_raw",
    "Vigência": "vigencia_raw",
    "Obs": "obs",
}
RATE_COLS = ["debito", "credito_vista", "credito_2a6", "credito_7a12", "pix", "antecipacao"]


def _safe_rate(value: object) -> object:
    """Converte taxa; mantém None quando não é número (ex.: 'padrão') para o motor decidir."""
    try:
        return parse.rate(value)
    except ValueError:
        return None


def load_taxas(path: Path) -> pd.DataFrame:
    # sem read_only: comentários de célula carregam regra de negócio (ex.: Casa do Estudante, R6)
    ws = openpyxl.load_workbook(path, data_only=True)[SHEET]
    rows = list(ws.iter_rows(min_row=HEADER_ROW))
    header = [cell.value for cell in rows[0]]
    records = [
        {
            "linha_origem": HEADER_ROW + offset,
            **dict(zip(header, (cell.value for cell in row), strict=False)),
            "comentarios": " | ".join(c.comment.text.strip() for c in row if c.comment) or None,
        }
        for offset, row in enumerate(rows[1:], start=1)
        if row[0].value and row[1].value  # linha de lojista: tem nome e CNPJ (ignora rodapé '* spread...')
    ]
    df = pd.DataFrame(records).rename(columns=COLUMNS)
    return df.assign(
        cnpj=df["cnpj_raw"].map(parse.cnpj),
        ec_orbe=df["ec_orbe"].map(lambda v: str(v).strip() if v else None),
        spread_remessa=df["spread_remessa_raw"].map(_safe_rate),
        **{col: df[col].map(_safe_rate) for col in RATE_COLS},
    )
