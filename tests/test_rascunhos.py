"""Rascunhos de envio a terceiros (P36): quem recebe, o que sai da empresa e o que volta validado.

O modelo da OpenAI é sempre substituído por um falso: os testes nunca chamam a rede.
"""

import re
from pathlib import Path

import pytest

from tarvo import condicoes, rascunhos
from tarvo.orquestrador import run_closing

RAIZ = Path(__file__).resolve().parents[1]
DATA = RAIZ / "data" / "raw" / "set2026"
ROTA, CASA = "95927868000148", "00520815000100"


@pytest.fixture(scope="module")
def fechamento(tmp_path_factory):
    return run_closing(DATA, tmp_path_factory.mktemp("saida"), "2026-09")


def _gerar(r, pedir):
    return rascunhos.gerar(r.pendencias, r.rastro, r.comissoes, r.divergencias, r.lancamentos,
                           condicoes.carregar(), "2026-09", pedir=pedir)


def modelo_bom(instrucoes: str, entrada: str) -> str:
    """Imita um modelo obediente: só marcadores, cita o principal de cada tópico, sem números."""
    principais = sorted(set(re.findall(r"\{((?:VALOR|CONDICAO|PEDIR)_\d+)\}", entrada)))
    corpo = "\n".join(f"Tratamos o ponto que soma {{{m}}}." for m in principais)
    return (f"Assunto: Pendências de {{COMPETENCIA}}\n\nPrezados, {{DESTINATARIO}}.\n\n{corpo}\n"
            "A lista segue abaixo.")


def por_chave(lista):
    return {r["chave"]: r for r in lista}


# ----- quem recebe o quê -----

def test_todo_tipo_de_pendencia_esta_classificado():
    tipos = set()
    for arquivo in (RAIZ / "src" / "tarvo").rglob("*.py"):
        tipos |= set(re.findall(r'"tipo": "([A-Z_]+)"', arquivo.read_text(encoding="utf-8")))
    com_mensagem = {t for t, _ in rascunhos.TEXTOS} | set(rascunhos.CADASTRO) | set(rascunhos.ESCLARECIMENTO)
    assert tipos - com_mensagem - rascunhos.SEM_RASCUNHO == set()
    assert com_mensagem & rascunhos.SEM_RASCUNHO == set()


def test_setembro_tem_uma_mensagem_por_destinatario(fechamento):
    r = por_chave(_gerar(fechamento, modelo_bom))
    assert set(r) == {"orbe", "ponte", "comercial", f"lojista:{ROTA}", f"lojista:{CASA}",
                      "lojista:22224579000109", "lojista:17217888000111", "lojista_extrato:L65"}
    assert r["ponte"]["pendencias"][0] == "RM-DUPREL-2026-09-PC-0926-0162"
    assert len(r["ponte"]["pendencias"]) == 6
    # Casa: dois destinatários externos e o Comercial recebem a mesma pendência, cada um com o seu texto
    casa = f"CK-COND-PEND-2026-09-{CASA}"
    assert all(casa in r[k]["pendencias"] for k in ("orbe", "comercial", f"lojista:{CASA}"))
    # ação interna não vira mensagem
    todas = {p for x in r.values() for p in x["pendencias"]}
    internas = ("CK-NTNEG", "RM-CONTEST-", "EX-PN-AURORA-L50", "EX-PN-AURORA-L92")
    assert not any(p.startswith(internas) for p in todas)


# ----- o que sai da empresa (pseudonimização) -----

def test_nada_sensivel_sai_para_o_modelo(fechamento):
    enviados = []
    _gerar(fechamento, lambda i, e: enviados.append(i + e) or modelo_bom(i, e))
    sensiveis = (set(fechamento.comissoes["lojista"]) | set(fechamento.comissoes["cnpj"])
                 | {"Atlas", "MUNDO ABERTO", "TX884", "PC-0926", "AN884", "R$"})
    assert len(enviados) == 8
    for pacote in enviados:
        assert not re.search(r"\d", rascunhos.MARCADOR.sub("", pacote)), "algarismo no pacote"
        assert not [s for s in sensiveis if s and s in pacote]


# ----- o que volta (validação e preenchimento local) -----

def test_valores_reais_entram_so_depois_na_maquina_da_tarvo(fechamento):
    r = por_chave(_gerar(fechamento, modelo_bom))
    rota = r[f"lojista:{ROTA}"]
    assert rota["status"] == "gerado" and "R$ 1.546,28" in rota["corpo"]
    assert rota["assunto"] == "Pendências de 09/2026" and "Rota Global Intercâmbio Ltda" in rota["corpo"]
    assert len(rota["anexo"]) == 88 and rota["anexo"][1].startswith("TX")  # título + 87 transações
    assert "taxa de 0,00% em todas as modalidades, de 01/09/2026 a 31/12/2026" not in rota["corpo"]
    assert "-R$ 1.351,87" in r["ponte"]["corpo"]  # diferença até a trava do PC-0926-0210 (R28.3)
    assert "{" not in "".join(x["corpo"] for x in r.values())


@pytest.mark.parametrize("texto, motivo", [
    ("Assunto: x\n\nPrezados. O valor é {VALOR_1} em 2026.", "números"),
    ("Assunto: x\n\nPrezados. {VALOR_1} {INVENTADO_1}.", "marcadores que não existem"),
    ("Assunto: x\n\nPrezados, sem o valor.", "faltou citar"),
    ("Assunto: x\n\nPrezados. {VALOR_1}.\nAtenciosamente,", "despedida"),
    ("Assunto: x\n\nPrezados. {VALOR_1}, pago no próximo repasse.", "prazo"),
    ("Prezados. {VALOR_1}.", "Assunto"),
])
def test_validador_barra_o_que_o_modelo_nao_pode_fazer(texto, motivo):
    problemas = rascunhos.validar(texto, {"VALOR_1": "R$ 10,00"}, ["VALOR_1"])
    assert any(motivo in p for p in problemas)
    assert rascunhos.validar("Assunto: x\n\nPrezados. {VALOR_1}.", {"VALOR_1": "R$ 10,00"}, ["VALOR_1"]) == []


def test_reprovado_tenta_de_novo_com_os_motivos(fechamento):
    chamadas = []

    def teimoso_depois_obediente(instrucoes, entrada):
        chamadas.append(entrada)
        if "reprovada" not in entrada:
            return "Assunto: x\n\nValor de 1.546,28."
        return modelo_bom(instrucoes, entrada)

    r = por_chave(_gerar(fechamento, teimoso_depois_obediente))
    assert all(x["status"] == "gerado" for x in r.values())
    assert sum("reprovada pelos motivos" in c for c in chamadas) == 8


def test_reprovado_duas_vezes_nao_aparece(fechamento):
    r = _gerar(fechamento, lambda i, e: "Assunto: x\n\nValor de 1.546,28.")
    assert {x["status"] for x in r} == {"reprovado"} and all(x["corpo"] == "" for x in r)


def test_erro_na_api_nao_derruba_o_fechamento(fechamento):
    def fora_do_ar(instrucoes, entrada):
        raise ConnectionError("sem rede")

    assert {x["status"] for x in _gerar(fechamento, fora_do_ar)} == {"erro"}


def test_sem_chave_fica_indisponivel_e_vai_para_o_historico(fechamento):
    assert {x["status"] for x in fechamento.rascunhos} == {"indisponivel"}
    assert "OPENAI_API_KEY" in fechamento.rascunhos[0]["aviso"]
    assert (fechamento.out_dir / "rascunhos.json").exists()
    assert not (fechamento.out_dir.parents[1] / "rascunhos.json").exists()  # nunca na raiz de saida/


# ----- ligação com a OpenAI (cliente simulado) -----

def test_usa_o_modelo_configurado_pela_api_de_responses(monkeypatch):
    chamadas = []

    class Respostas:
        def create(self, **kwargs):
            chamadas.append(kwargs)
            return type("Resposta", (), {"output_text": "Assunto: x\n\nPrezados. {VALOR_1}."})()

    class ClienteFalso:
        def __init__(self, api_key, timeout):
            assert api_key == "chave-de-teste"
            self.responses = Respostas()

    import openai
    monkeypatch.setattr(openai, "OpenAI", ClienteFalso)
    monkeypatch.setenv("OPENAI_API_KEY", "chave-de-teste")
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    pedir = rascunhos._pedir_openai()
    assert pedir("instruções", "entrada") == "Assunto: x\n\nPrezados. {VALOR_1}."
    assert chamadas[0]["model"] == "gpt-6-luna"
    assert chamadas[0]["instructions"] == "instruções" and chamadas[0]["input"] == "entrada"
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert rascunhos._pedir_openai() is None


def test_painel_recebe_os_rascunhos(tmp_path):
    from fastapi.testclient import TestClient

    from tarvo.web.api import criar_app
    resposta = TestClient(criar_app(dados=DATA, saida=tmp_path / "saida")).get("/api/fechamento").json()
    assert {r["chave"] for r in resposta["rascunhos"]} >= {"orbe", "ponte", "comercial"}
