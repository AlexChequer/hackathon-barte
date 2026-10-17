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
    assert (orbe["arquivo_origem"] == "orbe").sum() == 1943
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


def test_ajustes_tardios_da_orbe_entram_na_mesma_base_com_arquivo_de_origem(sources):
    """Arquivo 06 (13h10 de 17/10): mesmo formato do 01; opcional; pode haver mais de um."""
    orbe = sources["orbe"]
    assert len(orbe) == 1943 + 14
    assert orbe["id_transacao"].is_unique
    origem = orbe.set_index("id_transacao")["arquivo_origem"]
    assert origem["TX88447225"] == "orbe_ajustes" and origem["TX88410932"] == "orbe"


def test_sem_arquivo_de_ajustes_continua_funcionando(tmp_path):
    for f in DATA.iterdir():
        if not f.name.startswith("06_"):
            (tmp_path / f.name).write_bytes(f.read_bytes())
    assert len(load_all(tmp_path)["orbe"]) == 1943
