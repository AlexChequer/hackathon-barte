"""Causa da divergência de checkout (coluna `causa_divergencia` e motivo da CONTESTACAO_ORBE)."""

import datetime as dt
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from tarvo.engines import checkout as ck
from tarvo.engines import checkout_causa as cc
from tarvo.loaders import load_all

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
BRIDGE_CNPJ = "22224579000109"
ROTA_CNPJ = "95927868000148"


@pytest.fixture(scope="module")
def sources():
    return load_all(DATA)


@pytest.fixture(scope="module")
def res(sources):
    return ck.run(sources["orbe"], sources["taxas"], "2026-09")


def test_contagem_por_causa_em_setembro(res):
    ck_div = res.divergencias[res.divergencias["linha_negocio"] == "CHECKOUT"]
    assert ck_div["causa_divergencia"].value_counts().to_dict() == {
        cc.COND: 118, cc.DEGRAU: 87, cc.OUTRA_VIGENCIA: 5,
    }
    assert (ck_div.loc[ck_div["id_saida"].str.startswith("CK-COND-"), "causa_divergencia"] == cc.COND).all()
    assert (ck_div.loc[ck_div["cnpj"] == ROTA_CNPJ, "causa_divergencia"] == cc.DEGRAU).all()
    assert (ck_div.loc[ck_div["cnpj"] == BRIDGE_CNPJ, "causa_divergencia"] == cc.OUTRA_VIGENCIA).all()


def test_causa_nao_muda_valores(res):
    ck_div = res.divergencias[res.divergencias["linha_negocio"] == "CHECKOUT"]
    assert len(ck_div) == 210
    assert sum(ck_div["diferenca_brl"], Decimal(0)) == Decimal("16973.65")
    valores = dict(zip(res.pendencias["id_saida"], res.pendencias["valor_brl"], strict=True))
    assert valores[f"CK-CONTEST-2026-09-{ROTA_CNPJ}"] == Decimal("1546.28")
    assert valores[f"CK-CONTEST-2026-09-{BRIDGE_CNPJ}"] == Decimal("29.95")
    assert valores["CK-COND-PEND-2026-09-00520815000100"] == Decimal("15396.77")  # R33


def _motivo(res, cnpj):
    pend = res.pendencias
    return pend.loc[pend["id_saida"] == f"CK-CONTEST-2026-09-{cnpj}", "motivo"].iloc[0]


def test_motivo_da_contestacao_cita_causa_e_mantem_acao(res):
    rota, bridge = _motivo(res, ROTA_CNPJ), _motivo(res, BRIDGE_CNPJ)
    for motivo in (rota, bridge):
        assert "(R1, R16.3, R28.1)" in motivo and "Prevenção:" in motivo and ";" not in motivo
    assert ("Causa: degrau sistêmico, +0,50 p.p. em todos os produtos de crédito desde 12/09/2026 "
            "(débito, Pix e antecipação corretos)") in rota
    assert ("Causa: taxa de outra vigência, a Orbe aplicou 2,59% (vigência até 14/09/2026) "
            "no crédito à vista entre 15/09 e 18/09/2026 em vez de 2,19%") in bridge


def _datas_e_taxas_do_lojista(sources, res, cnpj):
    """Datas e taxas que existem nos dados da pendência: transações do rastro e vigências do CNPJ."""
    pend_id = f"CK-CONTEST-2026-09-{cnpj}"
    txs = set(res.rastro.loc[res.rastro["id_saida"] == pend_id, "ref_origem"])
    orbe = sources["orbe"][sources["orbe"]["id_transacao"].isin(txs)]
    taxas = sources["taxas"][sources["taxas"]["cnpj"] == cnpj]
    datas = set(orbe["data_movimento"]) | set(orbe["data_venda_original"].dropna())
    for v in taxas["vigencia_raw"]:
        achadas = re.findall(r"\d{2}/\d{2}/\d{4}", str(v))
        datas |= {dt.datetime.strptime(d, "%d/%m/%Y").date() for d in achadas}
    contrato = {t for c in ("debito", "credito_vista", "credito_2a6", "credito_7a12", "pix", "antecipacao")
                for t in taxas[c] if t is not None}
    aplicadas = set(orbe["taxa_aplicada"])
    deltas = {a - c for a in aplicadas for c in contrato}
    return datas, {t * 100 for t in contrato | aplicadas}, {d * 100 for d in deltas}


@pytest.mark.parametrize("cnpj", [ROTA_CNPJ, BRIDGE_CNPJ])
def test_todo_numero_do_texto_da_causa_existe_nos_dados(sources, res, cnpj):
    causa = _motivo(res, cnpj).split("Causa:", 1)[1].split("Detalhe:", 1)[0]
    datas, taxas, deltas = _datas_e_taxas_do_lojista(sources, res, cnpj)
    anos = {d.year for d in datas}

    def num(s):
        return Decimal(s.replace(",", "."))

    for m in re.finditer(r"([+-]\d+,\d+) p\.p\.", causa):
        assert num(m.group(1)) in deltas, m.group(0)
    for m in re.finditer(r"(?<![+\d,])(\d+,\d+)%", causa):
        assert num(m.group(1)) in taxas, m.group(0)
    for m in re.finditer(r"(\d{2})/(\d{2})(?:/(\d{4}))?", causa):
        d, mes, ano = int(m.group(1)), int(m.group(2)), m.group(3)
        candidatos = {dt.date(int(ano), mes, d)} if ano else {dt.date(a, mes, d) for a in anos}
        assert candidatos & datas, m.group(0)
    resto = re.sub(r"[+-]?\d+,\d+(?: p\.p\.|%)|\d{2}/\d{2}(?:/\d{4})?|2–6x|7–12x", "", causa)
    assert not re.search(r"\d", resto), resto


# ----- regras em dados sintéticos -----

def _entry(linha, ini=None, fim=None, **taxas):
    base = dict(debito=Decimal("0.0149"), credito_vista=Decimal("0.0249"), credito_2a6=Decimal("0.0299"),
                credito_7a12=Decimal("0.0359"), pix=Decimal("0.0089"), antecipacao=Decimal("0.021"))
    base.update(taxas)
    return ck.LojistaTaxas(linha_origem=linha, lojista="X", cnpj="1", vigencia_inicio=ini, vigencia_fim=fim,
                           linha_planilha=linha, **base)


def _linhas(rows):
    out = []
    for i, (produto, dia, planilha, aplicada, linha) in enumerate(rows):
        out.append({"id_transacao": f"T{i}", "cnpj": "1", "tipo": "VENDA", "produto": produto,
                    "data_referencia": dt.date(2026, 9, dia), "taxa_planilha": Decimal(planilha),
                    "taxa_aplicada": Decimal(aplicada), "linha_planilha": linha,
                    "divergencia": Decimal("1") if planilha != aplicada else Decimal("0")})
    return pd.DataFrame(out)


def test_degrau_vem_antes_de_casar_com_taxa_de_outro_produto():
    """Rota: 2,49% + 0,50 = 2,99% (taxa do 2–6x) e mesmo assim é degrau, não outra faixa."""
    linhas = _linhas([("credito_vista", 12, "0.0249", "0.0299", 1),
                      ("credito_2a6", 12, "0.0299", "0.0349", 1),
                      ("credito_vista", 11, "0.0249", "0.0249", 1)])
    assert cc.classificar(linhas, {"ec": [_entry(1)]}) == {"T0": cc.DEGRAU, "T1": cc.DEGRAU}


def test_um_produto_so_nao_e_degrau():
    linhas = _linhas([("credito_vista", 12, "0.0249", "0.0299", 1)])
    assert cc.classificar(linhas, {"ec": [_entry(1)]}) == {"T0": cc.NAO_DETERMINADA}


def test_linha_correta_dentro_da_janela_desfaz_o_degrau():
    linhas = _linhas([("credito_vista", 12, "0.0249", "0.0299", 1),
                      ("credito_vista", 13, "0.0249", "0.0249", 1),
                      ("credito_vista", 14, "0.0249", "0.0299", 1),
                      ("credito_2a6", 12, "0.0299", "0.0349", 1)])
    causas = cc.classificar(linhas, {"ec": [_entry(1)]})
    assert set(causas.values()) == {cc.NAO_DETERMINADA}


def test_taxa_de_outra_vigencia():
    reg = {"ec": [_entry(1, fim=dt.date(2026, 9, 14), credito_vista=Decimal("0.0259")),
                  _entry(2, ini=dt.date(2026, 9, 15), credito_vista=Decimal("0.0219"))]}
    linhas = _linhas([("credito_vista", 16, "0.0219", "0.0259", 2)])
    assert cc.classificar(linhas, reg) == {"T0": cc.OUTRA_VIGENCIA}


def test_degrau_que_tambem_casa_com_outra_vigencia_fica_nao_determinada():
    """Duas regras explicam a mesma transação: não escolhemos por prioridade."""
    reg = {"ec": [_entry(1, fim=dt.date(2026, 9, 11), credito_vista=Decimal("0.0299"),
                         credito_2a6=Decimal("0.0349")),
                  _entry(2, ini=dt.date(2026, 9, 12))]}
    linhas = _linhas([("credito_vista", 12, "0.0249", "0.0299", 2),
                      ("credito_2a6", 12, "0.0299", "0.0349", 2)])
    assert set(cc.classificar(linhas, reg).values()) == {cc.NAO_DETERMINADA}
