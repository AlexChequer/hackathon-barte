"""Condições comerciais fora da planilha (R6, R16.1, R22): Casa do Estudante e o critério Orbe × Tarvo."""

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pytest

from tarvo import condicoes
from tarvo.engines import checkout as ck
from tarvo.loaders import load_all

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
CASA_CNPJ = "00520815000100"
ROTA_CNPJ = "95927868000148"


@pytest.fixture(scope="module")
def sources():
    return load_all(DATA)


@pytest.fixture(scope="module")
def res(sources):
    return ck.run(sources["orbe"], sources["taxas"], "2026-09")


def test_casa_vem_do_arquivo_de_condicoes():
    conds = condicoes.carregar()
    casa = condicoes.vigente(conds, CASA_CNPJ, dt.date(2026, 10, 15), "credito_vista")
    assert casa is not None and casa.taxas["credito_vista"] == Decimal("0")
    assert casa.aprovado_por == "Comercial"
    assert condicoes.vigente(conds, CASA_CNPJ, dt.date(2027, 1, 1), "credito_vista") is None


def test_casa_fica_marcada_como_condicao_e_nao_como_divergencia_da_orbe(res):
    div = res.divergencias
    casa = div[div["cnpj"] == CASA_CNPJ]
    assert len(casa) == 118
    assert casa["id_saida"].str.startswith("CK-COND-").all()
    assert sum(casa["diferenca_brl"]) == Decimal("15397.42")


def test_rota_continua_divergencia_cobravel_da_orbe(res):
    rota = res.divergencias[res.divergencias["cnpj"] == ROTA_CNPJ]
    assert len(rota) == 87
    assert rota["id_saida"].str.startswith("CK-DIV-").all()


def test_uma_pendencia_por_lojista_com_total_e_rastro_por_transacao(res):
    pend = res.pendencias[res.pendencias["tipo"] == "CONDICAO_NAO_INFORMADA_ORBE"]
    assert len(pend) == 1
    linha = pend.iloc[0]
    assert linha["valor_brl"] == Decimal("15397.42")
    assert "Comercial" in linha["quem_decide"]
    rastro = res.rastro[res.rastro["id_saida"] == linha["id_saida"]]
    assert len(rastro) == 118
    assert sum(rastro["valor"]) == linha["valor_brl"]


def test_orbe_acima_da_planilha_durante_condicao_separa_as_duas_partes(sources):
    """Orbe cobra 0,5 p.p. acima da planilha numa venda da Casa: 2,69% é da Tarvo, 0,5 p.p. é da Orbe."""
    orbe = sources["orbe"].copy()
    alvo = orbe["id_transacao"] == "TX88410932"
    orbe.loc[alvo, "taxa_aplicada"] = Decimal("0.0319")
    res = ck.run(orbe, sources["taxas"], "2026-09")
    linhas = res.divergencias[res.divergencias["ref_origem"] == "TX88410932"].set_index("id_saida")
    assert linhas.loc["CK-COND-TX88410932", "diferenca_brl"] == Decimal("16.38")
    assert linhas.loc["CK-DIV-TX88410932", "diferenca_brl"] == Decimal("3.04")


def test_uma_contestacao_da_orbe_por_lojista_com_diferenca_liquida(res):
    """R1 + R24.1 + R16.3: uma pendência por (Orbe, lojista), valor líquido dos CK-DIV, Helena decide."""
    pend = res.pendencias[res.pendencias["tipo"] == "CONTESTACAO_ORBE"].set_index("ref_origem")
    assert set(pend.index) == {ROTA_CNPJ, "22224579000109"}
    assert pend.loc[ROTA_CNPJ, "valor_brl"] == Decimal("1546.28")  # 83 vendas − 4 estornos
    assert pend.loc["22224579000109", "valor_brl"] == Decimal("29.95")
    assert set(pend["quem_decide"]) == {"Financeiro"}
    for _, linha in pend.iterrows():
        rastro = res.rastro[res.rastro["id_saida"] == linha["id_saida"]]
        divs = res.divergencias[res.divergencias["id_saida"].str.startswith("CK-DIV-")
                                & (res.divergencias["cnpj"] == linha.name)]
        assert sorted(rastro["ref_origem"]) == sorted(divs["ref_origem"])
        assert sum(rastro["valor"]) == linha["valor_brl"]


def test_casa_nao_entra_na_contestacao_da_orbe(res):
    pend = res.pendencias[res.pendencias["tipo"] == "CONTESTACAO_ORBE"]
    assert CASA_CNPJ not in set(pend["ref_origem"])


def test_contestacao_usa_o_nome_canonico_do_lojista(res):
    pend = res.pendencias[res.pendencias["ref_origem"] == "22224579000109"]
    assert pend["motivo"].iloc[0].startswith("Escola Bridge de Idiomas Ltda")
