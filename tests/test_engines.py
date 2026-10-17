"""Casos críticos do fechamento de set/2026.

Casa isenta, estorno de agosto com taxa histórica, Bridge colapsado por CNPJ,
Atlas sem contrato, Rota Global, 4 negativos da Ponte, duplicata resolvida,
transferência Aurora→Meridiano em trânsito, PIX sem identificação, rastro exato.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from tarvo import rules
from tarvo.engines import checkout as ck
from tarvo.engines import extratos as ex
from tarvo.engines import remessa as rm
from tarvo.loaders import load_all

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
CASA_CNPJ = "00520815000100"
BRIDGE_CNPJ = "22224579000109"
ROTA_CNPJ = "95927868000148"
ATLAS_EC = "1076801732"


@pytest.fixture(scope="module")
def sources():
    return load_all(DATA)


@pytest.fixture(scope="module")
def res_checkout(sources):
    return ck.run(sources["orbe"], sources["taxas"], "2026-09")


@pytest.fixture(scope="module")
def res_remessa(sources):
    return rm.run(sources["ponte"], sources["taxas"], "2026-09")


@pytest.fixture(scope="module")
def res_extratos(sources):
    return ex.run(sources["aurora"], sources["meridiano"], sources["plano"], "2026-09")


# ---------------- CHECKOUT ----------------

def test_casa_do_estudante_commission_is_only_estorno(res_checkout):
    """Casa isenta em set-dez. Setembro só tem o estorno TX88445133 de agosto (-5.50)."""
    casa = res_checkout.comissoes[res_checkout.comissoes["cnpj"] == CASA_CNPJ]
    assert len(casa) == 1
    assert casa["comissao_brl"].iloc[0] == Decimal("-5.50")


def test_casa_negative_commission_opens_pendencia(res_checkout):
    pend = res_checkout.pendencias
    casa_pend = pend[(pend["tipo"] == "NOTA_NEGATIVA")]
    assert len(casa_pend) == 1
    assert casa_pend["valor_brl"].iloc[0] == Decimal("-5.50")


def test_casa_has_no_nota_in_september(res_checkout):
    casa_notas = res_checkout.notas[res_checkout.notas["tomador_cnpj"] == CASA_CNPJ]
    assert casa_notas.empty


def test_bridge_single_nota_per_cnpj(res_checkout):
    bridge = res_checkout.notas[res_checkout.notas["tomador_cnpj"] == BRIDGE_CNPJ]
    assert len(bridge) == 1


def test_atlas_opens_sem_contrato_pendencias(res_checkout):
    pend = res_checkout.pendencias
    atlas = pend[pend["tipo"] == "SEM_CONTRATO"]
    assert len(atlas) >= 1
    assert not res_checkout.comissoes["cnpj"].astype(str).str.contains("ATLAS").any()


def test_tx88445133_estorno_uses_historical_rate_no_divergence(res_checkout):
    """O estorno não deve aparecer em divergências — contrato = aplicada = taxa histórica."""
    div = res_checkout.divergencias
    assert (div["ref_origem"] == "TX88445133").sum() == 0


def test_rota_global_divergence_is_always_0_5_pp_in_credit(res_checkout):
    """Rota Global: aplicada = contratada + 0,50pp em todas as modalidades de crédito."""
    div = res_checkout.divergencias
    rota = div[div["cnpj"] == ROTA_CNPJ]
    assert len(rota) > 0
    diffs_pp = (rota["taxa_aplicada_pct"] - rota["taxa_contratada_pct"]).abs().unique()
    assert set(diffs_pp.tolist()) == {Decimal("0.5000")}


def test_rastro_covers_every_checkout_commission(res_checkout):
    """Cada id_saida de comissão tem rastro cuja soma bate em centavos exatos."""
    from tarvo.output import check_rastro
    diff = check_rastro(res_checkout.comissoes, "comissao_brl",
                        res_checkout.rastro.dropna(subset=["id_saida"]))
    assert diff.empty


# ---------------- REMESSA ----------------

def test_ponte_nota_unica(res_remessa):
    assert len(res_remessa.notas) == 1
    assert res_remessa.notas["tomador_cnpj"].iloc[0] == rules.PONTE_CNPJ


def test_ponte_nota_total_equals_sum_of_participacoes(res_remessa):
    nota_valor = res_remessa.notas["valor_brl"].iloc[0]
    participacoes = res_remessa.rastro[res_remessa.rastro["metadata"] == "participacao_remessa"]
    assert sum(participacoes["valor"]) == nota_valor


def test_four_negative_operations_are_excluded(res_remessa):
    pend = res_remessa.pendencias
    negs = pend[pend["tipo"] == "SPREAD_NEGATIVO_CONTESTAR"]
    assert set(negs["ref_origem"]) == rules.PONTE_NEGATIVOS_EXCLUIR_SET2026
    # Nenhuma participação de comissão para esses negativos.
    assert not any(ref in rules.PONTE_NEGATIVOS_EXCLUIR_SET2026
                   for ref in res_remessa.rastro["ref_origem"]
                   if res_remessa.rastro.loc[res_remessa.rastro["ref_origem"] == ref,
                                             "metadata"].iloc[0] == "participacao_remessa")


def test_duplicata_pc0926_0162_dedup_sem_pendencia_conflito(res_remessa):
    """PC-0926-0162 aparece 2× com mesmos dados → fica 1× sem abrir conflito."""
    pend = res_remessa.pendencias
    assert "PC-0926-0162" not in set(pend["ref_origem"])
    # E a operação entra em participação exatamente 1 vez.
    parts = res_remessa.rastro[(res_remessa.rastro["ref_origem"] == "PC-0926-0162")
                                & (res_remessa.rastro["metadata"] == "participacao_remessa")]
    assert len(parts) == 1


# ---------------- EXTRATOS ----------------

def test_todos_os_lancamentos_classificados(res_extratos):
    lanc = res_extratos.lancamentos
    assert len(lanc) == 184
    assert lanc["conta_codigo"].notna().all()


def test_transferencia_30_09_fica_em_transito(res_extratos):
    pend = res_extratos.pendencias
    transito = pend[pend["tipo"] == "TRANSFERENCIA_EM_TRANSITO"]
    assert len(transito) == 1


def test_pix_sem_identificacao_fica_em_pendencia(res_extratos):
    pend = res_extratos.pendencias
    pix_nid = pend[pend["tipo"] == "PIX_NAO_IDENTIFICADO"]
    assert len(pix_nid) == 1


def test_devolucao_mundo_aberto_abre_pendencia(res_extratos):
    pend = res_extratos.pendencias
    dev = pend[pend["tipo"] == "DEVOLUCAO_LOJISTA_SEM_MOTIVO"]
    assert len(dev) == 1


def test_rastro_lancamentos_bate_em_centavos(res_extratos):
    from tarvo.output import check_rastro
    lanc = res_extratos.lancamentos.copy()
    rastro = res_extratos.rastro.copy()
    diff = check_rastro(lanc.assign(valor=lanc["valor"]), "valor", rastro)
    assert diff.empty


# ---------------- ORQUESTRADOR ----------------

def test_orquestrador_end_to_end_sem_problemas(tmp_path):
    """Rodada completa não deve gerar problema de rastro nem id duplicado."""
    from tarvo.orquestrador import run_closing
    r = run_closing(DATA, tmp_path, "2026-09")
    assert r.problemas_rastro.empty
    assert r.problemas_integridade == []
    # 6 arquivos escritos.
    arquivos = {p.name for p in r.out_dir.iterdir() if p.suffix == ".csv"}
    assert arquivos == {
        "comissoes_por_lojista.csv", "divergencias_taxa.csv", "notas_a_emitir.csv",
        "lancamentos_classificados.csv", "pendencias.csv", "rastro.csv",
    }


def test_reprocessamento_idempotente_mesma_execucao_cria_nova_linha(tmp_path):
    """Rodar 2x com mesmo input: ambas gravam execução; nenhuma decisão para reavaliar."""
    from tarvo.orquestrador import run_closing
    from tarvo.persistencia import listar_execucoes
    run_closing(DATA, tmp_path, "2026-09")
    run_closing(DATA, tmp_path, "2026-09")
    execs = listar_execucoes(tmp_path, "2026-09")
    assert len(execs) == 2


def test_decisao_marcada_reavaliar_quando_rules_mudam(tmp_path):
    """Se rules_version muda entre execuções, decisões viram 'precisa_reavaliar'."""
    from tarvo.orquestrador import run_closing
    from tarvo.persistencia import listar_decisoes, registrar_decisao, registrar_execucao
    run_closing(DATA, tmp_path, "2026-09")
    registrar_decisao(
        saida=tmp_path, competencia="2026-09", id_saida="CK-DIV-FAKE",
        tipo_pendencia="DIVERGENCIA_CHECKOUT", decisao="aceitar",
        autor="tester", hashes_atuais={}, rules_version="v1",
    )
    # Nova execução com rules_version diferente simula upgrade de regra.
    registrar_execucao(
        saida=tmp_path, competencia="2026-09", commit=None,
        hashes={}, rules_version="v2",
        contagens={}, duracoes_s={},
    )
    decisoes = listar_decisoes(tmp_path, "2026-09")
    assert len(decisoes) == 1
    assert decisoes[0]["precisa_reavaliar"] == 1
    assert "rules_version_mudou" in decisoes[0]["motivo_reavaliar"]
