"""Pendências agregadas do checkout: uma por contraparte e por lojista (R24.1).

- Orbe × lojista (`CONTESTACAO_ORBE`): a Orbe cobrou diferente da planilha (= contrato, R28.1).
  Valor = soma líquida das divergências `CK-DIV` do lojista: venda e estorno se anulam e a Helena
  cobra da Orbe só o que sobra (R16.3). Ela decide caso a caso (R1, R16.7).
- Tarvo × lojista (`CONDICAO_NAO_INFORMADA_ORBE`): concessão comercial fora da planilha (R6, R22).

Cada pendência tem rastro por transação; o detalhe fica em `divergencias_taxa` (R29.3).
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from tarvo import rules
from tarvo.condicoes import Condicao
from tarvo.money import ZERO, pct, q, sum_q

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


def _devolucao(tx: pd.Series) -> Decimal:
    """R33: devolve o que saiu do bolso do lojista (valor_taxa da Orbe) menos a comissão contratada,
    sem a parte que é erro da própria Orbe (essa vai na contestação, CK-DIV)."""
    return tx["valor_taxa_orbe"] - tx["comissao"] - tx["divergencia"]


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
            rastro.append({"id_saida": div_id, "arquivo_origem": ARQUIVO_ORBE,
                           "ref_origem": tx["id_transacao"], "valor": tx["divergencia_condicao"],
                           "metadata": f"divergencia_condicao;{tx['condicao_id']}"})
            rastro.append({"id_saida": pend_id, "arquivo_origem": ARQUIVO_ORBE,
                           "ref_origem": tx["id_transacao"], "valor": _devolucao(tx),
                           "metadata": f"pendencia_CONDICAO_NAO_INFORMADA_ORBE;{tx['condicao_id']}"})
        total = sum_q(_devolucao(tx) for _, tx in grupo.iterrows())
        formula = sum_q(grupo["divergencia_condicao"])
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
                f"mas vale condição comercial registrada fora dela ({fontes}). Devolver {total} ao lojista "
                f"(o que a Orbe descontou de fato, R33; pela fórmula da divergência: {formula}); "
                "não cobrar da Orbe (R16.1, R22). Atualizar a planilha e avisar a Orbe. "
                "Detalhe por transação: linhas CK-COND-* em divergencias_taxa."
            ),
            "quem_decide": "Financeiro + Comercial",
        })
    return divergencias, rastro, pendencias


def pendencias_sem_contrato(transacoes: list[pd.Series], competencia: str) -> tuple[list[dict], list[dict]]:
    """1 pendência por EC sem contrato (R3, R24.1), identificada pelo CNPJ confirmado (R30).

    Valor = o que a Orbe cobrou (exposição, P10): sem taxa contratada não há comissão a apurar.
    O id usa o CNPJ para casar com a confirmação do Comercial no mês seguinte (R18).
    """
    rastro, pendencias = [], []
    por_ec: dict[str, list[pd.Series]] = {}
    for tx in transacoes:
        por_ec.setdefault(str(tx["cod_estabelecimento"]), []).append(tx)
    for ec, txs in sorted(por_ec.items()):
        cadastro = rules.EC_SEM_CONTRATO[ec]
        chave = cadastro.get("cnpj") or f"EC{ec}"
        pend_id = f"CK-SEMCONTRATO-{competencia}-{chave}"
        valores = [q(tx["valor_taxa"] or ZERO) for tx in txs]
        for tx, valor in zip(txs, valores, strict=True):
            rastro.append({"id_saida": pend_id, "arquivo_origem": ARQUIVO_ORBE,
                           "ref_origem": tx["id_transacao"], "valor": valor,
                           "metadata": "pendencia_SEM_CONTRATO"})
        total, bruto = sum_q(valores), sum_q(q(tx["valor_bruto"]) for tx in txs)
        pendencias.append({
            "id": pend_id,  # rastro já emitido por transação; não passa pelo laço genérico
            "tipo": "SEM_CONTRATO",
            "ref_origem": chave,
            "valor_brl": total,
            "motivo": (
                f"{cadastro['nome']} (CNPJ {cadastro.get('cnpj') or 'não confirmado'}, EC {ec}) sem contrato "
                f"vigente: {len(txs)} transações, bruto {bruto}, a Orbe cobrou {total}. Não fatura até o "
                "Comercial confirmar a taxa; ao confirmar, a taxa vale desde o início e as linhas entram no "
                f"mês seguinte (R3, R18). Fonte do CNPJ: {cadastro['fonte']}."
            ),
            "quem_decide": "Comercial",
        })
    return rastro, pendencias


def _sem_historico(ec: str, txs: pd.DataFrame, competencia: str, ecs_com_contrato: set[str]) -> bool:
    """P22: primeira movimentação depois do 1º dia do mês, ou EC sem contrato vigente."""
    primeiro_dia = f"{competencia}-01"
    return ec not in ecs_com_contrato or txs["data_movimento"].min().isoformat() > primeiro_dia


def alertas_antecipacao(
    transacoes: list[pd.Series], cnpj_por_ec: dict[str, str], competencia: str
) -> tuple[list[dict], list[dict]]:
    """R16.6 + R28.2 + R32 (P22): lojista sem histórico com antecipado acumulado > vendido acumulado.

    Conta o pico: o risco existiu no dia em que o dinheiro foi adiantado; reversões posteriores
    vão no motivo. Valor = total antecipado no mês, com as antecipações no rastro.
    """
    if not transacoes:
        return [], []
    df = pd.DataFrame(transacoes)
    df["ec"] = df["cod_estabelecimento"].astype(str)
    com_contrato = set(cnpj_por_ec) - set(rules.EC_SEM_CONTRATO)
    rastro, pendencias = [], []
    for ec, txs in df.groupby("ec", sort=True):
        antecipacoes = txs[txs["tipo_lancamento"] == "ANTECIPACAO"].sort_values("data_movimento")
        if antecipacoes.empty or not _sem_historico(ec, txs, competencia, com_contrato):
            continue
        vendas = txs[txs["tipo_lancamento"] == "VENDA"]
        pico = None
        for data in sorted(set(antecipacoes["data_movimento"])):
            ate_a_data = antecipacoes[antecipacoes["data_movimento"] <= data]
            antecipado = sum_q(q(v) for v in ate_a_data["valor_bruto"])
            vendido = sum_q(q(v) for v in vendas[vendas["data_movimento"] <= data]["valor_bruto"])
            if antecipado > vendido:
                pico = (data, antecipado, vendido)
                break
        if pico is None:
            continue
        chave = cnpj_por_ec.get(ec) or f"EC{ec}"
        pend_id = f"CK-ALERTA-ANT-{competencia}-{chave}"
        valores = [q(v) for v in antecipacoes["valor_bruto"]]
        for (_, tx), valor in zip(antecipacoes.iterrows(), valores, strict=True):
            rastro.append({"id_saida": pend_id, "arquivo_origem": ARQUIVO_ORBE,
                           "ref_origem": tx["id_transacao"], "valor": valor,
                           "metadata": "pendencia_ALERTA_ANTECIPACAO"})
        reversoes = txs[(txs["tipo_lancamento"] == "REVERSAO ANTECIPACAO")
                        & txs["id_referencia"].isin(set(antecipacoes["id_transacao"]))]
        rev_txt = ", ".join(
            f"{r['id_transacao']} em {r['data_movimento']:%d/%m} (reverte {r['id_referencia']})"
            for _, r in reversoes.iterrows()
        ) or "nenhuma"
        total = sum_q(valores)
        data, antecipado, vendido = pico
        pendencias.append({
            "id": pend_id,  # rastro já emitido por antecipação; não passa pelo laço genérico
            "tipo": "ALERTA_ANTECIPACAO",
            "ref_origem": chave,
            "valor_brl": total,
            "motivo": (
                f"{txs['nome_estabelecimento'].iloc[0]} (EC {ec}) sem histórico (primeira movimentação "
                f"em {txs['data_movimento'].min():%d/%m}) antecipou mais do que vendeu: em {data:%d/%m}, "
                f"{antecipado} antecipados × {vendido} vendidos no mês. Total antecipado no mês {total}; "
                f"reversões depois: {rev_txt}. Alerta para o Financeiro e o Comercial (R16.6, R28.2, R32)."
            ),
            "quem_decide": "Financeiro + Comercial",
        })
    return rastro, pendencias
