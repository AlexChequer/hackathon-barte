"""Motor REMESSA: participação Tarvo (50% × spread R$), divergência contratual, nota única da Ponte.

Fontes: `ponte` + `taxas` (coluna `spread_remessa`). Regras: R4/R5/R7/R8, premissas P5/P7/P12/P14.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pandas as pd

from tarvo import rules
from tarvo.engines import EngineResult
from tarvo.money import ZERO, pct, q, q_mul, sum_q

ARQUIVO_PONTE = "ponte"
ARQUIVO_TAXAS = "taxas"

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

    # 2) 4 negativos de setembro: excluir (P12) com pendência de contestação.
    divergencias_rows: list[dict] = []
    rastro_rows: list[dict] = []

    por_lojista: dict[str, Decimal] = {}
    nomes_por_cnpj: dict[str, list[str]] = {}
    rastros_por_lojista: dict[str, list[tuple[str, Decimal]]] = {}
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
                    f"Contestar com a Ponte.{f' Obs. da Ponte: {obs}.' if obs else ''}"
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
        rastros_por_lojista.setdefault(cnpj, []).append((n_op, participacao))
        nota_contribuicoes.append({"n_operacao": n_op, "cnpj": cnpj, "participacao": participacao})

        # Divergência de spread (R5/R7 + P5/P7).
        contratado = contratos.get(cnpj)
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
        for n_op, valor in rastros_por_lojista[cnpj]:
            rastro_rows.append({
                "id_saida": id_saida,
                "arquivo_origem": ARQUIVO_PONTE,
                "ref_origem": n_op,
                "valor": valor,
                "metadata": "participacao_remessa",
            })

    # 4) Nota única (R4 + P14): tomador = Ponte Câmbio.
    total_nota = sum_q([r["valor"] for r in rastro_rows if r.get("metadata") == "participacao_remessa"])
    notas_rows: list[dict] = []
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
                "metadata": "nota_remessa",
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
                partes.append(f"{len(valores)} {rotulo} ({sum_q(valores)})")
        sobra = (f" Os {arredondamento} restantes são arredondamento por operação (R8), sem contestação."
                 if arredondamento != ZERO else "")
        pendencias.append({
            "id": pend_id,
            "tipo": "DIFERENCA_RELATORIO_PONTE",
            "ref_origem": "relatorio_ponte",
            "arquivo_origem": ARQUIVO_PONTE,
            "valor_brl": diferenca,
            "motivo": (
                f"50% do spread declarado pela Ponte ({q(total_declarado)}) menos a nota ({total_nota}) "
                f"dá {q(total_declarado) - total_nota}. Desse total, {diferenca} vêm de linhas do relatório "
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
        if p["id"] == pend_id:
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
