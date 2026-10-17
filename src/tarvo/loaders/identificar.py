"""Reconhece cada arquivo do mês: primeiro pelo padrão de nome; se o nome não bater (arquivo
renomeado, "relatorio (1).csv"), pela assinatura do conteúdo. Ajustes da Orbe têm o mesmo formato
do relatório principal, então só são reconhecidos pelo nome (R34: avisar o que quebra)."""

from __future__ import annotations

import io
import zipfile
from fnmatch import fnmatch

from tarvo import frentes
from tarvo.loaders import ESPERADOS, IGNORADOS

ORBE_CABECALHO = "id_transacao;data_movimento;cod_estabelecimento"
AURORA_CABECALHO = "Data;Lançamento;Documento;Valor (R$);Saldo (R$)"


def _texto(conteudo: bytes, limite: int = 4096) -> str:
    trecho = conteudo[:limite]
    try:
        return trecho.decode("utf-8")
    except UnicodeDecodeError:
        return trecho.decode("latin-1")


def _abas_xlsx(conteudo: bytes) -> str:
    """Texto do workbook.xml (nomes das abas) sem abrir a planilha inteira."""
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            return z.read("xl/workbook.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError):
        return ""


def _por_conteudo(conteudo: bytes) -> str | None:
    texto = _texto(conteudo)
    if texto.startswith(ORBE_CABECALHO):
        return "orbe"
    if texto.startswith("COD_CONTA;"):
        return "plano"
    if AURORA_CABECALHO in texto:
        return "aurora"
    if "OFXHEADER" in texto or "<STMTTRN>" in _texto(conteudo, 65536):
        return "meridiano"
    if conteudo[:2] == b"PK" and "Taxas vigentes" in _abas_xlsx(conteudo):
        return "taxas"
    if ("MIME-Version" in texto or "Content-Type" in texto) and b".xlsx" in conteudo:
        return "ponte"
    return None


def identificar(nome: str, conteudo: bytes) -> tuple[str, str] | None:
    """(chave do arquivo, "nome" | "conteudo") ou None se não é um arquivo do fechamento."""
    for e in ESPERADOS:
        if fnmatch(nome, e["padrao"]):
            return e["chave"], "nome"
    chave = _por_conteudo(conteudo)
    return (chave, "conteudo") if chave else None


def _canonico(chave: str, indice: int, original: str) -> str:
    extensao = original.rsplit(".", 1)[-1].lower() if "." in original else "csv"
    if chave == "orbe_ajustes":
        return f"06_orbe_ajustes_enviado{indice + 1}.{extensao}"
    padrao = next(e["padrao"] for e in ESPERADOS if e["chave"] == chave)
    return padrao.replace("*", "_enviado" if padrao.endswith("*.xlsx") else "enviado", 1)


def classificar_lote(arquivos: list[tuple[str, bytes]]) -> dict:
    """Classifica um lote de upload: cada arquivo com a chave e o nome com que será gravado.

    `problemas` impedem o envio (arquivo repetido ou desconhecido, ou nada pode rodar).
    `faltando` e `bloqueios` só avisam: o fechamento roda o que der (R34)."""
    itens, problemas, contagem = [], [], {}
    for nome, conteudo in arquivos:
        if any(fnmatch(nome, p) for p in IGNORADOS):
            continue
        achado = identificar(nome, conteudo)
        if achado is None:
            problemas.append(f"{nome}: não é um arquivo do fechamento")
            itens.append({"nome": nome, "chave": None, "por": None, "nome_canonico": None})
            continue
        chave, por = achado
        indice = contagem.get(chave, 0)
        contagem[chave] = indice + 1
        canonico = nome if por == "nome" else _canonico(chave, indice, nome)
        itens.append({"nome": nome, "chave": chave, "por": por, "nome_canonico": canonico})
    faltando = []
    for e in (e for e in ESPERADOS if e["obrigatorio"]):
        achados = [i["nome"] for i in itens if i["chave"] == e["chave"]]
        if not achados:
            faltando.append(e["chave"])
        elif len(achados) > 1:
            problemas.append(f"mais de um {e['nome']}: {', '.join(achados)}")
    presentes = {e["chave"] for e in ESPERADOS if e["obrigatorio"]} - set(faltando)
    if not any(frentes.roda(f, presentes) for f in frentes.FRENTES):
        problemas.append("com esses arquivos nenhuma parte do fechamento pode rodar")
    return {"arquivos": itens, "problemas": problemas, "faltando": faltando,
            "bloqueios": frentes.bloqueios(presentes)}
