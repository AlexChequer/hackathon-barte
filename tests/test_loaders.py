"""Testes de integração dos loaders contra o data pack real de set/2026 (somente leitura)."""

from decimal import Decimal
from pathlib import Path

import pytest

from tarvo.loaders import find_file, load_all
from tarvo.loaders.ponte import load_ponte_footer

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"


@pytest.fixture(scope="module")
def sources():
    return load_all(DATA)


def test_orbe_has_all_rows_with_traceable_line(sources):
    orbe = sources["orbe"]
    assert len(orbe) == 1943
    assert orbe["id_transacao"].is_unique
    assert orbe["linha_origem"].iloc[0] == 2


def test_taxas_reads_every_lojista_row(sources):
    taxas = sources["taxas"]
    assert len(taxas) == 25
    assert taxas["cnpj"].str.len().eq(14).all()
    oxford = taxas[taxas["lojista"].str.startswith("Oxford")].iloc[0]
    assert oxford["credito_vista"] == Decimal("0.0259")  # veio como texto '2,59%'


def test_taxas_keeps_cell_comments(sources):
    taxas = sources["taxas"]
    casa = taxas[taxas["ec_orbe"] == "1018325654"].iloc[0]
    assert "condição especial" in casa["comentarios"]


def test_ponte_rows_match_declared_footer(sources):
    ponte = sources["ponte"]
    footer = load_ponte_footer(find_file(DATA, "ponte"))
    assert len(ponte) == footer["Total de operações:"] == 233
    assert sum(ponte["spread_brl"]) == Decimal(str(footer["Spread total R$:"]))


def test_aurora_uses_physical_line_numbers(sources):
    aurora = sources["aurora"]
    # linha física 1-based: L8 = SALDO ANTERIOR (ignorado), L9 = primeira TED da Orbe
    assert aurora["ref_origem"].iloc[0] == "L9"
    assert aurora["ref_origem"].is_unique


def test_meridiano_parses_all_ofx_transactions(sources):
    meridiano = sources["meridiano"]
    assert len(meridiano) == 100
    assert meridiano["ref_origem"].is_unique


def test_plano_has_postable_accounts(sources):
    plano = sources["plano"]
    assert plano["aceita_lancamento"].any()
    assert "3.1.01" in set(plano["COD_CONTA"])
