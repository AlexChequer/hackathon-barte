"""Pendências da remessa pedidas pela Helena (R10, R12, R28.3): dado real de set/2026 + casos sintéticos."""

from decimal import Decimal
from pathlib import Path

import pytest

from tarvo.engines import remessa as rm
from tarvo.loaders import load_all

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
MUNDO_ABERTO = "17217888000111"


@pytest.fixture(scope="module")
def fontes():
    return load_all(DATA)


@pytest.fixture(scope="module")
def res(fontes):
    return rm.run(fontes["ponte"], fontes["taxas"], "2026-09")


def _pend(res, tipo):
    return res.pendencias[res.pendencias["tipo"] == tipo]


def _rastro(res, id_saida):
    return res.rastro[res.rastro["id_saida"] == id_saida]


# --- gap 6: contestação com a Ponte, uma por lojista (R10, R12, R24.1) ---

def test_mundo_aberto_vira_uma_contestacao_com_as_23_operacoes(res):
    pend = _pend(res, "CONTESTACAO_PONTE")
    assert list(pend["ref_origem"]) == [MUNDO_ABERTO]
    linha = pend.iloc[0]
    assert linha["valor_brl"] == Decimal("1418.85")
    assert linha["quem_decide"] == "Financeiro"
    rastro = _rastro(res, linha["id_saida"])
    assert len(rastro) == 23 and sum(rastro["valor"]) == linha["valor_brl"]
    divs = res.divergencias[res.divergencias["cnpj"] == MUNDO_ABERTO]
    assert sorted(rastro["ref_origem"]) == sorted(divs["ref_origem"])


def test_sintetico_dois_lojistas_com_spread_acima_viram_duas_contestacoes(fontes):
    ponte = fontes["ponte"].copy()
    alvo = ponte.index[(ponte["cnpj"] != MUNDO_ABERTO) & (ponte["spread_brl"] > 0)][0]
    ponte.loc[alvo, "spread_pct"] = Decimal("0.02")  # contrato padrão 1,5%: 0,5 p.p. acima
    res = rm.run(ponte, fontes["taxas"], "2026-09")
    pend = _pend(res, "CONTESTACAO_PONTE")
    assert len(pend) == 2
    outro = pend[pend["ref_origem"] == ponte.loc[alvo, "cnpj"]].iloc[0]
    assert len(_rastro(res, outro["id_saida"])) == 1
