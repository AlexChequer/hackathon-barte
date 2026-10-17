"""Streamlit por cima do mesmo orquestrador que a CLI usa.

Uso: `streamlit run src/tarvo/ui/app.py`. A interface não implementa lógica de negócio.
Ela chama `tarvo.orquestrador.run_closing` com o mesmo caminho de dados/saída e mostra:

- resumo (contagens, duração, hashes do data pack, commit, versão de regras);
- avaliação contra `tests/fixtures/referencia_<competencia>.json`;
- pré-visualização de cada CSV com filtro básico;
- fila de pendências agrupada por "quem decide";
- histórico de execuções e decisões (SQLite).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from tarvo import rules
from tarvo.avaliacao import avaliar_e_persistir, carregar_referencia
from tarvo.orquestrador import run_closing
from tarvo.persistencia import (
    listar_decisoes,
    listar_execucoes,
    registrar_decisao,
)

st.set_page_config(page_title="Tarvo – Fechamento", page_icon="📊", layout="wide")

REPO = Path(__file__).resolve().parents[3]
DEFAULT_DADOS = REPO / "data" / "raw" / "set2026"
DEFAULT_SAIDA = REPO / "saida"
DEFAULT_FIXTURES = REPO / "tests" / "fixtures"

SAIDAS_CSV = [
    "comissoes_por_lojista.csv",
    "divergencias_taxa.csv",
    "notas_a_emitir.csv",
    "lancamentos_classificados.csv",
    "pendencias.csv",
    "rastro.csv",
]


# ---------- Sidebar: parâmetros + ação ----------

with st.sidebar:
    st.title("Fechamento Tarvo")
    dados = Path(st.text_input("Pasta `data/raw/<competencia>`", str(DEFAULT_DADOS)))
    saida = Path(st.text_input("Pasta `saida/`", str(DEFAULT_SAIDA)))
    competencia = st.text_input("Competência (AAAA-MM; vazio = inferir dos dados)", "").strip() or None
    fixtures = Path(st.text_input("Pasta de referência", str(DEFAULT_FIXTURES)))
    rodar = st.button("Rodar fechamento", type="primary", use_container_width=True)
    st.caption(f"Regras: `{rules.VERSION}`")


def _ultimo_dir(saida: Path, comp: str) -> Path | None:
    base = saida / comp
    if not base.exists():
        return None
    execs = sorted((p for p in base.iterdir() if p.is_dir() and p.name.startswith("exec_")),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return execs[0] if execs else None


def _ler_csv(dir_: Path, nome: str) -> pd.DataFrame:
    p = dir_ / nome
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p, sep=";", dtype=str)


# ---------- Ação: rodar ----------
if rodar:
    try:
        with st.spinner("Rodando engines…"):
            resultado = run_closing(dados, saida, competencia)
            st.session_state["competencia"] = resultado.competencia
            relatorio = avaliar_e_persistir(resultado, fixtures_dir=fixtures, saida=saida)
        st.success(f"Execução #{resultado.execucao_id} gravada em `{resultado.out_dir}`.")
        if not resultado.problemas_rastro.empty:
            st.error(f"Rastro não bate em {len(resultado.problemas_rastro)} linhas.")
        if resultado.problemas_integridade:
            st.error(f"Integridade: {resultado.problemas_integridade}")
    except (FileNotFoundError, ValueError) as exc:
        st.error(f"Falha: {exc}")


# ---------- Última execução ----------
competencia = competencia or st.session_state.get("competencia")
if competencia is None:
    st.info("Nenhuma execução ainda. Rode o fechamento no menu lateral.")
    st.stop()
exec_dir = _ultimo_dir(saida, competencia)
if exec_dir is None:
    st.info("Nenhuma execução ainda. Rode o fechamento no menu lateral.")
    st.stop()

st.subheader(f"Competência {competencia} — `{exec_dir.name}`")

tabs = st.tabs([
    "Resumo", "Comissões", "Divergências", "Notas",
    "Lançamentos", "Pendências", "Rastro", "Histórico",
])

csvs = {nome: _ler_csv(exec_dir, nome) for nome in SAIDAS_CSV}


# ---------- Tab Resumo ----------
with tabs[0]:
    col_a, col_b, col_c, col_d, col_e, col_f = st.columns(6)
    col_a.metric("Comissões", len(csvs["comissoes_por_lojista.csv"]))
    col_b.metric("Divergências", len(csvs["divergencias_taxa.csv"]))
    col_c.metric("Notas", len(csvs["notas_a_emitir.csv"]))
    col_d.metric("Lançamentos", len(csvs["lancamentos_classificados.csv"]))
    col_e.metric("Pendências", len(csvs["pendencias.csv"]))
    col_f.metric("Rastro", len(csvs["rastro.csv"]))

    av_path = exec_dir / "avaliacao.json"
    if av_path.exists():
        st.markdown("### Avaliação vs referência")
        rel = json.loads(av_path.read_text(encoding="utf-8"))
        resumo = rel["resumo"]
        c1, c2, c3 = st.columns(3)
        c1.metric("Casos de referência OK",
                  f"{resumo['casos_referencia_ok']}/{resumo['casos_referencia_total']}")
        c2.metric("Classificação",
                  f"{resumo['classificacao_num']}/{resumo['classificacao_den']}")
        c3.metric("Falhas de rastro",
                  f"{resumo['rastro_falhas']}/{resumo['rastro_total_saidas']}")
        casos_df = pd.DataFrame(rel["casos"])
        if not casos_df.empty:
            st.dataframe(casos_df, use_container_width=True, hide_index=True)
    else:
        if carregar_referencia(fixtures, competencia) is None:
            st.info("Sem referência para esta competência; avaliação não executada.")


def _tabela(df: pd.DataFrame, busca_cols: list[str], chave: str) -> None:
    if df.empty:
        st.info("Vazio.")
        return
    q = st.text_input("Filtro (contains, case-insensitive)", key=f"q_{chave}")
    view = df
    if q:
        mask = pd.Series(False, index=df.index)
        for c in busca_cols:
            if c in df.columns:
                mask |= df[c].astype(str).str.contains(q, case=False, na=False)
        view = df[mask]
    st.caption(f"{len(view)} de {len(df)} linhas")
    st.dataframe(view, use_container_width=True, hide_index=True)


with tabs[1]:
    _tabela(csvs["comissoes_por_lojista.csv"], ["cnpj", "lojista", "linha_negocio"], "cm")
with tabs[2]:
    _tabela(csvs["divergencias_taxa.csv"], ["cnpj", "ref_origem", "linha_negocio"], "dv")
with tabs[3]:
    _tabela(csvs["notas_a_emitir.csv"], ["tomador_cnpj", "tomador", "linha_negocio"], "nt")
with tabs[4]:
    _tabela(csvs["lancamentos_classificados.csv"],
            ["ref_origem", "descricao", "conta_codigo", "banco"], "lc")

# Pendências com agrupamento por "quem decide" + registro de decisão.
with tabs[5]:
    pend = csvs["pendencias.csv"]
    if pend.empty:
        st.info("Sem pendências.")
    else:
        por_decide = pend.groupby("quem_decide").size().reset_index(name="qtd")
        st.markdown("**Fila por responsável**")
        st.dataframe(por_decide, use_container_width=True, hide_index=True)
        _tabela(pend, ["id_saida", "tipo", "motivo", "ref_origem"], "pn")

        st.markdown("### Registrar decisão")
        with st.form("decisao"):
            id_saida = st.selectbox("id_saida", pend["id_saida"].tolist())
            tipo_pend = pend.loc[pend["id_saida"] == id_saida, "tipo"].iloc[0] \
                if id_saida else ""
            decisao = st.text_input("Decisão", "")
            autor = st.text_input("Autor", "")
            ok = st.form_submit_button("Gravar")
            if ok and id_saida and decisao and autor:
                hashes = {}
                avp = exec_dir / "avaliacao.json"
                if avp.exists():
                    hashes = {"execucao_id": json.loads(avp.read_text()).get("execucao_id")}
                registrar_decisao(
                    saida=saida, competencia=competencia, id_saida=id_saida,
                    tipo_pendencia=tipo_pend, decisao=decisao, autor=autor,
                    hashes_atuais=hashes, rules_version=rules.VERSION,
                )
                st.success(f"Decisão gravada para {id_saida}.")

with tabs[6]:
    _tabela(csvs["rastro.csv"], ["id_saida", "ref_origem", "arquivo_origem"], "rt")

# Histórico de execuções e decisões.
with tabs[7]:
    st.markdown("### Execuções")
    try:
        execs = listar_execucoes(saida, competencia)
        if execs:
            df = pd.DataFrame(execs)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sem execuções no SQLite.")
        st.markdown("### Decisões")
        decs = listar_decisoes(saida, competencia)
        if decs:
            df = pd.DataFrame(decs)
            if "precisa_reavaliar" in df.columns:
                reav = df[df["precisa_reavaliar"] == 1]
                if not reav.empty:
                    st.warning(f"{len(reav)} decisão(ões) marcadas para reavaliar.")
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sem decisões registradas.")
    except Exception as exc:  # noqa: BLE001
        st.error(f"Falha ao ler histórico: {exc}")
