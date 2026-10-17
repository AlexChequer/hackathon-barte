"""Ciclo de decisão: proposta, aprovação, reaproveitamento, resultado operacional.

Cobre as regras do prompt do time:
- Proposta pendente ou usuário sem permissão não altera números do fechamento.
- Aprovação externa preserva responsável e evidência.
- Condição aprovada não se aplica fora do CNPJ ou vigência.
- Casos semelhantes aparecem como precedente, mas não herdam autorização.
- Alteração de composição exige reavaliação; alteração irrelevante preserva a decisão.
- Reprocessamento não duplica efeitos.
- Resolução parcial mantém saldo aberto.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tarvo import autenticacao as auth
from tarvo import casos as casos_mod
from tarvo import condicoes, decisoes, tratamentos
from tarvo.orquestrador import run_closing
from tarvo.web.api import criar_app

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data" / "raw" / "set2026"


@pytest.fixture()
def saida(tmp_path):
    return tmp_path / "saida"


@pytest.fixture()
def config(tmp_path):
    destino = tmp_path / "condicoes_comerciais.json"
    shutil.copy(condicoes.CAMINHO_PADRAO, destino)
    return destino


@pytest.fixture()
def usuarios(tmp_path):
    destino = tmp_path / "usuarios.json"
    destino.write_text(
        '{"usuarios": ['
        '{"nome": "Helena", "perfil": "financeiro"},'
        '{"nome": "Marina", "perfil": "comercial"},'
        '{"nome": "Fox", "perfil": "operador"}'
        "]}",
        encoding="utf-8",
    )
    return destino


@pytest.fixture()
def cliente(saida, config, usuarios):
    return TestClient(
        criar_app(dados=DATA, saida=saida, condicoes_path=config, usuarios_path=usuarios)
    )


HEAD_HELENA = {"X-Tarvo-Usuario": "Helena", "X-Tarvo-Perfil": "financeiro"}
HEAD_COMERCIAL = {"X-Tarvo-Usuario": "Marina", "X-Tarvo-Perfil": "comercial"}
HEAD_OPERADOR = {"X-Tarvo-Usuario": "Fox", "X-Tarvo-Perfil": "operador"}


# --- Modelo ---------------------------------------------------------


def test_caso_tem_identidade_estavel_entre_execucoes(saida, config):
    r1 = run_closing(DATA, saida, condicoes_path=config)
    r2 = run_closing(DATA, saida, condicoes_path=config)
    hashes1 = {k: c.caso_hash for k, c in r1.casos.items()}
    hashes2 = {k: c.caso_hash for k, c in r2.casos.items()}
    assert hashes1 == hashes2 and hashes1


def test_registrar_caso_novo_cria_evento_de_abertura(saida):
    caso = casos_mod.Caso(caso_hash="abc123", tipo="CONTESTACAO_ORBE", cnpj="",
                          ref="X", competencia="2026-09", composicao=("TX1",))
    decisoes.registrar_caso(saida, caso)
    eventos = decisoes.eventos_do_caso(saida, "abc123")
    assert [e["tipo_evento"] for e in eventos] == ["ABERTO"]


def test_mudanca_de_composicao_registra_evento(saida):
    caso = casos_mod.Caso(caso_hash="abc999", tipo="X", cnpj="", ref="R",
                          competencia="2026-09", composicao=("A",))
    decisoes.registrar_caso(saida, caso)
    caso2 = casos_mod.Caso(caso_hash="abc999", tipo="X", cnpj="", ref="R",
                           competencia="2026-09", composicao=("A", "B"))
    decisoes.registrar_caso(saida, caso2)
    tipos = [e["tipo_evento"] for e in decisoes.eventos_do_caso(saida, "abc999")]
    assert "COMPOSICAO_MUDOU" in tipos


# --- Permissão R20 --------------------------------------------------


def test_proposta_pendente_nao_altera_fechamento(cliente):
    antes = cliente.get("/api/fechamento").json()
    casos = antes["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    r = cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "caso_hash": caso_hash, "escopo": "CASO", "acao_tipo": "ANOTAR_PROVIDENCIA",
        "parametros": {}, "justificativa": "primeira avaliação"})
    assert r.status_code == 201
    depois = cliente.get("/api/fechamento").json()
    assert antes["totais"] == depois["totais"]
    assert len(antes["tabelas"]["pendencias"]) == len(depois["tabelas"]["pendencias"])


def test_operador_nao_pode_aprovar(cliente):
    casos = cliente.get("/api/fechamento").json()["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    r = cliente.post("/api/decisoes", headers=HEAD_COMERCIAL, json={
        "caso_hash": caso_hash, "escopo": "CASO",
        "acao_tipo": "ANOTAR_PROVIDENCIA",
        "parametros": {}, "justificativa": "nota"}).json()
    r2 = cliente.post(f"/api/decisoes/{r['id']}/aprovar", headers=HEAD_OPERADOR, json={})
    assert r2.status_code == 403


def test_comercial_nao_aprova_regra_de_fechamento(cliente):
    casos = cliente.get("/api/fechamento").json()["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    r = cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "caso_hash": caso_hash, "escopo": "CASO",
        "acao_tipo": "RECONHECER_RESOLUCAO",
        "parametros": {"evidencia": "e-mail da Ponte"}, "justificativa": "resposta aceita"}).json()
    r2 = cliente.post(f"/api/decisoes/{r['id']}/aprovar", headers=HEAD_COMERCIAL, json={})
    assert r2.status_code == 403


def test_financeiro_nao_aprova_condicao_comercial(cliente):
    casos = cliente.get("/api/fechamento").json()["casos"]
    sinal = next(c for c in casos.values() if c["tipo"] == "CONDICAO_NAO_INFORMADA_ORBE")
    r = cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "caso_hash": sinal["caso_hash"], "escopo": "CONDICAO", "cnpj": sinal["cnpj"],
        "acao_tipo": "REGISTRAR_CONDICAO_COMERCIAL",
        "parametros": {"cnpj": sinal["cnpj"], "inicio": "2026-09-01",
                        "taxas": {"credito_vista": "0.0199"}},
        "justificativa": "condição comercial Casa"}).json()
    r2 = cliente.post(f"/api/decisoes/{r['id']}/aprovar", headers=HEAD_HELENA, json={})
    assert r2.status_code == 403


def test_sem_usuario_retorna_401(cliente):
    assert cliente.post("/api/decisoes", json={"escopo": "CASO"}).status_code == 401


# --- Aprovação externa ----------------------------------------------


def test_aprovacao_externa_preserva_responsavel(cliente):
    casos = cliente.get("/api/fechamento").json()["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    r = cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "caso_hash": caso_hash, "escopo": "CASO",
        "acao_tipo": "RECONHECER_RESOLUCAO",
        "parametros": {"evidencia": "e-mail da Ponte 12/10"},
        "justificativa": "ponte aceitou"}).json()
    r2 = cliente.post(f"/api/decisoes/{r['id']}/aprovar", headers=HEAD_HELENA, json={
        "aprovacao_externa": {"aprovador": "Carlos (Comercial, por e-mail)",
                              "evidencia": "e-mail 12/10", "data": "2026-10-12"}}).json()
    aprovada = r2["decisao"]
    assert aprovada["status"] == "APROVADA"
    assert aprovada["aprovador"] == "Helena"
    assert aprovada["aprovacao_externa"]["aprovador"].startswith("Carlos")


# --- Vigência / escopo ---------------------------------------------


def test_condicao_fora_do_cnpj_nao_se_aplica(saida):
    caso = casos_mod.Caso(caso_hash="h1", tipo="CONDICAO_NAO_INFORMADA_ORBE",
                          cnpj="00000000000000", ref="00000000000000",
                          competencia="2026-10", composicao=())
    assert decisoes.encontrar_condicao_aplicavel(saida, caso, "2026-10") is None


def test_condicao_fora_da_vigencia_nao_se_aplica(cliente, saida):
    cliente.get("/api/fechamento")
    casos = cliente.get("/api/fechamento").json()["casos"]
    sinal = next(c for c in casos.values() if c["tipo"] == "CONDICAO_NAO_INFORMADA_ORBE")
    prop = cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "escopo": "CONDICAO", "cnpj": sinal["cnpj"],
        "vigencia_inicio": "2027-01-01", "vigencia_fim": "2027-12-31",
        "acao_tipo": "REGISTRAR_CONDICAO_COMERCIAL",
        "parametros": {"cnpj": sinal["cnpj"], "inicio": "2027-01-01",
                        "taxas": {"credito_vista": "0.0199"}},
        "justificativa": "futura"}).json()
    cliente.post(f"/api/decisoes/{prop['id']}/aprovar", headers=HEAD_COMERCIAL, json={})
    caso = casos_mod.Caso(caso_hash="x", tipo="CONDICAO_NAO_INFORMADA_ORBE",
                          cnpj=sinal["cnpj"], ref=sinal["cnpj"],
                          competencia="2026-09", composicao=())
    assert decisoes.encontrar_condicao_aplicavel(saida, caso, "2026-09") is None


def test_precedente_nao_concede_autorizacao(cliente, saida):
    casos = cliente.get("/api/fechamento").json()["casos"]
    duas = [c for c in casos.values() if c["tipo"] == "SPREAD_NEGATIVO_CONTESTAR"]
    assert len(duas) >= 2
    aprovada_prop = cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "caso_hash": duas[0]["caso_hash"], "escopo": "CASO",
        "acao_tipo": "ANOTAR_PROVIDENCIA",
        "parametros": {}, "justificativa": "anotada"}).json()
    cliente.post(f"/api/decisoes/{aprovada_prop['id']}/aprovar",
                 headers=HEAD_HELENA, json={})
    caso_outro = casos_mod.Caso(
        caso_hash=duas[1]["caso_hash"], tipo="SPREAD_NEGATIVO_CONTESTAR",
        cnpj="", ref=duas[1]["ref"], competencia="2026-09", composicao=())
    assert decisoes.encontrar_decisao_para_caso(saida, caso_outro) is None
    prec = decisoes.precedentes_para(saida, caso_outro)
    assert prec and prec[0]["caso_hash"] == duas[0]["caso_hash"]


# --- Reprocessamento ------------------------------------------------


def test_reprocessar_nao_duplica_aplicacoes(cliente, saida, config):
    cliente.get("/api/fechamento")
    casos = cliente.get("/api/fechamento").json()["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    prop = cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "caso_hash": caso_hash, "escopo": "CASO",
        "acao_tipo": "AGUARDAR_INFORMACAO",
        "parametros": {"destinatario": "Comercial"},
        "justificativa": "aguardando resposta"}).json()
    cliente.post(f"/api/decisoes/{prop['id']}/aprovar", headers=HEAD_HELENA, json={})
    run_closing(DATA, saida, condicoes_path=config)
    run_closing(DATA, saida, condicoes_path=config)
    # Invariante: no máximo uma aplicação por (decisao, execucao).
    with decisoes.conectar(saida) as db:
        duplicadas = db.execute(
            "SELECT decisao_id, execucao_id, COUNT(*) c FROM aplicacoes"
            " WHERE decisao_id = ? GROUP BY decisao_id, execucao_id HAVING c > 1",
            (prop["id"],),
        ).fetchall()
    assert duplicadas == []


# --- Resultado operacional parcial ----------------------------------


def test_resolucao_parcial_mantem_saldo_aberto(cliente):
    casos = cliente.get("/api/fechamento").json()["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    r = cliente.post(f"/api/casos/{caso_hash}/resultado", headers=HEAD_HELENA, json={
        "status": "PARCIAL", "saldo_centavos": 50000,
        "descricao": "metade da fatura paga, resto em espera"})
    assert r.status_code == 201
    ultimo = decisoes.ultimo_resultado(Path(cliente.app.state.saida), caso_hash)
    assert ultimo["status"] == "PARCIAL" and ultimo["saldo_centavos"] == 50000


def test_resolucao_integral_exige_evidencia(cliente):
    casos = cliente.get("/api/fechamento").json()["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    r = cliente.post(f"/api/casos/{caso_hash}/resultado", headers=HEAD_HELENA, json={
        "status": "RESOLVIDO"})
    assert r.status_code == 422


# --- Catálogo de ações ---------------------------------------------


def test_catalogo_de_tratamentos_tem_as_acoes_de_r20(cliente):
    acoes = {a["tipo"]: a for a in cliente.get("/api/tratamentos").json()["acoes"]}
    assert set(acoes) == set(tratamentos.ACOES)
    assert "comercial" in acoes["REGISTRAR_CONDICAO_COMERCIAL"]["aprovado_por"]
    assert "financeiro" in acoes["RECONHECER_RESOLUCAO"]["aprovado_por"]


# --- Métricas -------------------------------------------------------


def test_metricas_contam_decisoes_e_resultados(cliente):
    casos = cliente.get("/api/fechamento").json()["casos"]
    caso_hash = next(iter(casos.values()))["caso_hash"]
    cliente.post("/api/decisoes", headers=HEAD_OPERADOR, json={
        "caso_hash": caso_hash, "escopo": "CASO",
        "acao_tipo": "ANOTAR_PROVIDENCIA",
        "parametros": {}, "justificativa": "teste"})
    m = cliente.get("/api/metricas").json()
    assert m["decisoes_por_status"]["PENDENTE"] >= 1
    assert "casos_sem_resolucao" in m


# --- Autenticação com arquivo config ---------------------------------


def test_usuario_fora_do_cadastro_quando_arquivo_existe(tmp_path):
    users = tmp_path / "usuarios.json"
    users.write_text('{"usuarios":[{"nome":"Helena","perfil":"financeiro"}]}',
                      encoding="utf-8")
    with pytest.raises(auth.ErroAutenticacao):
        auth.resolver("Desconhecido", "operador", caminho=users)
