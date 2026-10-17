"""Motor REMESSA: participação Tarvo (50% × spread R$), divergência contratual, nota única da Ponte.

Fontes: `ponte` + `taxas` (coluna `spread_remessa`). Regras: R4/R5/R7/R8, premissas P5/P7/P12/P14.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal

import pandas as pd

from tarvo import rules
from tarvo.engines import EngineResult
from tarvo.money import ZERO, brl, pct, pct_br, q, q_mul, sum_q

ARQUIVO_PONTE = "ponte"
ARQUIVO_TAXAS = "taxas"
# R27/P21: linha nova da Ponte com o ajuste de uma contestação aceita, apontando a operação original.
AJUSTE_REF = re.compile(r"AJUSTE\s+REF\s+(PC-[\w-]+)", re.IGNORECASE)

# Por que uma linha do relatório da Ponte não entra na nota (rastro da RM-CONTEST, P27).
FORA_DA_NOTA = {
    "duplicata": ("linha repetida contada 1×", "linhas repetidas contadas 1×"),
    "conflito": ("duplicata conflitante", "duplicatas conflitantes"),
    "fora_competencia": ("operação fora da competência", "operações fora da competência"),
    "status": ("status de compliance não previsto", "status de compliance não previstos"),
    "negativo": ("spread negativo", "spreads negativos"),
}


def _spread_contratado(taxas: pd.DataFrame) -> dict[str, Decimal]:
    """CNPJ → spread contratado. Vazio/'padrão' resolvido = 1,5% (R5). Texto inválido fica None."""
    out: dict[str, Decimal] = {}
    for _, r in taxas.iterrows():
        cnpj = r["cnpj"]
        valor_raw = r["spread_remessa_raw"]
        valor = r["spread_remessa"]
        if valor is not None:
            out[cnpj] = Decimal(str(valor))
        elif valor_raw is None or (isinstance(valor_raw, float) and pd.isna(valor_raw)):
            out[cnpj] = rules.SPREAD_PADRAO
        elif isinstance(valor_raw, str) and valor_raw.strip().lower() == "padrão":
            out[cnpj] = rules.SPREAD_PADRAO
        # texto inválido não resolvido: deixa cair como ausente para o motor pendir
    return out


def _dentro_competencia(data: dt.date | None, competencia: str) -> bool:
    if data is None:
        return False
    return f"{data.year:04d}-{data.month:02d}" == competencia


def _nome_lojista(nomes: list[str]) -> str:
    """Nome representativo quando o mesmo CNPJ aparece com variações no relatório da Ponte."""
    limpos = [n for n in (str(x).strip() for x in nomes if x) if n]
    return max(limpos, key=len) if limpos else "?"


def run(ponte: pd.DataFrame, taxas: pd.DataFrame, competencia: str) -> EngineResult:
    result = EngineResult()
    contratos = _spread_contratado(taxas)
    cnpjs_na_planilha = set(taxas["cnpj"].dropna())

    # 1) Deduplicação (R5, P14): PC-0926-0162 aparece 2× com mesmos dados financeiros.
    #    Operações com mesmo n_operacao e dados financeiros divergentes abrem pendência técnica.
    deduped: list[pd.Series] = []
    duplicados_resolvidos: list[dict] = []
    pendencias: list[dict] = []
    fora_da_nota: list[tuple[pd.Series, str]] = []  # (linha do relatório, motivo) que a nota não soma
    for n_op, grupo in ponte.groupby("n_operacao", sort=False):
        if len(grupo) == 1:
            deduped.append(grupo.iloc[0])
            continue
        chaves_fin = ["valor_me", "valor_brl", "spread_brl", "taxa_cliente", "ptax_ref"]
        unicos = grupo[chaves_fin].drop_duplicates()
        if len(unicos) == 1:
            # Preserva a primeira; registra evidência da repetição.
            primeira = grupo.iloc[0]
            deduped.append(primeira)
            pendencias.append(_pendencia_duplicata(n_op, grupo, competencia))
            for _, extra in grupo.iloc[1:].iterrows():
                fora_da_nota.append((extra, "duplicata"))
                duplicados_resolvidos.append({
                    "n_operacao": n_op,
                    "linha_origem": int(extra["linha_origem"]),
                    "observacao": extra.get("observacao"),
                })
        else:
            # Conflito financeiro: não escolhe sozinho, abre pendência.
            for _, linha in grupo.iterrows():
                fora_da_nota.append((linha, "conflito"))
                pendencias.append({
                    "id": f"RM-DUPCONF-{n_op}-{int(linha['linha_origem'])}",
                    "tipo": "DUPLICATA_CONFLITANTE",
                    "ref_origem": f"{n_op}#L{int(linha['linha_origem'])}",
                    "ref_rastro": n_op,  # o rastro aponta a operação; a linha física vai na metadata
                    "arquivo_origem": ARQUIVO_PONTE,
                    "valor_brl": q(linha["spread_brl"] or ZERO),
                    "motivo": f"{n_op} aparece com dados financeiros divergentes entre linhas.",
                    "quem_decide": "Financeiro",  # R11/R12: Helena decide; a Ponte só recebe a contestação
                    "cnpj": linha["cnpj"],
                    "linha_negocio": "REMESSA",
                })

    # 2) Spread negativo: fora da comissão e da nota, com pendência de contestação (P12).
    divergencias_rows: list[dict] = []
    rastro_rows: list[dict] = []

    por_lojista: dict[str, Decimal] = {}
    nomes_por_cnpj: dict[str, list[str]] = {}
    rastros_por_lojista: dict[str, list[tuple[str, Decimal, str]]] = {}  # (operação, valor, metadata extra)
    nota_contribuicoes: list[dict] = []

    for op in deduped:
        n_op = op["n_operacao"]
        cnpj = op["cnpj"]
        cliente = op["cliente"]
        data_contratacao = op.get("data_contratacao")
        spread_brl = op["spread_brl"]
        if not _dentro_competencia(data_contratacao, competencia):
            fora_da_nota.append((op, "fora_competencia"))
            pendencias.append({
                "id": f"RM-FORA-{n_op}",
                "tipo": "FORA_COMPETENCIA",
                "ref_origem": n_op,
                "arquivo_origem": ARQUIVO_PONTE,
                "valor_brl": q(spread_brl or ZERO),
                "motivo": (
                    f"Operação {n_op} com data_contratacao {data_contratacao} fora da competência"
                    f" {competencia}. Não entra na apuração do mês."
                ),
                "quem_decide": "Financeiro",
                "cnpj": cnpj,
                "linha_negocio": "REMESSA",
            })
            continue
        if spread_brl is None:
            pendencias.append({
                "id": f"RM-SPRAUS-{n_op}",
                "tipo": "SPREAD_AUSENTE",
                "ref_origem": n_op,
                "arquivo_origem": ARQUIVO_PONTE,
                "valor_brl": ZERO,
                "motivo": (
                    f"Operação {n_op} ({cliente}) sem spread R$ no relatório da Ponte."
                    " Não dá para apurar comissão sem o valor."
                ),
                "quem_decide": "Financeiro",  # R11/R12: Helena decide; a Ponte só recebe a contestação
                "cnpj": cnpj,
                "linha_negocio": "REMESSA",
            })
            continue
        spread_pct_valor = op["spread_pct"]
        ptax = op["ptax_ref"]
        valor_me = op["valor_me"]
        status = op.get("status_compliance") or ""

        # Status compliance: ambos entram (R5). Qualquer outro status desconhecido → pendência técnica.
        if status not in rules.PONTE_STATUS_VALIDOS:
            fora_da_nota.append((op, "status"))
            pendencias.append({
                "id": f"RM-STATUS-{n_op}",
                "tipo": "STATUS_DESCONHECIDO",
                "ref_origem": n_op,
                "arquivo_origem": ARQUIVO_PONTE,
                "valor_brl": q(spread_brl),
                "motivo": f"Operação {n_op} com status compliance '{status}' não previsto.",
                "quem_decide": "Financeiro",  # R11/R12: Helena decide; a Ponte só recebe a contestação
                "cnpj": cnpj,
                "linha_negocio": "REMESSA",
            })
            continue

        # R5: spread negativo não é aceito, em qualquer mês. Fica fora da comissão e da nota
        # e vira pendência de contestação com o valor cheio da operação (R12). Quem decide
        # é a Helena; a Ponte é a destinatária da contestação (R11, R12).
        # R27/P21/P31: ajuste de contestação aceita entra na comissão e na nota do mês em que aparece,
        # pelos mesmos 50% de qualquer linha do relatório (spread cheio, R10). Não é spread negativo a
        # contestar nem divergência. O rastro aponta a linha do ajuste (existe neste arquivo) e cita a
        # operação original na metadata.
        if ajuste := AJUSTE_REF.search(str(op.get("observacao") or "")):
            participacao = q_mul(spread_brl, Decimal("0.5"))
            extra = f",ajuste_ref={ajuste.group(1).upper()}"
            por_lojista[cnpj] = por_lojista.get(cnpj, ZERO) + participacao
            nomes_por_cnpj.setdefault(cnpj, []).append(cliente)
            rastros_por_lojista.setdefault(cnpj, []).append((n_op, participacao, extra))
            nota_contribuicoes.append({"n_operacao": n_op, "cnpj": cnpj, "participacao": participacao,
                                       "extra": extra})
            continue

        if spread_brl < 0:
            fora_da_nota.append((op, "negativo"))
            obs = op.get("observacao") or ""
            pendencias.append({
                "id": f"RM-NEG-{n_op}",
                "tipo": "SPREAD_NEGATIVO_CONTESTAR",
                "ref_origem": n_op,
                "arquivo_origem": ARQUIVO_PONTE,
                "valor_brl": q(spread_brl),
                "motivo": (
                    f"Spread negativo em {n_op} ({cliente}): fora da comissão e da nota (R5). "
                    f"Valor do relatório (o que aconteceu): {brl(spread_brl)}. "
                    + _ate_o_contrato(spread_pct_valor, contratos.get(cnpj), ptax, valor_me)
                    + f"{f' Obs. da Ponte: {obs}.' if obs else ''}"
                ),
                "quem_decide": "Financeiro",
                "cnpj": cnpj,
                "linha_negocio": "REMESSA",
            })
            continue

        # Participação por operação (R5 + R8). R24.1: agrupa por CNPJ só; o nome varia entre linhas.
        participacao = q_mul(spread_brl, Decimal("0.5"))
        por_lojista.setdefault(cnpj, ZERO)
        por_lojista[cnpj] += participacao
        nomes_por_cnpj.setdefault(cnpj, []).append(cliente)
        rastros_por_lojista.setdefault(cnpj, []).append((n_op, participacao, ""))
        nota_contribuicoes.append({"n_operacao": n_op, "cnpj": cnpj, "participacao": participacao,
                                   "extra": ""})

        # Divergência de spread (R5/R7 + P5/P7).
        contratado = contratos.get(cnpj)
        if contratado is None and cnpj not in cnpjs_na_planilha:
            # P16 (R17): a Ponte paga a nossa metade e a nota tem que bater com o repasse, então a
            # participação já entrou acima. Falta o cadastro, que é do Comercial (R24.1).
            pendencias.append({
                "id": f"RM-SEMCAD-{n_op}",
                "tipo": "LOJISTA_REMESSA_SEM_CADASTRO",
                "ref_origem": n_op,
                "arquivo_origem": ARQUIVO_PONTE,
                "valor_brl": participacao,
                "motivo": (
                    f"Operação {n_op} de {cliente} (CNPJ {cnpj}) não tem lojista na planilha de taxas. "
                    f"A participação de {brl(participacao)} entrou na comissão e na nota, porque a Ponte "
                    "paga pelo realizado. Sem spread contratado, não dá para checar divergência (P16, R17)."
                ),
                "quem_decide": "Comercial",
                "cnpj": cnpj,
                "linha_negocio": "REMESSA",
            })
            continue
        if contratado is None:
            pendencias.append({
                "id": f"RM-SEMSPR-{n_op}",
                "tipo": "SPREAD_CONTRATADO_INVALIDO",
                "ref_origem": n_op,
                "arquivo_origem": ARQUIVO_PONTE,
                "valor_brl": ZERO,
                "motivo": f"Spread remessa inválido para CNPJ {cnpj}, não resolvido como padrão.",
                "quem_decide": "Financeiro",
                "cnpj": cnpj,
                "linha_negocio": "REMESSA",
            })
            continue

        if spread_pct_valor is None or ptax is None or valor_me is None:
            continue
        diferenca = spread_pct_valor - contratado
        if abs(diferenca) > rules.TOLERANCIA_REMESSA_FRACAO:
            diff_brl = q(diferenca * ptax * valor_me)  # valor cheio por operação (P5)
            div_id = f"RM-DIV-{n_op}"
            divergencias_rows.append({
                "id_saida": div_id,
                "cnpj": cnpj,
                "linha_negocio": "REMESSA",
                "ref_origem": n_op,
                "taxa_contratada_pct": pct(contratado),
                "taxa_aplicada_pct": pct(spread_pct_valor),
                "diferenca_brl": diff_brl,
            })
            rastro_rows.append({
                "id_saida": div_id,
                "arquivo_origem": ARQUIVO_PONTE,
                "ref_origem": n_op,
                "valor": diff_brl,
                "metadata": "divergencia_remessa",
            })
            # Divergência não vira pendência: a linha em divergencias.csv já é a saída oficial
            # para o humano decidir. Duplicar causaria id_saida repetido e rastro em dobro.

    # Duplicatas: rastro por cópia a mais (a pendência foi aberta na deduplicação, R12).
    for p in pendencias:
        if p["tipo"] == "DUPLICATA_RELATORIO_PONTE":
            for valor in p["copias"]:
                rastro_rows.append({"id_saida": p["id"], "arquivo_origem": ARQUIVO_PONTE,
                                    "ref_origem": p["ref_origem"], "valor": valor,
                                    "metadata": "pendencia_DUPLICATA_RELATORIO_PONTE"})

    # Contestação com a Ponte: uma pendência por lojista com spread acima do contrato (R10, R12,
    # R24.1), valor cheio (R7), rastro por operação. A nota segue pelo realizado (R10).
    for cnpj, total, linhas in _divergencias_por_lojista(divergencias_rows):
        contesta_id = f"RM-CONTESTA-{competencia}-{cnpj}"
        pares = sorted({(linha["taxa_contratada_pct"], linha["taxa_aplicada_pct"]) for linha in linhas})
        faixa = (f"contrato {pct_br(pares[0][0])} × cobrado de {pct_br(pares[0][1])} "
                 f"a {pct_br(pares[-1][1])}")
        pendencias.append({
            "id": contesta_id,
            "tipo": "CONTESTACAO_PONTE",
            "ref_origem": cnpj,
            "arquivo_origem": ARQUIVO_PONTE,
            "valor_brl": total,
            "motivo": (
                f"{_nome_lojista(nomes_por_cnpj.get(cnpj, []))}: {len(linhas)} operações com spread acima do "
                f"contratado ({faixa}), diferença cheia {brl(total)} (R7). Contestar com a Ponte com as "
                "operações listadas no rastro. A nota do mês sai pelo realizado. Se a Ponte devolver, a "
                "nossa metade sai no mês do ajuste (R10, R12)."
            ),
            "quem_decide": "Financeiro",
            "cnpj": cnpj,
            "linha_negocio": "REMESSA",
            "rastro_proprio": True,
        })
        for linha in linhas:
            rastro_rows.append({"id_saida": contesta_id, "arquivo_origem": ARQUIVO_PONTE,
                                "ref_origem": linha["ref_origem"], "valor": linha["diferenca_brl"],
                                "metadata": "pendencia_CONTESTACAO_PONTE"})

    # 3) Comissões REMESSA por lojista.
    comissao_rows_df: list[dict] = []
    for cnpj, total in sorted(por_lojista.items()):
        id_saida = f"RM-CM-{competencia}-{cnpj}"
        comissao_rows_df.append({
            "id_saida": id_saida,
            "cnpj": cnpj,
            "lojista": _nome_lojista(nomes_por_cnpj[cnpj]),
            "linha_negocio": "REMESSA",
            "comissao_brl": total,
        })
        for n_op, valor, extra in rastros_por_lojista[cnpj]:
            rastro_rows.append({
                "id_saida": id_saida,
                "arquivo_origem": ARQUIVO_PONTE,
                "ref_origem": n_op,
                "valor": valor,
                "metadata": f"participacao_remessa{extra}",
            })

    # 4) Nota única (R4 + P14): tomador = Ponte Câmbio.
    total_nota = sum_q(c["participacao"] for c in nota_contribuicoes)
    notas_rows: list[dict] = []
    if nota_contribuicoes and total_nota <= ZERO:
        # R27: mês zerado ou negativo (ex.: ajuste maior que as participações) não emite nota e vira
        # pendência para a Helena, com o rastro nas operações que formam o saldo.
        pend_nota = f"RM-NTNEG-{competencia}-PONTE"
        pendencias.append({
            "id": pend_nota,
            "tipo": "NOTA_NEGATIVA" if total_nota < ZERO else "NOTA_ZERO_INESPERADA",
            "ref_origem": rules.PONTE_CNPJ,
            "arquivo_origem": ARQUIVO_PONTE,
            "valor_brl": total_nota,
            "motivo": (
                f"Participação da Tarvo no spread da Ponte em {_competencia_fmt(competencia)} fechou em "
                f"{brl(total_nota)}, somando {len(nota_contribuicoes)} operações"
                f"{_resumo_ajustes(nota_contribuicoes)}. Zerado ou negativo não emite nota (R4, R27)."
            ),
            "quem_decide": "Financeiro",
            "cnpj": rules.PONTE_CNPJ,
            "linha_negocio": "REMESSA",
            "rastro_proprio": True,
        })
        for contrib in nota_contribuicoes:
            rastro_rows.append({"id_saida": pend_nota, "arquivo_origem": ARQUIVO_PONTE,
                                "ref_origem": contrib["n_operacao"], "valor": contrib["participacao"],
                                "metadata": f"pendencia_NOTA_PONTE{contrib['extra']}"})
    if total_nota > ZERO:
        nota_id = f"RM-NT-{competencia}-PONTE"
        notas_rows.append({
            "id_saida": nota_id,
            "tomador_cnpj": rules.PONTE_CNPJ,
            "tomador": rules.PONTE_NOME,
            "linha_negocio": "REMESSA",
            "valor_brl": total_nota,
            "discriminacao": f"Intermediação de câmbio - competência {_competencia_fmt(competencia)}",
        })
        for contrib in nota_contribuicoes:
            rastro_rows.append({
                "id_saida": nota_id,
                "arquivo_origem": ARQUIVO_PONTE,
                "ref_origem": contrib["n_operacao"],
                "valor": contrib["participacao"],
                "metadata": f"nota_remessa{contrib['extra']}",
            })

    # 5) Nota × 50% do declarado pela Ponte (P14, P27). A diferença vem das linhas do relatório
    #    que a nota não soma; cada uma entra no rastro com a participação que teria (R8). O que
    #    sobra é arredondamento por operação: vai no motivo, não é contestável nem tem linha.
    total_declarado = sum_q([v for v in ponte["spread_brl"].tolist() if v is not None]) * Decimal("0.5")
    contribuicoes = [(linha, motivo, q_mul(linha["spread_brl"], Decimal("0.5")))
                     for linha, motivo in fora_da_nota if linha["spread_brl"] is not None]
    diferenca = sum_q(c for _, _, c in contribuicoes)
    arredondamento = q(total_declarado) - total_nota - diferenca
    pend_id = f"RM-CONTEST-{competencia}"
    if diferenca != ZERO:
        partes = []
        for chave, (singular, plural) in FORA_DA_NOTA.items():
            valores = [c for _, motivo, c in contribuicoes if motivo == chave]
            if valores:
                rotulo = singular if len(valores) == 1 else plural
                partes.append(f"{len(valores)} {rotulo} ({brl(sum_q(valores))})")
        sobra = (f" Os {brl(arredondamento)} restantes são arredondamento por operação (R8), sem contestação."
                 if arredondamento != ZERO else "")
        pendencias.append({
            "id": pend_id,
            "tipo": "DIFERENCA_RELATORIO_PONTE",
            "ref_origem": "relatorio_ponte",
            "arquivo_origem": ARQUIVO_PONTE,
            "valor_brl": diferenca,
            "motivo": (
                f"50% do spread declarado pela Ponte ({brl(total_declarado)}) menos a nota "
                f"({brl(total_nota)}) dá {brl(q(total_declarado) - total_nota)}. Desse total, "
                f"{brl(diferenca)} vêm de linhas do relatório "
                f"que não entram na nota: {', '.join(partes)} (R5, R12, P12).{sobra}"
            ),
            "quem_decide": "Financeiro",  # R11/R12: Helena decide; a Ponte só recebe a contestação
            "cnpj": rules.PONTE_CNPJ,
            "linha_negocio": "REMESSA",
        })
        for linha, motivo, contribuicao in contribuicoes:
            rastro_rows.append({
                "id_saida": pend_id,
                "arquivo_origem": ARQUIVO_PONTE,
                "ref_origem": linha["n_operacao"],
                "valor": contribuicao,
                "metadata": (f"pendencia_DIFERENCA_RELATORIO_PONTE,{motivo},"
                             f"linha=L{int(linha['linha_origem'])}"),
            })

    # Rastro das pendências (`check_rastro` exige origem para todas as saídas). A RM-CONTEST já
    # emitiu o seu por operação; a duplicata conflitante aponta a operação (`ref_rastro`).
    pend_df = pd.DataFrame(pendencias)
    for p in pendencias:
        if p["id"] == pend_id or p.get("rastro_proprio"):
            continue
        ref = p.get("ref_rastro", p["ref_origem"])
        metadata = f"pendencia_{p['tipo']}"
        if ref != p["ref_origem"]:
            metadata += f",linha={p['ref_origem'].rsplit('#', 1)[-1]}"
        rastro_rows.append({
            "id_saida": p["id"],
            "arquivo_origem": p.get("arquivo_origem", ARQUIVO_PONTE),
            "ref_origem": ref,
            "valor": p["valor_brl"],
            "metadata": metadata,
        })

    result.comissoes = pd.DataFrame(comissao_rows_df)
    result.divergencias = pd.DataFrame(divergencias_rows)
    result.notas = pd.DataFrame(notas_rows)
    result.pendencias = pend_df.rename(columns={"id": "id_saida"})[
        ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"]
    ] if not pend_df.empty else pd.DataFrame()
    result.rastro = pd.DataFrame(rastro_rows)
    result.diagnosticos = [{"codigo": "DUPLICATA_RESOLVIDA", **d} for d in duplicados_resolvidos]
    return result


def _resumo_ajustes(contribuicoes: list[dict]) -> str:
    ajustes = [c for c in contribuicoes if c["extra"]]
    if not ajustes:
        return ""
    return (f", entre elas {len(ajustes)} de ajuste de contestação (R27) que somam "
            f"{brl(sum_q(c['participacao'] for c in ajustes))}")


def _ate_o_contrato(spread_pct, contratado, ptax, valor_me) -> str:
    """R28.3: o que a Helena vai pedir à Ponte, porque a trava deveria ter sido honrada."""
    if None in (spread_pct, contratado, ptax, valor_me):
        return "Sem spread contratado ou dados da operação para calcular a diferença até o contrato."
    diferenca = (spread_pct - contratado) * ptax * valor_me
    if not diferenca.is_finite():
        return "Sem spread contratado ou dados da operação para calcular a diferença até o contrato."
    diferenca = q(diferenca)
    return (f"Diferença até o spread do contrato ({pct_br(pct(contratado))} sobre a PTAX), o que pedir à "
            f"Ponte: {brl(diferenca)} (R28.3).")


def _pendencia_duplicata(n_op: str, grupo: pd.DataFrame, competencia: str) -> dict:
    """R12: a operação conta uma vez no fechamento e entra na lista para a Ponte corrigir o relatório."""
    copias = [q(v or ZERO) for v in grupo.iloc[1:]["spread_brl"]]
    total = sum_q(copias)
    linhas = ", ".join(f"L{int(n)}" for n in grupo["linha_origem"])
    return {
        "id": f"RM-DUPREL-{competencia}-{n_op}",
        "tipo": "DUPLICATA_RELATORIO_PONTE",
        "ref_origem": n_op,
        "arquivo_origem": ARQUIVO_PONTE,
        "valor_brl": total,
        "motivo": (
            f"{n_op} ({grupo.iloc[0]['cliente']}) aparece {len(grupo)} vezes no relatório da Ponte "
            f"({linhas}). No fechamento conta uma vez (R5). O relatório soma {brl(total)} de spread a mais, "
            f"o que aumenta a nossa metade em {brl(total * Decimal('0.5'))} no total da Ponte. "
            "Pedir à Ponte que corrija o relatório (R12)."
        ),
        "quem_decide": "Financeiro",
        "cnpj": grupo.iloc[0]["cnpj"],
        "linha_negocio": "REMESSA",
        "rastro_proprio": True,
        "copias": copias,
    }


def _divergencias_por_lojista(divergencias: list[dict]) -> list[tuple[str, Decimal, list[dict]]]:
    por: dict[str, list[dict]] = {}
    for linha in divergencias:
        por.setdefault(linha["cnpj"], []).append(linha)
    return [(cnpj, sum_q(linha["diferenca_brl"] for linha in linhas), linhas)
            for cnpj, linhas in sorted(por.items())]


def _competencia_fmt(competencia: str) -> str:
    """Aceita '2026-09' (ISO) ou 'set2026' e devolve '09/2026'."""
    if len(competencia) == 7 and competencia[4] == "-":
        return f"{competencia[5:]}/{competencia[:4]}"
    meses = {
        "jan": "01", "fev": "02", "mar": "03", "abr": "04", "mai": "05", "jun": "06",
        "jul": "07", "ago": "08", "set": "09", "out": "10", "nov": "11", "dez": "12",
    }
    if len(competencia) >= 7:
        mes, ano = competencia[:3], competencia[3:]
        return f"{meses.get(mes.lower(), mes)}/{ano}"
    return competencia
