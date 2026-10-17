"""05a - Extrato Banco Aurora (CSV com cabeçalho de banco e rodapé).

ref_origem = número da linha física do arquivo (L10, L11...), como pede o case.
"""

from pathlib import Path

import pandas as pd

from tarvo import parse
from tarvo.loaders.layout import LayoutInvalido

COLUMN_HEADER = "Data;Lançamento;Documento;Valor (R$);Saldo (R$)"
NON_TRANSACTIONS = {"SALDO ANTERIOR", "SALDO FINAL"}


def load_aurora(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        header_idx = next(i for i, line in enumerate(lines) if line.strip() == COLUMN_HEADER)
    except StopIteration as exc:
        candidato = next((line for line in lines if line.startswith("Data;")), "")
        raise LayoutInvalido(path, [c for c in COLUMN_HEADER.split(";") if c not in candidato.split(";")]
                             or [COLUMN_HEADER], candidato.split(";")) from exc
    records = []
    for idx, line in enumerate(lines[header_idx + 1:], start=header_idx + 2):
        data, descricao, documento, valor, saldo = (line.split(";") + [""] * 5)[:5]
        if not data or not valor or descricao.strip() in NON_TRANSACTIONS:
            continue
        records.append({
            "ref_origem": f"L{idx}",
            "data": parse.br_date(data),
            "descricao": descricao.strip(),
            "documento": documento.strip() or None,
            "valor": parse.br_decimal(valor),
            "saldo": parse.br_decimal(saldo),
        })
    return pd.DataFrame(records)
