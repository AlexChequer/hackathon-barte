"""Comissão de CHECKOUT por lojista, com rastro linha a linha. 100% determinístico, só Decimal.

Cada linha da Orbe vai para exatamente um id_saida:
  CHK-<cnpj>          comissão do lojista
  PEND-EC-<ec>        EC sem CNPJ (não fatura)
  PEND-TX-<id>        linha que não dá para calcular (taxa ausente, referência quebrada...)
  FORA-<tipo>         tipo excluído por premissa (contabilizado para o total fechar)
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

from src.cadastro import Cadastro, chave_taxa
from src.leitura import LinhaOrbe

CENTAVO = Decimal("0.01")
TIPOS = ("VENDA", "ESTORNO", "ANTECIPACAO", "REVERSAO ANTECIPACAO")


def arredondar(valor: Decimal) -> Decimal:
    """R8: meio centavo vai para longe do zero (0,005 -> 0,01; -0,005 -> -0,01)."""
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


@dataclass
class Rastro:
    id_saida: str
    arquivo_origem: str
    ref_origem: str
    valor: Decimal
    tipo_lancamento: str
    valor_bruto: Decimal
    valor_taxa_orbe: Decimal
    taxa_contratada_pct: Decimal | None
    obs: str = ""


@dataclass
class Pendencia:
    id_saida: str
    tipo: str
    ref_origem: str
    valor_brl: Decimal
    motivo: str
    quem_decide: str


@dataclass
class Comissao:
    id_saida: str
    cnpj: str
    lojista: str
    comissao_brl: Decimal = Decimal("0")
    cobrado_orbe_brl: Decimal = Decimal("0")
    qtd_transacoes: int = 0
    ecs: set[str] = field(default_factory=set)


@dataclass
class Resultado:
    comissoes: list[Comissao]
    pendencias: list[Pendencia]
    rastro: list[Rastro]
    controle: dict


def calcular(orbe: list[LinhaOrbe], cadastro: Cadastro, premissas: dict, arquivo_orbe: str) -> Resultado:
    if premissas["base_comissao"] != "bruto_x_taxa_contratada":
        raise ValueError(f"base_comissao não suportada: {premissas['base_comissao']}")
    if premissas["arredondamento"] != "ROUND_HALF_UP":
        raise ValueError(f"arredondamento não suportado: {premissas['arredondamento']}")
    if premissas["ec_sem_cnpj"] != "pendencia":
        raise ValueError("ec_sem_cnpj só aceita 'pendencia': nunca inventar CNPJ")

    tipos_fora = set()
    if not premissas["incluir_antecipacao"]:
        tipos_fora |= {"ANTECIPACAO", "REVERSAO ANTECIPACAO"}

    rastro: list[Rastro] = []
    pend_linha: list[Pendencia] = []
    pend_ec: dict[str, list[LinhaOrbe]] = defaultdict(list)
    comissao_por_id: dict[str, Decimal] = {}
    contagem_ids = defaultdict(int)
    for linha in orbe:
        contagem_ids[linha.id_transacao] += 1

    def registrar(linha, id_saida, valor, taxa=None, obs=""):
        rastro.append(Rastro(
            id_saida, arquivo_orbe, linha.id_transacao, valor, linha.tipo,
            linha.valor_bruto, linha.valor_taxa, taxa * 100 if taxa is not None else None, obs,
        ))

    def pendencia_linha(linha, tipo, motivo, quem="Financeiro"):
        id_saida = f"PEND-TX-{linha.id_transacao}"
        pend_linha.append(Pendencia(id_saida, tipo, linha.id_transacao, linha.valor_taxa, motivo, quem))
        registrar(linha, id_saida, linha.valor_taxa, obs="valor = cobrado pela Orbe; comissão não calculada")

    # Antecipações antes das reversões: a reversão anula a comissão da antecipação que ela referencia.
    ordem = {t: i for i, t in enumerate(TIPOS)}
    for linha in sorted(orbe, key=lambda x: ordem.get(x.tipo, len(TIPOS))):
        if contagem_ids[linha.id_transacao] > 1:
            pendencia_linha(linha, "ID_DUPLICADO",
                            f"id_transacao {linha.id_transacao} aparece {contagem_ids[linha.id_transacao]}x "
                            "no relatório da Orbe; confirmar se é reprocessamento antes de faturar")
            continue
        if linha.valor_bruto - linha.valor_taxa != linha.valor_liquido:
            pendencia_linha(linha, "LINHA_INCONSISTENTE",
                            f"valor_liquido {linha.valor_liquido} != bruto {linha.valor_bruto} - taxa "
                            f"{linha.valor_taxa} na linha {linha.linha_arquivo} da Orbe")
            continue
        if linha.tipo not in TIPOS:
            pendencia_linha(linha, "TIPO_DESCONHECIDO", f"tipo_lancamento '{linha.tipo}' não previsto")
            continue
        if linha.tipo in tipos_fora:
            registrar(linha, f"FORA-{linha.tipo.replace(' ', '_')}", linha.valor_taxa,
                      obs="excluído por premissas.json")
            continue

        cnpj = cadastro.ec_para_cnpj.get(linha.ec)
        if cnpj is None:
            pend_ec[linha.ec].append(linha)
            continue
        id_saida = f"CHK-{cnpj}"

        if linha.tipo == "REVERSAO ANTECIPACAO" and premissas["reversao_anula_antecipacao_referenciada"]:
            original = comissao_por_id.get(linha.id_referencia)
            if original is None:
                pendencia_linha(linha, "REVERSAO_SEM_REFERENCIA",
                                f"reversão aponta para {linha.id_referencia or '(vazio)'}, que não está "
                                "entre as antecipações calculadas deste relatório")
                continue
            valor = -original
            comissao_por_id[linha.id_transacao] = valor
            registrar(linha, id_saida, valor, obs=f"anula antecipação {linha.id_referencia}")
            continue

        chave = chave_taxa(linha)
        if chave is None:
            pendencia_linha(linha, "MODALIDADE_DESCONHECIDA",
                            f"modalidade '{linha.modalidade}' / {linha.parcelas} parcelas sem coluna na planilha")
            continue

        obs = ""
        dia = linha.data_movimento
        if linha.tipo == "ESTORNO" and premissas["estorno_taxa_da_venda_original"]:
            if linha.data_venda_original is None:
                pendencia_linha(linha, "ESTORNO_SEM_DATA_VENDA",
                                "estorno sem data_venda_original; não dá para saber a taxa da venda")
                continue
            dia = linha.data_venda_original
            if (dia.year, dia.month) != (linha.data_movimento.year, linha.data_movimento.month):
                obs = f"estorno_de_venda_de_{dia:%Y-%m}"

        taxa, origem = cadastro.taxa(cnpj, chave, dia)
        if taxa is None:
            pendencia_linha(linha, "TAXA_NAO_ENCONTRADA",
                            f"{cadastro.nome[cnpj]}: {origem} (coluna {chave}). Sem contrato, não fatura")
            continue
        if origem.startswith("isenção"):
            obs = f"{obs}; {origem}" if obs else origem

        valor = arredondar(linha.valor_bruto * taxa)
        comissao_por_id[linha.id_transacao] = valor
        registrar(linha, id_saida, valor, taxa, obs)

    # Uma pendência por EC sem vínculo, com o total cobrado pela Orbe (exposição, não comissão).
    pend_ec_lista = []
    quem_por_ec = premissas.get("quem_decide_ec_sem_cnpj", {})
    for ec, linhas in sorted(pend_ec.items()):
        id_saida = f"PEND-EC-{ec}"
        total = sum((x.valor_taxa for x in linhas), Decimal("0"))
        nomes = sorted({x.nome_orbe for x in linhas})
        pend_ec_lista.append(Pendencia(
            id_saida, "EC_SEM_CNPJ", f"EC:{ec}", total,
            f"EC {ec} ({' / '.join(nomes)}) com {len(linhas)} linhas na Orbe: "
            f"{cadastro.motivo_sem_vinculo(ec)}. Sem CNPJ e contrato não há comissão nem nota; "
            "valor_brl é o que a Orbe cobrou dessas linhas",
            quem_por_ec.get(ec, premissas.get("quem_decide_padrao", "Financeiro")),
        ))
        for x in linhas:
            registrar(x, id_saida, x.valor_taxa, obs="EC sem CNPJ; valor = cobrado pela Orbe")

    comissoes: dict[str, Comissao] = {}
    linhas_por_id = {x.id_transacao: x for x in orbe}
    for r in rastro:
        if not r.id_saida.startswith("CHK-"):
            continue
        cnpj = r.id_saida[4:]
        c = comissoes.setdefault(cnpj, Comissao(r.id_saida, cnpj, cadastro.nome[cnpj]))
        c.comissao_brl += r.valor
        c.cobrado_orbe_brl += r.valor_taxa_orbe
        c.qtd_transacoes += 1
        c.ecs.add(linhas_por_id[r.ref_origem].ec)

    lista_comissoes = [comissoes[k] for k in sorted(comissoes)]
    pendencias = pend_ec_lista + sorted(pend_linha, key=lambda p: p.id_saida)
    rastro.sort(key=lambda r: (r.id_saida, r.ref_origem))
    return Resultado(lista_comissoes, pendencias, rastro, montar_controle(orbe, lista_comissoes, pendencias, rastro))


def montar_controle(orbe, comissoes, pendencias, rastro) -> dict:
    zero = Decimal("0")

    def f2(v: Decimal) -> str:
        return f"{v:.2f}"

    por_tipo = defaultdict(lambda: zero)
    qtd_tipo = defaultdict(int)
    for x in orbe:
        por_tipo[x.tipo] += x.valor_taxa
        qtd_tipo[x.tipo] += 1
    total_orbe = sum(por_tipo.values(), zero)
    soma_com = sum((c.comissao_brl for c in comissoes), zero)
    cobrado_com = sum((c.cobrado_orbe_brl for c in comissoes), zero)
    soma_pend = sum((p.valor_brl for p in pendencias), zero)
    soma_fora = sum((r.valor for r in rastro if r.id_saida.startswith("FORA-")), zero)
    # Ponte: tudo que a Orbe cobrou = cobrado nas linhas faturadas + pendências + fora.
    diferenca = total_orbe - (cobrado_com + soma_pend + soma_fora)
    return {
        "linhas_orbe": len(orbe),
        "linhas_rastro": len(rastro),
        "orbe_valor_taxa_por_tipo": {t: f2(v) for t, v in por_tipo.items()},
        "orbe_qtd_por_tipo": dict(qtd_tipo),
        "soma_valor_taxa_orbe": f2(total_orbe),
        "soma_comissoes_contratadas": f2(soma_com),
        "soma_cobrado_orbe_nas_linhas_faturadas": f2(cobrado_com),
        "cobrado_orbe_menos_contratado": f2(cobrado_com - soma_com),
        "soma_pendencias": f2(soma_pend),
        "soma_fora": f2(soma_fora),
        "diferenca_fechamento": f2(diferenca),
        "qtd_lojistas_com_comissao": len(comissoes),
        "qtd_pendencias": len(pendencias),
    }


def conferir_rastro(res: Resultado) -> list[str]:
    """Problemas de rastro. Lista vazia = cada número de saída bate em centavos com suas linhas de origem."""
    problemas = []
    soma = defaultdict(lambda: Decimal("0"))
    for r in res.rastro:
        soma[r.id_saida] += r.valor
    reportado = {c.id_saida: c.comissao_brl for c in res.comissoes}
    reportado.update({p.id_saida: p.valor_brl for p in res.pendencias})
    for id_saida, valor in reportado.items():
        if soma.get(id_saida, Decimal("0")) != valor:
            problemas.append(f"{id_saida}: reportado {valor}, rastro soma {soma.get(id_saida)}")
    for id_saida in soma:
        if id_saida not in reportado and not id_saida.startswith("FORA-"):
            problemas.append(f"{id_saida}: está no rastro mas não em nenhuma saída")
    refs = defaultdict(int)
    for r in res.rastro:
        refs[r.ref_origem] += 1
    problemas += [f"{ref} aparece {n}x no rastro" for ref, n in refs.items() if n > 1]
    if res.controle["diferenca_fechamento"] != "0.00":
        problemas.append(f"fechamento não bate: diferença {res.controle['diferenca_fechamento']}")
    return problemas
