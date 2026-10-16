"""03 - E-mail da Ponte Câmbio com relatório xlsx em anexo."""

import email
import io
from email import policy
from pathlib import Path

import openpyxl
import pandas as pd

from tarvo import parse

SHEET = "Operações"
HEADER_ROW = 5
COLUMNS = {
    "Nº Operação": "n_operacao",
    "Data Contratação": "data_contratacao",
    "Data Liquidação": "data_liquidacao",
    "CNPJ Cliente": "cnpj_raw",
    "Cliente": "cliente",
    "Moeda": "moeda",
    "Valor ME": "valor_me",
    "Taxa Cliente": "taxa_cliente",
    "PTAX Ref.": "ptax_ref",
    "Valor R$": "valor_brl",
    "Spread R$": "spread_brl",
    "Spread %": "spread_pct",
    "Spread Estimado R$ (D-1)": "spread_estimado_brl",
    "IOF R$": "iof_brl",
    "Status Compliance": "status_compliance",
    "Observação": "observacao",
}
NUMBER_COLS = ["valor_me", "taxa_cliente", "ptax_ref", "valor_brl", "spread_brl",
               "spread_pct", "spread_estimado_brl", "iof_brl"]


def extract_attachment(path: Path) -> tuple[str, bytes, str]:
    """Devolve (nome do anexo, bytes do xlsx, corpo do e-mail em texto)."""
    msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
    body = msg.get_body(preferencelist=("plain",))
    attachments = [a for a in msg.iter_attachments() if (a.get_filename() or "").endswith(".xlsx")]
    if len(attachments) != 1:
        raise ValueError(f"esperava 1 anexo xlsx no e-mail, achei {len(attachments)}")
    att = attachments[0]
    return att.get_filename(), att.get_content(), body.get_content() if body else ""


def load_ponte(path: Path) -> pd.DataFrame:
    filename, content, _ = extract_attachment(path)
    ws = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)[SHEET]
    rows = list(ws.iter_rows(min_row=HEADER_ROW, values_only=True))
    header = list(rows[0])
    records = [
        {"linha_origem": HEADER_ROW + offset, **dict(zip(header, row, strict=False))}
        for offset, row in enumerate(rows[1:], start=1)
        if row[0] and str(row[0]).startswith("PC-")  # para antes do rodapé 'Total de operações'
    ]
    df = pd.DataFrame(records).rename(columns=COLUMNS)
    return df.assign(
        anexo=filename,
        cnpj=df["cnpj_raw"].map(parse.cnpj),
        data_contratacao=df["data_contratacao"].map(parse.br_date),
        data_liquidacao=df["data_liquidacao"].map(parse.br_date),
        **{col: df[col].map(parse.br_decimal) for col in NUMBER_COLS},
    )


def load_ponte_footer(path: Path) -> dict:
    """Totais declarados pela Ponte no rodapé, para conferência contra a soma das linhas."""
    _, content, _ = extract_attachment(path)
    ws = openpyxl.load_workbook(io.BytesIO(content), data_only=True, read_only=True)[SHEET]
    footer = {
        str(row[0]).strip(): row[1]
        for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True)
        if row[0] and str(row[0]).startswith(("Total", "Spread total"))
    }
    return footer
