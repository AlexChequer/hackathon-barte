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
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tarvo import autenticacao as auth_mod
from tarvo import condicoes as cond_mod
from tarvo import decisoes, rules, sinais, tratamentos
from tarvo.avaliacao import avaliar_e_persistir
from tarvo.loaders import ESPERADOS, FILES, OPCIONAIS, load_disponiveis
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


def criar_app(
    dados: Path,
    saida: Path,
    condicoes_path: Path | None = None,
    usuarios_path: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Tarvo · Fechamento", docs_url="/api/docs")
    app.state.dados = Path(dados)
    app.state.saida = Path(saida)
    app.state.condicoes = condicoes_path or cond_mod.CAMINHO_PADRAO
    app.state.usuarios = usuarios_path or auth_mod.CAMINHO_PADRAO
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
        casos_por_id = {k: {
            "caso_hash": c.caso_hash, "tipo": c.tipo, "cnpj": c.cnpj, "ref": c.ref,
            "competencia": c.competencia, "composicao": list(c.composicao),
        } for k, c in r.casos.items()}
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
            "bloqueios": r.bloqueios,
            "totais": _totais(r),
            "tabelas": {nome: _registros(getattr(r, nome)) for nome in
                        ("comissoes", "divergencias", "notas", "lancamentos", "pendencias")},
            "casos": casos_por_id,
            "aplicacoes_decisoes": r.aplicacoes_decisoes,
            "rascunhos": r.rascunhos,
        }

    def usuario_de(user: str | None, perfil: str | None) -> auth_mod.Usuario:
        try:
            return auth_mod.resolver(user, perfil, caminho=app.state.usuarios)
        except auth_mod.ErroAutenticacao as exc:
            raise HTTPException(401, str(exc)) from exc

    @app.get("/api/fechamento")
    def get_fechamento() -> dict:
        return resposta(resultado())

    @app.post("/api/fechar")
    def post_fechar() -> dict:
        return resposta(fechar())

    @app.get("/api/rastro")
    def get_rastro_completo() -> dict:
        return {"linhas": _registros(resultado().rastro)}

    @app.get("/api/rastro/{id_saida}")
    def get_rastro(id_saida: str) -> dict:
        rastro = resultado().rastro
        linhas = rastro[rastro["id_saida"] == id_saida]
        if linhas.empty:
            raise HTTPException(404, f"Sem rastro para {id_saida}")
        return {"id_saida": id_saida, "linhas": _registros(linhas)}

    @app.get("/api/lojistas")
    def get_lojistas() -> list[dict]:
        taxas = load_disponiveis(app.state.dados)[0]["taxas"]
        if taxas is None:
            return []
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
        taxas = load_disponiveis(app.state.dados)[0]["taxas"]
        if taxas is None:
            return []
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
            raise HTTPException(422, "Arquivos com problema: " + "; ".join(lote["problemas"]))
        destino = app.state.saida / "entradas" / dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        destino.mkdir(parents=True, exist_ok=True)
        canonicos = {i["nome"]: i["nome_canonico"] for i in lote["arquivos"]}
        for nome, conteudo in lidos:
            if canonicos.get(nome):
                (destino / canonicos[nome]).write_bytes(conteudo)
        app.state.dados = destino
        return resposta(fechar())

    @app.get("/api/tratamentos")
    def get_tratamentos() -> dict:
        return {"acoes": [
            {"tipo": a.tipo, "descricao": a.descricao,
             "aprovado_por": sorted(a.aprovado_por),
             "altera_referencia": a.altera_referencia,
             "altera_calculo": a.altera_calculo,
             "apenas_operacional": a.apenas_operacional,
             "parametros_obrigatorios": list(a.parametros_obrigatorios),
             "tipos_pendencia": list(a.tipos_pendencia)}
            for a in tratamentos.ACOES.values()
        ]}

    @app.get("/api/casos/{caso_hash}")
    def get_caso(caso_hash: str) -> dict:
        return {
            "decisoes": decisoes.listar_do_caso(app.state.saida, caso_hash),
            "eventos": decisoes.eventos_do_caso(app.state.saida, caso_hash),
            "resultados": decisoes.resultados_do_caso(app.state.saida, caso_hash),
        }

    @app.get("/api/casos/{caso_hash}/precedentes")
    def get_precedentes(caso_hash: str) -> dict:
        r = resultado()
        caso = next((c for c in r.casos.values() if c.caso_hash == caso_hash), None)
        if caso is None:
            raise HTTPException(404, f"caso {caso_hash} não está entre as pendências atuais")
        return {"precedentes": decisoes.precedentes_para(app.state.saida, caso)}

    @app.post("/api/decisoes", status_code=201)
    def post_proposta(
        corpo: dict,
        x_tarvo_usuario: Annotated[str | None, Header()] = None,
        x_tarvo_perfil: Annotated[str | None, Header()] = None,
    ) -> dict:
        u = usuario_de(x_tarvo_usuario, x_tarvo_perfil)
        try:
            return decisoes.salvar_proposta(
                app.state.saida, usuario=u,
                caso_hash=corpo.get("caso_hash"),
                escopo=str(corpo.get("escopo", "CASO")),
                acao_tipo=str(corpo.get("acao_tipo", "")),
                parametros=corpo.get("parametros") or {},
                justificativa=str(corpo.get("justificativa", "")),
                evidencias=corpo.get("evidencias"),
                cnpj=corpo.get("cnpj"),
                modalidade=corpo.get("modalidade"),
                vigencia_inicio=corpo.get("vigencia_inicio"),
                vigencia_fim=corpo.get("vigencia_fim"),
                dependencias=corpo.get("dependencias"),
                substitui_id=corpo.get("substitui_id"),
            )
        except decisoes.DecisaoInvalida as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post("/api/decisoes/{decisao_id}/aprovar")
    def post_aprovar(
        decisao_id: int,
        corpo: dict | None = None,
        x_tarvo_usuario: Annotated[str | None, Header()] = None,
        x_tarvo_perfil: Annotated[str | None, Header()] = None,
    ) -> dict:
        u = usuario_de(x_tarvo_usuario, x_tarvo_perfil)
        corpo = corpo or {}
        try:
            decisao = decisoes.aprovar(
                app.state.saida, decisao_id, usuario=u,
                hashes_atuais=(app.state.resultado.hashes if app.state.resultado else {}),
                rules_version=rules.VERSION,
                aprovacao_externa=corpo.get("aprovacao_externa"),
            )
        except decisoes.DecisaoInvalida as exc:
            raise HTTPException(422, str(exc)) from exc
        except auth_mod.SemPermissao as exc:
            raise HTTPException(403, str(exc)) from exc
        # Para ação REGISTRAR_CONDICAO_COMERCIAL, publicamos a condição (fonte única).
        if decisao["acao_tipo"] == "REGISTRAR_CONDICAO_COMERCIAL":
            try:
                publicado = cond_mod.registrar_condicao(app.state.condicoes, {
                    **decisao["parametros"],
                    "fonte": decisao["justificativa"],
                    "aprovado_por": u.perfil,
                    "registrado_por": u.nome,
                })
            except (ValueError, TypeError) as exc:
                raise HTTPException(422, f"não publicou condição: {exc}") from exc
            decisoes.registrar_aplicacao(
                app.state.saida, decisao_id=decisao_id, caso_hash=decisao.get("caso_hash"),
                execucao_id=None, competencia=decisao.get("vigencia_inicio", "")[:7] or "",
                efeito="CONDICAO_PUBLICADA", depois={"condicao_id": publicado["id"]},
            )
        if decisao["acao_tipo"] == "CONFIRMAR_ANOTACAO_SEM_EFEITO":
            cond_mod.registrar_sinal_resolvido(app.state.condicoes, {
                **decisao["parametros"],
                "fonte": decisao["justificativa"],
                "registrado_por": u.nome,
            })
            decisoes.registrar_aplicacao(
                app.state.saida, decisao_id=decisao_id, caso_hash=decisao.get("caso_hash"),
                execucao_id=None, competencia="", efeito="SINAL_RESOLVIDO",
            )
        return {"decisao": decisao, "fechamento": resposta(fechar())}

    @app.post("/api/decisoes/{decisao_id}/rejeitar")
    def post_rejeitar(
        decisao_id: int,
        corpo: dict,
        x_tarvo_usuario: Annotated[str | None, Header()] = None,
        x_tarvo_perfil: Annotated[str | None, Header()] = None,
    ) -> dict:
        u = usuario_de(x_tarvo_usuario, x_tarvo_perfil)
        try:
            return decisoes.rejeitar(app.state.saida, decisao_id, usuario=u,
                                     motivo=str(corpo.get("motivo", "")))
        except decisoes.DecisaoInvalida as exc:
            raise HTTPException(422, str(exc)) from exc
        except auth_mod.SemPermissao as exc:
            raise HTTPException(403, str(exc)) from exc

    @app.post("/api/decisoes/{decisao_id}/revogar")
    def post_revogar(
        decisao_id: int,
        corpo: dict,
        x_tarvo_usuario: Annotated[str | None, Header()] = None,
        x_tarvo_perfil: Annotated[str | None, Header()] = None,
    ) -> dict:
        u = usuario_de(x_tarvo_usuario, x_tarvo_perfil)
        try:
            return decisoes.revogar(app.state.saida, decisao_id, usuario=u,
                                    motivo=str(corpo.get("motivo", "")))
        except decisoes.DecisaoInvalida as exc:
            raise HTTPException(422, str(exc)) from exc
        except auth_mod.SemPermissao as exc:
            raise HTTPException(403, str(exc)) from exc

    @app.post("/api/casos/{caso_hash}/resultado", status_code=201)
    def post_resultado(
        caso_hash: str,
        corpo: dict,
        x_tarvo_usuario: Annotated[str | None, Header()] = None,
        x_tarvo_perfil: Annotated[str | None, Header()] = None,
    ) -> dict:
        u = usuario_de(x_tarvo_usuario, x_tarvo_perfil)
        try:
            return decisoes.registrar_resultado_operacional(
                app.state.saida, caso_hash=caso_hash, usuario=u,
                status=str(corpo.get("status", "")),
                saldo_centavos=corpo.get("saldo_centavos"),
                operacoes=corpo.get("operacoes"),
                evidencia=corpo.get("evidencia"),
                descricao=corpo.get("descricao"),
            )
        except decisoes.DecisaoInvalida as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/metricas")
    def get_metricas() -> dict:
        comp = app.state.resultado.competencia if app.state.resultado else None
        return decisoes.metricas(app.state.saida, comp)

    if (STATIC / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

        @app.get("/{caminho:path}", include_in_schema=False)
        def front(caminho: str) -> FileResponse:
            return FileResponse(STATIC / "index.html")

    return app
