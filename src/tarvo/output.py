"""Escrita dos arquivos de saida/ no formato fixo exigido pelo case.

CSV com ';', ponto decimal, datas AAAA-MM-DD, CNPJ só dígitos (14).
Valida igualdade exata (centavos) entre o valor da saída e a soma do rastro.
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
    if value is None:
        return ""
    return value


def write_output(df: pd.DataFrame, filename: str, out_dir: Path) -> Path:
    """Valida colunas obrigatórias e escreve. Colunas extras ficam depois das obrigatórias."""
    required = SCHEMAS[filename]
    if df.empty:
        formatted = pd.DataFrame(columns=required)
    else:
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"{filename}: faltam colunas obrigatórias {missing}")
        extras = [c for c in df.columns if c not in required]
        formatted = df[required + extras].map(_fmt)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / filename
    formatted.to_csv(target, sep=";", index=False, encoding="utf-8")
    return target


def check_rastro(reported: pd.DataFrame, value_col: str, rastro: pd.DataFrame) -> pd.DataFrame:
    """Linhas de saída cuja soma do rastro não bate em centavos exatos.

    Rejeita diferenças de 0.01 e saídas sem origem (inclusive quando valor = 0).
    Reporta também id_saida inexistente no rastro.
    """
    if reported.empty:
        return reported
    sums = rastro.groupby("id_saida")["valor"].apply(lambda s: sum(s, Decimal(0)))
    merged = reported.assign(soma_rastro=reported["id_saida"].map(sums))
    merged["tem_rastro"] = reported["id_saida"].isin(set(rastro["id_saida"].unique()))
    merged["esperado"] = reported[value_col].apply(lambda v: v if isinstance(v, Decimal) else Decimal(str(v)))
    merged["bate"] = merged.apply(
        lambda r: r["tem_rastro"] and r["soma_rastro"] == r["esperado"], axis=1
    )
    return merged[~merged["bate"]]


def validate_rastro_integrity(rastro: pd.DataFrame, all_outputs_ids: set[str]) -> list[dict]:
    """Checagens globais do rastro:
    - id_saida em rastro deve existir em alguma saída.
    - Várias linhas de rastro com o mesmo id_saida são permitidas, mas rastro em id inexistente é erro.
    """
    problemas: list[dict] = []
    if rastro.empty:
        return problemas
    rastro_ids = set(rastro["id_saida"].unique())
    orfaos = rastro_ids - all_outputs_ids
    if orfaos:
        problemas.append({"codigo": "RASTRO_ORFAO", "ids": sorted(orfaos)})
    return problemas


def validate_cobertura_entradas(
    entradas: dict[str, set[str]], rastro: pd.DataFrame
) -> list[dict]:
    """Para cada ref_origem de cada arquivo de entrada, confirma que ela aparece em alguma linha
    de saída via rastro. Caso contrário é dado perdido: INPUT_SEM_SAIDA.

    `entradas` é um dict `{arquivo_origem: set[ref_origem]}` com as refs que o fechamento se
    comprometeu a tocar (ex.: todas as transações Orbe, todas as operações da Ponte).
    """
    problemas: list[dict] = []
    if not entradas:
        return problemas
    if rastro.empty:
        cobertos: dict[str, set[str]] = {k: set() for k in entradas}
    else:
        cobertos = {
            arq: set(rastro.loc[rastro["arquivo_origem"] == arq, "ref_origem"].astype(str).unique())
            for arq in entradas
        }
    for arq, esperadas in entradas.items():
        esperadas_str = {str(r) for r in esperadas}
        faltantes = sorted(esperadas_str - cobertos.get(arq, set()))
        if faltantes:
            problemas.append({"codigo": "INPUT_SEM_SAIDA", "arquivo_origem": arq, "refs": faltantes})
    return problemas
