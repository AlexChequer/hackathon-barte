"""Do que cada frente do fechamento depende (R34: arquivo faltando não segura o mês inteiro).

Uma frente sem os arquivos de que precisa não roda e vira pendência FRENTE_BLOQUEADA, dizendo
o que falta e o que deixou de sair. As outras fecham normalmente.
"""

from __future__ import annotations

from decimal import Decimal

import pandas as pd

from tarvo.engines import EngineResult

NOME_ARQUIVO = {
    "orbe": "Relatório da Orbe",
    "taxas": "Tabela de taxas contratadas",
    "ponte": "Relatório de remessas (Ponte Câmbio)",
    "plano": "Plano de contas",
    "aurora": "Extrato Aurora",
    "meridiano": "Extrato Meridiano",
}

FRENTES = {
    "checkout": {
        "precisa": ["orbe", "taxas"],
        "nao_sai": ("comissões e notas de checkout, divergências da Orbe, contestação da Orbe, "
                    "devolução da Casa, alerta de antecipação e sinais da planilha"),
    },
    "remessa": {
        "precisa": ["ponte", "taxas"],
        "nao_sai": "comissões de remessa, nota da Ponte, divergências de spread e contestação dos negativos",
    },
    "extratos": {
        "precisa": ["plano"],
        "algum_de": ["aurora", "meridiano"],
        "nao_sai": "lançamentos classificados",
    },
}


def bloqueios(presentes: set[str]) -> list[dict]:
    """Frentes que não fecham por completo com os arquivos presentes, na ordem de FRENTES."""
    resultado = []
    for frente, regra in FRENTES.items():
        faltando = [a for a in regra["precisa"] if a not in presentes]
        alternativos = regra.get("algum_de", [])
        presentes_alt = [a for a in alternativos if a in presentes]
        if faltando or (alternativos and not presentes_alt):
            faltando = faltando + ([] if presentes_alt else alternativos)
            resultado.append({"frente": frente, "faltando": faltando, "parcial": False,
                              "nao_sai": regra["nao_sai"]})
        elif alternativos and len(presentes_alt) < len(alternativos):
            ausentes = [a for a in alternativos if a not in presentes]
            resultado.append({
                "frente": frente, "faltando": ausentes, "parcial": True,
                "nao_sai": "lançamentos de " + ", ".join(NOME_ARQUIVO[a] for a in ausentes)
                           + " e a conferência de transferência entre contas (precisa dos dois bancos)",
            })
    return resultado


def roda(frente: str, presentes: set[str]) -> bool:
    return not any(b["frente"] == frente and not b["parcial"] for b in bloqueios(presentes))


def pendencias_bloqueio(lista: list[dict], competencia: str) -> EngineResult:
    """Uma pendência por frente bloqueada (valor zero, rastro apontando o arquivo ausente)."""
    pendencias, rastro = [], []
    for b in lista:
        pend_id = f"BLOQ-{b['frente'].upper()}-{competencia}"
        nomes = ", ".join(NOME_ARQUIVO[a] for a in b["faltando"])
        estado = "fechou em parte" if b["parcial"] else "não fechou"
        pendencias.append({
            "id_saida": pend_id,
            "tipo": "FRENTE_BLOQUEADA",
            "ref_origem": "|".join(b["faltando"]),
            "valor_brl": Decimal("0.00"),
            "motivo": (f"Frente {b['frente']} {estado}: falta {nomes}. Não saiu: {b['nao_sai']}. "
                       "Envie o arquivo e feche de novo (R34)."),
            "quem_decide": "Financeiro",
        })
        rastro.append({"id_saida": pend_id, "arquivo_origem": "|".join(b["faltando"]),
                       "ref_origem": "arquivo ausente", "valor": Decimal("0.00"),
                       "metadata": "pendencia_FRENTE_BLOQUEADA"})
    return EngineResult(pendencias=pd.DataFrame(pendencias), rastro=pd.DataFrame(rastro))
