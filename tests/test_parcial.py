"""R34: arquivo faltando não segura o mês. Fecha o que não depende dele e marca o que ficou bloqueado."""

from decimal import Decimal
from pathlib import Path

import pytest

from tarvo import frentes
from tarvo.loaders.identificar import classificar_lote
from tarvo.orquestrador import run_closing

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"


def _sem(tmp_path: Path, *prefixos: str) -> Path:
    pasta = tmp_path / "dados"
    pasta.mkdir()
    for f in DATA.iterdir():
        if not f.name.startswith(prefixos):
            (pasta / f.name).write_bytes(f.read_bytes())
    return pasta


def _bloqueios(r):
    return r.pendencias[r.pendencias["tipo"] == "FRENTE_BLOQUEADA"]


def test_sem_ponte_fecha_checkout_e_extratos_e_bloqueia_remessa(tmp_path):
    r = run_closing(_sem(tmp_path, "03_"), tmp_path / "saida")
    assert not r.problemas_integridade and r.problemas_rastro.empty
    ck = r.comissoes[r.comissoes["linha_negocio"] == "CHECKOUT"]
    assert sum(ck["comissao_brl"]) == Decimal("203735.34")
    assert (r.comissoes["linha_negocio"] == "REMESSA").sum() == 0
    assert len(r.lancamentos) == 184
    assert [b["frente"] for b in r.bloqueios] == ["remessa"]
    bloq = _bloqueios(r)
    assert len(bloq) == 1 and "Ponte" in bloq.iloc[0]["motivo"]


def test_sem_meridiano_classifica_aurora_sem_inventar_transito(tmp_path):
    r = run_closing(_sem(tmp_path, "05b"), tmp_path / "saida")
    assert not r.problemas_integridade
    assert set(r.lancamentos["banco"]) == {"AURORA"} and len(r.lancamentos) == 84
    assert (r.pendencias["tipo"] == "TRANSFERENCIA_EM_TRANSITO").sum() == 0
    assert any(b["frente"] == "extratos" for b in r.bloqueios)


def test_sem_taxas_bloqueia_checkout_e_remessa_mas_classifica_extratos(tmp_path):
    r = run_closing(_sem(tmp_path, "02_"), tmp_path / "saida")
    assert r.comissoes.empty and r.notas.empty
    assert len(r.lancamentos) == 184
    assert {b["frente"] for b in r.bloqueios} == {"checkout", "remessa"}


def test_lote_sem_ponte_e_aceito_com_aviso_do_que_nao_sai():
    lote = [(f.name, f.read_bytes()) for f in DATA.iterdir() if not f.name.startswith(("03_", "00_"))]
    c = classificar_lote(lote)
    assert c["problemas"] == []
    assert [b["frente"] for b in c["bloqueios"]] == ["remessa"]


def test_lote_que_nao_fecha_nada_e_recusado():
    plano = "04_plano_de_contas_fenix_erp.csv"
    c = classificar_lote([(plano, (DATA / plano).read_bytes())])
    assert any("nenhuma parte" in p for p in c["problemas"])


@pytest.mark.parametrize("presentes, bloqueadas", [
    ({"orbe", "taxas", "ponte", "plano", "aurora", "meridiano"}, []),
    ({"orbe", "taxas", "plano", "aurora"}, ["remessa", "extratos"]),
])
def test_mapa_de_dependencias(presentes, bloqueadas):
    assert [b["frente"] for b in frentes.bloqueios(presentes)] == bloqueadas
