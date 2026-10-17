"""Detector de sinais de condição especial na planilha (obs + comentários de célula)."""

from pathlib import Path

import pytest

from tarvo import condicoes, sinais
from tarvo.loaders import load_all

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
CASA_CNPJ = "00520815000100"


class ClassificadorFalso:
    """Responde sim para textos da lista; registra o que recebeu."""

    nome = "falso"

    def __init__(self, positivos: set[str]):
        self.positivos = positivos
        self.recebidos: list[str] = []

    def relevantes(self, textos: list[str]) -> list[bool]:
        self.recebidos.extend(textos)
        return [t in self.positivos for t in textos]


@pytest.fixture(scope="module")
def taxas():
    return load_all(DATA)["taxas"]


def test_extrai_obs_e_comentarios_com_linha_da_planilha(taxas):
    extraidos = sinais.extrair(taxas)
    casa = [s for s in extraidos if s.cnpj == CASA_CNPJ]
    assert {s.campo for s in casa} == {"obs", "comentario"}
    assert {s.linha for s in casa} == {13}


def test_palavra_chave_pega_condicao_especial_mesmo_sem_modelo(taxas):
    marcados = sinais.detectar(sinais.extrair(taxas), classificador=None)
    casa = [m for m in marcados if m.sinal.cnpj == CASA_CNPJ]
    assert casa and all(m.metodo == "REGRA" for m in casa)
    assert not [m for m in marcados if m.sinal.texto == "EC pendente"]


def test_uniao_regra_e_modelo(taxas):
    clf = ClassificadorFalso({"só mudou o crédito à vista"})
    marcados = {m.sinal.texto: m.metodo for m in sinais.detectar(sinais.extrair(taxas), clf)}
    assert marcados["só mudou o crédito à vista"] == "MODELO"
    assert marcados["conversar com Diego (comercial) sobre condição especial"] == "REGRA"


def test_sinal_coberto_por_condicao_ou_resolvido_nao_vira_pendencia(taxas):
    res = sinais.run(taxas, "2026-09", classificador=None)
    assert res.pendencias.empty  # Casa coberta por COND-0001; Bridge/Mundo Aberto resolvidos no arquivo


def test_sem_registro_vira_pendencia_para_o_comercial(taxas):
    res = sinais.run(taxas, "2026-09", classificador=None, condicoes=(), resolvidos=())
    pend = res.pendencias
    assert set(pend["tipo"]) == {"CONDICAO_ESPECIAL_A_CONFIRMAR"}
    assert set(pend["quem_decide"]) == {"Comercial"}
    assert CASA_CNPJ in " ".join(pend["motivo"])
    assert (pend["valor_brl"] == 0).all()
    assert set(res.rastro["id_saida"]) == set(pend["id_saida"])


def test_resolvidos_carregados_do_arquivo():
    resolvidos = condicoes.carregar_sinais_resolvidos()
    assert any(r.cnpj == "22224579000109" for r in resolvidos)  # Bridge: renegociação já na planilha
