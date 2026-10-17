"""Rascunhos de envio a terceiros: uma mensagem por destinatário, juntando as pendências dele (P36).

Como funciona:
1. **Quem recebe o quê (regra, sem IA):** cada tipo de pendência diz para quem vai (Orbe, Ponte Câmbio,
   lojista, Comercial) ou que não gera mensagem (ação interna). Pendência com dois destinatários entra nas
   duas mensagens. Tipo novo sem classificação reprova `tests/test_rascunhos.py`.
2. **Pseudonimização:** o modelo recebe só a estrutura do problema. Nome, CNPJ, valor, taxa, data e id viram
   marcadores (`{VALOR_1}`, `{LOJISTA_1}`…). Nenhum dado da Tarvo ou dos clientes sai da empresa.
3. **Redação:** um modelo da OpenAI (`OPENAI_MODEL`, padrão `gpt-6-luna`) escreve assunto e corpo em volta
   dos marcadores. Sem `OPENAI_API_KEY`, os rascunhos ficam indisponíveis (não há texto padrão).
4. **Validação:** o texto só pode usar marcadores conhecidos, tem de citar o principal de cada tópico e não
   pode trazer número escrito pelo modelo, assinatura ou prazo. Reprovado, tenta de novo uma vez com os
   motivos; reprovado de novo, não é mostrado.
5. **Preenchimento local:** os marcadores são trocados pelos valores reais na máquina da Tarvo, e a lista de
   transações ou operações (do rastro) é anexada abaixo do texto, sem passar pelo modelo.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from decimal import Decimal

import pandas as pd

from tarvo import ambiente, rules
from tarvo.condicoes import Condicao
from tarvo.money import brl, pct, pct_br

log = logging.getLogger("tarvo.rascunhos")

MODELO_PADRAO = "gpt-6-luna"
ORBE = ("orbe", "Orbe", "contraparte")
PONTE = ("ponte", "Ponte Câmbio", "contraparte")
COMERCIAL = ("comercial", "Comercial (interno)", "interno")

# Ação interna, sem destinatário: não gera mensagem.
SEM_RASCUNHO = {
    "NOTA_NEGATIVA", "NOTA_ZERO_INESPERADA", "DIFERENCA_RELATORIO_PONTE", "PIX_NAO_IDENTIFICADO",
    "TRANSFERENCIA_EM_TRANSITO", "LANCAMENTO_SEM_REGRA", "FRENTE_BLOQUEADA",
}

INSTRUCOES = """Você redige rascunhos de e-mail em português do Brasil para o financeiro de uma empresa \
de pagamentos. Um analista vai revisar e enviar o texto.

Regras obrigatórias:
- Use só os fatos dos tópicos. Não acrescente fatos, causas, valores, datas nem pedidos que não estejam lá.
- Todo nome, CNPJ, valor, taxa, quantidade, data e identificador vem como marcador entre chaves, por \
exemplo {VALOR_1}. Copie o marcador exatamente como está, inclusive as chaves. Nunca escreva números, \
algarismos ou datas por conta própria e nunca invente marcadores.
- Cite pelo menos uma vez o valor de cada tópico ({VALOR_n}), o valor a pedir quando houver ({PEDIR_n}) \
e, no tópico sem valor, a condição ({CONDICAO_n}).
- Não inclua assinatura, nome de quem envia, cargo nem fórmula de despedida (como "Atenciosamente").
- Não prometa prazos, datas ou quando algo vai acontecer.
- Se houver lista de transações ou operações, diga que ela segue abaixo do texto; o sistema a anexa.
- Tom: {TOM}

Formato da resposta: a primeira linha é "Assunto: " seguido do assunto; depois uma linha em branco; \
depois o corpo do e-mail, começando pela saudação ao destinatário."""

TOM = {
    "contraparte": "formal e objetivo, de empresa para empresa parceira; um parágrafo por tópico.",
    "lojista": "cordial e claro, para um cliente; explique o que aconteceu sem jargão técnico.",
    "interno": "direto, entre colegas da mesma empresa; liste os pedidos de forma objetiva.",
}
PAPEL = {
    "contraparte": "empresa parceira (contraparte externa)",
    "lojista": "lojista, cliente da empresa",
    "interno": "área Comercial da própria empresa (mensagem interna)",
}
ENCERRAMENTOS = re.compile(
    r"^\s*(atenciosamente|cordialmente|abraços|att\.?|grato|grata|obrigad[oa]s?)\b",
    re.IGNORECASE | re.MULTILINE)
PRAZOS = re.compile(
    r"\bprazo|dias úteis|próxima semana|próximo repasse|\bamanhã\b|\bem breve\b", re.IGNORECASE)
MARCADOR = re.compile(r"\{([A-Z]+(?:_[A-Z]+)*(?:_\d+)?)\}")

# Texto de cada tópico, sem números: tudo que é dado vem como marcador.
TEXTOS = {
    ("CONTESTACAO_ORBE", "contraparte"):
        "Contestação: cobrança acima da taxa contratada em {QTD} transações do lojista {LOJISTA} "
        "(CNPJ {CNPJ}). Causa identificada: {causa}. Valor líquido a estornar: {VALOR}. Pedido: estornar o "
        "valor e corrigir o cadastro de taxas do lojista.",
    ("CONTESTACAO_ORBE", "lojista"):
        "Identificamos cobrança acima da taxa contratada em {QTD} transações suas. Valor a ressarcir: "
        "{VALOR}. O Financeiro vai confirmar a forma do ressarcimento.",
    ("CONDICAO_NAO_INFORMADA_ORBE", "lojista"):
        "A condição comercial acordada com a Tarvo ({CONDICAO}) não foi aplicada na cobrança de {QTD} "
        "transações. Valor a devolver: {VALOR}. O Financeiro vai confirmar a forma da devolução.",
    ("CONDICAO_NAO_INFORMADA_ORBE", "contraparte"):
        "Aviso de condição comercial vigente para o lojista {LOJISTA} (CNPJ {CNPJ}): {CONDICAO}. Pedido: "
        "atualizar o cadastro de taxas do lojista. As transações já processadas não geram cobrança à Orbe.",
    ("CONDICAO_NAO_INFORMADA_ORBE", "interno"):
        "Devolução de {VALOR} ao lojista {LOJISTA} (CNPJ {CNPJ}) pela condição comercial ({CONDICAO}) que "
        "não chegou à Orbe em {QTD} transações. Pedido: confirmar a devolução com o Financeiro e avisar a "
        "Orbe de condições novas antes do início da vigência.",
    ("CONTESTACAO_PONTE", "contraparte"):
        "Contestação: spread acima do contratado em {QTD} operações do lojista {LOJISTA} (CNPJ {CNPJ}). "
        "Diferença total: {VALOR}. Pedido: devolver a diferença ao lojista.",
    ("CONTESTACAO_PONTE", "lojista"):
        "Identificamos spread de câmbio acima do contratado em {QTD} remessas suas, somando {VALOR}. "
        "Contestamos a diferença com o parceiro de câmbio e vamos informar o retorno.",
    ("SPREAD_NEGATIVO_CONTESTAR", "contraparte"):
        "Operação {REF} com spread negativo no relatório ({VALOR}). Pela trava contratada, a diferença a "
        "corrigir é {PEDIR}. Pedido: honrar a trava e corrigir a operação.",
    ("DUPLICATA_RELATORIO_PONTE", "contraparte"):
        "Operação {REF} aparece repetida no relatório (linhas {LINHAS}), somando {VALOR} de spread a mais. "
        "Pedido: corrigir o relatório. No fechamento a operação foi contada uma vez.",
    ("DEVOLUCAO_LOJISTA_SEM_MOTIVO", "lojista"):
        "Recebemos em {DATA} a devolução de um PIX de repasse no valor de {VALOR}, sem motivo informado. "
        "Pedido: informar o motivo e confirmar os dados para refazer o repasse.",
    ("SEM_CONTRATO", "interno"):
        "Lojista {LOJISTA} (CNPJ {CNPJ}, EC {EC}) sem contrato vigente: {QTD} transações no mês, com {VALOR} "
        "cobrados pela Orbe e nada faturado. Pedido: confirmar o contrato e as taxas por modalidade para "
        "faturar desde o início.",
    ("ALERTA_ANTECIPACAO", "interno"):
        "Lojista {LOJISTA} (CNPJ {CNPJ}), sem histórico, antecipou {VALOR} no mês, acima do que vendeu. "
        "Pedido: confirmar o contrato antes de liberar novas antecipações.",
    ("CADASTRO", "interno"):
        "Cadastro: {assunto} (referência {REF}, valor envolvido {VALOR}). Pedido: confirmar o cadastro ou a "
        "taxa para o próximo fechamento.",
    ("ESCLARECIMENTO", "contraparte"):
        "Esclarecimento: {assunto} (referência {REF}, valor {VALOR}). Pedido: confirmar qual informação "
        "vale.",
}
# Pendências que pedem esclarecimento a quem enviou o arquivo, e as que são cadastro para o Comercial.
ESCLARECIMENTO = {
    "DUPLICATA_CONFLITANTE": "o mesmo identificador aparece com dados diferentes",
    "FORA_COMPETENCIA": "o registro tem data fora do mês do relatório",
    "REVERSAO_SEM_REFERENCIA": "a reversão aponta para uma antecipação que não está no relatório",
    "SPREAD_AUSENTE": "a operação veio sem o valor do spread",
    "STATUS_DESCONHECIDO": "a operação veio com um status de compliance não previsto",
}
CADASTRO = {
    "CONDICAO_ESPECIAL_A_CONFIRMAR": "anotação na planilha de taxas que pode indicar condição comercial",
    "EC_NAO_CADASTRADO": "estabelecimento da Orbe sem linha na planilha de taxas",
    "VIGENCIA_AUSENTE": "venda sem taxa vigente na data",
    "SEM_TAXA_CONTRATADA": "modalidade sem taxa contratada",
    "LOJISTA_REMESSA_SEM_CADASTRO": "lojista com remessa na Ponte sem cadastro na planilha",
    "SPREAD_CONTRATADO_INVALIDO": "spread de remessa ilegível na planilha",
}


@dataclass
class Topico:
    pendencia: str
    texto: str  # com marcadores locais {CAMPO}; numerados ao montar a mensagem
    valores: dict[str, str]
    anexo: list[str] = field(default_factory=list)
    obrigatorios: tuple[str, ...] = ("VALOR",)  # marcadores que o texto tem de citar


@dataclass
class Rascunho:
    chave: str
    destinatario: str
    papel: str
    pendencias: list[str]
    status: str = "indisponivel"  # gerado | indisponivel | reprovado | erro
    assunto: str = ""
    corpo: str = ""
    anexo: list[str] = field(default_factory=list)
    aviso: str = ""


@dataclass
class _Contexto:
    rastro: pd.DataFrame
    nomes: dict[str, str]
    divergencias: pd.DataFrame
    lancamentos: pd.DataFrame
    condicoes: tuple[Condicao, ...]

    def linhas(self, id_saida: str) -> pd.DataFrame:
        return self.rastro[self.rastro["id_saida"] == id_saida] if not self.rastro.empty else self.rastro

    def nome(self, cnpj: str) -> str:
        return self.nomes.get(cnpj, cnpj)

    def anexo(self, id_saida: str, titulo: str) -> list[str]:
        linhas = self.linhas(id_saida)
        if linhas.empty:
            return []
        valores = (brl(Decimal(str(v))) for v in linhas["valor"])
        return [titulo, *(f"{ref}: {v}" for ref, v in zip(linhas["ref_origem"], valores, strict=True))]

    def causa(self, id_saida: str) -> str:
        div = self.divergencias
        if div.empty or "causa_divergencia" not in div:
            return "não determinada"
        ids = set(self.linhas(id_saida)["ref_origem"])
        causas = sorted(set(div.loc[div["ref_origem"].isin(ids), "causa_divergencia"].dropna()))
        return ", ".join(c.lower() for c in causas) or "não determinada"

    def condicao(self, cnpj: str) -> str:
        partes = []
        for c in (c for c in self.condicoes if c.cnpj == cnpj):
            taxas = {pct_br(pct(Decimal(str(v)))) for v in c.taxas.values()}
            taxa = (f"taxa de {taxas.pop()} em todas as modalidades" if len(taxas) == 1
                    else "taxas diferenciadas")
            periodo = (f"de {c.inicio:%d/%m/%Y} a {c.fim:%d/%m/%Y}" if c.fim
                       else f"a partir de {c.inicio:%d/%m/%Y}")
            partes.append(f"{taxa}, {periodo}")
        return ", ".join(partes) or "condição comercial registrada"

    def lancamento(self, ref: str) -> tuple[str, str]:
        """(nome no extrato, data) do lançamento, para o lojista identificado só pelo extrato."""
        lanc = self.lancamentos
        lanc = lanc[lanc["ref_origem"] == ref] if not lanc.empty else lanc
        if lanc.empty:
            return ref, ""
        descricao = str(lanc["descricao"].iloc[0])
        nome = descricao.split(" - ", 1)[-1].strip() if " - " in descricao else descricao
        return nome, pd.Timestamp(lanc["data"].iloc[0]).strftime("%d/%m/%Y")


def _de(motivo: str, padrao: str) -> str:
    m = re.search(padrao, str(motivo))
    return m.group(1) if m else ""


def _topicos(p: dict, ctx: _Contexto) -> list[tuple[tuple[str, str, str], Topico]]:
    """(destinatário, tópico) de uma pendência. Lista vazia = pendência sem mensagem."""
    tipo, pid, ref = p["tipo"], p["id_saida"], str(p["ref_origem"])
    valor = brl(Decimal(str(p["valor_brl"])))
    qtd = str(len(ctx.linhas(pid)))
    lojista = ("lojista:" + ref, ctx.nome(ref), "lojista")
    loja = {"LOJISTA": ctx.nome(ref), "CNPJ": ref}

    def t(chave: tuple[str, str], valores: dict[str, str], anexo: list[str] | None = None,
          obrigatorios: tuple[str, ...] = ("VALOR",), **fixos: str) -> Topico:
        return Topico(pid, TEXTOS[chave].replace("{causa}", fixos.get("causa", "")).replace(
            "{assunto}", fixos.get("assunto", "")), valores, anexo or [], obrigatorios)

    if tipo == "CONTESTACAO_ORBE":
        v = {"VALOR": valor, "QTD": qtd, **loja}
        anexo = ctx.anexo(pid, f"Transações de {ctx.nome(ref)} (diferença por transação):")
        return [(ORBE, t((tipo, "contraparte"), v, anexo, causa=ctx.causa(pid))),
                (lojista, t((tipo, "lojista"), v, anexo))]
    if tipo == "CONDICAO_NAO_INFORMADA_ORBE":
        v = {"VALOR": valor, "QTD": qtd, "CONDICAO": ctx.condicao(ref), **loja}
        anexo = ctx.anexo(pid, f"Transações de {ctx.nome(ref)} (valor a devolver por transação):")
        aviso = {"CONDICAO": v["CONDICAO"], **loja}
        return [(lojista, t((tipo, "lojista"), v, anexo)),
                (ORBE, t((tipo, "contraparte"), aviso, obrigatorios=("CONDICAO",))),
                (COMERCIAL, t((tipo, "interno"), v))]
    if tipo == "CONTESTACAO_PONTE":
        v = {"VALOR": valor, "QTD": qtd, **loja}
        anexo = ctx.anexo(pid, f"Operações de {ctx.nome(ref)} (diferença por operação):")
        return [(PONTE, t((tipo, "contraparte"), v, anexo)), (lojista, t((tipo, "lojista"), v, anexo))]
    if tipo == "SPREAD_NEGATIVO_CONTESTAR":
        pedir = _de(p["motivo"], r"o que pedir à Ponte: (-?R\$ [\d.,]+)") or valor
        return [(PONTE, t((tipo, "contraparte"), {"VALOR": valor, "REF": ref, "PEDIR": pedir},
                          obrigatorios=("VALOR", "PEDIR")))]
    if tipo == "DUPLICATA_RELATORIO_PONTE":
        linhas = _de(p["motivo"], r"\((L\d+(?:, L\d+)*)\)") or ref
        return [(PONTE, t((tipo, "contraparte"), {"VALOR": valor, "REF": ref, "LINHAS": linhas}))]
    if tipo == "DEVOLUCAO_LOJISTA_SEM_MOTIVO":
        nome, data = ctx.lancamento(ref)
        destino = ("lojista_extrato:" + ref, f"{nome} (extrato, {ref})", "lojista")
        return [(destino, t((tipo, "lojista"), {"VALOR": valor, "DATA": data}))]
    if tipo == "SEM_CONTRATO":
        ec = next((e for e, c in rules.EC_SEM_CONTRATO.items() if c.get("cnpj") == ref), "")
        return [(COMERCIAL, t((tipo, "interno"), {"VALOR": valor, "QTD": qtd, "EC": ec, **loja}))]
    if tipo == "ALERTA_ANTECIPACAO":
        return [(COMERCIAL, t((tipo, "interno"), {"VALOR": valor, **loja}))]
    if tipo in CADASTRO:
        return [(COMERCIAL, t(("CADASTRO", "interno"), {"VALOR": valor, "REF": ref}, assunto=CADASTRO[tipo]))]
    if tipo in ESCLARECIMENTO:
        destino = PONTE if pid.startswith("RM-") else ORBE
        return [(destino, t(("ESCLARECIMENTO", "contraparte"), {"VALOR": valor, "REF": ref},
                            assunto=ESCLARECIMENTO[tipo]))]
    return []


def _montar(topicos: list[Topico], destinatario: str, papel: str,
            competencia: str) -> tuple[str, dict[str, str], list[str]]:
    """Pacote para o modelo (só marcadores), mapa marcador → valor real (local) e marcadores obrigatórios."""
    valores = {"DESTINATARIO": destinatario, "COMPETENCIA": f"{competencia[5:]}/{competencia[:4]}"}
    linhas, obrigatorios = [], []
    for k, topico in enumerate(topicos, start=1):
        texto = topico.texto
        for campo, valor in topico.valores.items():
            texto = texto.replace("{" + campo + "}", "{" + f"{campo}_{k}" + "}")
            valores[f"{campo}_{k}"] = valor
        linhas.append(f"- {texto}")  # sem numeração: nenhum algarismo vai no pacote
        obrigatorios += [f"{m}_{k}" for m in topico.obrigatorios]
    pacote = (f"Destinatário: {PAPEL[papel]}, chamado {{DESTINATARIO}}.\n"
              "Mês de referência: {COMPETENCIA}.\nTópicos:\n" + "\n".join(linhas))
    return pacote, valores, obrigatorios


def validar(texto: str, valores: dict[str, str], obrigatorios: list[str]) -> list[str]:
    """Problemas do texto devolvido pelo modelo (vazio = aprovado). Ver as regras em INSTRUCOES."""
    problemas = []
    if not texto.lower().startswith("assunto:"):
        problemas.append('a primeira linha precisa começar com "Assunto:"')
    usados = set(MARCADOR.findall(texto))
    if desconhecidos := sorted(usados - set(valores)):
        problemas.append(f"marcadores que não existem: {desconhecidos}")
    if faltando := [m for m in obrigatorios if m not in usados]:
        problemas.append(f"faltou citar: {faltando}")
    if re.search(r"\d", MARCADOR.sub("", texto)):
        problemas.append("há números escritos fora dos marcadores")
    if ENCERRAMENTOS.search(texto):
        problemas.append("há fórmula de despedida ou assinatura")
    if PRAZOS.search(texto):
        problemas.append("há menção a prazo")
    return problemas


def _preencher(texto: str, valores: dict[str, str]) -> str:
    return MARCADOR.sub(lambda m: valores.get(m.group(1), m.group(0)), texto)


def _redigir(r: Rascunho, pacote: str, valores: dict[str, str], obrigatorios: list[str],
             pedir: Callable[[str, str], str]) -> Rascunho:
    instrucoes = INSTRUCOES.replace("{TOM}", TOM[r.papel])
    entrada = pacote
    for tentativa in (1, 2):
        try:
            texto = pedir(instrucoes, entrada).strip()
        except Exception as exc:  # erro de rede ou da API: o rascunho fica indisponível, o fechamento segue
            log.warning("rascunho para %s falhou: %s", r.destinatario, exc)
            r.status, r.aviso = "erro", f"Falha ao chamar o modelo ({type(exc).__name__})."
            return r
        problemas = validar(texto, valores, obrigatorios)
        if not problemas:
            assunto, _, corpo = texto.partition("\n")
            r.status = "gerado"
            r.assunto = _preencher(assunto.split(":", 1)[1].strip(), valores)
            r.corpo = _preencher(corpo.strip(), valores)
            return r
        log.info("rascunho para %s reprovado na tentativa %d: %s", r.destinatario, tentativa, problemas)
        entrada = (f"{pacote}\n\nSua resposta anterior foi reprovada pelos motivos abaixo. Reescreva "
                   "seguindo todas as regras.\n- " + "\n- ".join(problemas))
    r.status = "reprovado"
    r.aviso = "O texto do modelo não passou na validação: " + ", ".join(problemas) + "."
    return r


def _pedir_openai() -> Callable[[str, str], str] | None:
    ambiente.carregar_env()
    chave = os.environ.get("OPENAI_API_KEY", "").strip()
    if not chave:
        return None
    from openai import OpenAI  # import tardio: sem chave, o fechamento não precisa do pacote

    cliente = OpenAI(api_key=chave, timeout=90.0)
    modelo = os.environ.get("OPENAI_MODEL", "").strip() or MODELO_PADRAO

    def pedir(instrucoes: str, entrada: str) -> str:
        resposta = cliente.responses.create(model=modelo, instructions=instrucoes, input=entrada,
                                            max_output_tokens=4000)
        return resposta.output_text

    return pedir


ORDEM_PAPEL = {"contraparte": 0, "interno": 1, "lojista": 2}


def gerar(
    pendencias: pd.DataFrame, rastro: pd.DataFrame, comissoes: pd.DataFrame, divergencias: pd.DataFrame,
    lancamentos: pd.DataFrame, condicoes: tuple[Condicao, ...], competencia: str,
    pedir: Callable[[str, str], str] | None = None,
) -> list[dict]:
    """Um rascunho por destinatário. `pedir(instruções, entrada) -> texto` chama o modelo (o teste injeta)."""
    if pendencias.empty:
        return []
    nomes = {c["cnpj"]: c["nome"] for c in rules.EC_SEM_CONTRATO.values() if c.get("cnpj")}
    if not comissoes.empty:  # nome da planilha (checkout) vale sobre o nome cortado do relatório da Ponte
        por_linha = comissoes.sort_values("linha_negocio", key=lambda s: s.eq("CHECKOUT"))
        nomes |= dict(zip(por_linha["cnpj"], por_linha["lojista"], strict=True))
    ctx = _Contexto(rastro, nomes, divergencias, lancamentos, condicoes)

    por_destino: dict[str, tuple[tuple[str, str, str], list[Topico]]] = {}
    for p in pendencias.to_dict("records"):
        for destino, topico in _topicos(p, ctx):
            por_destino.setdefault(destino[0], (destino, []))[1].append(topico)

    tarefas = []
    for (chave, nome, papel), topicos in por_destino.values():
        r = Rascunho(chave, nome, papel, [t.pendencia for t in topicos],
                     anexo=[linha for t in topicos for linha in t.anexo])
        tarefas.append((r, *_montar(topicos, nome, papel, competencia)))

    pedir = pedir or _pedir_openai()
    if pedir is None:
        for r, *_ in tarefas:
            r.aviso = "Rascunhos indisponíveis: configure OPENAI_API_KEY no arquivo .env."
        prontos = [t[0] for t in tarefas]
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            prontos = list(pool.map(lambda t: _redigir(*t, pedir), tarefas))
    prontos.sort(key=lambda r: (ORDEM_PAPEL[r.papel], r.destinatario))
    return [asdict(r) for r in prontos]
