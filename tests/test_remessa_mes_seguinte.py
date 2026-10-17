"""Remessa em meses sem caso em setembro: nota da Ponte ≤ 0 (R27) e lojista fora da planilha (P16)."""

from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from tarvo import controle
from tarvo.engines import remessa as rm
from tarvo.loaders import load_all
from tarvo.money import q_mul

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"


@pytest.fixture(scope="module")
def fontes():
    return load_all(DATA)


def _pend(res, tipo):
    return res.pendencias[res.pendencias["tipo"] == tipo] if not res.pendencias.empty else res.pendencias


def test_ajuste_maior_que_o_mes_nao_emite_nota_e_vira_pendencia(fontes):
    ponte = fontes["ponte"]
    base = ponte[ponte["n_operacao"] == "PC-0926-0011"].copy()  # spread positivo, Mundo Aberto
    ajuste = base.assign(n_operacao="PC-0926-9001", spread_brl=Decimal("-500.00"), spread_pct=None,
                         observacao="AJUSTE REF PC-0826-0001", linha_origem=999)
    relatorio = pd.concat([base, ajuste], ignore_index=True)
    res = rm.run(relatorio, fontes["taxas"], "2026-09")
    esperado = q_mul(base["spread_brl"].iloc[0], Decimal("0.5")) - Decimal("250.00")  # R8: por operação
    assert res.notas.empty
    pend = _pend(res, "NOTA_NEGATIVA").iloc[0]
    assert pend["id_saida"] == "RM-NTNEG-2026-09-PONTE" and pend["quem_decide"] == "Financeiro"
    assert pend["valor_brl"] == esperado
    assert "ajuste de contestação (R27)" in pend["motivo"]
    rastro = res.rastro[res.rastro["id_saida"] == pend["id_saida"]]
    assert sum(rastro["valor"], Decimal(0)) == pend["valor_brl"]
    assert set(rastro["ref_origem"]) == {"PC-0926-0011", "PC-0926-9001"}
    assert _pend(res, "SPREAD_NEGATIVO_CONTESTAR").empty  # ajuste não é negativo a contestar


def test_lojista_da_ponte_fora_da_planilha_fatura_e_pede_cadastro_ao_comercial(fontes):
    ponte = fontes["ponte"].copy()
    alvo = ponte.index[ponte["n_operacao"] == "PC-0926-0011"][0]
    ponte.loc[alvo, "cnpj"] = "11111111000111"
    res = rm.run(ponte, fontes["taxas"], "2026-09")
    pend = _pend(res, "LOJISTA_REMESSA_SEM_CADASTRO").iloc[0]
    participacao = q_mul(ponte.loc[alvo, "spread_brl"], Decimal("0.5"))
    assert pend["quem_decide"] == "Comercial" and pend["valor_brl"] == participacao
    assert "11111111000111" in set(res.comissoes["cnpj"])  # a nossa metade continua na nota (P16)
    assert _pend(res, "SPREAD_CONTRATADO_INVALIDO").empty
    relatorio, problemas = controle.ponte_ponte(ponte, res.rastro, "2026-09")
    assert problemas == [] and relatorio["fecha"]
