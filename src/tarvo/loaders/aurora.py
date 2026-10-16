"""05a - Extrato Banco Aurora (CSV com cabeçalho de banco e rodapé).

ref_origem = número da linha física do arquivo (L10, L11...), como pede o case.
"""

from pathlib import Path

import pandas as pd

from tarvo import parse

COLUMN_HEADER = "Data;Lançamento;Documento;Valor (R$);Saldo (R$)"
NON_TRANSACTIONS = {"SALDO ANTERIOR", "SALDO FINAL"}


def load_aurora(path: Path) -> pd.DataFrame:
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        header_idx = next(i for i, line in enumerate(lines) if line.strip() == COLUMN_HEADER)
    except StopIteration as exc:
        raise ValueError(f"cabeçalho '{COLUMN_HEADER}' não encontrado em {path.name}") from exc
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
