"""Outubro SINTÉTICO de ponta a ponta (O1: roda no mês seguinte sem mexer no código).

O pacote é gerado a partir de setembro em pasta temporária (tests/sinteticos/outubro.py).
Cada teste afirma um comportamento esperado pelas respostas do financeiro."""

from decimal import Decimal

import pytest
from tests.sinteticos.outubro import AJUSTE_REF, CNPJ_MAPLE, EC_NOVO, gerar_outubro

from tarvo.orquestrador import run_closing

CASA, ROTA, BRIDGE, ATLAS = "00520815000100", "95927868000148", "22224579000109", "39566044000119"


@pytest.fixture(scope="module")
def outubro(tmp_path_factory):
    base = tmp_path_factory.mktemp("outubro")
    return run_closing(gerar_outubro(base / "dados"), base / "saida")


def _pend(r, tipo):
    return r.pendencias[r.pendencias["tipo"] == tipo]


def test_fecha_outubro_inteiro_sem_mexer_no_codigo(outubro):
    assert outubro.competencia == "2026-10"
    assert not outubro.problemas_integridade and outubro.problemas_rastro.empty
    assert outubro.bloqueios == []
    assert len(outubro.lancamentos) == 184


def test_casa_continua_isenta_e_o_estorno_de_setembro_tambem(outubro):
    """R6 (set→dez) + R2: o estorno agora é de venda de setembro, já isenta: sem nota negativa."""
    assert not _pend(outubro, "CONDICAO_NAO_INFORMADA_ORBE").empty
    assert _pend(outubro, "NOTA_NEGATIVA").empty
    casa = outubro.comissoes[outubro.comissoes["cnpj"] == CASA]
    assert casa["comissao_brl"].iloc[0] == Decimal("0.00")
    assert CASA not in set(outubro.notas["tomador_cnpj"])


def test_contestacao_com_a_orbe_segue_para_rota_e_bridge(outubro):
    assert set(_pend(outubro, "CONTESTACAO_ORBE")["ref_origem"]) == {ROTA, BRIDGE}


def test_atlas_continua_sem_contrato_e_com_alerta(outubro):
    assert list(_pend(outubro, "SEM_CONTRATO")["ref_origem"]) == [ATLAS]
    assert list(_pend(outubro, "ALERTA_ANTECIPACAO")["ref_origem"]) == [ATLAS]


def test_lojista_novo_vira_pendencia_do_comercial_e_nao_fatura(outubro):
    novos = _pend(outubro, "EC_NAO_CADASTRADO")
    assert len(novos) == 3 and set(novos["quem_decide"]) == {"Comercial"}
    assert novos["motivo"].str.contains(EC_NOVO).all()


def test_anotacao_nova_na_planilha_pede_confirmacao_ao_comercial(outubro):
    sinal = _pend(outubro, "CONDICAO_ESPECIAL_A_CONFIRMAR")
    assert len(sinal) == 1 and CNPJ_MAPLE in sinal["id_saida"].iloc[0]


def test_repasse_da_ponte_do_mes_anterior_baixa_o_recebivel(outubro):
    lanc = outubro.lancamentos
    repasse = lanc[lanc["descricao"].str.contains("REPASSE COMISSAO 09/2026", na=False)]
    assert list(repasse["conta_codigo"]) == ["1.1.03.002"]


def test_transferencia_sem_chegada_continua_em_transito(outubro):
    assert list(_pend(outubro, "TRANSFERENCIA_EM_TRANSITO")["ref_origem"]) == ["L92"]


def test_ajuste_de_contestacao_da_ponte_abate_a_comissao_do_mes(outubro):
    """R27: linha nova com Spread R$ negativo e obs 'AJUSTE REF PC-…' entra na comissão do mês,
    dentro da nota única para a Ponte, com o rastro apontando a operação original."""
    negativos = _pend(outubro, "SPREAD_NEGATIVO_CONTESTAR")
    assert "PC-1026-9001" not in set(negativos["ref_origem"])
    rastro = outubro.rastro
    assert ((rastro["ref_origem"] == "PC-1026-9001") & (rastro["metadata"].str.contains(AJUSTE_REF))).any()
    # P31: spread do ajuste vem cheio (devolução ao lojista); sai a nossa metade, na comissão e na nota (R10).
    do_ajuste = rastro[rastro["ref_origem"] == "PC-1026-9001"].set_index("id_saida")["valor"]
    assert set(do_ajuste.index) == {"RM-CM-2026-10-17217888000111", "RM-NT-2026-10-PONTE"}
    assert set(do_ajuste) == {Decimal("-14.78")}
    assert outubro.divergencias[outubro.divergencias["ref_origem"] == "PC-1026-9001"].empty
    assert outubro.controle["ponte"]["fecha"]
