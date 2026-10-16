import datetime as dt
from decimal import Decimal

import pytest

from tarvo import parse


@pytest.mark.parametrize(("raw", "expected"), [
    ("1.234,56", Decimal("1234.56")),
    ("-389,00", Decimal("-389.00")),
    ("207215.87", Decimal("207215.87")),
    (608.88, Decimal("608.88")),
    ("", None),
])
def test_br_decimal(raw, expected):
    assert parse.br_decimal(raw) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    (0.0259, Decimal("0.0259")),
    ("2,59%", Decimal("0.0259")),
    ("0,89%", Decimal("0.0089")),
    ("2,10", Decimal("0.021")),
])
def test_rate_accepts_fraction_and_percent_text(raw, expected):
    assert parse.rate(raw) == expected


def test_rate_rejects_non_numeric_text():
    with pytest.raises(ValueError):
        parse.rate("padrão")


@pytest.mark.parametrize(("raw", "expected"), [
    ("22.224.579/0001-09", "22224579000109"),
    (3229837000103, "03229837000103"),  # veio como número no xlsx e perdeu o zero
    ("00520815000100", "00520815000100"),
    (None, None),
])
def test_cnpj_normalizes_to_14_digits(raw, expected):
    assert parse.cnpj(raw) == expected


def test_br_date_formats():
    assert parse.br_date("01/09/2026") == dt.date(2026, 9, 1)
    assert parse.br_date("20260901120000[-3:BRT]") == dt.date(2026, 9, 1)
    assert parse.br_date(dt.datetime(2026, 9, 30)) == dt.date(2026, 9, 30)
