"""Próximo passo de cada pendência (coluna extra `proximo_passo` em pendencias.csv, P29).

R26 (organização): pendência de acompanhamento não é alarme falso "desde que tenha motivo e
próximo passo". O `motivo` diz o que aconteceu e por quê; aqui fica a ação concreta e com quem.

Um texto por tipo, montado só com os campos da própria pendência. Tipo novo sem entrada aqui
reprova `tests/test_proximo_passo.py`: toda pendência nasce com próximo passo.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pandas as pd

from tarvo.money import ZERO, brl

log = logging.getLogger("tarvo.pendencias")


def _contestacao_orbe(p: dict) -> str:
    if p["valor_brl"] < ZERO:
        return ("Confirmar com a Orbe a cobrança abaixo do contrato e decidir caso a caso (R16.7). "
                "As transações estão no rastro.")
    return (f"Enviar à Orbe as transações do rastro e pedir o estorno de {brl(p['valor_brl'])}. "
            "Ressarcir o lojista (R1, R16.3, R28.1).")


PROXIMO_PASSO: dict[str, Callable[[dict], str]] = {
    # checkout
    "CONTESTACAO_ORBE": _contestacao_orbe,
    "CONDICAO_NAO_INFORMADA_ORBE": lambda p: (
        f"Devolver {brl(p['valor_brl'])} ao lojista, com o Comercial, sem cobrar da Orbe. Atualizar a "
        "planilha e avisar a Orbe da condição para os próximos meses (R16.1, R22, R33)."),
    "CONDICAO_ESPECIAL_A_CONFIRMAR": lambda p: (
        "Comercial confirma se a anotação muda a taxa. Se mudar, registrar a condição na tela "
        "Condições comerciais (taxa por modalidade, início e fim) e fechar de novo (R20)."),
    "SEM_CONTRATO": lambda p: (
        "Diego (Comercial) confirma o contrato e a taxa (R38). Confirmado, o fechamento do mês "
        "seguinte fatura estas transações junto (R18). O repasse ao lojista não para (R25)."),
    "ALERTA_ANTECIPACAO": lambda p: (
        "Helena e Diego (Comercial) confirmam o contrato do lojista antes de liberar novas antecipações "
        "(R16.6, R28.2)."),
    "NOTA_NEGATIVA": lambda p: (
        "Não emitir nota para a Ponte. Helena decide com a Ponte como tratar o saldo do mês (R27)."
        if str(p["id_saida"]).startswith("RM-") else
        "Não emitir nota. Helena trata o saldo com o lojista. O negativo não passa sozinho para o mês "
        "seguinte (R4)."),
    "NOTA_ZERO_INESPERADA": lambda p: (
        "Não emitir nota para a Ponte. Conferir no rastro as operações e os ajustes do mês (R27)."
        if str(p["id_saida"]).startswith("RM-") else
        "Conferir no rastro as transações do lojista antes de decidir se há nota (R4)."),
    "EC_NAO_CADASTRADO": lambda p: (
        "Comercial cadastra o EC na planilha de taxas (CNPJ e taxas) e o fechamento roda de novo (R3)."),
    "VIGENCIA_AUSENTE": lambda p: (
        "Comercial informa a taxa vigente na data da venda e corrige a vigência na planilha. Depois, fechar "
        "de novo."),
    "SEM_TAXA_CONTRATADA": lambda p: (
        "Comercial informa a taxa da modalidade, ou confirma que a venda não é permitida (ex.: acima de "
        "12x, R24.3). Depois, fechar de novo."),
    "REVERSAO_SEM_REFERENCIA": lambda p: (
        "Pedir à Orbe a antecipação que esta reversão anula. Sem ela, a reversão não entra na comissão."),
    # checkout e remessa
    "DUPLICATA_CONFLITANTE": lambda p: (
        "Pedir a quem enviou o relatório qual das linhas vale. Até a resposta, nenhuma entra no fechamento."),
    "FORA_COMPETENCIA": lambda p: (
        "Confirmar com quem enviou o arquivo se a linha é deste mês. Se não for, entra no fechamento do mês "
        "certo."),
    # remessa
    "CONTESTACAO_PONTE": lambda p: (
        f"Contestar com a Ponte as operações do rastro ({brl(p['valor_brl'])}) e ressarcir o lojista. A "
        "nota segue pelo realizado e a nossa metade sai no mês em que a Ponte devolver (R10, R12)."),
    "SPREAD_NEGATIVO_CONTESTAR": lambda p: (
        "Contestar com a Ponte e pedir a diferença até o spread do contrato, que está no motivo (R12, "
        "R28.3). A operação fica fora da comissão e da nota (R5)."),
    "DUPLICATA_RELATORIO_PONTE": lambda p: (
        "Pedir à Ponte que corrija o relatório. No fechamento a operação já conta uma vez (R12)."),
    "DIFERENCA_RELATORIO_PONTE": lambda p: (
        "Conferir o TED de repasse da Ponte quando cair: ele deve bater com a nota, não com 50% do "
        "relatório. Não contar com desconto da Ponte (R11)."),
    "SPREAD_AUSENTE": lambda p: (
        "Pedir à Ponte o Spread R$ da operação. Sem ele, a operação não entra na comissão."),
    "STATUS_DESCONHECIDO": lambda p: (
        "Confirmar com a Ponte o status de compliance. Se a operação valer, fechar de novo."),
    "LOJISTA_REMESSA_SEM_CADASTRO": lambda p: (
        "Comercial cadastra o lojista na planilha de taxas, com o spread de remessa contratado. A "
        "participação já está na nota, e a divergência passa a ser checada no fechamento seguinte (P16)."),
    "SPREAD_CONTRATADO_INVALIDO": lambda p: (
        "Comercial corrige o spread de remessa do lojista na planilha (vazio ou \"padrão\" vale 1,5%, R5)."),
    # extratos
    "PIX_NAO_IDENTIFICADO": lambda p: (
        "Caio identifica o pagador com o banco, pelo CNPJ do extrato, até o fechamento de outubro "
        "(R38). Até lá, fica em créditos não identificados, sem virar receita (R6)."),
    "DEVOLUCAO_LOJISTA_SEM_MOTIVO": lambda p: (
        "Confirmar com o lojista o motivo da devolução e refazer o repasse. Até lá, fica em repasses a "
        "pagar (R6, P17)."),
    "TRANSFERENCIA_EM_TRANSITO": lambda p: (
        "Conferir o crédito no Meridiano no início do mês seguinte e baixar a conta de transferências "
        "entre contas (R6)."),
    "LANCAMENTO_SEM_REGRA": lambda p: (
        "Classificar à mão no plano de contas. Se o lançamento for recorrente, pedir uma regra nova."),
    # fechamento parcial
    "FRENTE_BLOQUEADA": lambda p: (
        "Enviar o arquivo que falta, ou o arquivo no layout esperado, e fechar de novo (R34)."),
}

SEM_TEXTO = "Analisar o motivo e decidir com quem está em quem_decide."


def com_proximo_passo(pendencias: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta `proximo_passo` (depois das colunas obrigatórias, como as outras extras)."""
    if pendencias.empty:
        return pendencias
    sem_texto = sorted(set(pendencias["tipo"]) - set(PROXIMO_PASSO))
    if sem_texto:
        log.warning("pendência sem próximo passo definido: %s", sem_texto)
    passos = [PROXIMO_PASSO[p["tipo"]](p) if p["tipo"] in PROXIMO_PASSO else SEM_TEXTO
              for p in pendencias.to_dict("records")]
    return pendencias.assign(proximo_passo=passos)
