"""API do painel (tarvo.web): fina sobre o orquestrador e sobre config/condicoes_comerciais.json."""

import json
import shutil
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tarvo import condicoes
from tarvo.web.api import criar_app

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "raw" / "set2026"


@pytest.fixture()
def config(tmp_path):
    destino = tmp_path / "condicoes_comerciais.json"
    shutil.copy(condicoes.CAMINHO_PADRAO, destino)
    return destino


@pytest.fixture()
def cliente(tmp_path, config):
    return TestClient(criar_app(dados=DATA, saida=tmp_path / "saida", condicoes_path=config))


def test_registrar_condicao_valida_grava_e_gera_id(config):
    nova = condicoes.registrar_condicao(config, {
        "cnpj": "95927868000148", "taxas": {"credito_vista": "0.0199"},
        "inicio": "2026-10-01", "fim": "2026-12-31", "descricao": "promo",
        "fonte": "pendência TX-SINAL", "aprovado_por": "Comercial", "registrado_por": "Helena",
    })
    assert nova["id"] == "COND-0002"
    salvas = condicoes.carregar(config)
    assert [c.id for c in salvas] == ["COND-0001", "COND-0002"]
    assert salvas[1].taxas["credito_vista"] == Decimal("0.0199")


@pytest.mark.parametrize("ruim, erro", [
    ({"cnpj": "123"}, "CNPJ"),
    ({"taxas": {}}, "taxa"),
    ({"taxas": {"credito_vista": "1.5"}}, "entre 0"),
    ({"taxas": {"boleto": "0"}}, "modalidade"),
    ({"inicio": "2026-12-31", "fim": "2026-10-01"}, "fim"),
    ({"aprovado_por": ""}, "aprovou"),
])
def test_registrar_condicao_invalida_nao_grava(config, ruim, erro):
    base = {"cnpj": "95927868000148", "taxas": {"credito_vista": "0.0199"}, "inicio": "2026-10-01",
            "fim": "2026-12-31", "fonte": "x", "aprovado_por": "Comercial"}
    antes = config.read_text()
    with pytest.raises(ValueError, match=erro):
        condicoes.registrar_condicao(config, {**base, **ruim})
    assert config.read_text() == antes


def test_api_fechamento_traz_tabelas_e_validacoes(cliente):
    r = cliente.get("/api/fechamento")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["competencia"] == "2026-09"
    assert corpo["validacoes"]["rastro_ok"] and corpo["validacoes"]["integridade_ok"]
    assert len(corpo["tabelas"]["pendencias"]) == 14
    assert corpo["totais"]["comissao_checkout"] == "203735.34"


def test_api_rastro_soma_o_valor_do_numero(cliente):
    cliente.get("/api/fechamento")
    r = cliente.get("/api/rastro/CK-CONTEST-2026-09-95927868000148").json()
    assert sum(Decimal(linha["valor"]) for linha in r["linhas"]) == Decimal("1546.28")


def test_api_registrar_condicao_e_refechar(cliente, config):
    r = cliente.post("/api/condicoes", json={
        "cnpj": "95927868000148", "taxas": {"credito_vista": "0.0299"}, "inicio": "2026-09-01",
        "fim": "2026-12-31", "fonte": "teste", "aprovado_por": "Comercial", "registrado_por": "Helena",
    })
    assert r.status_code == 201, r.text
    assert json.loads(config.read_text())["condicoes"][-1]["cnpj"] == "95927868000148"
    assert cliente.post("/api/condicoes", json={"cnpj": "1"}).status_code == 422


def test_api_lista_os_arquivos_esperados(cliente):
    esperados = cliente.get("/api/arquivos-esperados").json()
    obrigatorios = [a for a in esperados if a["obrigatorio"]]
    assert len(obrigatorios) == 6
    assert any(not a["obrigatorio"] and "ajustes" in a["padrao"] for a in esperados)


def _arquivos(nomes):
    return [("arquivos", (DATA.joinpath(n).name, DATA.joinpath(n).read_bytes())) for n in nomes]


def test_upload_sem_um_obrigatorio_e_recusado_com_o_nome_que_falta(cliente):
    nomes = [f.name for f in DATA.iterdir() if not f.name.startswith(("03_", "00_"))]
    r = cliente.post("/api/arquivos", files=_arquivos(nomes))
    assert r.status_code == 422
    assert "Ponte" in r.json()["detail"] and "faltando" in r.json()["detail"]


def test_upload_com_obrigatorio_duplicado_e_recusado(cliente):
    nomes = [f.name for f in DATA.iterdir() if not f.name.startswith("00_")]
    arquivos = _arquivos(nomes) + [("arquivos", ("01_orbe_relatorio_comissoes_out2026.csv", b"x"))]
    r = cliente.post("/api/arquivos", files=arquivos)
    assert r.status_code == 422 and "mais de um" in r.json()["detail"]


def test_upload_completo_fecha_o_mes(cliente):
    nomes = [f.name for f in DATA.iterdir() if not f.name.startswith("00_")]
    r = cliente.post("/api/arquivos", files=_arquivos(nomes))
    assert r.status_code == 200, r.text
    assert r.json()["totais"]["comissao_checkout"] == "203735.34"
