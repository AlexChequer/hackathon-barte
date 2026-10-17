"""Constantes de negócio reunidas num único lugar.

Toda referência aqui aponta para a resposta/premissa de `HIPOTESES.md` que a autoriza.
Mudança de regra implica bump de VERSION para a persistência marcar execuções antigas.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

VERSION = "2026-10-17.3"

# R3: de-para EC Orbe → CNPJ e ECs sem contrato vêm de config/cadastro_ec.json (fonte e quem aprovou
# em cada item). EC novo confirmado pelo financeiro entra no JSON, não no código. Taxas e vigências vêm
# das linhas da planilha com esse CNPJ (em runtime); o nome do lojista nunca é usado para casar.
CAMINHO_CADASTRO_EC = Path(__file__).resolve().parents[2] / "config" / "cadastro_ec.json"


def carregar_cadastro_ec(caminho: Path = CAMINHO_CADASTRO_EC) -> tuple[dict[str, str], dict[str, dict]]:
    """(EC → CNPJ confirmado, EC sem contrato → identidade). Arquivo ausente = nenhum cadastro extra."""
    if not caminho.exists():
        return {}, {}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    para_cnpj = {str(ec): item["cnpj"] for ec, item in dados.get("ec_para_cnpj", {}).items()}
    sem_contrato = {str(ec): dict(item) for ec, item in dados.get("ec_sem_contrato", {}).items()}
    return para_cnpj, sem_contrato


# R3 + P10 + R30: EC sem contrato vigente → não fatura, 1 pendência por lojista para o Comercial (R24.1),
# enquanto a planilha não tiver linha vigente para ele (R18). CNPJ só como identidade, nunca para taxa.
EC_PARA_CNPJ, EC_SEM_CONTRATO = carregar_cadastro_ec()

# R6: condições comerciais fora da planilha (ex.: isenção da Casa do Estudante) ficam em
# config/condicoes_comerciais.json, lidas por tarvo.condicoes.

# R5: Ponte Câmbio – spread padrão (vazio ou texto "padrão" na planilha) = 1,5%.
SPREAD_PADRAO = Decimal("0.015")

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

# R6/R9: baixa de passivos/recebível de competências anteriores já provisionadas.
CONTA_BAIXA_PASSIVO = {
    "folha": "2.1.04.001",
    "inss": "2.1.04.002",
    "fgts": "2.1.04.003",
    "iss": "2.1.03.003",
    "pis": "2.1.03.001",
    "cofins": "2.1.03.002",
    "irrf": "2.1.03.004",
    "repasse_ponte": "1.1.03.002",
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
