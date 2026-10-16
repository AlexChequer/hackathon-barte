"""Parsers de valores no formato em que os sistemas da Tarvo exportam (pt-BR, misturado)."""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation

CNPJ_DIGITS = 14


def br_decimal(value: object) -> Decimal | None:
    """'1.234,56' / '-389,00' / 1234.56 -> Decimal. Vazio -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    text = text.replace(".", "").replace(",", ".") if "," in text else text
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"valor numérico inválido: {value!r}") from exc


def rate(value: object) -> Decimal | None:
    """Taxa como fração. Aceita 0.0259, '2,59%' ou '2,59' (pct). Texto não numérico -> ValueError."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = str(value).strip()
    if not text:
        return None
    is_pct = text.endswith("%")
    number = br_decimal(text.rstrip("%").strip())
    if number is None:
        return None
    return number / 100 if is_pct or number >= 1 else number


def br_date(value: object) -> dt.date | None:
    """'01/09/2026', datetime, date ou OFX '20260901120000[-3:BRT]' -> date."""
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if re.fullmatch(r"\d{8}.*", text):
        return dt.datetime.strptime(text[:8], "%Y%m%d").date()
    return dt.datetime.strptime(text, "%d/%m/%Y").date()


def cnpj(value: object) -> str | None:
    """Normaliza CNPJ para 14 dígitos. Recupera zero à esquerda perdido quando veio como número."""
    if value is None:
        return None
    if isinstance(value, float):
        value = int(value)
    digits = re.sub(r"\D", "", str(value))
    if not digits:
        return None
    if len(digits) > CNPJ_DIGITS:
        raise ValueError(f"CNPJ com dígitos demais: {value!r}")
    return digits.zfill(CNPJ_DIGITS)
