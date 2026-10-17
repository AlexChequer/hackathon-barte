"""Download da saída pelo painel: os 6 CSVs do fechamento na tela, idênticos aos gravados."""

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tarvo.orquestrador import SAIDAS
from tarvo.web.api import criar_app

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"


@pytest.fixture(scope="module")
def painel(tmp_path_factory):
    saida = tmp_path_factory.mktemp("saida")
    cliente = TestClient(criar_app(dados=DATA, saida=saida))
    cliente.get("/api/fechamento")  # fecha o mês
    return cliente, saida


def test_zip_traz_os_6_csvs_iguais_aos_gravados(painel):
    cliente, saida = painel
    r = cliente.get("/api/saida.zip")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    assert 'filename="saida_2026-09.zip"' in r.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(r.content)) as pacote:
        assert sorted(pacote.namelist()) == sorted(SAIDAS)
        for nome in SAIDAS:
            assert pacote.read(nome) == (saida / nome).read_bytes()


@pytest.mark.parametrize("nome", SAIDAS)
def test_cada_csv_avulso_e_o_arquivo_gravado(painel, nome):
    cliente, saida = painel
    r = cliente.get(f"/api/saida/{nome}")
    assert r.status_code == 200 and r.content == (saida / nome).read_bytes()
    assert nome in r.headers["content-disposition"]


def test_so_baixa_arquivo_de_saida(painel):
    cliente, _ = painel
    assert cliente.get("/api/saida/rascunhos.json").status_code == 404
    fuga = cliente.get("/api/saida/..%2F..%2F.env")  # cai na página do painel, nunca no arquivo
    assert b"OPENAI_API_KEY" not in fuga.content and b"TARVO_CLASSIFICADOR" not in fuga.content
