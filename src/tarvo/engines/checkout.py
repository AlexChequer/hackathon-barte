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
from tarvo.engines import EngineResult, checkout_causa
from tarvo.engines.checkout_pendencias import (
    alertas_antecipacao,
    divergencias_condicao,
    nome_lojista,
    pendencias_contestacao_orbe,
    pendencias_sem_contrato,
)
from tarvo.money import ZERO, brl, pct, pct_br, q, q_mul, sum_q

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


def _cnpj_por_ec(registry: dict[str, list[LojistaTaxas]]) -> dict[str, str]:
    """EC → CNPJ: planilha/de-para R3 (registry) + ECs sem contrato com CNPJ de identidade (R30)."""
    mapa = {ec: entries[0].cnpj for ec, entries in registry.items() if entries}
    mapa.update({ec: c["cnpj"] for ec, c in rules.EC_SEM_CONTRATO.items() if c.get("cnpj")})
    return mapa


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
    coluna: str | None = None  # produto da planilha (credito_vista, antecipacao, …)


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
    return TaxaResolvida(contratada, planilha, condicao, coluna)


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


def _dedup_orbe(
    orbe: pd.DataFrame,
) -> tuple[list[pd.Series], list[dict], list[dict]]:
    """R24.1: id_transacao duplicado com mesmos dados financeiros entra 1×; dados divergentes
    abrem pendência DUPLICATA_CONFLITANTE para o Financeiro.
    """
    chaves_fin = ["valor_bruto", "valor_taxa", "valor_liquido", "taxa_aplicada", "tipo_lancamento"]
    deduped: list[pd.Series] = []
    duplicados_resolvidos: list[dict] = []
    pendencias: list[dict] = []
    for id_tx, grupo in orbe.groupby("id_transacao", sort=False):
        if len(grupo) == 1:
            deduped.append(grupo.iloc[0])
            continue
        unicos = grupo[chaves_fin].drop_duplicates()
        if len(unicos) == 1:
            deduped.append(grupo.iloc[0])
            for _, extra in grupo.iloc[1:].iterrows():
                duplicados_resolvidos.append({
                    "id_transacao": id_tx, "linha_origem": int(extra["linha_origem"]),
                })
        else:
            for _, linha in grupo.iterrows():
                pendencias.append({
                    "id": f"CK-DUPCONF-{id_tx}-L{int(linha['linha_origem'])}",
                    "tipo": "DUPLICATA_CONFLITANTE",
                    "ref_origem": f"{id_tx}#L{int(linha['linha_origem'])}",
                    "ref_rastro": id_tx,  # o rastro aponta a transação; a linha física vai na metadata
                    "arquivo_origem": ARQUIVO_ORBE,
                    "valor_brl": q(linha["valor_taxa"] or ZERO),
                    "motivo": (
                        f"id_transacao {id_tx} aparece em linhas com dados financeiros divergentes."
                        " Não escolhemos qual é a correta."
                    ),
                    "quem_decide": "Financeiro",
                    "cnpj": None,
                    "linha_negocio": "CHECKOUT",
                    "ec": str(linha.get("cod_estabelecimento")),
                })
    return deduped, duplicados_resolvidos, pendencias


def _dentro_competencia(data: dt.date | None, competencia: str) -> bool:
    """R24.1: só considera dentro quando a data existe e bate com AAAA-MM."""
    if data is None:
        return False
    return f"{data.year:04d}-{data.month:02d}" == competencia


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

    deduped, duplicados_resolvidos, pendencias_tx = _dedup_orbe(orbe)

    # Pré-pass: comissão arredondada de cada ANTECIPACAO para a REVERSAO achar em qualquer ordem (P13).
    comissao_antecipacao: dict[str, Decimal] = {}
    for tx in deduped:
        if tx["tipo_lancamento"] != "ANTECIPACAO":
            continue
        ec = str(tx["cod_estabelecimento"])
        if ec in rules.EC_SEM_CONTRATO:
            continue
        entries = registry.get(ec)
        if not entries:
            continue
        data_regra = _data_vigencia(tx)
        entry = _row_vigente(entries, data_regra) if data_regra else entries[-1]
        if entry is None:
            continue
        # Mesma taxa da passada principal: inclui condição comercial vigente (P19; ex.: Casa 0%).
        contratada = _taxa_contratada(entry, tx, data_regra, condicoes).contratada
        if contratada is None:
            continue
        bruto = tx["valor_bruto"] if isinstance(tx["valor_bruto"], Decimal) \
            else Decimal(str(tx["valor_bruto"]))
        comissao_antecipacao[tx["id_transacao"]] = q_mul(bruto, contratada)

    linhas_tx: list[dict] = []  # cada tx vira "contribuicao" de comissao + info de divergência
    sem_contrato_tx: list[pd.Series] = []
    diagnosticos: list[dict] = [
        {"codigo": "DUPLICATA_RESOLVIDA_ORBE", **d} for d in duplicados_resolvidos
    ]

    for tx in deduped:
        ec = str(tx["cod_estabelecimento"])
        tipo = tx["tipo_lancamento"]
        valor_bruto = tx["valor_bruto"] if isinstance(tx["valor_bruto"], Decimal) \
            else Decimal(str(tx["valor_bruto"]))
        taxa_aplicada = tx["taxa_aplicada"]
        data_tx = tx["data_movimento"]
        data_regra = _data_vigencia(tx)

        # EC sem contrato (R3/P10/R30): não fatura, não inventa taxa; agrega por lojista no fim.
        if ec in rules.EC_SEM_CONTRATO:
            sem_contrato_tx.append(tx)
            continue

        # Competência: a venda cai no mês da data_movimento; estorno cai no mês do estorno (R2/R29).
        # Linha com data fora da competência não deveria estar neste lote: pendência para o Financeiro.
        if not _dentro_competencia(data_tx, competencia):
            pendencias_tx.append({
                "id": f"CK-FORA-{tx['id_transacao']}",
                "tipo": "FORA_COMPETENCIA",
                "ref_origem": tx["id_transacao"],
                "arquivo_origem": ARQUIVO_ORBE,
                "valor_brl": q(tx["valor_taxa"] or ZERO),
                "motivo": (
                    f"Transação {tx['id_transacao']} com data_movimento {data_tx} fora da "
                    f"competência {competencia}. Não entra na apuração do mês."
                ),
                "quem_decide": "Financeiro",
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
                "valor_taxa_orbe": q(tx["valor_taxa"] or ZERO),
                "data_movimento": data_tx,
                "tipo": tipo,
                "taxa_contratada": contratada,
                "taxa_planilha": taxa.planilha,
                "taxa_aplicada": taxa_aplicada,
                "linha_planilha": entry.linha_planilha,
                "contratada_fonte": "antecipacao_original",
                "condicao_id": None,
                "produto": taxa.coluna,
                "data_referencia": data_regra,
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
        divergencia, divergencia_condicao = _divergencias(valor_bruto, taxa_aplicada, taxa)

        linhas_tx.append({
            "id_transacao": tx["id_transacao"],
            "cnpj": entry.cnpj,
            "lojista": entry.lojista,
            "ec": ec,
            "comissao": comissao,
            "divergencia": divergencia,
            "divergencia_condicao": divergencia_condicao,
            "valor_taxa_orbe": q(tx["valor_taxa"] or ZERO),
            "data_movimento": data_tx,
            "tipo": tipo,
            "taxa_contratada": contratada,
            "taxa_planilha": taxa.planilha,
            "taxa_aplicada": taxa_aplicada,
            "linha_planilha": entry.linha_planilha,
            "contratada_fonte": "condicao" if taxa.condicao else "planilha",
            "condicao_id": taxa.condicao.id if taxa.condicao else None,
            "valor_bruto": valor_bruto,
            "produto": taxa.coluna,
            "data_referencia": data_regra,
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
    rastro_proprio: set[str] = set()  # pendências que já emitem rastro por transação

    if not linhas_df.empty:
        # R4: 1 nota por CNPJ. Bridge tem 2 linhas de vigência com mesmo CNPJ: colapsa aqui.
        for cnpj, grupo in linhas_df.groupby("cnpj", sort=True):
            lojista = nome_lojista(grupo)
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
                    "metadata": f"tipo={tx['tipo']},taxa_contratada={pct(tx['taxa_contratada'])}",
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
                    rastro_rows.extend(_rastro_por_transacao(grupo, f"CK-NTZERO-{competencia}-{cnpj}",
                                                             "pendencia_NOTA_ZERO_INESPERADA"))
                    rastro_proprio.add(f"CK-NTZERO-{competencia}-{cnpj}")
                    pend_df = pd.concat([pend_df, pd.DataFrame([{
                        "id": f"CK-NTZERO-{competencia}-{cnpj}",
                        "tipo": "NOTA_ZERO_INESPERADA",
                        "ref_origem": cnpj,
                        "arquivo_origem": ARQUIVO_ORBE,
                        "valor_brl": ZERO,
                        "motivo": (
                            f"Comissão de checkout de {lojista} em {_competencia_fmt(competencia)}"
                            " fechou em R$ 0,00 sem regra conhecida (R4)."
                        ),
                        "quem_decide": "Financeiro",
                        "cnpj": cnpj,
                        "linha_negocio": "CHECKOUT",
                        "ec": grupo["ec"].iloc[0],
                    }])], ignore_index=True)
            else:  # negativo
                # Rastro = as transações que formam o saldo negativo (as mesmas da comissão).
                rastro_rows.extend(_rastro_por_transacao(grupo, f"CK-NTNEG-{competencia}-{cnpj}",
                                                         "pendencia_NOTA_NEGATIVA"))
                rastro_proprio.add(f"CK-NTNEG-{competencia}-{cnpj}")
                pend_df = pd.concat([pend_df, pd.DataFrame([{
                    "id": f"CK-NTNEG-{competencia}-{cnpj}",
                    "tipo": "NOTA_NEGATIVA",
                    "ref_origem": cnpj,
                    "arquivo_origem": ARQUIVO_ORBE,
                    "valor_brl": total_comissao,
                    "motivo": (
                        f"Comissão de checkout de {lojista} em {_competencia_fmt(competencia)} ficou "
                        f"negativa ({brl(total_comissao)}), e comissão negativa não emite nota (R4). "
                        f"{_composicao_negativa(grupo)}"
                    ),
                    "quem_decide": "Financeiro",
                    "cnpj": cnpj,
                    "linha_negocio": "CHECKOUT",
                    "ec": grupo["ec"].iloc[0],
                }])], ignore_index=True)

        # Divergências por transação (R1 + R8), com a causa decidida por regra (P26)
        causas = checkout_causa.classificar(linhas_df, registry)
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
                "causa_divergencia": causas[tx["id_transacao"]],
            })
            rastro_rows.append({
                "id_saida": div_id,
                "arquivo_origem": ARQUIVO_ORBE,
                "ref_origem": tx["id_transacao"],
                "valor": tx["divergencia"],
                "metadata": "divergencia_checkout",
            })

        cond_rows, cond_rastro, cond_pend = divergencias_condicao(linhas_df, condicoes, competencia)
        divergencias_rows.extend(cond_rows)
        rastro_rows.extend(cond_rastro)
        contest_rastro, contest_pend = pendencias_contestacao_orbe(
            linhas_df, competencia, causas, registry)
        rastro_rows.extend(contest_rastro)
        pendencias_cond = cond_pend + contest_pend
    else:
        pendencias_cond = []

    # Rastro de pendências (precisa de origem para `check_rastro`, inclusive quando valor=0).
    # Pendência com `rastro_proprio` já emitiu uma linha por transação acima.
    for p in pend_df.to_dict("records") if not pend_df.empty else []:
        if p["id"] in rastro_proprio:
            continue
        rastro_rows.append(_rastro_pendencia(p))

    result.comissoes = pd.DataFrame(comissoes_rows)
    result.divergencias = pd.DataFrame(divergencias_rows)
    result.notas = pd.DataFrame(notas_rows)
    sc_rastro, sc_pend = pendencias_sem_contrato(sem_contrato_tx, competencia)
    tx_mes = [tx for tx in deduped if _dentro_competencia(tx.get("data_movimento"), competencia)]
    al_rastro, al_pend = alertas_antecipacao(tx_mes, _cnpj_por_ec(registry), competencia)
    sc_rastro, sc_pend = sc_rastro + al_rastro, sc_pend + al_pend
    rastro_rows.extend(sc_rastro)
    pendencias_cond = pendencias_cond + sc_pend
    if pendencias_cond:
        pend_df = pd.concat([pend_df, pd.DataFrame(pendencias_cond)], ignore_index=True)
    if not pend_df.empty:
        result.pendencias = pend_df.rename(columns={"id": "id_saida"})[
            ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"]
        ]
    result.rastro = pd.DataFrame(rastro_rows)
    result.diagnosticos = diagnosticos
    return result


def _composicao_negativa(grupo: pd.DataFrame) -> str:
    """De onde vem o saldo negativo: as transações com comissão ≠ 0, maiores primeiro (até 5)."""
    pesam = grupo[grupo["comissao"] != ZERO]
    pesam = pesam.reindex(pesam["comissao"].map(abs).sort_values(ascending=False).index)
    itens = []
    for _, tx in pesam.head(5).iterrows():
        data = tx["data_referencia"]
        venda = f"venda de {data:%d/%m/%Y}, " if tx["tipo"] == "ESTORNO" and data else ""
        taxa = pct_br(pct(tx["taxa_contratada"]))
        itens.append(f"{tx['id_transacao']} ({tx['tipo'].lower()}, {venda}taxa {taxa}) {brl(tx['comissao'])}")
    resto = f" e mais {len(pesam) - 5}" if len(pesam) > 5 else ""
    isentas = len(grupo) - len(pesam)
    zeradas = f" As outras {isentas} transações têm comissão R$ 0,00." if isentas else ""
    return f"Vem de: {', '.join(itens)}{resto}.{zeradas}"


def _rastro_por_transacao(grupo: pd.DataFrame, id_saida: str, metadata: str) -> list[dict]:
    """Uma linha de rastro por transação do lojista, com a comissão de cada uma."""
    return [{"id_saida": id_saida, "arquivo_origem": ARQUIVO_ORBE, "ref_origem": tx["id_transacao"],
             "valor": tx["comissao"], "metadata": metadata} for _, tx in grupo.iterrows()]


def _rastro_pendencia(p: dict) -> dict:
    """Rastro de pendência de uma linha. `ref_rastro` (se houver) é a ref real no arquivo de origem."""
    ref = p.get("ref_rastro")
    if not isinstance(ref, str):
        ref = p["ref_origem"]
    metadata = f"pendencia_{p['tipo']}"
    if ref != p["ref_origem"]:
        metadata += f",linha={str(p['ref_origem']).rsplit('#', 1)[-1]}"
    return {"id_saida": p["id"], "arquivo_origem": p.get("arquivo_origem", ARQUIVO_ORBE), "ref_origem": ref,
            "valor": p["valor_brl"], "metadata": metadata}


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


def _explicar_zero(grupo: pd.DataFrame) -> list[str]:
    """R6/P11: zero é 'sem nota sem alarme' quando há explicação (ex.: Casa isenta set-dez)."""
    razoes = []
    por_condicao = grupo[(grupo["contratada_fonte"] == "condicao") & (grupo["taxa_contratada"] == ZERO)]
    for cid in sorted(set(por_condicao["condicao_id"])):
        razoes.append(f"Condição comercial {cid} com taxa zero (config/condicoes_comerciais.json).")
    return razoes
