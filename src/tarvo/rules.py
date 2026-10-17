"""Constantes de negócio reunidas num único lugar.

Toda referência aqui aponta para a resposta/premissa de `HIPOTESES.md` que a autoriza.
Mudança de regra implica bump de VERSION para a persistência marcar execuções antigas.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

VERSION = "2026-10-17.1"

# R3: de-para EC Orbe → CNPJ, confirmado pela Helena. Taxas e vigências vêm das
# linhas da planilha com esse CNPJ (em runtime); o nome do lojista não é usado.
EC_PARA_CNPJ = {
    "1043300981": "66564512000199",  # Novo Horizonte Intercâmbio
    "1043396662": "78576234000179",  # Horizonte Viagens e Turismo
    "1038867654": "07752116000126",  # Kiwi Experience
}

# R3 + P10: Atlas (1076801732) não tem contrato vigente.
EC_SEM_CONTRATO = {"1076801732": "ATLAS IDIOMAS"}

# R6 + P6: Casa do Estudante tem tarifa 0% em MDR e antecipação de 01/09 a 31/12/2026.
# Estorno de venda anterior usa a taxa histórica da linha vigente.
CASA_ESTUDANTE_EC = "1018325654"
CASA_ESTUDANTE_INICIO = dt.date(2026, 9, 1)
CASA_ESTUDANTE_FIM = dt.date(2026, 12, 31)

# R5: Ponte Câmbio – spread padrão (vazio ou texto "padrão" na planilha) = 1,5%.
SPREAD_PADRAO = Decimal("0.015")

# R5 + P12: as 4 operações negativas de setembro ficam fora da comissão/nota (contestação).
# Não é regra automática para competências futuras.
PONTE_NEGATIVOS_EXCLUIR_SET2026 = {"PC-0926-0210", "PC-0926-0326", "PC-0926-0491", "PC-0926-0545"}

# R4: tomador da nota de remessa é a Ponte Câmbio.
PONTE_CNPJ = "75374179000146"
PONTE_NOME = "Ponte Câmbio S.A."

# P7: tolerância de 0,01 ponto percentual (0.0001 em fração) para divergência de remessa.
TOLERANCIA_REMESSA_FRACAO = Decimal("0.0001")

# R9: tabela de contrapartida para despesas que vão direto no mês.
CONTA_DESPESAS_DIRETAS = {
    "tarifa": "4.2.01",
    "condominio": "4.2.02",
    "aluguel": "4.2.02",
    "cloud": "4.2.03",
    "assinatura": "4.2.04",
    "seguro": "4.2.05",
    "contabilidade": "4.2.06",
    "iof": "4.3.01",
}

# R6: baixa de passivos/recebível (competências de agosto já provisionadas).
CONTA_BAIXA_PASSIVO = {
    "folha": "2.1.04.001",
    "inss": "2.1.04.002",
    "fgts": "2.1.04.003",
    "iss": "2.1.03.003",
    "pis": "2.1.03.001",
    "cofins": "2.1.03.002",
    "irrf": "2.1.03.004",
    "repasse_ponte_08": "1.1.03.002",
}

# Classificações por natureza de movimento (regra determinística).
CONTA_RECEBIMENTO_ORBE = "1.1.03.001"
CONTA_TRANSFERENCIA_PROPRIA = "1.1.09.001"
CONTA_REPASSE_A_LOJISTA = "2.1.01.001"
CONTA_DEVOLUCAO_A_LOJISTA = "2.1.01.002"
CONTA_RECURSO_LOJISTA_REMESSA = "2.1.02.001"
CONTA_CDB = "1.1.02.001"
CONTA_RENDIMENTO = "3.2.01"
CONTA_IOF = "4.3.01"
CONTA_NAO_IDENTIFICADO = "1.1.09.002"

# "APROVADO C/ RESSALVA" entra normalmente (R5).
PONTE_STATUS_VALIDOS = {"APROVADO", "APROVADO C/ RESSALVA"}
