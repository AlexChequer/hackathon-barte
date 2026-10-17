"""Detector de sinais de condição comercial escondida em texto livre da planilha de taxas.

A isenção da Casa do Estudante só aparecia em obs e comentário de célula (R6). Todo fechamento
lê esses textos: palavras-chave (sempre) OU classificador binário Laya (open source, local, só
sim/não). Sinal sem condição registrada nem resolução anterior vira pendência para o Comercial
(R20, R24.1: cadastro e contrato quem decide é o comercial). O motor não muda nenhuma taxa por
causa de um sinal: só pede a confirmação.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

import pandas as pd

from tarvo import condicoes as cond_mod
from tarvo.engines import EngineResult

log = logging.getLogger("tarvo.sinais")

PALAVRAS_CHAVE = re.compile(
    r"comercial|condi[cç][aã]o|especial|negocia|isen[cçt]|zerad|desconto|estrat[eé]gic|acordo|promo"
    r"|aditivo|vig[eê]ncia|cortesia",
    re.IGNORECASE,
)
# Comitê de 3 instruções curtas, voto majoritário (guardrail). Medido em
# tests/fixtures/sinais_rotulados.json: instrução única longa = 8/15; comitê + palavras-chave = 13/15.
CONTEXTO = ("Anotação de uma planilha de taxas que uma subadquirente cobra de lojistas (MDR, antecipação, "
            "spread). ")
PERGUNTAS_LAYA = (
    "A anotação fala de negociação, acordo comercial, condição especial, desconto ou isenção de taxa?",
    "Esta anotação diz que a taxa deste lojista foi negociada, mudou, tem desconto, isenção ou condição "
    "especial com o comercial?",
    CONTEXTO + "Responda sim para condição especial, negociação, renegociação, desconto, isenção, tarifa "
    "zerada, aditivo ou nova vigência de taxa. Responda não para assunto cadastral ou operacional: EC, "
    "inatividade, uso só de remessa, conta bancária, contato, boleto, CNPJ.",
)
LAYA_VERSAO = "0.4.8"
LAYA_MODELO = "multilingual"
CORTE = 0.5


@dataclass(frozen=True)
class Sinal:
    cnpj: str
    lojista: str
    linha: int
    campo: str
    texto: str


@dataclass(frozen=True)
class SinalMarcado:
    sinal: Sinal
    metodo: str  # REGRA, MODELO ou AMBOS


class Classificador(Protocol):
    nome: str

    def relevantes(self, textos: list[str]) -> list[bool]: ...


class LayaClassificador:
    """Laya `noul` (probabilidade de sim), 3 instruções, voto majoritário. Sem texto gerado, sem motivo."""

    nome = f"laya-{LAYA_MODELO}-{LAYA_VERSAO}"

    def __init__(self) -> None:
        from laya import Router  # import tardio: dependência opcional (pip install ".[classificador]")

        self._router = Router(default=LAYA_MODELO)

    def relevantes(self, textos: list[str]) -> list[bool]:
        perguntas = {f"q{i}": {"type": "noul", "instructions": p} for i, p in enumerate(PERGUNTAS_LAYA)}
        votos_minimos = len(PERGUNTAS_LAYA) // 2 + 1
        resultado = []
        for texto in textos:
            respostas = self._router.predict({"anotacao": texto}, perguntas, model=LAYA_MODELO)["answers"]
            votos = sum(r["noul"] >= CORTE for r in respostas.values())
            resultado.append(votos >= votos_minimos)
        return resultado


def classificador_padrao() -> Classificador | None:
    """`TARVO_CLASSIFICADOR=laya` (padrão) ou `nenhum`. Sem o pacote, segue só com palavras-chave."""
    escolha = os.environ.get("TARVO_CLASSIFICADOR", "laya").strip().lower()
    if escolha == "nenhum":
        return None
    try:
        return LayaClassificador()
    except ImportError:
        log.warning("Laya não instalado: sinais detectados só por palavras-chave "
                    "(pip install '.[classificador]' para ativar)")
        return None


def extrair(taxas: pd.DataFrame) -> list[Sinal]:
    """Um sinal por texto de obs ou comentário de célula, com a linha física da planilha."""
    sinais = []
    for _, row in taxas.iterrows():
        for campo, coluna in (("obs", "obs"), ("comentario", "comentarios")):
            texto = row.get(coluna)
            if isinstance(texto, str) and texto.strip():
                sinais.append(Sinal(row["cnpj"], str(row["lojista"]).strip(), int(row["linha_origem"]),
                                    campo, texto.strip()))
    return sinais


def detectar(sinais: list[Sinal], classificador: Classificador | None) -> list[SinalMarcado]:
    por_regra = [bool(PALAVRAS_CHAVE.search(s.texto)) for s in sinais]
    textos = [s.texto for s in sinais]
    por_modelo = classificador.relevantes(textos) if classificador else [False] * len(sinais)
    metodos = {(True, True): "AMBOS", (True, False): "REGRA", (False, True): "MODELO"}
    return [SinalMarcado(s, metodos[(r, m)]) for s, r, m in zip(sinais, por_regra, por_modelo, strict=True)
            if r or m]


def _mes(competencia: str) -> tuple[dt.date, dt.date]:
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    inicio = dt.date(ano, mes, 1)
    fim = dt.date(ano + mes // 12, mes % 12 + 1, 1) - dt.timedelta(days=1)
    return inicio, fim


def _coberto(sinal: Sinal, competencia: str, condicoes, resolvidos) -> bool:
    inicio, fim = _mes(competencia)
    if any(c.cnpj == sinal.cnpj and c.inicio <= fim and (c.fim is None or c.fim >= inicio)
           for c in condicoes):
        return True
    return any(r.cnpj == sinal.cnpj and r.texto == sinal.texto for r in resolvidos)


def run(
    taxas: pd.DataFrame,
    competencia: str,
    classificador: Classificador | None,
    condicoes: tuple[cond_mod.Condicao, ...] | None = None,
    resolvidos: tuple[cond_mod.SinalResolvido, ...] | None = None,
) -> EngineResult:
    condicoes = cond_mod.carregar() if condicoes is None else condicoes
    resolvidos = cond_mod.carregar_sinais_resolvidos() if resolvidos is None else resolvidos
    marcados = detectar(extrair(taxas), classificador)
    pendencias, rastro = [], []
    for m in marcados:
        s = m.sinal
        if _coberto(s, competencia, condicoes, resolvidos):
            continue
        chave = hashlib.sha1(f"{s.cnpj}|{s.texto}".encode()).hexdigest()[:8]
        pend_id = f"TX-SINAL-{competencia}-{s.cnpj}-{chave}"
        pendencias.append({
            "id_saida": pend_id,
            "tipo": "CONDICAO_ESPECIAL_A_CONFIRMAR",
            "ref_origem": f"L{s.linha}",
            "valor_brl": Decimal("0.00"),
            "motivo": (
                f"{s.lojista} ({s.cnpj}), planilha L{s.linha} ({s.campo}): \"{s.texto}\". "
                f"Pode indicar condição comercial fora da planilha (detectado por {m.metodo}). "
                "Confirmar se muda a taxa; se sim, informar taxa por modalidade, início e fim."
            ),
            "quem_decide": "Comercial",
        })
        rastro.append({"id_saida": pend_id, "arquivo_origem": "taxas", "ref_origem": f"L{s.linha}",
                       "valor": Decimal("0.00"), "metadata": f"sinal_{s.campo};metodo={m.metodo}"})
    return EngineResult(pendencias=pd.DataFrame(pendencias), rastro=pd.DataFrame(rastro))
