"""04 - Plano de contas exportado do ERP Fênix (ISO-8859-1)."""

from pathlib import Path

import pandas as pd

from tarvo.loaders.layout import exigir

ENCODING = "latin-1"


def load_plano(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding=ENCODING)
    exigir(path, raw.columns, ["COD_CONTA", "DESCRICAO", "ACEITA_LANCTO"])
    return raw.assign(aceita_lancamento=raw["ACEITA_LANCTO"].eq("S"))
