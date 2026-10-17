"""Pilar 2 do nível extra: toda pendência explicada (motivo + próximo passo), com valores em pt-BR.

R26: "pendência de acompanhamento não é alarme falso, desde que tenha motivo e próximo passo".
"""

import csv
import re
from decimal import Decimal
from pathlib import Path

import pytest

from tarvo import pendencias as pend_mod
from tarvo.money import brl, pct_br
from tarvo.orquestrador import run_closing

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data" / "raw" / "set2026"
# Valor monetário com ponto decimal no meio de um texto (ex.: "15396.77"): formato de CSV, não de pessoa.
DECIMAL_COM_PONTO = re.compile(r"(?<![\d.,])-?\d+\.\d{2}(?![\d%])")


@pytest.fixture(scope="module")
def fechamento(tmp_path_factory):
    saida = tmp_path_factory.mktemp("saida")
    return saida, run_closing(DATA, saida, "2026-09")


def _pend(res):
    return res.pendencias.set_index("id_saida")


def test_todo_tipo_de_pendencia_do_codigo_tem_proximo_passo():
    tipos = set()
    for arquivo in (RAIZ / "src" / "tarvo").rglob("*.py"):
        tipos |= set(re.findall(r'"tipo": "([A-Z_]+)"', arquivo.read_text(encoding="utf-8")))
    assert len(tipos) >= 25
    assert tipos - set(pend_mod.PROXIMO_PASSO) == set()


def test_toda_pendencia_de_setembro_sai_com_proximo_passo(fechamento):
    _, res = fechamento
    passos = res.pendencias["proximo_passo"]
    assert passos.notna().all() and (passos.str.len() > 20).all()
    assert not (passos == pend_mod.SEM_TEXTO).any()


def test_proximo_passo_e_coluna_extra_depois_das_obrigatorias(fechamento):
    saida, _ = fechamento
    with open(saida / "pendencias.csv", newline="", encoding="utf-8") as f:
        cabecalho = next(csv.reader(f, delimiter=";"))
    obrigatorias = ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"]
    assert cabecalho == [*obrigatorias, "proximo_passo"]


def test_textos_trazem_valores_em_reais_no_formato_brasileiro(fechamento):
    _, res = fechamento
    for coluna in ("motivo", "proximo_passo"):
        textos = res.pendencias.set_index("id_saida")[coluna]
        com_ponto = {i: DECIMAL_COM_PONTO.findall(t) for i, t in textos.items()
                     if DECIMAL_COM_PONTO.search(t)}
        assert com_ponto == {}, coluna


def test_nota_negativa_explica_de_onde_vem_o_saldo(fechamento):
    _, res = fechamento
    motivo = _pend(res).loc["CK-NTNEG-2026-09-00520815000100", "motivo"]
    assert "TX88445133 (estorno, venda de 21/08/2026, taxa 1,49%) -R$ 5,50" in motivo
    assert "As outras 118 transações têm comissão R$ 0,00" in motivo


def test_motivos_reforcados(fechamento):
    _, res = fechamento
    p = _pend(res)
    assert "CNPJ do pagador no extrato: 38.686.002/0001-80" in p.loc["EX-PN-AURORA-L50", "motivo"]
    assert "R$ 12.400,00 em 23/09/2026" in p.loc["EX-PN-AURORA-L65", "motivo"]
    assert "Conferir o TED de repasse da Ponte" in p.loc["RM-CONTEST-2026-09", "proximo_passo"]
    assert "pedir o estorno de R$ 1.546,28" in p.loc["CK-CONTEST-2026-09-95927868000148", "proximo_passo"]
    assert "setembro" not in p.loc["RM-CONTESTA-2026-09-17217888000111", "motivo"]  # nada fixo do mês (O1)


def test_formatadores_de_texto():
    assert brl(Decimal("-1351.87")) == "-R$ 1.351,87"
    assert brl(Decimal("0.005")) == "R$ 0,01"  # R8: meio centavo para cima
    assert brl(Decimal("-0.00")) == "R$ 0,00"
    assert brl(Decimal("NaN")) == "valor indisponível"
    assert pct_br(Decimal("2.1900")) == "2,19%" and pct_br(Decimal("1.4991")) == "1,4991%"
    assert pct_br(None) == "—" and pct_br(Decimal("NaN")) == "—"
