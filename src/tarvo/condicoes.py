"""Condições comerciais registradas fora da planilha de taxas (fonte única).

A planilha é o que a Orbe conhece. Uma condição comercial (ex.: isenção da Casa do Estudante, R6)
muda a taxa contratada sem mudar a planilha. O motor usa a condição vigente quando houver e
compara a cobrança da Orbe com a planilha para separar falha da Orbe de falha da Tarvo (R16.1).
"""

from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "condicoes_comerciais.json"
COLUNAS_TAXA = ("debito", "credito_vista", "credito_2a6", "credito_7a12", "pix", "antecipacao")


@dataclass(frozen=True)
class Condicao:
    id: str
    cnpj: str
    taxas: dict[str, Decimal]
    inicio: dt.date
    fim: dt.date | None
    fonte: str
    aprovado_por: str
    descricao: str = ""

    def vale_em(self, data: dt.date) -> bool:
        return self.inicio <= data and (self.fim is None or data <= self.fim)


def _parse(item: dict) -> Condicao:
    taxas = {k: Decimal(str(v)) for k, v in item["taxas"].items()}
    desconhecidas = set(taxas) - set(COLUNAS_TAXA)
    if desconhecidas:
        raise ValueError(f"condição {item.get('id')}: modalidade desconhecida {sorted(desconhecidas)}")
    return Condicao(
        id=item["id"],
        cnpj=str(item["cnpj"]).zfill(14),
        taxas=taxas,
        inicio=dt.date.fromisoformat(item["inicio"]),
        fim=dt.date.fromisoformat(item["fim"]) if item.get("fim") else None,
        fonte=item["fonte"],
        aprovado_por=item["aprovado_por"],
        descricao=item.get("descricao", ""),
    )


def carregar(caminho: Path = CAMINHO_PADRAO) -> tuple[Condicao, ...]:
    """Lê o arquivo de condições. Arquivo ausente = nenhuma condição (não é erro)."""
    if not caminho.exists():
        return ()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return tuple(_parse(item) for item in dados.get("condicoes", []))


def vigente(condicoes: tuple[Condicao, ...], cnpj: str, data: dt.date, coluna: str) -> Condicao | None:
    """Condição que define a taxa de `coluna` para o CNPJ na data, ou None."""
    candidatas = [c for c in condicoes if c.cnpj == cnpj and coluna in c.taxas and c.vale_em(data)]
    return max(candidatas, key=lambda c: c.inicio) if candidatas else None


@dataclass(frozen=True)
class SinalResolvido:
    """Texto da planilha já analisado (ex.: renegociação que já está na própria planilha)."""

    cnpj: str
    texto: str
    decisao: str
    fonte: str


def carregar_sinais_resolvidos(caminho: Path = CAMINHO_PADRAO) -> tuple[SinalResolvido, ...]:
    if not caminho.exists():
        return ()
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return tuple(
        SinalResolvido(str(i["cnpj"]).zfill(14), i["texto"].strip(), i["decisao"], i["fonte"])
        for i in dados.get("sinais_resolvidos", [])
    )


CAMPOS_OBRIGATORIOS = ("cnpj", "taxas", "inicio", "fonte", "aprovado_por")


def _validar_condicao(dados: dict) -> dict:
    """Valida na fronteira (tela/API). Taxas como fração em texto ("0.0199" = 1,99%)."""
    faltando = [c for c in CAMPOS_OBRIGATORIOS if not dados.get(c)]
    if "aprovado_por" in faltando:
        raise ValueError("informe quem aprovou a condição (R20: taxa e condição comercial = Comercial)")
    cnpj = "".join(ch for ch in str(dados.get("cnpj", "")) if ch.isdigit())
    if len(cnpj) != 14:
        raise ValueError(f"CNPJ precisa ter 14 dígitos (recebido: {dados.get('cnpj')!r})")
    taxas = dados.get("taxas") or {}
    if not taxas:
        raise ValueError("informe ao menos uma taxa por modalidade")
    desconhecidas = sorted(set(taxas) - set(COLUNAS_TAXA))
    if desconhecidas:
        raise ValueError(f"modalidade desconhecida: {desconhecidas}; use {list(COLUNAS_TAXA)}")
    normalizadas = {}
    for coluna, valor in taxas.items():
        taxa = Decimal(str(valor))
        if not Decimal("0") <= taxa < Decimal("1"):
            raise ValueError(f"taxa de {coluna} precisa estar entre 0 e 1 como fração (0.0199 = 1,99%)")
        normalizadas[coluna] = str(taxa)
    inicio = dt.date.fromisoformat(str(dados["inicio"]))
    fim = dt.date.fromisoformat(str(dados["fim"])) if dados.get("fim") else None
    if fim is not None and fim < inicio:
        raise ValueError("a data de fim não pode ser anterior ao início")
    if faltando:
        raise ValueError(f"campos obrigatórios faltando: {faltando}")
    return {
        "cnpj": cnpj,
        "lojista": dados.get("lojista", ""),
        "taxas": normalizadas,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat() if fim else None,
        "descricao": dados.get("descricao", ""),
        "fonte": dados["fonte"],
        "aprovado_por": dados["aprovado_por"],
        "registrado_por": dados.get("registrado_por") or "tela",
        "registrado_em": dt.date.today().isoformat(),
    }


def _ler_arquivo(caminho: Path) -> dict:
    if not caminho.exists():
        return {"condicoes": [], "sinais_resolvidos": []}
    return json.loads(caminho.read_text(encoding="utf-8"))


def _gravar_arquivo(caminho: Path, dados: dict) -> None:
    temporario = caminho.with_suffix(".tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(caminho)  # troca atômica: nunca deixa o arquivo pela metade


def registrar_condicao(caminho: Path, dados: dict) -> dict:
    """Acrescenta uma condição validada (não altera as existentes) e devolve o registro gravado."""
    nova = _validar_condicao(dados)
    atual = _ler_arquivo(caminho)
    existentes = atual.get("condicoes", [])
    numero = max((int(c["id"].split("-")[1]) for c in existentes), default=0) + 1
    registro = {"id": f"COND-{numero:04d}", **nova}
    _gravar_arquivo(caminho, {**atual, "condicoes": [*existentes, registro]})
    return registro


def registrar_sinal_resolvido(caminho: Path, dados: dict) -> dict:
    """Marca um texto da planilha como já analisado (não muda taxa) para não voltar como pendência."""
    cnpj = "".join(ch for ch in str(dados.get("cnpj", "")) if ch.isdigit())
    texto = str(dados.get("texto", "")).strip()
    if len(cnpj) != 14 or not texto or not dados.get("fonte"):
        raise ValueError("informe CNPJ (14 dígitos), o texto da planilha e a fonte da decisão")
    registro = {"cnpj": cnpj, "texto": texto, "decisao": dados.get("decisao") or "nao_muda_taxa",
                "fonte": dados["fonte"], "registrado_por": dados.get("registrado_por") or "tela",
                "registrado_em": dt.date.today().isoformat()}
    atual = _ler_arquivo(caminho)
    _gravar_arquivo(caminho, {**atual, "sinais_resolvidos": [*atual.get("sinais_resolvidos", []), registro]})
    return registro
