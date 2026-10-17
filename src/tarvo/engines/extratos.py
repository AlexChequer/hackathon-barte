"""Motor EXTRATOS: classifica Aurora/Meridiano no plano de contas via regra determinística.

Regras: R6 (baixa de passivo/recebível para competências provisionadas) e R9 (contrapartida,
só contas analíticas que aceitam lançamento). Casos sem regra viram pendência com
`conta_codigo=None` e `confianca=0`, nunca ganham conta inventada.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pandas as pd

from tarvo import rules
from tarvo.engines import EngineResult
from tarvo.money import q

CONFIANCA_REGRA = Decimal("1.00")
CONFIANCA_PENDENTE = Decimal("0.00")


def _classifica_aurora(row: pd.Series) -> dict:
    """Classifica uma linha do Aurora. Retorna dict com conta, metodo, motivo e opcional pendência."""
    desc = (row["descricao"] or "").upper()
    data = row["data"]
    # Entradas da Orbe (TED RECEBIDA ... ORBE ADQUIRENCIA)
    if "TED RECEBIDA" in desc and "ORBE" in desc:
        return _res(rules.CONTA_RECEBIMENTO_ORBE, motivo="Recebimento TED da Orbe (R9).")
    # Transferência entre contas próprias (Aurora → Meridiano)
    if "TRANSF ENTRE CONTAS" in desc and "MERIDIANO" in desc:
        pend = None
        # Transferência em 30/09 ainda não cai no Meridiano em setembro (R6: cai em 01/10).
        if isinstance(data, dt.date) and data == dt.date(2026, 9, 30):
            pend = {
                "tipo": "TRANSFERENCIA_EM_TRANSITO",
                "motivo": "Saída de 300.000 em 30/09 só credita no Meridiano em 01/10. Mantém em trânsito.",
                "quem_decide": "Financeiro",
            }
        return _res(rules.CONTA_TRANSFERENCIA_PROPRIA,
                    motivo="Transferência entre contas próprias (Aurora→Meridiano).", pendencia=pend)
    # Folha salários agosto (R6 → baixa 2.1.04.001)
    if "PAGTO SALARIOS" in desc or "FOLHA" in desc:
        return _res(rules.CONTA_BAIXA_PASSIVO["folha"],
                    motivo="Baixa de folha de agosto já provisionada (R6).")
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
            return _res(codigo, motivo=f"Baixa de obrigação fiscal de agosto já provisionada ({chave}, R6).")
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
                        "motivo": "Devolução PIX Mundo Aberto; motivo da devolução não identificado (R6).",
                        "quem_decide": "Financeiro",
                    })
    # PIX RECEBIDO sem identificação (R6)
    if "PIX RECEBIDO" in desc and "SEM IDENTIFICACAO" in desc:
        return _res(rules.CONTA_NAO_IDENTIFICADO,
                    motivo="PIX recebido sem identificação (R6, aguardar identificação).",
                    pendencia={
                        "tipo": "PIX_NAO_IDENTIFICADO",
                        "motivo": (
                            "PIX recebido sem identificação: fica em créditos não"
                            " identificados até alguém reconhecer."
                        ),
                        "quem_decide": "Financeiro",
                    })
    # PIX ENVIADO (repasse a lojista) — classificação padrão
    if "PIX ENVIADO" in desc:
        return _res(rules.CONTA_REPASSE_A_LOJISTA, motivo="PIX de repasse a lojista.")
    return _sem_regra(row)


def _classifica_meridiano(row: pd.Series) -> dict:
    desc = (row["descricao"] or "").upper()
    # TED RECEB da própria Tarvo (chegada de transferência entre contas)
    if "TED RECEBIDA" in desc and ("TARVO PAGAMENTOS" in desc or "MESMA TITULARIDADE" in desc):
        return _res(rules.CONTA_TRANSFERENCIA_PROPRIA,
                    motivo="Chegada de transferência entre contas próprias (R9).")
    # TED RECEB PONTE CAMBIO REPASSE COMISSAO 08/2026 (R6)
    if "TED RECEB PONTE CAMBIO" in desc and "REPASSE COMISSAO 08/2026" in desc:
        return _res(rules.CONTA_BAIXA_PASSIVO["repasse_ponte_08"],
                    motivo="Baixa de comissão de câmbio 08/2026 já provisionada (R6).")
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


def run(aurora: pd.DataFrame, meridiano: pd.DataFrame, plano: pd.DataFrame, competencia: str) -> EngineResult:
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
            "confianca": cls["confianca"],
            "motivo": cls["motivo"],
        })
        rastros.append({
            "id_saida": id_saida,
            "arquivo_origem": banco.lower(),
            "ref_origem": ref,
            "valor": row["valor"],
            "metadata": f"classificacao={conta or 'PENDENTE'};metodo={cls['metodo']}",
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

    for _, row in aurora.iterrows():
        _emit("AURORA", row, _classifica_aurora(row))
    for _, row in meridiano.iterrows():
        _emit("MERIDIANO", row, _classifica_meridiano(row))

    result.lancamentos = pd.DataFrame(lancamentos)
    result.pendencias = pd.DataFrame(pendencias)
    result.rastro = pd.DataFrame(rastros)
    return result
