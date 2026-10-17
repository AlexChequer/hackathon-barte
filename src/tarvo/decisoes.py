"""Serviço de decisões (propor, aprovar, rejeitar, revogar, substituir).

Separa claramente:
- `salvar_proposta`: só grava (status PENDENTE), não altera números oficiais.
- `aprovar`: verifica perfil contra `tratamentos.ACOES[acao].aprovado_por`.
- `substituir`: nova versão aprovada substitui a anterior (status SUBSTITUIDA).
- `revogar`: encerra a decisão sem substituição.

Decisões em escopo CASO valem só para aquele caso. Em escopo CONDICAO, podem ser
reaplicadas quando houver correspondência de CNPJ, modalidade e vigência. A publicação
de uma condição comercial continua sendo via `condicoes.registrar_condicao`, chamada
como "aplicação" da decisão aprovada (fonte única: condicoes_comerciais.json).

Nada aqui aceita `aprovado_por` do formulário como aprovação autenticada. Para registro
de **aprovação externa** (ex.: Comercial aprovou no e-mail), usar o parâmetro
`aprovacao_externa`: fica guardado quem aprovou + evidência, mas quem a Tarvo responde
é o `aprovador` autenticado.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from tarvo import autenticacao as auth
from tarvo import tratamentos
from tarvo.persistencia import conectar

log = logging.getLogger("tarvo.decisoes")


class DecisaoInvalida(ValueError):
    """Parâmetros insuficientes ou transição de estado proibida."""


ESTADOS = frozenset({"PENDENTE", "APROVADA", "REJEITADA", "REVOGADA", "SUBSTITUIDA"})


def _agora() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _dumps(valor: Any) -> str:
    return json.dumps(valor or {}, ensure_ascii=False, sort_keys=True)


def registrar_caso(saida: Path, caso) -> None:
    """Upsert do caso + evento se a composição mudou (aba RASTREABILIDADE)."""
    composicao = list(caso.composicao)
    with conectar(saida) as db:
        existente = db.execute(
            "SELECT composicao_hash FROM casos WHERE caso_hash = ?", (caso.caso_hash,)
        ).fetchone()
        agora = _agora()
        if existente is None:
            db.execute(
                "INSERT INTO casos (caso_hash, tipo, cnpj, ref, competencia,"
                " composicao_hash, composicao_json, primeira_vista, ultima_vista)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (caso.caso_hash, caso.tipo, caso.cnpj, caso.ref, caso.competencia,
                 caso.composicao_hash, _dumps(composicao), agora, agora),
            )
            _evento(db, caso.caso_hash, "ABERTO",
                    {"tipo": caso.tipo, "ref": caso.ref, "cnpj": caso.cnpj,
                     "composicao": composicao}, autor=None)
            return
        db.execute(
            "UPDATE casos SET ultima_vista = ?, composicao_hash = ?, composicao_json = ?"
            " WHERE caso_hash = ?",
            (agora, caso.composicao_hash, _dumps(composicao), caso.caso_hash),
        )
        if existente["composicao_hash"] != caso.composicao_hash:
            _evento(db, caso.caso_hash, "COMPOSICAO_MUDOU",
                    {"composicao": composicao}, autor=None)
            # Decisão aprovada em escopo CASO precisa ser reavaliada: anotamos no evento.
            db.execute(
                "UPDATE decisoes_v2 SET hashes_na_decisao = COALESCE(hashes_na_decisao,'')"
                " || '|composicao_mudou'"
                " WHERE caso_hash = ? AND status = 'APROVADA' AND escopo = 'CASO'",
                (caso.caso_hash,),
            )


def _evento(db: sqlite3.Connection, caso_hash: str, tipo: str, payload: dict,
            *, autor: str | None) -> None:
    db.execute(
        "INSERT INTO casos_eventos (caso_hash, timestamp, tipo_evento, autor, payload_json)"
        " VALUES (?,?,?,?,?)",
        (caso_hash, _agora(), tipo, autor, _dumps(payload)),
    )


def salvar_proposta(
    saida: Path,
    *,
    usuario: auth.Usuario,
    caso_hash: str | None,
    escopo: str,
    acao_tipo: str,
    parametros: dict,
    justificativa: str,
    evidencias: list[dict] | None = None,
    cnpj: str | None = None,
    modalidade: str | None = None,
    vigencia_inicio: str | None = None,
    vigencia_fim: str | None = None,
    dependencias: list[str] | None = None,
    substitui_id: int | None = None,
) -> dict:
    """Grava a proposta como PENDENTE. Não altera o fechamento."""
    if escopo not in ("CASO", "CONDICAO"):
        raise DecisaoInvalida(f"escopo inválido: {escopo!r}")
    if escopo == "CASO" and not caso_hash:
        raise DecisaoInvalida("escopo CASO exige caso_hash")
    if escopo == "CONDICAO" and not cnpj:
        raise DecisaoInvalida("escopo CONDICAO exige CNPJ")
    if not justificativa.strip():
        raise DecisaoInvalida("informe a justificativa (R20: motivo registrado)")
    faltando = tratamentos.valida_parametros(acao_tipo, parametros)
    if faltando:
        raise DecisaoInvalida(
            f"parâmetros obrigatórios faltando para {acao_tipo}: {faltando}"
        )
    with conectar(saida) as db:
        versao = 1
        if substitui_id is not None:
            anterior = db.execute(
                "SELECT versao FROM decisoes_v2 WHERE id = ?", (substitui_id,)
            ).fetchone()
            if anterior is None:
                raise DecisaoInvalida(f"decisão {substitui_id} não existe")
            versao = int(anterior["versao"]) + 1
        cur = db.execute(
            "INSERT INTO decisoes_v2 (caso_hash, escopo, cnpj, modalidade, vigencia_inicio,"
            " vigencia_fim, acao_tipo, parametros_json, justificativa, evidencias_json,"
            " dependencias_json, status, versao, substitui_id, autor, autor_perfil, criado_em)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?, 'PENDENTE', ?,?,?,?,?)",
            (caso_hash, escopo, cnpj, modalidade, vigencia_inicio, vigencia_fim,
             acao_tipo, _dumps(parametros), justificativa, _dumps(evidencias or []),
             _dumps(dependencias or []), versao, substitui_id,
             usuario.nome, usuario.perfil, _agora()),
        )
        decisao_id = cur.lastrowid
        if caso_hash:
            _evento(db, caso_hash, "PROPOSTA",
                    {"decisao_id": decisao_id, "acao": acao_tipo, "versao": versao},
                    autor=usuario.nome)
    return ler(saida, int(decisao_id))


def aprovar(
    saida: Path,
    decisao_id: int,
    *,
    usuario: auth.Usuario,
    hashes_atuais: dict[str, str] | None = None,
    rules_version: str | None = None,
    aprovacao_externa: dict | None = None,
) -> dict:
    """Marca APROVADA se o perfil do usuário autoriza a ação (R20)."""
    with conectar(saida) as db:
        linha = db.execute(
            "SELECT * FROM decisoes_v2 WHERE id = ?", (decisao_id,)
        ).fetchone()
        if linha is None:
            raise DecisaoInvalida(f"decisão {decisao_id} não existe")
        if linha["status"] != "PENDENTE":
            raise DecisaoInvalida(
                f"decisão {decisao_id} está {linha['status']}; só PENDENTE pode ser aprovada"
            )
        acao = tratamentos.ACOES.get(linha["acao_tipo"])
        if acao is None:
            raise DecisaoInvalida(f"ação desconhecida: {linha['acao_tipo']}")
        auth.exige(
            usuario, acao.aprovado_por,
            f"aprovar {linha['acao_tipo']} (R20)",
        )
        db.execute(
            "UPDATE decisoes_v2 SET status = 'APROVADA', aprovador = ?, aprovador_perfil = ?,"
            " aprovado_em = ?, aprovacao_externa_json = ?, hashes_na_decisao = ?,"
            " rules_na_decisao = ? WHERE id = ?",
            (usuario.nome, usuario.perfil, _agora(), _dumps(aprovacao_externa or {}),
             _dumps(hashes_atuais or {}), rules_version or "", decisao_id),
        )
        if linha["substitui_id"]:
            db.execute(
                "UPDATE decisoes_v2 SET status = 'SUBSTITUIDA' WHERE id = ? AND status = 'APROVADA'",
                (linha["substitui_id"],),
            )
            if linha["caso_hash"]:
                _evento(db, linha["caso_hash"], "SUBSTITUIDA",
                        {"decisao_id": linha["substitui_id"], "por": decisao_id},
                        autor=usuario.nome)
        if linha["caso_hash"]:
            _evento(db, linha["caso_hash"], "APROVADA",
                    {"decisao_id": decisao_id, "aprovador": usuario.nome,
                     "externa": bool(aprovacao_externa)}, autor=usuario.nome)
    return ler(saida, decisao_id)


def rejeitar(saida: Path, decisao_id: int, *, usuario: auth.Usuario, motivo: str) -> dict:
    with conectar(saida) as db:
        linha = db.execute(
            "SELECT * FROM decisoes_v2 WHERE id = ?", (decisao_id,)
        ).fetchone()
        if linha is None:
            raise DecisaoInvalida(f"decisão {decisao_id} não existe")
        if linha["status"] != "PENDENTE":
            raise DecisaoInvalida(f"só PENDENTE pode ser rejeitada; está {linha['status']}")
        acao = tratamentos.ACOES.get(linha["acao_tipo"])
        if acao is not None:
            auth.exige(usuario, acao.aprovado_por, f"rejeitar {linha['acao_tipo']}")
        db.execute(
            "UPDATE decisoes_v2 SET status = 'REJEITADA', aprovador = ?, aprovador_perfil = ?,"
            " aprovado_em = ? WHERE id = ?",
            (usuario.nome, usuario.perfil, _agora(), decisao_id),
        )
        if linha["caso_hash"]:
            _evento(db, linha["caso_hash"], "REJEITADA",
                    {"decisao_id": decisao_id, "motivo": motivo}, autor=usuario.nome)
    return ler(saida, decisao_id)


def revogar(saida: Path, decisao_id: int, *, usuario: auth.Usuario, motivo: str) -> dict:
    with conectar(saida) as db:
        linha = db.execute(
            "SELECT * FROM decisoes_v2 WHERE id = ?", (decisao_id,)
        ).fetchone()
        if linha is None:
            raise DecisaoInvalida(f"decisão {decisao_id} não existe")
        if linha["status"] != "APROVADA":
            raise DecisaoInvalida(
                f"só APROVADA pode ser revogada; está {linha['status']}"
            )
        acao = tratamentos.ACOES.get(linha["acao_tipo"])
        if acao is not None:
            auth.exige(usuario, acao.aprovado_por, f"revogar {linha['acao_tipo']}")
        db.execute(
            "UPDATE decisoes_v2 SET status = 'REVOGADA' WHERE id = ?", (decisao_id,)
        )
        if linha["caso_hash"]:
            _evento(db, linha["caso_hash"], "REVOGADA",
                    {"decisao_id": decisao_id, "motivo": motivo}, autor=usuario.nome)
    return ler(saida, decisao_id)


def ler(saida: Path, decisao_id: int) -> dict:
    with conectar(saida) as db:
        linha = db.execute(
            "SELECT * FROM decisoes_v2 WHERE id = ?", (decisao_id,)
        ).fetchone()
        if linha is None:
            raise DecisaoInvalida(f"decisão {decisao_id} não existe")
        return _como_dict(linha)


def _como_dict(linha: sqlite3.Row) -> dict:
    d = dict(linha)
    for campo in ("parametros_json", "evidencias_json", "dependencias_json",
                  "aprovacao_externa_json"):
        if d.get(campo):
            try:
                d[campo.removesuffix("_json")] = json.loads(d[campo])
            except (json.JSONDecodeError, TypeError):
                d[campo.removesuffix("_json")] = None
    return d


def listar_do_caso(saida: Path, caso_hash: str) -> list[dict]:
    with conectar(saida) as db:
        rows = db.execute(
            "SELECT * FROM decisoes_v2 WHERE caso_hash = ? ORDER BY id DESC",
            (caso_hash,),
        ).fetchall()
        return [_como_dict(r) for r in rows]


def eventos_do_caso(saida: Path, caso_hash: str) -> list[dict]:
    with conectar(saida) as db:
        rows = db.execute(
            "SELECT * FROM casos_eventos WHERE caso_hash = ? ORDER BY id DESC",
            (caso_hash,),
        ).fetchall()
        resposta = []
        for r in rows:
            d = dict(r)
            if d.get("payload_json"):
                try:
                    d["payload"] = json.loads(d["payload_json"])
                except json.JSONDecodeError:
                    d["payload"] = None
            resposta.append(d)
        return resposta


def listar_condicoes_aprovadas(saida: Path) -> list[dict]:
    """Decisões em escopo CONDICAO, status APROVADA, para checagem de reaplicação."""
    with conectar(saida) as db:
        rows = db.execute(
            "SELECT * FROM decisoes_v2 WHERE escopo = 'CONDICAO' AND status = 'APROVADA'"
            " ORDER BY id DESC"
        ).fetchall()
        return [_como_dict(r) for r in rows]


def registrar_aplicacao(
    saida: Path,
    *,
    decisao_id: int,
    caso_hash: str | None,
    execucao_id: int | None,
    competencia: str,
    efeito: str,
    antes: dict | None = None,
    depois: dict | None = None,
    delta_centavos: int | None = None,
) -> int:
    """Registra que a decisão produziu efeito nesta execução. Idempotente por (decisão, execução)."""
    with conectar(saida) as db:
        existe = db.execute(
            "SELECT id FROM aplicacoes WHERE decisao_id = ? AND execucao_id = ?",
            (decisao_id, execucao_id),
        ).fetchone()
        if existe:
            return int(existe["id"])
        cur = db.execute(
            "INSERT INTO aplicacoes (decisao_id, caso_hash, execucao_id, competencia,"
            " timestamp, efeito, antes_json, depois_json, delta_centavos)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (decisao_id, caso_hash, execucao_id, competencia, _agora(), efeito,
             _dumps(antes or {}), _dumps(depois or {}), delta_centavos),
        )
        if caso_hash:
            _evento(db, caso_hash, "APLICADA",
                    {"decisao_id": decisao_id, "efeito": efeito,
                     "delta_centavos": delta_centavos}, autor=None)
        return int(cur.lastrowid)


def registrar_resultado_operacional(
    saida: Path,
    *,
    caso_hash: str,
    usuario: auth.Usuario,
    status: str,
    saldo_centavos: int | None = None,
    operacoes: list[str] | None = None,
    evidencia: str | None = None,
    descricao: str | None = None,
) -> dict:
    """Separado do tratamento no fechamento: aqui vai o que **de fato aconteceu**."""
    STATUS_OK = {"ABERTO", "AGUARDANDO_RETORNO", "PARCIAL", "RESOLVIDO"}
    if status not in STATUS_OK:
        raise DecisaoInvalida(f"status inválido: {status!r}; use {sorted(STATUS_OK)}")
    if status == "RESOLVIDO" and not evidencia:
        raise DecisaoInvalida(
            "resolução integral exige evidência (ex.: TED, e-mail, protocolo)"
        )
    if status == "PARCIAL" and saldo_centavos is None and not operacoes:
        raise DecisaoInvalida(
            "resolução parcial exige saldo_centavos ou operações resolvidas"
        )
    with conectar(saida) as db:
        cur = db.execute(
            "INSERT INTO resultados_operacionais (caso_hash, timestamp, autor, status,"
            " saldo_centavos, operacoes_json, evidencia, descricao)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (caso_hash, _agora(), usuario.nome, status, saldo_centavos,
             _dumps(operacoes or []), evidencia, descricao),
        )
        _evento(db, caso_hash, "RESULTADO",
                {"status": status, "saldo_centavos": saldo_centavos,
                 "operacoes": operacoes}, autor=usuario.nome)
        return {"id": int(cur.lastrowid)}


def resultados_do_caso(saida: Path, caso_hash: str) -> list[dict]:
    with conectar(saida) as db:
        rows = db.execute(
            "SELECT * FROM resultados_operacionais WHERE caso_hash = ? ORDER BY id DESC",
            (caso_hash,),
        ).fetchall()
        resposta = []
        for r in rows:
            d = dict(r)
            if d.get("operacoes_json"):
                try:
                    d["operacoes"] = json.loads(d["operacoes_json"])
                except json.JSONDecodeError:
                    d["operacoes"] = None
            resposta.append(d)
        return resposta


def ultimo_resultado(saida: Path, caso_hash: str) -> dict | None:
    resultados = resultados_do_caso(saida, caso_hash)
    return resultados[0] if resultados else None


# ---- reutilização em 3 níveis -------------------------------------------------


def _parse_data(valor: str | None):
    if not valor:
        return None
    try:
        return dt.date.fromisoformat(valor)
    except ValueError:
        return None


def encontrar_decisao_para_caso(saida: Path, caso) -> dict | None:
    """Nível 1: decisão APROVADA diretamente ligada a este caso_hash."""
    decisoes = listar_do_caso(saida, caso.caso_hash)
    for d in decisoes:
        if d["status"] == "APROVADA":
            return d
    return None


def encontrar_condicao_aplicavel(saida: Path, caso, competencia: str) -> dict | None:
    """Nível 2: decisão de escopo CONDICAO cobre este CNPJ/modalidade/vigência.

    O match é determinístico: CNPJ precisa casar. Modalidade só é exigida se a condição
    aprovada declarou modalidade. Vigência: a competência cai dentro de inicio..fim.
    """
    if not caso.cnpj:
        return None
    hoje = _parse_data(f"{competencia}-01")
    for d in listar_condicoes_aprovadas(saida):
        if d.get("cnpj") and d["cnpj"] != caso.cnpj:
            continue
        inicio = _parse_data(d.get("vigencia_inicio"))
        fim = _parse_data(d.get("vigencia_fim"))
        if inicio and hoje and hoje < inicio:
            continue
        if fim and hoje and hoje > fim:
            continue
        return d
    return None


def precedentes_para(saida: Path, caso) -> list[dict]:
    """Nível 3: decisões em casos com o mesmo tipo, mas identidade diferente."""
    with conectar(saida) as db:
        rows = db.execute(
            "SELECT d.*, c.ref AS caso_ref, c.cnpj AS caso_cnpj FROM decisoes_v2 d"
            " JOIN casos c ON d.caso_hash = c.caso_hash"
            " WHERE c.tipo = ? AND d.caso_hash <> ? AND d.status IN ('APROVADA','REJEITADA')"
            " ORDER BY d.id DESC LIMIT 10",
            (caso.tipo, caso.caso_hash),
        ).fetchall()
        return [_como_dict(r) for r in rows]


# ---- métricas ----------------------------------------------------------------


def metricas(saida: Path, competencia: str | None = None) -> dict:
    """Métricas simples para o painel/relatório, consultáveis sem embedding."""
    with conectar(saida) as db:
        por_status = {s: 0 for s in ESTADOS}
        for s, c in db.execute(
            "SELECT status, COUNT(*) FROM decisoes_v2 GROUP BY status"
        ).fetchall():
            por_status[s] = int(c)
        aplicacoes = int(db.execute(
            "SELECT COUNT(*) FROM aplicacoes"
            + (" WHERE competencia = ?" if competencia else ""),
            (competencia,) if competencia else (),
        ).fetchone()[0])
        reaplicadas = int(db.execute(
            "SELECT COUNT(*) FROM aplicacoes a"
            " JOIN decisoes_v2 d ON a.decisao_id = d.id"
            " WHERE d.escopo = 'CONDICAO'"
            + (" AND a.competencia = ?" if competencia else ""),
            (competencia,) if competencia else (),
        ).fetchone()[0])
        resultados_abertos = int(db.execute(
            "SELECT COUNT(*) FROM casos c WHERE NOT EXISTS ("
            "  SELECT 1 FROM resultados_operacionais r"
            "  WHERE r.caso_hash = c.caso_hash AND r.status = 'RESOLVIDO'"
            ")"
        ).fetchone()[0])
        parciais = int(db.execute(
            "SELECT COUNT(DISTINCT caso_hash) FROM resultados_operacionais"
            " WHERE status = 'PARCIAL'"
        ).fetchone()[0])
    return {
        "decisoes_por_status": por_status,
        "aplicacoes_total": aplicacoes,
        "aplicacoes_por_condicao": reaplicadas,
        "casos_sem_resolucao": resultados_abertos,
        "casos_parcialmente_resolvidos": parciais,
    }
