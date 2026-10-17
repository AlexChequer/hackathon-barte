"""01 - Relatório de comissões da adquirente Orbe (CSV ; com decimal vírgula)."""

from pathlib import Path

import pandas as pd

from tarvo import parse
from tarvo.loaders.layout import exigir

MONEY_COLS = ["valor_bruto", "valor_taxa", "valor_liquido"]
HEADER_LINES = 1
COLUNAS = ["id_transacao", "data_movimento", "cod_estabelecimento", "nome_estabelecimento", "tipo_lancamento",
           "modalidade", "qtd_parcelas", "valor_bruto", "taxa_aplicada_pct", "valor_taxa", "valor_liquido",
           "id_referencia", "data_venda_original"]


def load_orbe(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, sep=";", dtype=str, keep_default_na=False, encoding="utf-8")
    exigir(path, raw.columns, COLUNAS)
    return raw.assign(
        linha_origem=raw.index + HEADER_LINES + 1,
        data_movimento=raw["data_movimento"].map(parse.br_date),
        data_venda_original=raw["data_venda_original"].map(parse.br_date),
        qtd_parcelas=pd.to_numeric(raw["qtd_parcelas"], errors="coerce").astype("Int64"),
        taxa_aplicada=raw["taxa_aplicada_pct"].map(lambda v: parse.br_decimal(v) / 100),
        **{col: raw[col].map(parse.br_decimal) for col in MONEY_COLS},
    )


# R18: transações de EC sem contrato ficam guardadas no histórico do fechamento, no layout do 01, para o
# mês seguinte reler com `load_orbe` e faturar quando o Comercial confirmar o contrato.
ARQUIVO_PENDENTES = "orbe_pendentes"
NOME_PENDENTES = "pendentes_sem_contrato.csv"
ORDEM_01 = ["id_transacao", "data_movimento", "cod_estabelecimento", "nome_estabelecimento",
            "tipo_lancamento", "modalidade", "qtd_parcelas", "bandeira", "valor_bruto", "taxa_aplicada_pct",
            "valor_taxa", "valor_liquido", "id_referencia", "data_venda_original"]


def escrever_orbe(linhas: pd.DataFrame, path: Path) -> None:
    """Grava linhas lidas por `load_orbe` de volta no layout do relatório 01 (CSV ; com decimal vírgula)."""
    def data(d) -> str:
        return "" if d is None or pd.isna(d) else d.strftime("%d/%m/%Y")

    def numero(v) -> str:
        return "" if v is None or pd.isna(v) else format(v, "f").replace(".", ",")

    saida = pd.DataFrame({
        "id_transacao": linhas["id_transacao"],
        "data_movimento": linhas["data_movimento"].map(data),
        "cod_estabelecimento": linhas["cod_estabelecimento"],
        "nome_estabelecimento": linhas["nome_estabelecimento"],
        "tipo_lancamento": linhas["tipo_lancamento"],
        "modalidade": linhas["modalidade"],
        "qtd_parcelas": linhas["qtd_parcelas"].map(lambda v: "" if pd.isna(v) else str(int(v))),
        "bandeira": linhas["bandeira"] if "bandeira" in linhas else "",
        "valor_bruto": linhas["valor_bruto"].map(numero),
        "taxa_aplicada_pct": linhas["taxa_aplicada_pct"],
        "valor_taxa": linhas["valor_taxa"].map(numero),
        "valor_liquido": linhas["valor_liquido"].map(numero),
        "id_referencia": linhas["id_referencia"],
        "data_venda_original": linhas["data_venda_original"].map(data),
    })[ORDEM_01]
    saida.to_csv(path, sep=";", index=False, encoding="utf-8")
