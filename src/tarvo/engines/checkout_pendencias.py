"""Pendências agregadas do checkout: uma por contraparte e por lojista (R24.1).

- Orbe × lojista (`CONTESTACAO_ORBE`): a Orbe cobrou diferente da planilha (= contrato, R28.1).
  Valor = soma líquida das divergências `CK-DIV` do lojista: venda e estorno se anulam e a Helena
  cobra da Orbe só o que sobra (R16.3). Ela decide caso a caso (R1, R16.7).
- Tarvo × lojista (`CONDICAO_NAO_INFORMADA_ORBE`): concessão comercial fora da planilha (R6, R22).

Cada pendência tem rastro por transação; o detalhe fica em `divergencias_taxa` (R29.3).
"""

from __future__ import annotations

import pandas as pd

from tarvo.condicoes import Condicao
from tarvo.money import ZERO, pct, sum_q

ARQUIVO_ORBE = "orbe"


def nome_lojista(grupo: pd.DataFrame) -> str:
    """Escolhe um nome representativo quando o CNPJ aparece em 2 linhas (ex.: Bridge)."""
    nomes = grupo["lojista"].dropna().unique().tolist()
    return max(nomes, key=len) if nomes else "?"


def _resumo_taxas(grupo: pd.DataFrame, coluna_aplicada: str) -> str:
    pares = sorted({(pct(c), pct(a)) for c, a in zip(grupo["taxa_contratada"], grupo[coluna_aplicada],
                                                     strict=True)})
    return ", ".join(f"contrato {c}% × cobrado {a}%" for c, a in pares[:4]) + (" …" if len(pares) > 4 else "")


def pendencias_contestacao_orbe(linhas_df: pd.DataFrame, competencia: str) -> tuple[list[dict], list[dict]]:
    """1 pendência por lojista com divergência contratual da Orbe; rastro = as linhas CK-DIV."""
    rastro, pendencias = [], []
    divergentes = linhas_df[linhas_df["divergencia"] != ZERO]
    for cnpj, grupo in divergentes.groupby("cnpj", sort=True):
        total = sum_q(grupo["divergencia"])
        if total == ZERO:  # R16.3: venda e estorno se anularam, nada a cobrar
            continue
        pend_id = f"CK-CONTEST-{competencia}-{cnpj}"
        for _, tx in grupo.iterrows():
            rastro.append({"id_saida": pend_id, "arquivo_origem": ARQUIVO_ORBE,
                           "ref_origem": tx["id_transacao"], "valor": tx["divergencia"],
                           "metadata": "pendencia_CONTESTACAO_ORBE"})
        sentido = ("a Orbe cobrou a mais: ressarcir o lojista e cobrar da Orbe" if total > ZERO
                   else "a Orbe cobrou a menos que o contrato")
        pendencias.append({
            "id": pend_id,  # rastro já emitido por transação; não passa pelo laço genérico
            "tipo": "CONTESTACAO_ORBE",
            "ref_origem": cnpj,
            "valor_brl": total,
            "motivo": (
                f"{nome_lojista(linhas_df[linhas_df['cnpj'] == cnpj])}: {len(grupo)} transações com taxa "
                "diferente do contrato "
                f"({_resumo_taxas(grupo, 'taxa_aplicada')}); diferença líquida {total}, {sentido} "
                "(R1, R16.3, R28.1). Detalhe: linhas CK-DIV-* em divergencias_taxa."
            ),
            "quem_decide": "Financeiro",
        })
    return rastro, pendencias


def divergencias_condicao(
    linhas_df: pd.DataFrame, condicoes: tuple[Condicao, ...], competencia: str
) -> tuple[list[dict], list[dict], list[dict]]:
    """Linhas CK-COND (detalhe por transação) + 1 pendência por lojista com o total (R22, R24.1).

    Não entra na cobrança da Orbe: a Orbe cobrou certo pela planilha (R16.1). Pendência para o
    Financeiro com o Comercial: devolver ao lojista, atualizar a planilha e avisar a Orbe.
    """
    por_id = {c.id: c for c in condicoes}
    divergencias, rastro, pendencias = [], [], []
    marcadas = linhas_df[linhas_df["divergencia_condicao"] != ZERO]
    for cnpj, grupo in marcadas.groupby("cnpj", sort=True):
        pend_id = f"CK-COND-PEND-{competencia}-{cnpj}"
        for _, tx in grupo.iterrows():
            div_id = f"CK-COND-{tx['id_transacao']}"
            divergencias.append({
                "id_saida": div_id,
                "cnpj": cnpj,
                "linha_negocio": "CHECKOUT",
                "ref_origem": tx["id_transacao"],
                "taxa_contratada_pct": pct(tx["taxa_contratada"]),
                "taxa_aplicada_pct": pct(tx["taxa_planilha"]),
                "diferenca_brl": tx["divergencia_condicao"],
            })
            for id_saida, meta in [(div_id, f"divergencia_condicao;{tx['condicao_id']}"),
                                   (pend_id, f"pendencia_CONDICAO_NAO_INFORMADA_ORBE;{tx['condicao_id']}")]:
                rastro.append({"id_saida": id_saida, "arquivo_origem": ARQUIVO_ORBE,
                               "ref_origem": tx["id_transacao"], "valor": tx["divergencia_condicao"],
                               "metadata": meta})
        total = sum_q(grupo["divergencia_condicao"])
        conds = [por_id[c] for c in sorted(set(grupo["condicao_id"]))]
        fontes = "; ".join(f"{c.id} ({c.fonte}, aprovado por {c.aprovado_por})" for c in conds)
        pendencias.append({
            "id": pend_id,  # rastro já emitido por transação acima; não passa pelo laço genérico
            "tipo": "CONDICAO_NAO_INFORMADA_ORBE",
            "ref_origem": cnpj,
            "valor_brl": total,
            "motivo": (
                f"{nome_lojista(linhas_df[linhas_df['cnpj'] == cnpj])}: a Orbe cobrou a taxa da planilha em "
                f"{len(grupo)} transações, "
                f"mas vale condição comercial registrada fora dela ({fontes}). Devolver {total} ao lojista; "
                "não cobrar da Orbe (R16.1, R22). Atualizar a planilha e avisar a Orbe. "
                "Detalhe por transação: linhas CK-COND-* em divergencias_taxa."
            ),
            "quem_decide": "Financeiro + Comercial",
        })
    return divergencias, rastro, pendencias
