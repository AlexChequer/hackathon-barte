"""SQLite leve: execuções, decisões, casos, aplicações e resultados operacionais.

- `execucoes` guarda metadados de cada rodada.
- `casos` guarda a identidade estável do problema (`casos.Caso`) e a composição vigente.
- `casos_eventos` guarda a linha do tempo do caso (abertura, mudança de composição,
  proposta, aprovação, aplicação, resolução).
- `decisoes` guarda escolhas humanas, versionadas, com estado e aprovador.
- `aplicacoes` guarda em que execução uma decisão aprovada produziu efeito.
- `resultados_operacionais` separa o tratamento no fechamento da resposta de fato
  (parcial/total, aguardando retorno).
- Decisões antigas (schema v1) continuam legíveis, só não entram nas consultas novas.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import sqlite3
from pathlib import Path

log = logging.getLogger("tarvo.persist")

SCHEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    competencia   TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    commit_hash   TEXT,
    hashes_json   TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    contagens     TEXT NOT NULL,
    duracoes_s    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decisoes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    competencia        TEXT NOT NULL,
    id_saida           TEXT NOT NULL,
    tipo_pendencia     TEXT NOT NULL,
    decisao            TEXT NOT NULL,
    autor              TEXT NOT NULL,
    timestamp          TEXT NOT NULL,
    hashes_na_decisao  TEXT NOT NULL,
    rules_na_decisao   TEXT NOT NULL,
    precisa_reavaliar  INTEGER NOT NULL DEFAULT 0,
    motivo_reavaliar   TEXT,
    UNIQUE(competencia, id_saida)
);

-- Novas tabelas (ciclo de resolução de pendências)
CREATE TABLE IF NOT EXISTS casos (
    caso_hash          TEXT PRIMARY KEY,
    tipo               TEXT NOT NULL,
    cnpj               TEXT NOT NULL,
    ref                TEXT NOT NULL,
    competencia        TEXT NOT NULL,
    composicao_hash    TEXT NOT NULL,
    composicao_json    TEXT NOT NULL,
    primeira_vista     TEXT NOT NULL,
    ultima_vista       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS casos_eventos (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_hash          TEXT NOT NULL,
    timestamp          TEXT NOT NULL,
    tipo_evento        TEXT NOT NULL,
    autor              TEXT,
    payload_json       TEXT NOT NULL,
    FOREIGN KEY (caso_hash) REFERENCES casos(caso_hash)
);

CREATE TABLE IF NOT EXISTS decisoes_v2 (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_hash              TEXT,
    escopo                 TEXT NOT NULL,                 -- CASO | CONDICAO
    cnpj                   TEXT,
    modalidade             TEXT,
    vigencia_inicio        TEXT,
    vigencia_fim           TEXT,
    acao_tipo              TEXT NOT NULL,
    parametros_json        TEXT NOT NULL,
    justificativa          TEXT NOT NULL,
    evidencias_json        TEXT NOT NULL,
    dependencias_json      TEXT NOT NULL,
    status                 TEXT NOT NULL,                 -- PENDENTE|APROVADA|REJEITADA|REVOGADA|SUBSTITUIDA
    versao                 INTEGER NOT NULL DEFAULT 1,
    substitui_id           INTEGER,
    autor                  TEXT NOT NULL,
    autor_perfil           TEXT NOT NULL,
    criado_em              TEXT NOT NULL,
    aprovador              TEXT,
    aprovador_perfil       TEXT,
    aprovado_em            TEXT,
    aprovacao_externa_json TEXT,
    hashes_na_decisao      TEXT,
    rules_na_decisao       TEXT,
    FOREIGN KEY (caso_hash) REFERENCES casos(caso_hash)
);

CREATE TABLE IF NOT EXISTS aplicacoes (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    decisao_id         INTEGER NOT NULL,
    caso_hash          TEXT,
    execucao_id        INTEGER,
    competencia        TEXT NOT NULL,
    timestamp          TEXT NOT NULL,
    efeito             TEXT NOT NULL,                     -- CONDICAO_PUBLICADA|SINAL_RESOLVIDO|...
    antes_json         TEXT,
    depois_json        TEXT,
    delta_centavos     INTEGER,
    FOREIGN KEY (decisao_id) REFERENCES decisoes_v2(id)
);

CREATE TABLE IF NOT EXISTS resultados_operacionais (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    caso_hash          TEXT NOT NULL,
    timestamp          TEXT NOT NULL,
    autor              TEXT NOT NULL,
    status             TEXT NOT NULL,                     -- ABERTO|AGUARDANDO_RETORNO|PARCIAL|RESOLVIDO
    saldo_centavos     INTEGER,
    operacoes_json     TEXT,
    evidencia          TEXT,
    descricao          TEXT,
    FOREIGN KEY (caso_hash) REFERENCES casos(caso_hash)
);

CREATE INDEX IF NOT EXISTS idx_exec_competencia ON execucoes(competencia);
CREATE INDEX IF NOT EXISTS idx_dec_competencia ON decisoes(competencia);
CREATE INDEX IF NOT EXISTS idx_decv2_caso ON decisoes_v2(caso_hash);
CREATE INDEX IF NOT EXISTS idx_decv2_status ON decisoes_v2(status);
CREATE INDEX IF NOT EXISTS idx_decv2_cnpj ON decisoes_v2(cnpj);
CREATE INDEX IF NOT EXISTS idx_apl_decisao ON aplicacoes(decisao_id);
CREATE INDEX IF NOT EXISTS idx_apl_caso ON aplicacoes(caso_hash);
CREATE INDEX IF NOT EXISTS idx_result_caso ON resultados_operacionais(caso_hash);
CREATE INDEX IF NOT EXISTS idx_evt_caso ON casos_eventos(caso_hash);
"""


def _conn(saida: Path) -> sqlite3.Connection:
    saida.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(saida / "tarvo.db")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def conectar(saida: Path) -> sqlite3.Connection:
    """Conexão pública para outros módulos (decisoes). Garante o schema."""
    return _conn(saida)


def registrar_execucao(
    *,
    saida: Path,
    competencia: str,
    commit: str | None,
    hashes: dict[str, str],
    rules_version: str,
    contagens: dict[str, int],
    duracoes_s: dict[str, float],
) -> int:
    """Grava a execução e marca decisões afetadas se o hash dos dados mudou.

    Idempotente no sentido de 'rodar de novo não quebra'. Cada chamada cria uma nova
    linha em `execucoes` (histórico), mas as decisões continuam valendo salvo se o hash
    mudou — nesse caso, marcamos `precisa_reavaliar` com o motivo.
    """
    hashes_json = json.dumps(hashes, sort_keys=True)
    with _conn(saida) as db:
        cur = db.execute(
            "INSERT INTO execucoes (competencia, timestamp, commit_hash, hashes_json,"
            " rules_version, contagens, duracoes_s) VALUES (?,?,?,?,?,?,?)",
            (
                competencia,
                dt.datetime.now().isoformat(timespec="seconds"),
                commit,
                hashes_json,
                rules_version,
                json.dumps(contagens, sort_keys=True),
                json.dumps(duracoes_s, sort_keys=True),
            ),
        )
        execucao_id = cur.lastrowid
        # Marcar decisões cujos hashes de origem ou regras divergem do que vemos agora.
        afetadas = db.execute(
            "SELECT id, hashes_na_decisao, rules_na_decisao FROM decisoes"
            " WHERE competencia = ? AND precisa_reavaliar = 0",
            (competencia,),
        ).fetchall()
        for linha in afetadas:
            motivos = []
            if linha["hashes_na_decisao"] != hashes_json:
                motivos.append("hash_dados_mudou")
            if linha["rules_na_decisao"] != rules_version:
                motivos.append("rules_version_mudou")
            if motivos:
                db.execute(
                    "UPDATE decisoes SET precisa_reavaliar = 1, motivo_reavaliar = ?"
                    " WHERE id = ?",
                    (",".join(motivos), linha["id"]),
                )
    log.info("execução #%s registrada (competência %s)", execucao_id, competencia)
    return int(execucao_id)


def registrar_decisao(
    *,
    saida: Path,
    competencia: str,
    id_saida: str,
    tipo_pendencia: str,
    decisao: str,
    autor: str,
    hashes_atuais: dict[str, str],
    rules_version: str,
) -> None:
    """Grava uma decisão humana sobre uma pendência. Upsert por (competencia, id_saida)."""
    with _conn(saida) as db:
        db.execute(
            "INSERT INTO decisoes (competencia, id_saida, tipo_pendencia, decisao, autor,"
            " timestamp, hashes_na_decisao, rules_na_decisao, precisa_reavaliar)"
            " VALUES (?,?,?,?,?,?,?,?,0)"
            " ON CONFLICT(competencia, id_saida) DO UPDATE SET"
            "   tipo_pendencia = excluded.tipo_pendencia,"
            "   decisao = excluded.decisao,"
            "   autor = excluded.autor,"
            "   timestamp = excluded.timestamp,"
            "   hashes_na_decisao = excluded.hashes_na_decisao,"
            "   rules_na_decisao = excluded.rules_na_decisao,"
            "   precisa_reavaliar = 0,"
            "   motivo_reavaliar = NULL",
            (
                competencia, id_saida, tipo_pendencia, decisao, autor,
                dt.datetime.now().isoformat(timespec="seconds"),
                json.dumps(hashes_atuais, sort_keys=True),
                rules_version,
            ),
        )


def listar_decisoes(saida: Path, competencia: str) -> list[dict]:
    with _conn(saida) as db:
        rows = db.execute(
            "SELECT * FROM decisoes WHERE competencia = ? ORDER BY timestamp DESC",
            (competencia,),
        ).fetchall()
        return [dict(r) for r in rows]


def listar_execucoes(saida: Path, competencia: str) -> list[dict]:
    with _conn(saida) as db:
        rows = db.execute(
            "SELECT * FROM execucoes WHERE competencia = ? ORDER BY id DESC",
            (competencia,),
        ).fetchall()
        return [dict(r) for r in rows]
