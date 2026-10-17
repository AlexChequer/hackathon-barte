"""R34: parceiro muda o layout sem avisar. A solução avisa o que quebrou (arquivo, coluna esperada,
colunas encontradas) e fecha o que não depende daquele arquivo. Arquivos sintéticos derivados dos reais."""

from pathlib import Path

import openpyxl
import pytest

from tarvo.loaders.layout import LayoutInvalido
from tarvo.loaders.orbe import load_orbe
from tarvo.orquestrador import run_closing

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"


def _copia(tmp_path: Path) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    for f in DATA.iterdir():
        (pasta / f.name).write_bytes(f.read_bytes())
    return pasta


def _trocar_texto(arquivo: Path, de: str, para: str, encoding: str = "utf-8") -> None:
    texto = arquivo.read_text(encoding=encoding)
    assert de in texto
    arquivo.write_text(texto.replace(de, para, 1), encoding=encoding)


def _bloqueio(r, frente):
    return next(b for b in r.bloqueios if b["frente"] == frente)


def test_loader_diz_coluna_que_falta_e_as_que_vieram(tmp_path):
    pasta = _copia(tmp_path)
    orbe = next(pasta.glob("01_*"))
    _trocar_texto(orbe, "valor_bruto", "vlr_bruto")
    with pytest.raises(LayoutInvalido) as erro:
        load_orbe(orbe)
    msg = str(erro.value)
    assert "valor_bruto" in msg and "vlr_bruto" in msg and orbe.name in msg


def test_orbe_com_coluna_renomeada_bloqueia_checkout_e_fecha_o_resto(tmp_path):
    pasta = _copia(tmp_path)
    _trocar_texto(next(pasta.glob("01_*")), "valor_bruto", "vlr_bruto")
    r = run_closing(pasta, tmp_path / "saida")
    assert not r.problemas_integridade
    assert "valor_bruto" in _bloqueio(r, "checkout")["motivo_layout"]
    assert (r.comissoes["linha_negocio"] == "REMESSA").any() and len(r.lancamentos) == 184
    pend = r.pendencias[r.pendencias["tipo"] == "FRENTE_BLOQUEADA"]
    assert pend["motivo"].str.contains("vlr_bruto").any()


def test_planilha_de_taxas_com_cabecalho_trocado_bloqueia_checkout_e_remessa(tmp_path):
    pasta = _copia(tmp_path)
    arquivo = next(pasta.glob("02_*"))
    wb = openpyxl.load_workbook(arquivo)
    ws = wb["Taxas vigentes"]
    celula = next(c for c in ws[5] if c.value == "Débito")
    celula.value = "Taxa débito"
    wb.save(arquivo)
    r = run_closing(pasta, tmp_path / "saida")
    assert {b["frente"] for b in r.bloqueios} == {"checkout", "remessa"}
    assert "Débito" in _bloqueio(r, "checkout")["motivo_layout"]
    assert len(r.lancamentos) == 184


def test_extrato_aurora_com_cabecalho_trocado_fecha_so_o_meridiano(tmp_path):
    pasta = _copia(tmp_path)
    _trocar_texto(next(pasta.glob("05a_*")), "Valor (R$)", "Valor")
    r = run_closing(pasta, tmp_path / "saida")
    assert set(r.lancamentos["banco"]) == {"MERIDIANO"}
    assert "Valor (R$)" in _bloqueio(r, "extratos")["motivo_layout"]


def test_ofx_sem_transacoes_e_layout_invalido(tmp_path):
    pasta = _copia(tmp_path)
    ofx = next(pasta.glob("05b_*"))
    ofx.write_text(ofx.read_text(encoding="cp1252").replace("STMTTRN", "TRANSACAO"), encoding="cp1252")
    r = run_closing(pasta, tmp_path / "saida")
    assert set(r.lancamentos["banco"]) == {"AURORA"}
    assert "STMTTRN" in _bloqueio(r, "extratos")["motivo_layout"]
