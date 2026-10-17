"""API do painel. Não tem regra de negócio: chama `run_closing`, lê a saída e grava condições
comerciais pelo módulo `tarvo.condicoes` (que valida). Valores monetários saem como texto."""

from __future__ import annotations

import datetime as dt
import fnmatch
import logging
import math
from decimal import Decimal
from pathlib import Path
from typing import Annotated, Any

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tarvo import condicoes as cond_mod
from tarvo import rules, sinais
from tarvo.avaliacao import avaliar_e_persistir
from tarvo.loaders import ESPERADOS, FILES, OPCIONAIS, load_all
from tarvo.loaders.identificar import classificar_lote
from tarvo.orquestrador import ClosingResult, run_closing

log = logging.getLogger("tarvo.web")
STATIC = Path(__file__).resolve().parent / "static"
FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures"
LIMITE_UPLOAD = 20 * 1024 * 1024
PADROES_ACEITOS = [*FILES.values(), *OPCIONAIS.values(), "00_LEIA-ME*"]


def _json(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if valor is pd.NaT or valor is None:
        return None
    return valor


def _registros(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{k: _json(v) for k, v in linha.items()} for linha in df.to_dict("records")]


def _soma(df: pd.DataFrame, coluna: str, filtro=None) -> str:
    if df.empty:
        return "0.00"
    alvo = df[filtro(df)] if filtro is not None else df
    return str(sum((Decimal(str(v)) for v in alvo[coluna]), Decimal("0.00")))


def _totais(r: ClosingResult) -> dict:
    com, div = r.comissoes, r.divergencias

    def prefixo(p: str):
        return lambda d: d["id_saida"].str.startswith(p)

    return {
        "comissao_checkout": _soma(com, "comissao_brl", lambda d: d["linha_negocio"] == "CHECKOUT"),
        "comissao_remessa": _soma(com, "comissao_brl", lambda d: d["linha_negocio"] == "REMESSA"),
        "cobrar_orbe": _soma(div, "diferenca_brl", prefixo("CK-DIV")),
        "devolver_condicao": _soma(div, "diferenca_brl", prefixo("CK-COND")),
        "divergencia_remessa": _soma(div, "diferenca_brl", prefixo("RM-DIV")),
        "notas": _soma(r.notas, "valor_brl"),
    }


def _arquivos(dados: Path) -> list[dict]:
    achados = []
    for padrao in PADROES_ACEITOS:
        for f in sorted(dados.glob(padrao)):
            achados.append({"nome": f.name, "bytes": f.stat().st_size,
                            "opcional": any(fnmatch.fnmatch(f.name, p) for p in OPCIONAIS.values())})
    return achados


def criar_app(dados: Path, saida: Path, condicoes_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="Tarvo · Fechamento", docs_url="/api/docs")
    app.state.dados = Path(dados)
    app.state.saida = Path(saida)
    app.state.condicoes = condicoes_path or cond_mod.CAMINHO_PADRAO
    app.state.resultado = None
    app.state.avaliacao = None

    def fechar() -> ClosingResult:
        try:
            r = run_closing(app.state.dados, app.state.saida, condicoes_path=app.state.condicoes)
        except (FileNotFoundError, ValueError, KeyError) as exc:
            log.exception("falha no fechamento")
            raise HTTPException(
                400, f"Não foi possível fechar com os arquivos de {app.state.dados}: {exc}"
            ) from exc
        app.state.resultado = r
        app.state.avaliacao = avaliar_e_persistir(r, fixtures_dir=FIXTURES, saida=app.state.saida) \
            if FIXTURES.exists() else None
        return r

    def resultado() -> ClosingResult:
        return app.state.resultado or fechar()

    def resposta(r: ClosingResult) -> dict:
        aval = (app.state.avaliacao or {}).get("resumo")
        return {
            "competencia": r.competencia,
            "execucao_id": r.execucao_id,
            "pasta_saida": str(r.out_dir),
            "regras_versao": rules.VERSION,
            "duracao_s": r.duracoes_s.get("total"),
            "arquivos": _arquivos(app.state.dados),
            "validacoes": {
                "rastro_ok": r.problemas_rastro.empty,
                "integridade_ok": not r.problemas_integridade,
                "problemas": [str(p) for p in r.problemas_integridade][:20],
                "referencia": aval,
            },
            "totais": _totais(r),
            "tabelas": {nome: _registros(getattr(r, nome)) for nome in
                        ("comissoes", "divergencias", "notas", "lancamentos", "pendencias")},
        }

    @app.get("/api/fechamento")
    def get_fechamento() -> dict:
        return resposta(resultado())

    @app.post("/api/fechar")
    def post_fechar() -> dict:
        return resposta(fechar())

    @app.get("/api/rastro/{id_saida}")
    def get_rastro(id_saida: str) -> dict:
        rastro = resultado().rastro
        linhas = rastro[rastro["id_saida"] == id_saida]
        if linhas.empty:
            raise HTTPException(404, f"Sem rastro para {id_saida}")
        return {"id_saida": id_saida, "linhas": _registros(linhas)}

    @app.get("/api/lojistas")
    def get_lojistas() -> list[dict]:
        taxas = load_all(app.state.dados)["taxas"]
        unicos = taxas.drop_duplicates("cnpj")[["cnpj", "lojista"]]
        return [{"cnpj": c, "lojista": str(n).strip()} for c, n in unicos.itertuples(index=False)]

    @app.get("/api/condicoes")
    def get_condicoes() -> dict:
        bruto = cond_mod._ler_arquivo(app.state.condicoes)
        return {"condicoes": bruto.get("condicoes", []),
                "sinais_resolvidos": bruto.get("sinais_resolvidos", [])}

    @app.post("/api/condicoes", status_code=201)
    def post_condicao(corpo: dict) -> dict:
        try:
            registro = cond_mod.registrar_condicao(app.state.condicoes, corpo)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"condicao": registro, "fechamento": resposta(fechar())}

    @app.post("/api/sinais-resolvidos", status_code=201)
    def post_sinal_resolvido(corpo: dict) -> dict:
        try:
            registro = cond_mod.registrar_sinal_resolvido(app.state.condicoes, corpo)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"sinal": registro, "fechamento": resposta(fechar())}

    @app.get("/api/sinais")
    def get_sinais() -> list[dict]:
        r = resultado()
        taxas = load_all(app.state.dados)["taxas"]
        conds = cond_mod.carregar(app.state.condicoes)
        resolvidos = cond_mod.carregar_sinais_resolvidos(app.state.condicoes)
        return [{"id_saida": pid, "cnpj": m.sinal.cnpj, "lojista": m.sinal.lojista, "linha": m.sinal.linha,
                 "campo": m.sinal.campo, "texto": m.sinal.texto, "metodo": m.metodo}
                for m, pid in sinais.abertos(taxas, r.competencia, conds, resolvidos)]

    @app.get("/api/arquivos-esperados")
    def get_arquivos_esperados() -> list[dict]:
        return ESPERADOS

    async def _ler(arquivos: list[UploadFile]) -> list[tuple[str, bytes]]:
        lidos = []
        for a in arquivos:
            conteudo = await a.read()
            nome = Path(a.filename or "").name
            if len(conteudo) > LIMITE_UPLOAD:
                raise HTTPException(413, f"{nome} passa de 20 MB")
            lidos.append((nome, conteudo))
        return lidos

    @app.post("/api/arquivos/conferir")
    async def post_conferir(arquivos: Annotated[list[UploadFile], File()]) -> dict:
        """Só confere (não grava nem fecha): a tela mostra o que foi reconhecido e o que falta."""
        return classificar_lote(await _ler(arquivos))

    @app.post("/api/arquivos")
    async def post_arquivos(arquivos: Annotated[list[UploadFile], File()]) -> dict:
        lidos = await _ler(arquivos)
        lote = classificar_lote(lidos)
        if lote["problemas"]:
            raise HTTPException(422, "Envie exatamente os 6 arquivos do mês. " + "; ".join(lote["problemas"]))
        destino = app.state.saida / "entradas" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        destino.mkdir(parents=True, exist_ok=True)
        canonicos = {i["nome"]: i["nome_canonico"] for i in lote["arquivos"]}
        for nome, conteudo in lidos:
            if canonicos.get(nome):
                (destino / canonicos[nome]).write_bytes(conteudo)
        app.state.dados = destino
        return resposta(fechar())

    if (STATIC / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/{caminho:path}", include_in_schema=False)
        def front(caminho: str) -> FileResponse:
            return FileResponse(STATIC / "index.html")

    return app
