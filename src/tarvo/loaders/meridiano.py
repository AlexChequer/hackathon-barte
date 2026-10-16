"""05b - Extrato Banco Meridiano (OFX 1.02 SGML, charset 1252). ref_origem = FITID."""

import re
from pathlib import Path

import pandas as pd

from tarvo import parse

ENCODING = "cp1252"
BLOCK = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S)
TAG = re.compile(r"<(\w+)>([^<\r\n]*)")


def load_meridiano(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding=ENCODING)
    records = []
    for block in BLOCK.findall(text):
        tags = {k: v.strip() for k, v in TAG.findall(block)}
        records.append({
            "ref_origem": tags["FITID"],
            "data": parse.br_date(tags["DTPOSTED"]),
            "tipo": tags.get("TRNTYPE"),
            "descricao": tags.get("MEMO", ""),
            "documento": tags.get("CHECKNUM"),
            "valor": parse.br_decimal(tags["TRNAMT"]),
        })
    return pd.DataFrame(records)
