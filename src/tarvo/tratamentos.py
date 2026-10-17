"""Catálogo de ações suportadas pelo motor para resolver pendências.

Cada ação diz:
- `altera_referencia`: muda dados de referência (ex.: taxa, cadastro de EC).
- `altera_calculo`: muda cálculo/classificação do fechamento quando reprocessado.
- `apenas_operacional`: só registra uma providência (não muda número).

Quem aprova depende da R20: Comercial para taxa/condição comercial, Financeiro para
regra de fechamento. A autorização é checada em `autenticacao.exige` antes de o
estado da decisão passar para APROVADA.

Ação não listada aqui = o motor ainda não sabe aplicar. A decisão fica em estado
APROVADA mas com `aplicada=False`; o caso continua aberto com um aviso para a Helena.
"""

from __future__ import annotations

from dataclasses import dataclass

from tarvo.autenticacao import APROVA_CONDICAO_COMERCIAL, APROVA_REGRAS_FECHAMENTO


@dataclass(frozen=True)
class Acao:
    tipo: str
    descricao: str
    aprovado_por: frozenset[str]
    altera_referencia: bool = False
    altera_calculo: bool = False
    apenas_operacional: bool = False
    parametros_obrigatorios: tuple[str, ...] = ()
    tipos_pendencia: tuple[str, ...] = ()  # para quais tipos de pendência é oferecida


# R20: Comercial aprova taxa e condição comercial. Financeiro aprova regra de fechamento.
ACOES: dict[str, Acao] = {
    "REGISTRAR_CONDICAO_COMERCIAL": Acao(
        tipo="REGISTRAR_CONDICAO_COMERCIAL",
        descricao=(
            "Publicar condição comercial que muda a taxa contratada fora da planilha. "
            "Entra em condicoes_comerciais.json e passa a valer no próximo fechamento."
        ),
        aprovado_por=APROVA_CONDICAO_COMERCIAL,
        altera_referencia=True,
        altera_calculo=True,
        parametros_obrigatorios=("cnpj", "taxas", "inicio"),
        tipos_pendencia=("CONDICAO_ESPECIAL_A_CONFIRMAR", "CONDICAO_NAO_INFORMADA_ORBE"),
    ),
    "CONFIRMAR_ANOTACAO_SEM_EFEITO": Acao(
        tipo="CONFIRMAR_ANOTACAO_SEM_EFEITO",
        descricao=(
            "Marcar que uma anotação da planilha não altera a taxa (sinal já resolvido). "
            "Não muda número; impede a mesma pendência de voltar nos próximos meses."
        ),
        aprovado_por=APROVA_CONDICAO_COMERCIAL,
        altera_referencia=True,
        parametros_obrigatorios=("cnpj", "texto"),
        tipos_pendencia=("CONDICAO_ESPECIAL_A_CONFIRMAR",),
    ),
    "VINCULAR_CADASTRO_EC": Acao(
        tipo="VINCULAR_CADASTRO_EC",
        descricao=(
            "Vincular um EC a um CNPJ no cadastro de ECs. Para EC sem contrato, "
            "mantém a identidade e aguarda contrato (R18). Não cria taxa."
        ),
        aprovado_por=APROVA_CONDICAO_COMERCIAL,
        altera_referencia=True,
        parametros_obrigatorios=("ec", "cnpj"),
        tipos_pendencia=("SEM_CONTRATO", "EC_NAO_CADASTRADO"),
    ),
    "RECONHECER_RESOLUCAO": Acao(
        tipo="RECONHECER_RESOLUCAO",
        descricao=(
            "Registrar que a Ponte/Orbe/lojista aceitou a contestação ou devolveu "
            "o valor. Não altera o fechamento retroativamente; abre o acompanhamento "
            "do ajuste no mês em que o retorno for financeiro."
        ),
        aprovado_por=APROVA_REGRAS_FECHAMENTO,
        apenas_operacional=True,
        parametros_obrigatorios=("evidencia",),
        tipos_pendencia=(
            "CONTESTACAO_ORBE",
            "CONTESTACAO_PONTE",
            "SPREAD_NEGATIVO_CONTESTAR",
            "DUPLICATA_RELATORIO_PONTE",
            "DIFERENCA_RELATORIO_PONTE",
        ),
    ),
    "AGUARDAR_INFORMACAO": Acao(
        tipo="AGUARDAR_INFORMACAO",
        descricao=(
            "Confirmar que o caso está em acompanhamento (aguardando resposta de "
            "contraparte, cliente ou interno). Não altera número."
        ),
        aprovado_por=APROVA_REGRAS_FECHAMENTO,
        apenas_operacional=True,
        parametros_obrigatorios=("destinatario",),
    ),
    "CLASSIFICAR_LANCAMENTO": Acao(
        tipo="CLASSIFICAR_LANCAMENTO",
        descricao=(
            "Classificar manualmente um lançamento sem regra. Entra como regra para "
            "o motor quando o lançamento recorrer."
        ),
        aprovado_por=APROVA_REGRAS_FECHAMENTO,
        altera_calculo=True,
        parametros_obrigatorios=("conta_codigo", "motivo"),
        tipos_pendencia=("LANCAMENTO_SEM_REGRA", "PIX_NAO_IDENTIFICADO"),
    ),
    "ANOTAR_PROVIDENCIA": Acao(
        tipo="ANOTAR_PROVIDENCIA",
        descricao=(
            "Nota operacional (ex.: 'TED conferido com a Ponte', 'pedido reenvio do "
            "relatório'). Não altera cálculo nem referência."
        ),
        aprovado_por=APROVA_REGRAS_FECHAMENTO,
        apenas_operacional=True,
    ),
}


def para_tipo_pendencia(tipo_pendencia: str) -> list[Acao]:
    """Ações compatíveis com um tipo de pendência (+ ações universais operacionais)."""
    especificas = [a for a in ACOES.values() if tipo_pendencia in a.tipos_pendencia]
    universais = [a for a in ACOES.values()
                  if a.apenas_operacional and not a.tipos_pendencia]
    return especificas + universais


def valida_parametros(acao_tipo: str, parametros: dict) -> list[str]:
    """Devolve a lista de parâmetros obrigatórios faltando."""
    acao = ACOES.get(acao_tipo)
    if acao is None:
        return [f"acao_desconhecida:{acao_tipo}"]
    faltando = [p for p in acao.parametros_obrigatorios if not parametros.get(p)]
    return faltando
