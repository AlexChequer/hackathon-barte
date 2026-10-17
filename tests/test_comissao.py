"""Controles da comissão de checkout, recalculados a partir do arquivo cru da Orbe."""

import csv
import json
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import pytest

from src.calculo import arredondar, conferir_rastro
from src.escrita import escrever
from src.leitura import PADRAO_ORBE, achar_arquivo, normalizar_cnpj, numero_br
from src.main import PREMISSAS, rodar

DADOS = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
ATLAS = "1076801732"
DE_PARA_R3 = {"1043300981": "66564512000199", "1043396662": "78576234000179", "1038867654": "07752116000126"}


@pytest.fixture(scope="module")
def cru():
    with achar_arquivo(DADOS, PADRAO_ORBE).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


@pytest.fixture(scope="module")
def res():
    return rodar(DADOS)


def test_orbe_ids_unicos_e_liquido_consistente(cru):
    assert len({r["id_transacao"] for r in cru}) == len(cru)
    for r in cru:
        assert numero_br(r["valor_bruto"]) - numero_br(r["valor_taxa"]) == numero_br(r["valor_liquido"])


def test_fechamento_cobre_todo_o_valor_cobrado_pela_orbe(cru, res):
    total_orbe = sum(numero_br(r["valor_taxa"]) for r in cru)
    cobrado_faturado = sum(c.cobrado_orbe_brl for c in res.comissoes)
    pend = sum(p.valor_brl for p in res.pendencias)
    fora = sum(r.valor for r in res.rastro if r.id_saida.startswith("FORA-"))
    assert cobrado_faturado + pend + fora == total_orbe
    assert res.controle["diferenca_fechamento"] == "0.00"


def test_rastro_soma_bate_com_cada_saida(res):
    soma = defaultdict(Decimal)
    for r in res.rastro:
        soma[r.id_saida] += r.valor
    for c in res.comissoes:
        assert soma[c.id_saida] == c.comissao_brl, c.id_saida
    for p in res.pendencias:
        assert soma[p.id_saida] == p.valor_brl, p.id_saida
    assert conferir_rastro(res) == []


def test_cada_transacao_em_exatamente_um_id_saida(cru, res):
    refs = Counter(r.ref_origem for r in res.rastro)
    assert set(refs) == {r["id_transacao"] for r in cru}
    assert set(refs.values()) == {1}


def test_cnpj_14_digitos_sem_repeticao(res):
    cnpjs = [c.cnpj for c in res.comissoes]
    assert all(len(c) == 14 and c.isdigit() for c in cnpjs)
    assert len(cnpjs) == len(set(cnpjs))


@pytest.mark.parametrize("entrada, esperado", [
    (3229837000103, "03229837000103"),
    ("3229837000103", "03229837000103"),
    ("22.224.579/0001-09", "22224579000109"),
    ("00520815000100", "00520815000100"),
    (None, None),
    ("", None),
])
def test_normalizar_cnpj(entrada, esperado):
    assert normalizar_cnpj(entrada) == esperado


def test_ec_sem_vinculo_nao_vira_comissao(res):
    ecs_faturados = set().union(*(c.ecs for c in res.comissoes))
    assert ATLAS not in ecs_faturados
    pend = {p.ref_origem: p for p in res.pendencias if p.tipo == "EC_SEM_CNPJ"}
    assert set(pend) == {f"EC:{ATLAS}"}
    assert pend[f"EC:{ATLAS}"].quem_decide == "Comercial"


def test_de_para_r3_usa_cnpj_da_planilha(res):
    por_ec = {ec: c.cnpj for c in res.comissoes for ec in c.ecs}
    for ec, cnpj in DE_PARA_R3.items():
        assert por_ec[ec] == cnpj


def test_arredondamento_half_up_por_linha():
    assert arredondar(Decimal("0.005")) == Decimal("0.01")
    assert arredondar(Decimal("-0.005")) == Decimal("-0.01")
    assert arredondar(Decimal("608.88") * Decimal("0.0269")) == Decimal("16.38")  # Orbe truncou em 16,37


def test_casos_de_referencia(res):
    rastro = {r.ref_origem: r for r in res.rastro}
    com = {c.cnpj: c for c in res.comissoes}
    # R6 + R2: Casa isenta em setembro; único valor é o estorno de venda de agosto pela taxa histórica.
    assert com["00520815000100"].comissao_brl == Decimal("-5.50")
    assert rastro["TX88445133"].valor == Decimal("-5.50")
    assert rastro["TX88445133"].obs.startswith("estorno_de_venda_de_2026-08")
    # R4: reversão anula exatamente a antecipação referenciada.
    assert rastro["AN88445093"].valor == -rastro["AN88445076"].valor
    # Bridge: duas linhas de vigência, um lojista só.
    assert sum(1 for c in res.comissoes if c.cnpj == "22224579000109") == 1


def test_premissas_tem_fonte_para_cada_regra():
    p = json.loads(PREMISSAS.read_text(encoding="utf-8"))
    regras = [k for k in p if not k.startswith("_")]
    sem_fonte = [k for k in regras if f"_{k}" not in p and k not in ("quem_decide_padrao",)]
    assert sem_fonte == []


def test_escrita_formato_fixo(res, tmp_path):
    escrever(res, tmp_path)
    linhas = (tmp_path / "comissoes_por_lojista.csv").read_text(encoding="utf-8").splitlines()
    assert linhas[0].startswith("id_saida;cnpj;lojista;linha_negocio;comissao_brl")
    for linha in linhas[1:]:
        campos = linha.split(";")
        assert campos[3] == "CHECKOUT"
        assert len(campos[4].split(".")[1]) == 2
    rastro = (tmp_path / "rastro.csv").read_text(encoding="utf-8").splitlines()
    assert rastro[0].startswith("id_saida;arquivo_origem;ref_origem;valor")
    pend = (tmp_path / "pendencias.csv").read_text(encoding="utf-8").splitlines()
    assert pend[0] == "id_saida;tipo;ref_origem;valor_brl;motivo;quem_decide"
