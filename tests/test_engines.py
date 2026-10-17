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
# Fato do data pack de set/2026 (F2): as 4 operações com spread negativo.
NEGATIVOS_SET2026 = {"PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545"}


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


def test_atlas_vira_uma_pendencia_por_lojista_identificada_pelo_cnpj(res_checkout):
    """R3 + R24.1 + R30: 1 pendência para o Comercial, CNPJ da aba 2025 só como identidade."""
    atlas = res_checkout.pendencias[res_checkout.pendencias["tipo"] == "SEM_CONTRATO"]
    assert len(atlas) == 1
    linha = atlas.iloc[0]
    assert linha["id_saida"] == "CK-SEMCONTRATO-2026-09-39566044000119"
    assert linha["ref_origem"] == "39566044000119"
    assert linha["valor_brl"] == Decimal("7876.05")
    assert linha["quem_decide"] == "Comercial"
    assert "Atlas Idiomas Ltda" in linha["motivo"] and "1076801732" in linha["motivo"]
    rastro = res_checkout.rastro[res_checkout.rastro["id_saida"] == linha["id_saida"]]
    assert len(rastro) == 57
    assert sum(rastro["valor"]) == linha["valor_brl"]
    assert "39566044000119" not in set(res_checkout.comissoes["cnpj"])  # P24: não fatura
    assert "39566044000119" not in set(res_checkout.notas["tomador_cnpj"])


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
    assert set(negs["ref_origem"]) == NEGATIVOS_SET2026
    # Nenhuma participação de comissão para esses negativos.
    assert not any(ref in NEGATIVOS_SET2026
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


def test_ec_r3_resolvido_por_cnpj_mesmo_se_nome_mudar(sources):
    """R3: o de-para é EC → CNPJ. Renomear o lojista na planilha não pode quebrar o vínculo."""
    taxas = sources["taxas"].assign(lojista=lambda df: df["lojista"] + " (renomeado)")
    registry = ck.build_taxas_registry(taxas)
    for ec, cnpj in rules.EC_PARA_CNPJ.items():
        assert {e.cnpj for e in registry[ec]} == {cnpj}


def test_transferencia_sem_chegada_no_outro_banco_fica_em_transito_em_qualquer_data(sources):
    """Sem data fixa: a L92 fica em trânsito porque não tem TED de mesma titularidade no Meridiano."""
    aurora = sources["aurora"].assign(data=lambda df: df["data"].map(lambda d: d.replace(year=2027)))
    meridiano = sources["meridiano"].assign(data=lambda df: df["data"].map(lambda d: d.replace(year=2027)))
    res = ex.run(aurora, meridiano, sources["plano"], "2027-09")
    transito = res.pendencias[res.pendencias["tipo"] == "TRANSFERENCIA_EM_TRANSITO"]
    assert list(transito["ref_origem"]) == ["L92"]


def test_spread_negativo_fica_fora_em_qualquer_competencia(sources):
    """R5: spread negativo não é aceito. Não depende de lista fixa de ids nem do mês."""
    ponte = sources["ponte"].assign(
        data_contratacao=lambda df: df["data_contratacao"].map(
            lambda d: d.replace(year=2027) if d else d
        ),
    )
    res = rm.run(ponte, sources["taxas"], "2027-09")
    neg = res.pendencias[res.pendencias["tipo"] == "SPREAD_NEGATIVO_CONTESTAR"]
    assert len(neg) == 4
    assert set(neg["quem_decide"]) == {"Financeiro"}
    assert res.notas["valor_brl"].sum() == Decimal("39543.45")


def test_competencia_inferida_dos_dados(sources):
    from tarvo.orquestrador import inferir_competencia
    assert inferir_competencia(sources) == "2026-09"


# ---------------- ROBUSTEZ DE PIPELINE ----------------

def test_reversao_antecipacao_funciona_com_ordem_invertida(sources):
    """P13 + two-pass: a REVERSAO acha a comissão da ANTECIPACAO mesmo se vier antes dela."""
    orbe = sources["orbe"]
    tipos = set(orbe["tipo_lancamento"])
    assert {"ANTECIPACAO", "REVERSAO ANTECIPACAO"} <= tipos
    orig = ck.run(orbe, sources["taxas"], "2026-09")
    invertida = orbe.iloc[::-1].reset_index(drop=True)
    inv = ck.run(invertida, sources["taxas"], "2026-09")
    # Soma de comissões por CNPJ não pode variar com a ordem.
    orig_sum = orig.comissoes.set_index("cnpj")["comissao_brl"].to_dict()
    inv_sum = inv.comissoes.set_index("cnpj")["comissao_brl"].to_dict()
    assert orig_sum == inv_sum
    rev_sem_ref = inv.pendencias[inv.pendencias["tipo"] == "REVERSAO_SEM_REFERENCIA"]
    assert rev_sem_ref.empty  # com two-pass, não tem mais pendência de ordem


def test_transacao_duplicada_na_orbe_vai_contar_uma_vez(sources):
    """R24.1: id_transacao repetido com mesmos dados financeiros não dobra a comissão."""
    orbe = sources["orbe"]
    # Pega uma linha de venda simples e duplica.
    original = orbe[orbe["tipo_lancamento"] == "VENDA"].iloc[0]
    duplicada = original.copy()
    duplicada["linha_origem"] = int(orbe["linha_origem"].max()) + 1
    import pandas as pd
    orbe_dup = pd.concat([orbe, duplicada.to_frame().T], ignore_index=True)
    res_orig = ck.run(orbe, sources["taxas"], "2026-09")
    res_dup = ck.run(orbe_dup, sources["taxas"], "2026-09")
    cnpj_alvo = res_orig.comissoes.set_index("cnpj")["comissao_brl"].to_dict()
    cnpj_dup = res_dup.comissoes.set_index("cnpj")["comissao_brl"].to_dict()
    assert cnpj_alvo == cnpj_dup
    # Nenhuma pendência de conflito porque os dados são idênticos.
    assert "DUPLICATA_CONFLITANTE" not in set(res_dup.pendencias.get("tipo", []))


def test_transacao_fora_da_competencia_vai_para_pendencia(sources):
    """Linha com data_movimento fora da competência não entra na apuração."""
    import datetime as dt
    orbe = sources["orbe"].copy()
    linha = orbe[orbe["tipo_lancamento"] == "VENDA"].iloc[0].copy()
    linha["id_transacao"] = "TX-FORA-9999"
    linha["data_movimento"] = dt.date(2026, 8, 15)
    linha["linha_origem"] = int(orbe["linha_origem"].max()) + 1
    import pandas as pd
    orbe_fora = pd.concat([orbe, linha.to_frame().T], ignore_index=True)
    res = ck.run(orbe_fora, sources["taxas"], "2026-09")
    fora = res.pendencias[res.pendencias["tipo"] == "FORA_COMPETENCIA"]
    assert "TX-FORA-9999" in set(fora["ref_origem"])


def test_remessa_spread_ausente_vira_pendencia(sources):
    """Operação sem spread R$ não some em silêncio: abre pendência SPREAD_AUSENTE."""
    ponte = sources["ponte"].copy()
    alvo = ponte.index[0]
    ponte.at[alvo, "spread_brl"] = None
    res = rm.run(ponte, sources["taxas"], "2026-09")
    ausente = res.pendencias[res.pendencias["tipo"] == "SPREAD_AUSENTE"]
    assert len(ausente) == 1
    assert ausente["quem_decide"].iloc[0] == "Financeiro"  # R11, R12: Helena decide


def test_remessa_agrupa_por_cnpj_mesmo_com_nome_variando(sources):
    """Mesma empresa com variação do nome entre linhas: 1 linha de comissão por CNPJ."""
    ponte = sources["ponte"].copy()
    alvo = ponte[ponte["cnpj"] == ponte["cnpj"].mode().iloc[0]]
    assert len(alvo) >= 2
    # Força variação do nome mantendo o CNPJ.
    ponte.loc[alvo.index[:1], "cliente"] = ponte.loc[alvo.index[0], "cliente"] + " ME"
    res = rm.run(ponte, sources["taxas"], "2026-09")
    comissoes_cnpj = res.comissoes["cnpj"].value_counts()
    assert (comissoes_cnpj == 1).all()


def test_cobertura_entradas_detecta_input_sem_saida(tmp_path):
    """validate_cobertura_entradas: ref de entrada que não foi tocada por nenhuma saída é problema."""
    from tarvo.output import validate_cobertura_entradas
    rastro = __import__("pandas").DataFrame([
        {"id_saida": "X1", "arquivo_origem": "orbe", "ref_origem": "TX1", "valor": Decimal("1")},
    ])
    problemas = validate_cobertura_entradas({"orbe": {"TX1", "TX2"}}, rastro)
    assert any(p["codigo"] == "INPUT_SEM_SAIDA" and "TX2" in p["refs"] for p in problemas)


def test_repasse_da_ponte_de_mes_anterior_baixa_recebivel_em_qualquer_mes():
    """R6/R9: repasse de comissão de mês anterior baixa o recebível; não depende de '08/2026' fixo."""
    import datetime as dt

    import pandas as pd
    row = pd.Series({"descricao": "TED RECEB PONTE CAMBIO SA REPASSE COMISSAO 09/2026",
                     "data": dt.date(2026, 10, 6), "valor": Decimal("39543.45")})
    assert ex._classifica_meridiano(row)["conta_codigo"] == rules.CONTA_BAIXA_PASSIVO["repasse_ponte"]
