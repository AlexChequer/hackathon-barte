"""Causa da divergência de checkout, por transação (coluna extra `causa_divergencia`).

Diz POR QUE a taxa cobrada pela Orbe diferiu do contrato, para prevenir no mês seguinte.
Decidida só por regra sobre os dados do mês (ver HIPOTESES.md, P-causa):

1. `CK-COND-*` (condição comercial fora da planilha) → COND, já identificada pelo motor.
2. Degrau sistêmico, por (CNPJ, produto): todos os desvios com o mesmo delta sobre a planilha e
   toda linha dentro da janela [primeira, última data de referência que desvia] desviando; e
   ≥ 2 produtos do mesmo CNPJ com o mesmo delta e a mesma data de início.
3. Taxa de outra vigência: a taxa aplicada é a do mesmo produto numa outra linha de vigência do
   mesmo CNPJ, não vigente na data de referência.

O degrau é avaliado sobre o grupo antes de qualquer correspondência de taxa: na Rota, 2,49% +
0,50 = 2,99% (taxa contratada do 2–6x), e casar taxas antes chamaria as vendas à vista de
"outra faixa de parcelas". Transação que casa com mais de uma regra, ou com nenhuma, fica
NAO_DETERMINADA: nunca escolhemos entre candidatas.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pandas as pd

COND = "Condição comercial não informada à Orbe"
DEGRAU = "Degrau sistêmico"
OUTRA_VIGENCIA = "Taxa de outra vigência"
NAO_DETERMINADA = "Não determinada"

PRODUTOS_CREDITO = ("credito_vista", "credito_2a6", "credito_7a12")
NOME_PRODUTO = {
    "debito": "débito",
    "credito_vista": "crédito à vista",
    "credito_2a6": "crédito 2–6x",
    "credito_7a12": "crédito 7–12x",
    "pix": "Pix",
    "antecipacao": "antecipação",
}


def _desvio(tx: pd.Series) -> Decimal | None:
    """Delta da taxa aplicada sobre a planilha (o que a Orbe conhece). None = sem desvio."""
    aplicada, planilha = tx["taxa_aplicada"], tx["taxa_planilha"]
    if aplicada is None or planilha is None or pd.isna(aplicada) or pd.isna(planilha):
        return None
    return aplicada - planilha if aplicada != planilha else None


def _base(linhas_df: pd.DataFrame) -> pd.DataFrame:
    """Linhas com taxa própria (REVERSAO herda a comissão da antecipação, não tem taxa a comparar)."""
    base = linhas_df[linhas_df["tipo"] != "REVERSAO ANTECIPACAO"].copy()
    base["delta"] = base.apply(_desvio, axis=1)
    return base


def _degraus(base: pd.DataFrame) -> dict[tuple[str, str], tuple[Decimal, dt.date, dt.date]]:
    """(cnpj, produto) → (delta, início, fim) dos grupos que formam degrau sistêmico."""
    candidatos: dict[tuple[str, str], tuple[Decimal, dt.date, dt.date]] = {}
    for (cnpj, produto), grupo in base.groupby(["cnpj", "produto"], sort=True):
        desvios = grupo[grupo["delta"].notna()]
        if desvios.empty or desvios["delta"].nunique() != 1:
            continue
        ini, fim = desvios["data_referencia"].min(), desvios["data_referencia"].max()
        janela = grupo[(grupo["data_referencia"] >= ini) & (grupo["data_referencia"] <= fim)]
        if janela["delta"].isna().any():
            continue
        candidatos[(cnpj, produto)] = (desvios["delta"].iloc[0], ini, fim)
    # ≥ 2 produtos do mesmo CNPJ com o mesmo delta e a mesma data de início.
    contagem: dict[tuple[str, Decimal, dt.date], int] = {}
    for (cnpj, _), (delta, ini, _) in candidatos.items():
        contagem[(cnpj, delta, ini)] = contagem.get((cnpj, delta, ini), 0) + 1
    return {k: v for k, v in candidatos.items() if contagem[(k[0], v[0], v[1])] >= 2}


def _vigencias_por_cnpj(registry: dict) -> dict[str, list]:
    por_cnpj: dict[str, dict[int, object]] = {}
    for entries in registry.values():
        for e in entries:
            por_cnpj.setdefault(e.cnpj, {})[e.linha_origem] = e
    return {cnpj: list(es.values()) for cnpj, es in por_cnpj.items()}


def _vigente_em(entry, data: dt.date) -> bool:
    return ((entry.vigencia_inicio is None or entry.vigencia_inicio <= data)
            and (entry.vigencia_fim is None or entry.vigencia_fim >= data))


def outras_vigencias_com_taxa(tx: pd.Series, vigencias: list) -> list:
    """Linhas de vigência do CNPJ, não vigentes na data, cujo produto tem a taxa aplicada."""
    return [
        e for e in vigencias
        if e.linha_origem != tx["linha_planilha"]
        and not _vigente_em(e, tx["data_referencia"])
        and getattr(e, tx["produto"], None) == tx["taxa_aplicada"]
    ]


def classificar(linhas_df: pd.DataFrame, registry: dict) -> dict[str, str]:
    """id_transacao → causa, para as transações com divergência da Orbe (`CK-DIV-*`)."""
    if linhas_df.empty:
        return {}
    base = _base(linhas_df)
    degraus = _degraus(base)
    vigencias = _vigencias_por_cnpj(registry)
    causas: dict[str, str] = {}
    for _, tx in base[base["divergencia"] != 0].iterrows():
        candidatas = []
        if (tx["cnpj"], tx["produto"]) in degraus:
            candidatas.append(DEGRAU)
        if tx["produto"] and outras_vigencias_com_taxa(tx, vigencias.get(tx["cnpj"], [])):
            candidatas.append(OUTRA_VIGENCIA)
        causas[tx["id_transacao"]] = candidatas[0] if len(candidatas) == 1 else NAO_DETERMINADA
    return causas


# ----- texto da pendência CONTESTACAO_ORBE (sem ';': o CSV usa ';' como separador) -----

def _pp(delta: Decimal) -> str:
    v = (delta * 100).quantize(Decimal("0.01"))
    return f"{'+' if v > 0 else ''}{v}".replace(".", ",") + " p.p."


def _taxa(frac: Decimal) -> str:
    return f"{(frac * 100).quantize(Decimal('0.01'))}".replace(".", ",") + "%"


def _data(d: dt.date, ano: bool = True) -> str:
    return d.strftime("%d/%m/%Y" if ano else "%d/%m")


def _periodo(ini: dt.date, fim: dt.date) -> str:
    if ini == fim:
        return f"em {_data(ini)}"
    return f"entre {_data(ini, ano=ini.year != fim.year)} e {_data(fim)}"


def _vigencia_txt(e) -> str:
    if e.vigencia_inicio and e.vigencia_fim:
        return f"vigência de {_data(e.vigencia_inicio)} a {_data(e.vigencia_fim)}"
    if e.vigencia_fim:
        return f"vigência até {_data(e.vigencia_fim)}"
    if e.vigencia_inicio:
        return f"vigência a partir de {_data(e.vigencia_inicio)}"
    return "vigência sem data"


def _texto_degrau(linhas: pd.DataFrame, todas_cnpj: pd.DataFrame) -> str:
    produtos = sorted(set(linhas["produto"]), key=list(NOME_PRODUTO).index)
    delta = linhas.apply(_desvio, axis=1).iloc[0]
    ini = linhas["data_referencia"].min()
    if set(produtos) == set(PRODUTOS_CREDITO):
        onde = "todos os produtos de crédito"
    else:
        onde = ", ".join(NOME_PRODUTO[p] for p in produtos)
    # Produtos do lojista com transações desde o início do degrau e nenhuma fora do contrato.
    depois = _base(todas_cnpj)
    depois = depois[depois["data_referencia"] >= ini]
    corretos = [p for p in NOME_PRODUTO
                if p not in produtos and p in set(depois["produto"])
                and depois.loc[depois["produto"] == p, "delta"].isna().all()]
    nomes = [NOME_PRODUTO[p] for p in corretos]
    lista = " e ".join([", ".join(nomes[:-1]), nomes[-1]] if len(nomes) > 1 else nomes)
    sufixo = f" ({lista} corretos)" if corretos else ""
    return (f"degrau sistêmico, {_pp(delta)} em {onde} desde {_data(ini)}{sufixo}. "
            "Prevenção: pedir à Orbe o cadastro de taxas e conferir com a planilha. "
            "Confirmar com o Comercial se houve renegociação.")


def _texto_outra_vigencia(linhas: pd.DataFrame, vigencias: list) -> str:
    partes = []
    for (produto, aplicada, planilha), g in linhas.groupby(["produto", "taxa_aplicada", "taxa_planilha"],
                                                          sort=True):
        origem = outras_vigencias_com_taxa(g.iloc[0], vigencias)
        vig = " ou ".join(_vigencia_txt(e) for e in origem)
        partes.append(
            f"a Orbe aplicou {_taxa(aplicada)} ({vig}) no {NOME_PRODUTO[produto]} "
            f"{_periodo(g['data_referencia'].min(), g['data_referencia'].max())} em vez de {_taxa(planilha)}"
        )
    return ("taxa de outra vigência, " + ", e ".join(partes) + ". "
            "Prevenção: enviar a nova taxa à Orbe antes da data de vigência e conferir as primeiras "
            "transações.")


def texto_causa(grupo: pd.DataFrame, linhas_df: pd.DataFrame, causas: dict[str, str], registry: dict) -> str:
    """Causa agregada das transações `CK-DIV` de um lojista. Mais de uma: da maior para a menor em R$."""
    cnpj = grupo["cnpj"].iloc[0]
    por_causa = grupo.assign(causa=grupo["id_transacao"].map(causas)).groupby("causa")
    ordem = sorted(por_causa, key=lambda kv: (-sum(kv[1]["divergencia"], Decimal(0)), kv[0]))
    textos = []
    for causa, linhas in ordem:
        if causa == DEGRAU:
            txt = _texto_degrau(linhas, linhas_df[linhas_df["cnpj"] == cnpj])
        elif causa == OUTRA_VIGENCIA:
            txt = _texto_outra_vigencia(linhas, _vigencias_por_cnpj(registry).get(cnpj, []))
        else:
            txt = (f"não determinada por regra em {len(linhas)} transações. "
                   "Analisar as linhas CK-DIV-* antes de contestar.")
        if len(ordem) > 1:
            txt = f"{len(linhas)} transações, {sum(linhas['divergencia'], Decimal(0))}, {txt}"
        textos.append(txt)
    if len(textos) == 1:
        return f"Causa: {textos[0]}"
    return "Causas, da maior para a menor em R$: " + " ".join(f"({i}) {t}" for i, t in enumerate(textos, 1))
