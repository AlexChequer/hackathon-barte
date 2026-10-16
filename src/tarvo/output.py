"""Escrita dos arquivos de saida/ no formato fixo exigido pelo case (correção automática).

CSV com ';', ponto decimal, datas AAAA-MM-DD, CNPJ só dígitos (14).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from pathlib import Path

import pandas as pd

SCHEMAS: dict[str, list[str]] = {
    "comissoes_por_lojista.csv": ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl"],
    "divergencias_taxa.csv": ["id_saida", "cnpj", "linha_negocio", "ref_origem",
                              "taxa_contratada_pct", "taxa_aplicada_pct", "diferenca_brl"],
    "notas_a_emitir.csv": ["id_saida", "tomador_cnpj", "tomador", "linha_negocio", "valor_brl",
                           "discriminacao"],
    "lancamentos_classificados.csv": ["id_saida", "banco", "ref_origem", "data", "descricao", "valor",
                                      "conta_codigo", "metodo", "confianca"],
    "pendencias.csv": ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"],
    "rastro.csv": ["id_saida", "arquivo_origem", "ref_origem", "valor"],
}
LINHAS_NEGOCIO = {"CHECKOUT", "REMESSA"}
BANCOS = {"AURORA", "MERIDIANO"}
METODOS = {"REGRA", "IA", "HUMANO"}


def _fmt(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m-%d")
    return value


def write_output(df: pd.DataFrame, filename: str, out_dir: Path) -> Path:
    """Valida colunas obrigatórias e escreve. Colunas extras são mantidas depois das obrigatórias."""
    required = SCHEMAS[filename]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{filename}: faltam colunas obrigatórias {missing}")
    extras = [c for c in df.columns if c not in required]
    formatted = df[required + extras].map(_fmt)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / filename
    formatted.to_csv(target, sep=";", index=False, encoding="utf-8")
    return target


def check_rastro(reported: pd.DataFrame, value_col: str, rastro: pd.DataFrame,
                 tolerance: Decimal = Decimal("0.01")) -> pd.DataFrame:
    """Linhas de saída cujo valor não bate com a soma do rastro (deveria vir vazio)."""
    sums = rastro.groupby("id_saida")["valor"].apply(lambda s: sum(s, Decimal(0)))
    merged = reported.assign(soma_rastro=reported["id_saida"].map(sums))
    gap = (merged[value_col] - merged["soma_rastro"].fillna(Decimal(0))).abs()
    return merged[gap > tolerance]
