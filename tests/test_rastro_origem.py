"""Pilar 1 do nível extra: todo número aponta para linhas de origem reais, e cada fonte fecha.

- Guarda: linha de rastro com ref que não existe no arquivo (CNPJ, rótulo) reprova a execução.
- CK-NTNEG e RM-CONTEST com rastro por transação/operação.
- Fechamento contra a fonte (Orbe, Ponte, Aurora, Meridiano) em `controle_fechamento.json`.
"""

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from tarvo import controle, output
from tarvo.engines import remessa as rm
from tarvo.loaders import load_all
from tarvo.orquestrador import run_closing

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
CASA = "00520815000100"


@pytest.fixture(scope="module")
def fechamento(tmp_path_factory):
    saida = tmp_path_factory.mktemp("saida")
    return saida, run_closing(DATA, saida, "2026-09")


@pytest.fixture(scope="module")
def sources():
    return load_all(DATA)


def _rastro(res, id_saida):
    return res.rastro[res.rastro["id_saida"] == id_saida]


def test_fechamento_sem_problema_de_integridade(fechamento):
    _, res = fechamento
    assert res.problemas_integridade == []
    assert res.problemas_rastro.empty


# ----- guarda de origem -----

def test_guarda_reprova_ref_que_nao_existe_no_arquivo():
    rastro = pd.DataFrame([
        {"id_saida": "A", "arquivo_origem": "orbe", "ref_origem": "TX1", "valor": Decimal("1")},
        {"id_saida": "B", "arquivo_origem": "orbe", "ref_origem": CASA, "valor": Decimal("1")},
        {"id_saida": "C", "arquivo_origem": "ponte", "ref_origem": "relatorio_ponte", "valor": Decimal("1")},
    ])
    problemas = output.validate_refs_origem(rastro, {"orbe": {"TX1"}, "ponte": {"PC-1"}}, set())
    assert problemas[0]["codigo"] == "REF_ORIGEM_INEXISTENTE"
    assert {e["id_saida"] for e in problemas[0]["exemplos"]} == {"B", "C"}


def test_guarda_aceita_pendencia_de_arquivo_ausente():
    rastro = pd.DataFrame([{"id_saida": "BLOQ", "arquivo_origem": "ponte", "ref_origem": "arquivo ausente",
                            "valor": Decimal("0")}])
    assert output.validate_refs_origem(rastro, {}, {"ponte"}) == []
    assert output.validate_refs_origem(rastro, {}, set())[0]["codigo"] == "REF_ORIGEM_INEXISTENTE"


def test_todo_rastro_aponta_linha_real(fechamento, sources):
    _, res = fechamento
    orbe = sources["orbe"]
    refs = {a: set(g["id_transacao"].astype(str)) for a, g in orbe.groupby("arquivo_origem")}
    refs |= {"ponte": set(sources["ponte"]["n_operacao"]), "aurora": set(sources["aurora"]["ref_origem"]),
             "meridiano": set(sources["meridiano"]["ref_origem"]),
             "taxas": {f"L{n}" for n in sources["taxas"]["linha_origem"]}}
    assert output.validate_refs_origem(res.rastro, refs, set()) == []


# ----- etapa 2: rastro por transação/operação -----

def test_nota_negativa_da_casa_aponta_as_transacoes_da_comissao(fechamento):
    _, res = fechamento
    neg = _rastro(res, f"CK-NTNEG-2026-09-{CASA}")
    cm = _rastro(res, f"CK-CM-2026-09-{CASA}")
    assert len(neg) == len(cm) == 119
    assert set(neg["ref_origem"]) == set(cm["ref_origem"])
    assert sum(neg["valor"], Decimal(0)) == Decimal("-5.50")
    assert neg.loc[neg["valor"] != 0, "ref_origem"].tolist() == ["TX88445133"]  # estorno de venda de agosto


def test_diferenca_da_ponte_aponta_as_operacoes_fora_da_nota(fechamento):
    _, res = fechamento
    pend = res.pendencias.set_index("id_saida").loc["RM-CONTEST-2026-09"]
    rastro = _rastro(res, "RM-CONTEST-2026-09")
    assert pend["valor_brl"] == Decimal("-506.09")
    assert sum(rastro["valor"], Decimal(0)) == pend["valor_brl"]
    assert dict(zip(rastro["ref_origem"], rastro["valor"], strict=True)) == {
        "PC-0926-0162": Decimal("410.94"),  # 2ª ocorrência, contada 1× na nota
        "PC-0926-0210": Decimal("-343.76"), "PC-0926-0326": Decimal("-254.61"),
        "PC-0926-0491": Decimal("-146.14"), "PC-0926-0545": Decimal("-172.52"),
    }
    assert "-R$ 0,56 restantes são arredondamento por operação (R8)" in pend["motivo"]
    assert "4 spreads negativos (-R$ 917,03)" in pend["motivo"] and ";" not in pend["motivo"]


def test_duplicata_conflitante_aponta_a_operacao_real(sources):
    ponte = sources["ponte"]
    copia = ponte[ponte["n_operacao"] == "PC-0926-0011"].copy()
    copia["spread_brl"] = copia["spread_brl"] + Decimal("10")
    copia["linha_origem"] = 999
    relatorio_ponte = pd.concat([ponte, copia], ignore_index=True)
    res = rm.run(relatorio_ponte, sources["taxas"], "2026-09")
    dup = res.rastro[res.rastro["id_saida"].str.startswith("RM-DUPCONF-")]
    linha_original = int(ponte.loc[ponte["n_operacao"] == "PC-0926-0011", "linha_origem"].iloc[0])
    assert set(dup["ref_origem"]) == {"PC-0926-0011"}
    assert {m.rsplit("=", 1)[-1] for m in dup["metadata"]} == {"L999", f"L{linha_original}"}
    # As duas linhas em conflito ficam fora da nota e a ponte continua fechando.
    relatorio, problemas = controle.ponte_ponte(relatorio_ponte, res.rastro, "2026-09")
    assert problemas == [] and relatorio["fecha"]


# ----- etapa 3: fechamento contra a fonte -----

def test_controle_fica_no_historico_e_nao_na_raiz(fechamento):
    saida, res = fechamento
    assert (res.out_dir / "controle_fechamento.json").exists()
    assert not (saida / "controle_fechamento.json").exists()
    gravado = json.loads((res.out_dir / "controle_fechamento.json").read_text(encoding="utf-8"))
    assert gravado == res.controle


def test_cada_fonte_fecha_em_setembro(fechamento):
    _, res = fechamento
    c = res.controle
    assert all(c[f]["fecha"] for f in ("orbe", "ponte", "aurora", "meridiano"))
    assert c["orbe"]["cobrado_pela_orbe"] == "228576.04"
    assert c["orbe"]["truncamento_da_orbe"] == "-8.35"
    assert Decimal(c["orbe"]["maior_sobra_por_transacao"]) <= controle.TOLERANCIA_ORBE_POR_TRANSACAO
    assert c["ponte"]["arredondamento_por_operacao"] == "-0.56"
    assert c["ponte"]["fora_da_nota"] == "-506.09"


def test_orbe_nao_fecha_se_some_uma_comissao(fechamento, sources):
    _, res = fechamento
    alvo = _rastro(res, "CK-CM-2026-09-95927868000148").index[0]
    _, problemas = controle.ponte_orbe(sources["orbe"], res.rastro.drop(index=alvo))
    assert problemas[0]["codigo"] == "FECHAMENTO_NAO_BATE"


def test_orbe_exige_categoria_para_saida_nova(fechamento, sources):
    _, res = fechamento
    extra = pd.DataFrame([{"id_saida": "CK-NOVA-X", "arquivo_origem": "orbe", "ref_origem": "TX88445133",
                           "valor": Decimal("0"), "metadata": ""}])
    _, problemas = controle.ponte_orbe(sources["orbe"], pd.concat([res.rastro, extra], ignore_index=True))
    assert [p["codigo"] for p in problemas] == ["RASTRO_SEM_CATEGORIA"]


def test_banco_nao_fecha_se_some_um_lancamento_ou_quebra_o_saldo(fechamento, sources):
    _, res = fechamento
    aurora = sources["aurora"]
    _, faltou = controle.ponte_banco("aurora", aurora, res.lancamentos.iloc[1:])
    assert faltou[0]["codigo"] == "FECHAMENTO_NAO_BATE"
    quebrado = aurora.copy()
    quebrado.loc[quebrado.index[5], "saldo"] = quebrado.loc[quebrado.index[5], "saldo"] + Decimal("1")
    _, quebra = controle.ponte_banco("aurora", quebrado, res.lancamentos)
    assert quebra[0]["saldo_quebra_em"]
