"""Avaliação da saída contra uma referência manual + métricas gerais.

Lê `tests/fixtures/referencia_<competencia>.json`, compara com o `ClosingResult`
e produz um dict com métricas (numerador/denominador por métrica). Nunca inventa
baseline: cada caso aponta para R#/P#. Casos sem referência ficam marcados como
"não medidos".
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pandas as pd

from tarvo.orquestrador import ClosingResult


def _d(v: object) -> Decimal:
    return v if isinstance(v, Decimal) else Decimal(str(v))


def _acerto(status: bool) -> str:
    return "ok" if status else "falha"


def carregar_referencia(fixtures_dir: Path, competencia: str) -> dict | None:
    path = fixtures_dir / f"referencia_{competencia.replace('-', '_')}.json"
    if not path.exists():
        alt = fixtures_dir / f"referencia_{competencia.replace('-', '')}.json"
        if alt.exists():
            path = alt
        else:
            # tenta por mes abreviado (set2026)
            apelidos = {"2026-09": "set2026"}
            apelido = apelidos.get(competencia)
            if apelido:
                alt2 = fixtures_dir / f"referencia_{apelido}.json"
                if alt2.exists():
                    path = alt2
                else:
                    return None
            else:
                return None
    return json.loads(path.read_text(encoding="utf-8"))


def _comparar_comissoes(ref: list[dict], atual: pd.DataFrame) -> list[dict]:
    casos: list[dict] = []
    for item in ref:
        cnpj = item["cnpj"]
        linha = item["linha_negocio"]
        esperado = _d(item["valor_brl"])
        row = atual[(atual["cnpj"] == cnpj) & (atual["linha_negocio"] == linha)]
        encontrado = None if row.empty else _d(row["comissao_brl"].iloc[0])
        casos.append({
            "tipo": "comissao",
            "cnpj": cnpj,
            "linha_negocio": linha,
            "esperado": str(esperado),
            "encontrado": None if encontrado is None else str(encontrado),
            "status": _acerto(encontrado is not None and encontrado == esperado),
            "fonte_regra": item.get("fonte_regra"),
        })
    return casos


def _comparar_divergencias(ref: list[dict], atual: pd.DataFrame) -> list[dict]:
    casos: list[dict] = []
    for item in ref:
        if item.get("ref_origem") and "presente" in item:
            ref_origem = item["ref_origem"]
            present = (atual["ref_origem"] == ref_origem).any()
            esperado_present = bool(item["presente"])
            casos.append({
                "tipo": "divergencia_presenca",
                "ref_origem": ref_origem,
                "esperado_presente": esperado_present,
                "encontrado_presente": bool(present),
                "status": _acerto(present == esperado_present),
                "fonte_regra": item.get("fonte_regra"),
            })
            continue
        if item.get("agregacao") == "soma_diferenca_brl":
            cnpj = item["cnpj"]
            esperado = _d(item["valor_brl"])
            subset = atual[atual["cnpj"] == cnpj]
            soma = sum((_d(x) for x in subset["diferenca_brl"]), Decimal(0))
            casos.append({
                "tipo": "soma_divergencia_por_cnpj",
                "cnpj": cnpj,
                "esperado": str(esperado),
                "encontrado": str(soma),
                "status": _acerto(soma == esperado),
                "fonte_regra": item.get("fonte_regra"),
            })
            continue
        if item.get("agregacao") == "diferenca_pp_unica":
            cnpj = item["cnpj"]
            esperado = _d(item["valor_pp"])
            subset = atual[atual["cnpj"] == cnpj]
            if subset.empty:
                status_ok = False
                diffs = set()
            else:
                diffs = {
                    (_d(a) - _d(c)).copy_abs()
                    for a, c in zip(
                        subset["taxa_aplicada_pct"], subset["taxa_contratada_pct"], strict=True,
                    )
                }
                status_ok = diffs == {esperado}
            casos.append({
                "tipo": "diferenca_pp_unica",
                "cnpj": cnpj,
                "esperado_pp": str(esperado),
                "encontrado_pp": sorted(str(d) for d in diffs),
                "status": _acerto(status_ok),
                "fonte_regra": item.get("fonte_regra"),
            })
    return casos


def _comparar_notas(ref: list[dict], atual: pd.DataFrame) -> list[dict]:
    casos: list[dict] = []
    for item in ref:
        cnpj = item["tomador_cnpj"]
        row = atual[atual["tomador_cnpj"] == cnpj]
        if "unicidade" in item:
            esperado = item["unicidade"]
            casos.append({
                "tipo": "nota_unicidade",
                "tomador_cnpj": cnpj,
                "esperado_count": esperado,
                "encontrado_count": int(len(row)),
                "status": _acerto(len(row) == esperado),
                "fonte_regra": item.get("fonte_regra"),
            })
        if "valor_brl" in item:
            esperado_valor = _d(item["valor_brl"])
            encontrado_valor = None if row.empty else _d(row["valor_brl"].iloc[0])
            casos.append({
                "tipo": "nota_valor",
                "tomador_cnpj": cnpj,
                "esperado": str(esperado_valor),
                "encontrado": None if encontrado_valor is None else str(encontrado_valor),
                "status": _acerto(encontrado_valor is not None and encontrado_valor == esperado_valor),
                "fonte_regra": item.get("fonte_regra"),
            })
    return casos


def _comparar_pendencias(ref: list[dict], atual: pd.DataFrame) -> list[dict]:
    casos: list[dict] = []
    for item in ref:
        tipo = item["tipo"]
        subset = atual[atual["tipo"] == tipo]
        if "ref_origem" in item:
            achou = (subset["ref_origem"] == item["ref_origem"]).any()
            casos.append({
                "tipo": "pendencia_presenca",
                "tipo_pendencia": tipo,
                "ref_origem": item["ref_origem"],
                "status": _acerto(bool(achou)),
                "fonte_regra": item.get("fonte_regra"),
            })
            continue
        if "count_minimo" in item:
            casos.append({
                "tipo": "pendencia_count",
                "tipo_pendencia": tipo,
                "esperado_count_minimo": item["count_minimo"],
                "encontrado_count": int(len(subset)),
                "status": _acerto(len(subset) >= item["count_minimo"]),
                "fonte_regra": item.get("fonte_regra"),
            })
            continue
        if "valor_brl" in item:
            cnpj = item.get("cnpj")
            matches = subset
            if cnpj and "cnpj" in matches.columns:
                matches = matches[matches["cnpj"] == cnpj]
            esperado = _d(item["valor_brl"])
            achou = ((matches["valor_brl"].apply(_d) == esperado).any())
            casos.append({
                "tipo": "pendencia_valor",
                "tipo_pendencia": tipo,
                "esperado": str(esperado),
                "status": _acerto(bool(achou)),
                "fonte_regra": item.get("fonte_regra"),
            })
    return casos


def avaliar(resultado: ClosingResult, referencia: dict) -> dict:
    """Compara `resultado` com `referencia` e devolve dict pronto para JSON."""
    casos: list[dict] = []
    casos += _comparar_comissoes(referencia.get("comissoes", []), resultado.comissoes)
    casos += _comparar_divergencias(referencia.get("divergencias", []), resultado.divergencias)
    casos += _comparar_notas(referencia.get("notas", []), resultado.notas)
    casos += _comparar_pendencias(referencia.get("pendencias", []), resultado.pendencias)

    total = len(casos)
    acertos = sum(1 for c in casos if c["status"] == "ok")

    # Métricas globais (num/den), sem assumir 100% implícito.
    classif_total = len(resultado.lancamentos)
    classif_com_conta = int(resultado.lancamentos["conta_codigo"].notna().sum()) if classif_total else 0

    rastro_total_saidas = (
        len(resultado.comissoes) + len(resultado.divergencias) + len(resultado.notas)
        + len(resultado.lancamentos) + len(resultado.pendencias)
    )
    rastro_falhas = len(resultado.problemas_rastro)

    return {
        "competencia": resultado.competencia,
        "execucao_id": resultado.execucao_id,
        "resumo": {
            "casos_referencia_total": total,
            "casos_referencia_ok": acertos,
            "classificacao_num": classif_com_conta,
            "classificacao_den": classif_total,
            "rastro_falhas": rastro_falhas,
            "rastro_total_saidas": rastro_total_saidas,
            "integridade_global_problemas": resultado.problemas_integridade,
        },
        "casos": casos,
    }


def avaliar_e_persistir(
    resultado: ClosingResult,
    *,
    fixtures_dir: Path,
    saida: Path,
) -> dict | None:
    """Lê referência, avalia, grava `avaliacao.json` em `out_dir`. Retorna o dict."""
    ref = carregar_referencia(fixtures_dir, resultado.competencia)
    if ref is None:
        return None
    report = avaliar(resultado, ref)
    (resultado.out_dir / "avaliacao.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    # mantém o `saida` só para interface simétrica caso o chamador queira
    return report
