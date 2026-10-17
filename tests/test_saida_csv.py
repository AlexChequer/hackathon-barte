"""Os CSVs de saída são lidos por quem divide por ';' sem tratar aspas.

Nenhum campo pode conter ';', '\\n' ou '\\r', e toda linha tem o mesmo número de campos.
"""

import csv
from pathlib import Path

import pytest

from tarvo.orquestrador import run_closing

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"


@pytest.fixture(scope="module")
def latest(tmp_path_factory):
    saida = tmp_path_factory.mktemp("saida")
    run_closing(DATA, saida, "2026-09")
    return saida / "2026-09" / "latest"


def _csvs(latest: Path) -> list[Path]:
    arquivos = sorted(latest.glob("*.csv"))
    assert {p.name for p in arquivos} >= {
        "comissoes_por_lojista.csv", "divergencias_taxa.csv", "notas_a_emitir.csv",
        "lancamentos_classificados.csv", "pendencias.csv", "rastro.csv",
    }
    return arquivos


def test_toda_linha_tem_o_mesmo_numero_de_campos(latest):
    for arquivo in _csvs(latest):
        with open(arquivo, newline="", encoding="utf-8") as f:
            tamanhos = {len(linha) for linha in csv.reader(f, delimiter=";")}
        assert len(tamanhos) == 1, f"{arquivo.name}: linhas com {sorted(tamanhos)} campos"


def test_nenhum_campo_contem_separador_ou_quebra_de_linha(latest):
    for arquivo in _csvs(latest):
        with open(arquivo, newline="", encoding="utf-8") as f:
            ruins = [(n, campo) for n, linha in enumerate(csv.reader(f, delimiter=";"), 1)
                     for campo in linha if any(c in campo for c in ";\n\r")]
        assert not ruins, f"{arquivo.name}: {len(ruins)} campos com ';' ou quebra, ex.: {ruins[:2]}"


def test_split_ingenuo_por_ponto_e_virgula_le_as_mesmas_colunas(latest):
    for arquivo in _csvs(latest):
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
        cabecalho = len(linhas[0].split(";"))
        assert all(len(linha.split(";")) == cabecalho for linha in linhas), arquivo.name
