"""05b - Extrato Banco Meridiano (OFX 1.02 SGML, charset 1252). ref_origem = FITID."""

import re
from pathlib import Path

import pandas as pd

from tarvo import parse
from tarvo.loaders.layout import LayoutInvalido, exigir

ENCODING = "cp1252"
BLOCK = re.compile(r"<STMTTRN>(.*?)</STMTTRN>", re.S)
TAG = re.compile(r"<(\w+)>([^<\r\n]*)")
TAG_NOME = re.compile(r"<(\w+)>")


def load_meridiano(path: Path) -> pd.DataFrame:
    text = path.read_text(encoding=ENCODING)
    blocos = BLOCK.findall(text)
    if not blocos:
        raise LayoutInvalido(path, ["<STMTTRN>"], sorted(set(TAG_NOME.findall(text)))[:20])
    records = []
    for block in blocos:
        tags = {k: v.strip() for k, v in TAG.findall(block)}
        exigir(path, tags, ["FITID", "DTPOSTED", "TRNAMT"])
        records.append({
            "ref_origem": tags["FITID"],
            "data": parse.br_date(tags["DTPOSTED"]),
            "tipo": tags.get("TRNTYPE"),
            "descricao": tags.get("MEMO", ""),
            "documento": tags.get("CHECKNUM"),
            "valor": parse.br_decimal(tags["TRNAMT"]),
        })
    return pd.DataFrame(records)
