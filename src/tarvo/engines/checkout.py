"""Motor CHECKOUT: comissão contratada, divergências, notas e pendências a partir da Orbe.

Fontes: `orbe` (transações) e `taxas` (planilha de contratos vigentes).
Regras: `rules.py` + arredondamento em `money.q*`. Comentários apontam para R# / P#.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from decimal import Decimal

import pandas as pd

from tarvo import condicoes as cond_mod
from tarvo import rules
from tarvo.engines import EngineResult
from tarvo.money import ZERO, pct, q, q_mul, sum_q

ARQUIVO_ORBE = "orbe"
ARQUIVO_TAXAS = "taxas"

MODAL_MAP = {
    "CREDITO A VISTA": "credito_vista",
    "DEBITO": "debito",
    "PIX": "pix",
}


@dataclass(frozen=True)
class LojistaTaxas:
    """Row da planilha de taxas vigente para um EC, com as taxas por modalidade."""

    linha_origem: int
    lojista: str
    cnpj: str
    debito: Decimal | None
    credito_vista: Decimal | None
    credito_2a6: Decimal | None
    credito_7a12: Decimal | None
    pix: Decimal | None
    antecipacao: Decimal | None
    vigencia_inicio: dt.date | None
    vigencia_fim: dt.date | None
    linha_planilha: int


def _parse_vigencia(texto: object) -> tuple[dt.date | None, dt.date | None]:
    """Normaliza a coluna 'Vigência' da planilha de taxas em (inicio, fim)."""
    if texto is None or (isinstance(texto, float) and pd.isna(texto)):
        return None, None
    s = str(texto).strip().lower()
    if not s or s == "nan":
        return None, None
    if m := re.match(r"até\s+(\d{2}/\d{2}/\d{4})", s):
        return None, _d(m.group(1))
    if m := re.match(r"a partir de\s+(\d{2}/\d{2}/\d{4})", s):
        return _d(m.group(1)), None
    if m := re.match(r"(\d{2}/\d{2}/\d{4})", s):
        return _d(m.group(1)), None
    return None, None


def _d(ptbr: str) -> dt.date:
    d, m, y = ptbr.split("/")
    return dt.date(int(y), int(m), int(d))


def build_taxas_registry(taxas: pd.DataFrame) -> dict[str, list[LojistaTaxas]]:
    """EC → lista de LojistaTaxas (uma por vigência). Inclui as 3 linhas resolvidas por R3."""

    def _row_to_entry(row) -> LojistaTaxas:
        ini, fim = _parse_vigencia(row["vigencia_raw"])
        return LojistaTaxas(
            linha_origem=int(row["linha_origem"]),
            lojista=str(row["lojista"]).strip(),
            cnpj=row["cnpj"],
            debito=row["debito"],
            credito_vista=row["credito_vista"],
            credito_2a6=row["credito_2a6"],
            credito_7a12=row["credito_7a12"],
            pix=row["pix"],
            antecipacao=row["antecipacao"],
            vigencia_inicio=ini,
            vigencia_fim=fim,
            linha_planilha=int(row["linha_origem"]),
        )

    registry: dict[str, list[LojistaTaxas]] = {}
    for _, r in taxas.iterrows():
        ec = r.get("ec_orbe")
        if ec and str(ec).lower() != "nan":
            registry.setdefault(str(ec), []).append(_row_to_entry(r))
    # R3: EC → CNPJ. Todas as linhas desse CNPJ (uma por vigência). Sem linha → EC fica
    # fora do registry e a transação vira pendência CK-SEMCAD.
    for ec, cnpj in rules.EC_PARA_CNPJ.items():
        for _, r in taxas[taxas["cnpj"] == cnpj].iterrows():
            registry.setdefault(ec, []).append(_row_to_entry(r))
    return registry


def _data_vigencia(tx: pd.Series) -> dt.date | None:
    """Qual data decide a taxa (R2 + P3): venda da venda; venda original do estorno; venda da antecipação."""
    tipo = tx["tipo_lancamento"]
    if tipo == "ESTORNO":
        return tx.get("data_venda_original") or tx.get("data_movimento")
    return tx.get("data_movimento")


def _row_vigente(entries: list[LojistaTaxas], data: dt.date) -> LojistaTaxas | None:
    """Entre as linhas do EC, retorna a vigente na data (R2/P3). Default: a mais recente."""
    candidatos = [
        e for e in entries
        if (e.vigencia_inicio is None or e.vigencia_inicio <= data)
        and (e.vigencia_fim is None or e.vigencia_fim >= data)
    ]
    if candidatos:
        return max(candidatos, key=lambda e: (e.vigencia_inicio or dt.date.min))
    return None


def _modalidade_coluna(modalidade: str | None, qtd_parcelas: object) -> str | None:
    if not modalidade:
        return None
    if modalidade in MODAL_MAP:
        return MODAL_MAP[modalidade]
    if modalidade == "CREDITO PARCELADO":
        parcelas = int(qtd_parcelas) if pd.notna(qtd_parcelas) else 0
        if 2 <= parcelas <= 6:
            return "credito_2a6"
        if 7 <= parcelas <= 12:
            return "credito_7a12"
    return None


@dataclass(frozen=True)
class TaxaResolvida:
    """Taxa contratada da transação e de onde ela veio (planilha ou condição comercial)."""

    contratada: Decimal | None
    planilha: Decimal | None
    condicao: cond_mod.Condicao | None


def _taxa_contratada(
    entry: LojistaTaxas, tx: pd.Series, data_regra: dt.date, condicoes: tuple[cond_mod.Condicao, ...]
) -> TaxaResolvida:
    """Taxa da planilha (o que a Orbe conhece) e, se houver, a condição comercial vigente (R6)."""
    if tx["tipo_lancamento"] in {"ANTECIPACAO", "REVERSAO ANTECIPACAO"}:
        coluna = "antecipacao"
    else:
        coluna = _modalidade_coluna(tx.get("modalidade"), tx.get("qtd_parcelas"))
    planilha = getattr(entry, coluna) if coluna else None
    condicao = cond_mod.vigente(condicoes, entry.cnpj, data_regra, coluna) if coluna else None
    contratada = condicao.taxas[coluna] if condicao else planilha
    return TaxaResolvida(contratada, planilha, condicao)


def _divergencias(bruto: Decimal, aplicada: Decimal | None, taxa: TaxaResolvida) -> tuple[Decimal, Decimal]:
    """(parte da Orbe, parte da condição comercial), cada uma arredondada (R8).

    Orbe cobrou diferente da planilha → falha da Orbe (cobrável). Planilha diferente da condição
    comercial → a Orbe não foi avisada: falha da Tarvo, só devolver ao lojista (R16.1, R22).
    """
    if aplicada is None or aplicada == taxa.contratada:
        return ZERO, ZERO
    if taxa.condicao is None:
        return q_mul(bruto, aplicada - taxa.contratada), ZERO
    parte_orbe = q_mul(bruto, aplicada - taxa.planilha) if aplicada != taxa.planilha else ZERO
    parte_cond = q_mul(bruto, taxa.planilha - taxa.contratada) if taxa.planilha != taxa.contratada else ZERO
    return parte_orbe, parte_cond


def _diagnostico(code: str, **detalhes) -> dict:
    return {"codigo": code, **detalhes}


def run(
    orbe: pd.DataFrame,
    taxas: pd.DataFrame,
    competencia: str,
    condicoes: tuple[cond_mod.Condicao, ...] | None = None,
) -> EngineResult:
    registry = build_taxas_registry(taxas)
    if condicoes is None:
        condicoes = cond_mod.carregar()
    result = EngineResult()

    # Pré-indexa antecipações (REVERSÃO precisa recuperar a comissão da original: P13).
    comissao_antecipacao: dict[str, Decimal] = {}

    linhas_tx: list[dict] = []  # cada tx vira "contribuicao" de comissao + info de divergência
    pendencias_tx: list[dict] = []
    diagnosticos: list[dict] = []

    for _, tx in orbe.iterrows():
        ec = str(tx["cod_estabelecimento"])
        tipo = tx["tipo_lancamento"]
        valor_bruto = tx["valor_bruto"] if isinstance(tx["valor_bruto"], Decimal) \
            else Decimal(str(tx["valor_bruto"]))
        taxa_aplicada = tx["taxa_aplicada"]
        data_tx = tx["data_movimento"]
        data_regra = _data_vigencia(tx)

        # Atlas (R3/P10): sem contrato vigente, não fatura, não inventa.
        if ec in rules.EC_SEM_CONTRATO:
            pendencias_tx.append({
                "id": f"CK-ATLAS-{tx['id_transacao']}",
                "tipo": "SEM_CONTRATO",
                "ref_origem": tx["id_transacao"],
                "arquivo_origem": ARQUIVO_ORBE,
                "valor_brl": q(tx["valor_taxa"] or ZERO),
                "motivo": (
                    f"Atlas Idiomas (EC {ec}) sem contrato vigente (R3): não fatura. "
                    "Exposição bruta = cobrança da Orbe nesta transação."
                ),
                "quem_decide": "Comercial",
                "cnpj": None,
                "linha_negocio": "CHECKOUT",
                "ec": ec,
            })
            continue

        entries = registry.get(ec)
        if not entries:
            pendencias_tx.append({
                "id": f"CK-SEMCAD-{tx['id_transacao']}",
                "tipo": "EC_NAO_CADASTRADO",
                "ref_origem": tx["id_transacao"],
                "arquivo_origem": ARQUIVO_ORBE,
                "valor_brl": q(tx["valor_taxa"] or ZERO),
                "motivo": f"EC {ec} ({tx['nome_estabelecimento']}) sem linha vigente na planilha de taxas.",
                "quem_decide": "Comercial",
                "cnpj": None,
                "linha_negocio": "CHECKOUT",
                "ec": ec,
            })
            continue

        entry = _row_vigente(entries, data_regra) if data_regra else entries[-1]
        if entry is None:
            pendencias_tx.append({
                "id": f"CK-VIG-{tx['id_transacao']}",
                "tipo": "VIGENCIA_AUSENTE",
                "ref_origem": tx["id_transacao"],
                "arquivo_origem": ARQUIVO_ORBE,
                "valor_brl": q(tx["valor_taxa"] or ZERO),
                "motivo": (
                    f"Nenhuma vigência coincide com {data_regra} para EC {ec}"
                    f" ({tx['nome_estabelecimento']})."
                ),
                "quem_decide": "Financeiro",
                "cnpj": None,
                "linha_negocio": "CHECKOUT",
                "ec": ec,
            })
            continue

        taxa = _taxa_contratada(entry, tx, data_regra, condicoes)
        contratada = taxa.contratada

        # REVERSAO ANTECIPACAO (P13): anula comissão arredondada da antecipação original.
        if tipo == "REVERSAO ANTECIPACAO":
            ref = tx.get("id_referencia")
            comissao_original = comissao_antecipacao.get(ref)
            if comissao_original is None:
                pendencias_tx.append({
                    "id": f"CK-REVSEMREF-{tx['id_transacao']}",
                    "tipo": "REVERSAO_SEM_REFERENCIA",
                    "ref_origem": tx["id_transacao"],
                    "arquivo_origem": ARQUIVO_ORBE,
                    "valor_brl": q(tx["valor_taxa"] or ZERO),
                    "motivo": (
                        f"REVERSAO {tx['id_transacao']} aponta para antecipação {ref}"
                        " não encontrada no lote."
                    ),
                    "quem_decide": "Financeiro",
                    "cnpj": entry.cnpj,
                    "linha_negocio": "CHECKOUT",
                    "ec": ec,
                })
                continue
            comissao = -comissao_original
            linhas_tx.append({
                "id_transacao": tx["id_transacao"],
                "cnpj": entry.cnpj,
                "lojista": entry.lojista,
                "ec": ec,
                "comissao": comissao,
                "divergencia": ZERO,
                "divergencia_condicao": ZERO,
                "data_movimento": data_tx,
                "tipo": tipo,
                "taxa_contratada": contratada,
                "taxa_planilha": taxa.planilha,
                "taxa_aplicada": taxa_aplicada,
                "linha_planilha": entry.linha_planilha,
                "contratada_fonte": "antecipacao_original",
                "condicao_id": None,
            })
            continue

        if contratada is None:
            pendencias_tx.append({
                "id": f"CK-SEMTAX-{tx['id_transacao']}",
                "tipo": "SEM_TAXA_CONTRATADA",
                "ref_origem": tx["id_transacao"],
                "arquivo_origem": ARQUIVO_ORBE,
                "valor_brl": q(tx["valor_taxa"] or ZERO),
                "motivo": f"Taxa contratada ausente para modalidade {tx.get('modalidade')!r} do EC {ec}.",
                "quem_decide": "Financeiro",
                "cnpj": entry.cnpj,
                "linha_negocio": "CHECKOUT",
                "ec": ec,
            })
            continue

        comissao = q_mul(valor_bruto, contratada)
        if tipo == "ANTECIPACAO":
            comissao_antecipacao[tx["id_transacao"]] = comissao

        divergencia, divergencia_condicao = _divergencias(valor_bruto, taxa_aplicada, taxa)

        linhas_tx.append({
            "id_transacao": tx["id_transacao"],
            "cnpj": entry.cnpj,
            "lojista": entry.lojista,
            "ec": ec,
            "comissao": comissao,
            "divergencia": divergencia,
            "divergencia_condicao": divergencia_condicao,
            "data_movimento": data_tx,
            "tipo": tipo,
            "taxa_contratada": contratada,
            "taxa_planilha": taxa.planilha,
            "taxa_aplicada": taxa_aplicada,
            "linha_planilha": entry.linha_planilha,
            "contratada_fonte": "condicao" if taxa.condicao else "planilha",
            "condicao_id": taxa.condicao.id if taxa.condicao else None,
            "valor_bruto": valor_bruto,
        })

        # Divergência não vira pendência: a linha em divergencias.csv já representa a decisão
        # que o Financeiro precisa tomar. Duplicar na pendência causaria id_saida repetido.

    linhas_df = pd.DataFrame(linhas_tx)
    pend_df = pd.DataFrame(pendencias_tx)

    # ----- comissões por lojista -----
    comissoes_rows: list[dict] = []
    rastro_rows: list[dict] = []
    divergencias_rows: list[dict] = []
    notas_rows: list[dict] = []

    if not linhas_df.empty:
        # R4: 1 nota por CNPJ. Bridge tem 2 linhas de vigência com mesmo CNPJ: colapsa aqui.
        for cnpj, grupo in linhas_df.groupby("cnpj", sort=True):
            lojista = _canonical_lojista(grupo)
            total_comissao = sum_q(grupo["comissao"])
            id_saida = f"CK-CM-{competencia}-{cnpj}"
            comissoes_rows.append({
                "id_saida": id_saida,
                "cnpj": cnpj,
                "lojista": lojista,
                "linha_negocio": "CHECKOUT",
                "comissao_brl": total_comissao,
            })
            for _, tx in grupo.iterrows():
                rastro_rows.append({
                    "id_saida": id_saida,
                    "arquivo_origem": ARQUIVO_ORBE,
                    "ref_origem": tx["id_transacao"],
                    "valor": tx["comissao"],
                    "metadata": f"tipo={tx['tipo']};taxa_contratada={pct(tx['taxa_contratada'])}",
                })

            # Nota (R4/P11): só com saldo > 0. Saldo 0 por Casa isenta = sem nota sem pendência.
            if total_comissao > ZERO:
                nota_id = f"CK-NT-{competencia}-{cnpj}"
                notas_rows.append({
                    "id_saida": nota_id,
                    "tomador_cnpj": cnpj,
                    "tomador": lojista,
                    "linha_negocio": "CHECKOUT",
                    "valor_brl": total_comissao,
                    "discriminacao": (
                        "Intermediação de pagamentos (checkout) - competência "
                        f"{_competencia_fmt(competencia)}"
                    ),
                })
                for _, tx in grupo.iterrows():
                    rastro_rows.append({
                        "id_saida": nota_id,
                        "arquivo_origem": ARQUIVO_ORBE,
                        "ref_origem": tx["id_transacao"],
                        "valor": tx["comissao"],
                        "metadata": "nota_checkout",
                    })
            elif total_comissao == ZERO:
                # Zero: só vira pendência se não for Casa isenta ou outro cenário "explicado".
                razoes_isento = _explicar_zero(grupo)
                if not razoes_isento:
                    pend_df = pd.concat([pend_df, pd.DataFrame([{
                        "id": f"CK-NTZERO-{competencia}-{cnpj}",
                        "tipo": "NOTA_ZERO_INESPERADA",
                        "ref_origem": cnpj,
                        "arquivo_origem": ARQUIVO_ORBE,
                        "valor_brl": ZERO,
                        "motivo": (
                            f"Comissão de checkout de {lojista} em {competencia}"
                            " fechou em 0 sem regra conhecida."
                        ),
                        "quem_decide": "Financeiro",
                        "cnpj": cnpj,
                        "linha_negocio": "CHECKOUT",
                        "ec": grupo["ec"].iloc[0],
                    }])], ignore_index=True)
            else:  # negativo
                pend_df = pd.concat([pend_df, pd.DataFrame([{
                    "id": f"CK-NTNEG-{competencia}-{cnpj}",
                    "tipo": "NOTA_NEGATIVA",
                    "ref_origem": cnpj,
                    "arquivo_origem": ARQUIVO_ORBE,
                    "valor_brl": total_comissao,
                    "motivo": (
                        f"Comissão de {lojista} em {competencia} ficou negativa"
                        f" ({total_comissao}). R4: Helena decide."
                    ),
                    "quem_decide": "Financeiro",
                    "cnpj": cnpj,
                    "linha_negocio": "CHECKOUT",
                    "ec": grupo["ec"].iloc[0],
                }])], ignore_index=True)

        # Divergências por transação (R1 + R8)
        divergentes = linhas_df[linhas_df["divergencia"] != ZERO]
        for _, tx in divergentes.iterrows():
            div_id = f"CK-DIV-{tx['id_transacao']}"
            divergencias_rows.append({
                "id_saida": div_id,
                "cnpj": tx["cnpj"],
                "linha_negocio": "CHECKOUT",
                "ref_origem": tx["id_transacao"],
                "taxa_contratada_pct": pct(tx["taxa_contratada"]),
                "taxa_aplicada_pct": pct(tx["taxa_aplicada"]),
                "diferenca_brl": tx["divergencia"],
            })
            rastro_rows.append({
                "id_saida": div_id,
                "arquivo_origem": ARQUIVO_ORBE,
                "ref_origem": tx["id_transacao"],
                "valor": tx["divergencia"],
                "metadata": "divergencia_checkout",
            })

        cond_rows, cond_rastro, cond_pend = _divergencias_condicao(linhas_df, condicoes, competencia)
        divergencias_rows.extend(cond_rows)
        rastro_rows.extend(cond_rastro)
        pendencias_cond = cond_pend
    else:
        pendencias_cond = []

    # Rastro de pendências (precisa de origem para `check_rastro`, inclusive quando valor=0).
    for p in pend_df.to_dict("records") if not pend_df.empty else []:
        rastro_rows.append({
            "id_saida": p["id"],
            "arquivo_origem": p.get("arquivo_origem", ARQUIVO_ORBE),
            "ref_origem": p["ref_origem"],
            "valor": p["valor_brl"],
            "metadata": f"pendencia_{p['tipo']}",
        })

    result.comissoes = pd.DataFrame(comissoes_rows)
    result.divergencias = pd.DataFrame(divergencias_rows)
    result.notas = pd.DataFrame(notas_rows)
    if pendencias_cond:
        pend_df = pd.concat([pend_df, pd.DataFrame(pendencias_cond)], ignore_index=True)
    if not pend_df.empty:
        result.pendencias = pend_df.rename(columns={"id": "id_saida"})[
            ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"]
        ]
    result.rastro = pd.DataFrame(rastro_rows)
    result.diagnosticos = diagnosticos
    return result


def _divergencias_condicao(
    linhas_df: pd.DataFrame, condicoes: tuple[cond_mod.Condicao, ...], competencia: str
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
                f"{_canonical_lojista(grupo)}: a Orbe cobrou a taxa da planilha em {len(grupo)} transações, "
                f"mas vale condição comercial registrada fora dela ({fontes}). Devolver {total} ao lojista; "
                "não cobrar da Orbe (R16.1, R22). Atualizar a planilha e avisar a Orbe. "
                "Detalhe por transação: linhas CK-COND-* em divergencias_taxa."
            ),
            "quem_decide": "Financeiro + Comercial",
        })
    return divergencias, rastro, pendencias


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


def _canonical_lojista(grupo: pd.DataFrame) -> str:
    """Escolhe um nome representativo quando o CNPJ aparece em 2 linhas (ex.: Bridge)."""
    nomes = grupo["lojista"].dropna().unique().tolist()
    return max(nomes, key=len) if nomes else "?"


def _explicar_zero(grupo: pd.DataFrame) -> list[str]:
    """R6/P11: zero é 'sem nota sem alarme' quando há explicação (ex.: Casa isenta set-dez)."""
    razoes = []
    por_condicao = grupo[(grupo["contratada_fonte"] == "condicao") & (grupo["taxa_contratada"] == ZERO)]
    for cid in sorted(set(por_condicao["condicao_id"])):
        razoes.append(f"Condição comercial {cid} com taxa zero (config/condicoes_comerciais.json).")
    return razoes
