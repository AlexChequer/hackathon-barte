"""Fechamento contra a fonte: o total de cada arquivo de entrada é explicado pelas saídas.

O rastro garante que cada número aponta para linhas de origem. Isto garante o sentido inverso:
somando o que cada linha de origem virou nas saídas, chega-se ao total do arquivo, com a sobra
explicada (truncamento da Orbe, arredondamento por operação da Ponte). Sobra fora da tolerância
é número perdido ou contado duas vezes, e a execução falha (`FECHAMENTO_NAO_BATE`).

Grava `controle_fechamento.json` só no histórico da execução: `saida/` da raiz é só dos 6 CSVs.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

import pandas as pd

from tarvo.loaders.orbe import ARQUIVO_PENDENTES
from tarvo.money import ZERO, q, sum_q

# Orbe: em que parte do fechamento o valor cobrado de cada transação foi parar. A ordem importa
# (prefixo mais longo antes do mais curto: CK-COND-PEND antes de CK-COND).
COMPONENTES_ORBE = (
    ("CK-COND-PEND-", "devolucao_condicao_comercial"),
    ("CK-CM-", "comissao_contratada"),
    ("CK-DIV-", "divergencia_orbe"),
    ("CK-SEMCONTRATO-", "pendencia_sem_contrato"),
    ("CK-SEMCAD-", "pendencia_por_transacao"),
    ("CK-VIG-", "pendencia_por_transacao"),
    ("CK-SEMTAX-", "pendencia_por_transacao"),
    ("CK-REVSEMREF-", "pendencia_por_transacao"),
    ("CK-FORA-", "pendencia_por_transacao"),
    ("CK-DUPCONF-", "pendencia_por_transacao"),
)
# Saídas que detalham, repetem ou alertam sobre números já contados acima.
DERIVADAS_ORBE = ("CK-COND-", "CK-NT-", "CK-NTNEG-", "CK-NTZERO-", "CK-CONTEST-", "CK-ALERTA-ANT-")
# Arquivos da Orbe: o relatório, os ajustes tardios e as transações guardadas de meses anteriores (R18).
ARQUIVOS_ORBE = ("orbe", "orbe_ajustes", ARQUIVO_PENDENTES)
# A Orbe trunca (até -0,01) e a Tarvo arredonda comissão e divergência separadas (até ±0,005 cada).
TOLERANCIA_ORBE_POR_TRANSACAO = Decimal("0.02")


def _s(v: Decimal) -> str:
    return format(v, "f")


def _categoria(id_saida: str) -> str | None:
    for prefixo, categoria in COMPONENTES_ORBE:
        if id_saida.startswith(prefixo):
            return categoria
    return "derivada" if id_saida.startswith(DERIVADAS_ORBE) else None


def ponte_orbe(orbe: pd.DataFrame, rastro: pd.DataFrame) -> tuple[dict, list[dict]]:
    """Σ valor_taxa da Orbe = comissão + divergência + devolução + pendências + truncamento."""
    cobrado = defaultdict(lambda: ZERO)
    linhas = defaultdict(list)
    for id_tx, valor in zip(orbe["id_transacao"].astype(str), orbe["valor_taxa"], strict=True):
        cobrado[id_tx] += q(valor or ZERO)
        linhas[id_tx].append(q(valor or ZERO))

    da_orbe = rastro[rastro["arquivo_origem"].isin(ARQUIVOS_ORBE)] if not rastro.empty else rastro
    explicado = defaultdict(lambda: ZERO)
    por_categoria = defaultdict(lambda: ZERO)
    com_dupconf, sem_categoria = set(), set()
    for id_saida, ref, valor in zip(da_orbe["id_saida"], da_orbe["ref_origem"].astype(str), da_orbe["valor"],
                                    strict=True):
        categoria = _categoria(id_saida)
        if categoria is None:
            sem_categoria.add(id_saida)
        elif categoria != "derivada":
            explicado[ref] += valor
            por_categoria[categoria] += valor
            com_dupconf |= {ref} if id_saida.startswith("CK-DUPCONF-") else set()

    # R24.1: id repetido com os mesmos dados entra 1×. As cópias não viram saída nenhuma.
    for id_tx, valores in linhas.items():
        if len(valores) > 1 and id_tx not in com_dupconf:
            extra = sum_q(valores[1:])
            explicado[id_tx] += extra
            por_categoria["duplicata_resolvida"] += extra

    residuos = {id_tx: cobrado[id_tx] - explicado[id_tx] for id_tx in cobrado}
    fora = {i: r for i, r in residuos.items() if abs(r) > TOLERANCIA_ORBE_POR_TRANSACAO}
    orfas = sorted(set(explicado) - set(cobrado))
    total = sum_q(cobrado.values())
    truncamento = sum_q(residuos.values())
    relatorio = {
        "linhas": len(orbe),
        "transacoes": len(cobrado),
        "cobrado_pela_orbe": _s(total),
        "explicado_por": {k: _s(v) for k, v in sorted(por_categoria.items())},
        "truncamento_da_orbe": _s(truncamento),
        "tolerancia_por_transacao": _s(TOLERANCIA_ORBE_POR_TRANSACAO),
        "maior_sobra_por_transacao": _s(max((abs(r) for r in residuos.values()), default=ZERO)),
        "fecha": not fora and not orfas and not sem_categoria,
    }
    problemas = []
    if fora:
        problemas.append({"codigo": "FECHAMENTO_NAO_BATE", "fonte": "orbe", "qtd": len(fora),
                          "exemplos": {i: _s(r) for i, r in list(fora.items())[:10]}})
    if orfas:
        problemas.append({"codigo": "FECHAMENTO_NAO_BATE", "fonte": "orbe", "refs_sem_linha": orfas[:10]})
    if sem_categoria:
        problemas.append({"codigo": "RASTRO_SEM_CATEGORIA", "fonte": "orbe",
                          "ids": sorted(sem_categoria)[:10]})
    return relatorio, problemas


def ponte_ponte(ponte: pd.DataFrame, rastro: pd.DataFrame, competencia: str) -> tuple[dict, list[dict]]:
    """50% do spread declarado = nota + linhas fora da nota (RM-CONTEST) + arredondamento por operação."""
    spreads = [v for v in ponte["spread_brl"].tolist() if v is not None]
    por_linha = sum_q(q(v * Decimal("0.5")) for v in spreads)
    declarado = q(sum_q(spreads) * Decimal("0.5"))

    def soma(id_saida: str) -> Decimal:
        if rastro.empty:
            return ZERO
        return sum_q(rastro.loc[rastro["id_saida"] == id_saida, "valor"])

    nota, fora_da_nota = soma(f"RM-NT-{competencia}-PONTE"), soma(f"RM-CONTEST-{competencia}")
    sobra = por_linha - nota - fora_da_nota
    relatorio = {
        "linhas": len(ponte),
        "spread_declarado": _s(sum_q(spreads)),
        "metade_do_declarado": _s(declarado),
        "metade_por_operacao": _s(por_linha),
        "arredondamento_por_operacao": _s(declarado - por_linha),
        "nota": _s(nota),
        "fora_da_nota": _s(fora_da_nota),
        "fecha": sobra == ZERO,
    }
    problemas = [] if sobra == ZERO else [
        {"codigo": "FECHAMENTO_NAO_BATE", "fonte": "ponte", "sobra": _s(sobra)}]
    return relatorio, problemas


def ponte_banco(banco: str, extrato: pd.DataFrame, lancamentos: pd.DataFrame) -> tuple[dict, list[dict]]:
    """Todo movimento do extrato vira um lançamento, e o saldo corrido do extrato confere linha a linha."""
    nosso = lancamentos[lancamentos["banco"] == banco.upper()] if not lancamentos.empty else lancamentos
    total_extrato, total_lancado = sum_q(extrato["valor"]), sum_q(nosso["valor"]) if len(nosso) else ZERO
    quebras = []
    if "saldo" in extrato and len(extrato):
        anterior = None
        for ref, valor, saldo in zip(extrato["ref_origem"], extrato["valor"], extrato["saldo"], strict=True):
            if saldo is None:
                anterior = None
                continue
            if anterior is not None and anterior + valor != saldo:
                quebras.append(ref)
            anterior = saldo
    relatorio = {
        "movimentos_no_extrato": len(extrato),
        "lancamentos": len(nosso),
        "soma_extrato": _s(total_extrato),
        "soma_lancamentos": _s(total_lancado),
        "saldo_corrido": ("conferido linha a linha" if "saldo" in extrato
                          else "o arquivo não traz saldo por linha"),
        "fecha": len(extrato) == len(nosso) and total_extrato == total_lancado and not quebras,
    }
    problemas = [] if relatorio["fecha"] else [{
        "codigo": "FECHAMENTO_NAO_BATE", "fonte": banco, "movimentos": len(extrato),
        "lancamentos": len(nosso), "diferenca": _s(total_extrato - total_lancado),
        "saldo_quebra_em": quebras[:10]}]
    return relatorio, problemas
