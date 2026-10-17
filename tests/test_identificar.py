"""Reconhecer os arquivos do mês pelo nome (padrão) ou, se o nome não bater, pelo conteúdo."""

from pathlib import Path

import pytest

from tarvo.loaders.identificar import classificar_lote, identificar

DATA = Path(__file__).resolve().parents[1] / "data" / "raw" / "set2026"
RENOMEADOS = {
    "01_orbe_relatorio_comissoes_set2026.csv": ("Relatorio Orbe Outubro.csv", "orbe"),
    "02_tabela_taxas_contratadas.xlsx": ("taxas (1).xlsx", "taxas"),
    "03_email_ponte_cambio_relatorio_set2026.eml": ("Fwd_ relatorio ponte.eml", "ponte"),
    "04_plano_de_contas_fenix_erp.csv": ("plano.csv", "plano"),
    "05a_extrato_banco_aurora_cc4471_set2026.csv": ("extrato aurora.csv", "aurora"),
    "05b_extrato_banco_meridiano_cc90233_set2026.ofx": ("meridiano.ofx", "meridiano"),
}


@pytest.mark.parametrize("original, renomeado, chave", [(o, r, c) for o, (r, c) in RENOMEADOS.items()])
def test_reconhece_pelo_conteudo_quando_o_nome_nao_bate(original, renomeado, chave):
    achado = identificar(renomeado, (DATA / original).read_bytes())
    assert achado == (chave, "conteudo")


def test_nome_padrao_continua_valendo_e_ajustes_so_pelo_nome():
    assert identificar("01_orbe_relatorio_comissoes_out2026.csv", b"x") == ("orbe", "nome")
    ajustes = (DATA / "06_orbe_ajustes_tardios_set2026.csv").read_bytes()
    assert identificar("06_orbe_ajustes_tardios_set2026.csv", ajustes) == ("orbe_ajustes", "nome")


def test_lote_renomeado_completo_vira_nomes_canonicos():
    lote = [(r, (DATA / o).read_bytes()) for o, (r, _) in RENOMEADOS.items()]
    resultado = classificar_lote(lote)
    assert resultado["problemas"] == []
    canonicos = {item["nome_canonico"] for item in resultado["arquivos"]}
    assert "01_orbe_relatorio_comissoes_enviado.csv" in canonicos


def test_lote_com_arquivo_estranho_e_faltando_aponta_os_dois():
    lote = [(r, (DATA / o).read_bytes()) for o, (r, _) in RENOMEADOS.items() if not o.startswith("03_")]
    lote.append(("foto.png", b"\x89PNG..."))
    problemas = " ".join(classificar_lote(lote)["problemas"])
    assert "foto.png" in problemas and "Ponte" in problemas


def test_dois_relatorios_da_orbe_sem_nome_padrao_e_ambiguo():
    orbe = (DATA / "01_orbe_relatorio_comissoes_set2026.csv").read_bytes()
    lote = [(r, (DATA / o).read_bytes()) for o, (r, _) in RENOMEADOS.items()] + [("outro orbe.csv", orbe)]
    assert any("mais de um" in p for p in classificar_lote(lote)["problemas"])
