"""Motor EXTRATOS: classifica Aurora/Meridiano no plano de contas via regra determinística.

Regras: R6 (baixa de passivo/recebível para competências provisionadas) e R9 (contrapartida,
só contas analíticas que aceitam lançamento). Casos sem regra viram pendência com
`conta_codigo=None` e `confianca=0`, nunca ganham conta inventada.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pandas as pd

from tarvo import rules
from tarvo.engines import EngineResult
from tarvo.money import brl, q

CONFIANCA_REGRA = Decimal("1.00")
CONFIANCA_PENDENTE = Decimal("0.00")
# Conta dada pela regra, mas provisória: a linha abriu pendência (ex.: PIX sem identificação, R6).
CONFIANCA_PROVISORIA = Decimal("0.50")


def _classifica_aurora(row: pd.Series) -> dict:
    """Classifica uma linha do Aurora. Retorna dict com conta, metodo, motivo e opcional pendência."""
    desc = (row["descricao"] or "").upper()
    # Entradas da Orbe (TED RECEBIDA ... ORBE ADQUIRENCIA)
    if "TED RECEBIDA" in desc and "ORBE" in desc:
        return _res(rules.CONTA_RECEBIMENTO_ORBE, motivo="Recebimento TED da Orbe (R9).")
    # Transferência entre contas próprias (Aurora → Meridiano)
    if _eh_saida_transferencia_propria(desc):
        # A pendência de "em trânsito" é decidida no run(), cruzando com o outro banco.
        return _res(rules.CONTA_TRANSFERENCIA_PROPRIA,
                    motivo="Transferência entre contas próprias (Aurora→Meridiano).")
    # Folha do mês anterior (R6 → baixa 2.1.04.001)
    if "PAGTO SALARIOS" in desc or "FOLHA" in desc:
        return _res(rules.CONTA_BAIXA_PASSIVO["folha"],
                    motivo="Baixa de folha do mês anterior já provisionada (R6).")
    # Impostos/contribuições baixa de passivo
    for chave, codigo in [
        ("INSS", rules.CONTA_BAIXA_PASSIVO["inss"]),
        ("FGTS", rules.CONTA_BAIXA_PASSIVO["fgts"]),
        ("ISS", rules.CONTA_BAIXA_PASSIVO["iss"]),
        ("DARF 0561", rules.CONTA_BAIXA_PASSIVO["irrf"]),
        ("DARF 8109", rules.CONTA_BAIXA_PASSIVO["pis"]),
        ("DARF 2172", rules.CONTA_BAIXA_PASSIVO["cofins"]),
    ]:
        if chave in desc:
            return _res(codigo,
                        motivo=f"Baixa de obrigação fiscal do mês anterior já provisionada ({chave}, R6).")
    # Despesas administrativas diretas (R9)
    if "TAR " in desc or "TARIFA" in desc or "TAR PACOTE" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["tarifa"], motivo="Tarifa bancária (despesa direta, R9).")
    if "CONDOMINIO" in desc or "ALUGUEL" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["condominio"], motivo="Aluguel/condomínio (R9).")
    if "AMAZON WEB SERVICES" in desc or "AWS" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["cloud"], motivo="Cloud (R9).")
    if "GOOGLE WORKSPACE" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["assinatura"], motivo="Assinatura software (R9).")
    if "CONTABILIDADE" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["contabilidade"], motivo="Serviços contábeis (R9).")
    if "SEGURO" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["seguro"], motivo="Seguro (R9).")
    # Devolução Mundo Aberto - pendência (R6).
    if "DEVOLUCAO PIX" in desc and "MUNDO ABERTO" in desc:
        return _res(rules.CONTA_REPASSE_A_LOJISTA,
                    motivo="Devolução de PIX de repasse (R6, aguardar motivo com o lojista).",
                    pendencia={
                        "tipo": "DEVOLUCAO_LOJISTA_SEM_MOTIVO",
                        "motivo": (f"Devolução de PIX de repasse da Mundo Aberto, {brl(row['valor'])} em "
                                   f"{row['data']:%d/%m/%Y}, sem motivo informado. O repasse volta a ser "
                                   "devido ao lojista (R6, P17)."),
                        "quem_decide": "Financeiro",
                    })
    # PIX RECEBIDO sem identificação (R6)
    if "PIX RECEBIDO" in desc and "SEM IDENTIFICACAO" in desc:
        return _res(rules.CONTA_NAO_IDENTIFICADO,
                    motivo="PIX recebido sem identificação (R6, aguardar identificação).",
                    pendencia={
                        "tipo": "PIX_NAO_IDENTIFICADO",
                        "motivo": (
                            f"PIX recebido de {brl(row['valor'])} em {row['data']:%d/%m/%Y} sem identificação"
                            f"{_pagador(desc)}. Não é receita até alguém reconhecer: fica em créditos não "
                            "identificados (R6)."
                        ),
                        "quem_decide": "Financeiro",
                    })
    # PIX ENVIADO (repasse a lojista) — classificação padrão
    if "PIX ENVIADO" in desc:
        return _res(rules.CONTA_REPASSE_A_LOJISTA, motivo="PIX de repasse a lojista.")
    return _sem_regra(row)


def _pagador(desc: str) -> str:
    """CNPJ do pagador quando o extrato traz (14 dígitos na descrição), formatado."""
    if m := re.search(r"\b(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})\b", desc):
        return f" (CNPJ do pagador no extrato: {m[1]}.{m[2]}.{m[3]}/{m[4]}-{m[5]})"
    return ""


def _classifica_meridiano(row: pd.Series) -> dict:
    desc = (row["descricao"] or "").upper()
    # TED RECEB da própria Tarvo (chegada de transferência entre contas)
    if _eh_chegada_transferencia_propria(desc):
        return _res(rules.CONTA_TRANSFERENCIA_PROPRIA,
                    motivo="Chegada de transferência entre contas próprias (R9).")
    # Repasse da Ponte de comissão de mês anterior ao lançamento → baixa do recebível (R6, R9)
    if "TED RECEB PONTE CAMBIO" in desc and (ref := _mes_referencia_repasse(desc)):
        mes, ano = ref
        data = row["data"]
        if (ano, mes) < (data.year, data.month):
            return _res(rules.CONTA_BAIXA_PASSIVO["repasse_ponte"],
                        motivo=f"Baixa de comissão de câmbio {mes:02d}/{ano} já provisionada (R6).")
    # PIX RECEB PONTE AÉREA ESTUDANTIL = lojista (não Ponte Câmbio)
    if "PIX RECEB" in desc and "PONTE AEREA" in _ascii(desc):
        return _res(rules.CONTA_RECURSO_LOJISTA_REMESSA,
                    motivo="Recurso de lojista Ponte Aérea (não é Ponte Câmbio) para liquidação de remessa.")
    # Qualquer outro PIX RECEB = recurso de lojista para remessa
    if "PIX RECEB" in desc:
        return _res(rules.CONTA_RECURSO_LOJISTA_REMESSA,
                    motivo="Recurso de lojista para liquidação de remessa.")
    # TED ENVIADA à Ponte Câmbio = saída de recurso para liquidação (baixa 2.1.02.001)
    if "TED ENVIADA PONTE CAMBIO" in desc:
        return _res(
            rules.CONTA_RECURSO_LOJISTA_REMESSA,
            motivo=(
                "TED à Ponte Câmbio para liquidação de operações "
                "(contrapartida de recursos de lojista)."
            ),
        )
    # Aplicação/resgate CDB (não é receita; é 1.1.02.001)
    if "APLICACAO AUTOMATICA" in desc or "RESGATE AUTOMATICO" in desc:
        return _res(rules.CONTA_CDB, motivo="Movimentação CDB/aplicação automática (R9).")
    # Rendimento
    if "RENDIMENTO" in desc:
        return _res(rules.CONTA_RENDIMENTO, motivo="Rendimento de aplicação (R9).")
    # IOF
    if "IOF" in desc:
        return _res(rules.CONTA_IOF, motivo="IOF (R9).")
    # Tarifas (TARIFA PACOTE CAMBIO, TARIFA MANUTENCAO CONTA PJ)
    if "TARIFA" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["tarifa"], motivo="Tarifa bancária (despesa direta, R9).")
    # Seguro
    if "SEGURO" in desc:
        return _res(rules.CONTA_DESPESAS_DIRETAS["seguro"], motivo="Seguro (R9).")
    return _sem_regra(row)


def _ascii(s: str) -> str:
    """Normaliza acentos para comparação robusta ('PONTE AÉREA' == 'PONTE AEREA')."""
    return (
        s.replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O")
         .replace("Ú", "U").replace("Â", "A").replace("Ê", "E").replace("Ô", "O")
         .replace("Ã", "A").replace("Õ", "O").replace("Ç", "C")
    )


def _mes_referencia_repasse(desc: str) -> tuple[int, int] | None:
    """'... REPASSE COMISSAO 08/2026' → (8, 2026)."""
    m = re.search(r"REPASSE COMISSAO (\d{2})/(\d{4})", desc)
    return (int(m.group(1)), int(m.group(2))) if m else None


def _eh_saida_transferencia_propria(desc: str) -> bool:
    return "TRANSF ENTRE CONTAS" in desc and "MERIDIANO" in desc


def _eh_chegada_transferencia_propria(desc: str) -> bool:
    return "TED RECEBIDA" in desc and ("TARVO PAGAMENTOS" in desc or "MESMA TITULARIDADE" in desc)


def _transferencias_em_transito(aurora: pd.DataFrame, meridiano: pd.DataFrame) -> set[str]:
    """Saídas Aurora→Meridiano sem chegada correspondente (mesmo valor, data ≥ saída) no Meridiano.

    Casamento 1-para-1 por valor exato, na ordem das datas. Vale para qualquer mês (R6: a de 30/09
    só cai em 01/10, fora do extrato de setembro).
    """
    chegadas = [
        (r["data"], r["valor"]) for _, r in meridiano.iterrows()
        if _eh_chegada_transferencia_propria((r["descricao"] or "").upper())
    ]
    saidas = sorted(
        ((r["data"], -r["valor"], r["ref_origem"]) for _, r in aurora.iterrows()
         if _eh_saida_transferencia_propria((r["descricao"] or "").upper())),
        key=lambda t: t[0],
    )
    usadas: set[int] = set()
    em_transito: set[str] = set()
    for data_saida, valor, ref in saidas:
        par = next((i for i, (d, v) in enumerate(chegadas)
                    if i not in usadas and v == valor and d >= data_saida), None)
        if par is None:
            em_transito.add(ref)
        else:
            usadas.add(par)
    return em_transito


def _res(conta: str, *, motivo: str, pendencia: dict | None = None) -> dict:
    return {"conta_codigo": conta, "metodo": "REGRA", "confianca": CONFIANCA_REGRA,
            "motivo": motivo, "pendencia": pendencia}


def _sem_regra(row: pd.Series) -> dict:
    return {
        "conta_codigo": None, "metodo": "REGRA", "confianca": CONFIANCA_PENDENTE,
        "motivo": f"Sem regra determinística para '{row['descricao']}'",
        "pendencia": {
            "tipo": "LANCAMENTO_SEM_REGRA",
            "motivo": f"Lançamento '{row['descricao']}' não casou com nenhuma regra determinística.",
            "quem_decide": "Financeiro",
        },
    }


def run(
    aurora: pd.DataFrame, meridiano: pd.DataFrame, plano: pd.DataFrame, competencia: str,
    conferir_transito: bool = True,
) -> EngineResult:
    result = EngineResult()
    aceitas = set(plano[plano["aceita_lancamento"]]["COD_CONTA"])

    lancamentos: list[dict] = []
    pendencias: list[dict] = []
    rastros: list[dict] = []

    def _emit(banco: str, row: pd.Series, cls: dict) -> None:
        ref = row["ref_origem"]
        id_saida = f"EX-LC-{banco}-{ref}"
        conta = cls["conta_codigo"]
        if conta and conta not in aceitas:
            cls = {**cls, "conta_codigo": None, "confianca": CONFIANCA_PENDENTE,
                   "motivo": f"Conta {conta} não aceita lançamento no plano (erro técnico)."}
            conta = None
        lancamentos.append({
            "id_saida": id_saida,
            "banco": banco,
            "ref_origem": ref,
            "data": row["data"],
            "descricao": row["descricao"],
            "valor": row["valor"],
            "conta_codigo": conta,
            "metodo": cls["metodo"],
            "confianca": (CONFIANCA_PROVISORIA if conta and cls.get("pendencia") else cls["confianca"]),
            "motivo": cls["motivo"],
        })
        rastros.append({
            "id_saida": id_saida,
            "arquivo_origem": banco.lower(),
            "ref_origem": ref,
            "valor": row["valor"],
            "metadata": f"classificacao={conta or 'PENDENTE'},metodo={cls['metodo']}",
        })
        pend = cls.get("pendencia")
        if pend:
            pend_id = f"EX-PN-{banco}-{ref}"
            pendencias.append({
                "id_saida": pend_id,
                "tipo": pend["tipo"],
                "ref_origem": ref,
                "valor_brl": q(row["valor"]),
                "motivo": pend["motivo"],
                "quem_decide": pend["quem_decide"],
            })
            rastros.append({
                "id_saida": pend_id,
                "arquivo_origem": banco.lower(),
                "ref_origem": ref,
                "valor": q(row["valor"]),
                "metadata": f"pendencia_{pend['tipo']}",
            })

    # Sem um dos bancos não dá para saber se a transferência chegou (R34: não inventar pendência).
    em_transito = _transferencias_em_transito(aurora, meridiano) if conferir_transito else set()
    for _, row in aurora.iterrows():
        cls = _classifica_aurora(row)
        if row["ref_origem"] in em_transito:
            cls = {**cls, "pendencia": {
                "tipo": "TRANSFERENCIA_EM_TRANSITO",
                "motivo": (f"Saída de {brl(-row['valor'])} para o Meridiano em {row['data']:%d/%m/%Y} sem "
                           "chegada no extrato do Meridiano do mês. Fica em trânsito (R6)."),
                "quem_decide": "Financeiro",
            }}
        _emit("AURORA", row, cls)
    for _, row in meridiano.iterrows():
        _emit("MERIDIANO", row, _classifica_meridiano(row))

    result.lancamentos = pd.DataFrame(lancamentos)
    result.pendencias = pd.DataFrame(pendencias)
    result.rastro = pd.DataFrame(rastros)
    return result
