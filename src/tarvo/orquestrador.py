"""Orquestra os motores e consolida as 6 saídas. CLI e Streamlit chamam daqui.

Responsabilidades:
- Rodar engines/checkout, engines/remessa e engines/extratos.
- Consolidar DataFrames, validar rastro (igualdade exata + origem).
- Escrever CSVs preservando a execução anterior (dir por timestamp + symlink `latest`).
- Chamar `persistencia` para registrar execução e marcar decisões para reavaliação se o hash dos dados mudou.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from tarvo import output, persistencia, rules, sinais
from tarvo.engines import checkout, extratos, remessa
from tarvo.loaders import FILES, OPCIONAIS, load_all

log = logging.getLogger("tarvo.orq")


@dataclass
class ClosingResult:
    competencia: str
    execucao_id: int
    out_dir: Path
    comissoes: pd.DataFrame
    divergencias: pd.DataFrame
    notas: pd.DataFrame
    lancamentos: pd.DataFrame
    pendencias: pd.DataFrame
    rastro: pd.DataFrame
    problemas_rastro: pd.DataFrame
    problemas_integridade: list[dict]
    duracoes_s: dict[str, float]
    hashes: dict[str, str]
    commit: str | None


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit(repo: Path) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _mesclar(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatena mantendo colunas e removendo DataFrames vazios para evitar warnings."""
    nonempty = [d for d in dfs if not d.empty]
    if not nonempty:
        return pd.DataFrame()
    return pd.concat(nonempty, ignore_index=True)


# Fonte e coluna de data que definem a competência de cada arquivo (R2: data do movimento;
# R5: data de contratação).
DATAS_COMPETENCIA = {"orbe": "data_movimento", "ponte": "data_contratacao"}


def inferir_competencia(sources: dict[str, pd.DataFrame]) -> str:
    """AAAA-MM mais frequente nas datas da Orbe e da Ponte. Sem datas → ValueError."""
    meses = pd.concat([
        sources[k][col].dropna().map(lambda d: f"{d.year:04d}-{d.month:02d}")
        for k, col in DATAS_COMPETENCIA.items() if k in sources
    ])
    if meses.empty:
        raise ValueError("não foi possível inferir a competência: arquivos sem datas")
    contagem = meses.value_counts()
    if len(contagem) > 1:
        log.warning("datas de mais de um mês nos arquivos: %s", contagem.to_dict())
    return str(contagem.index[0])


def _rastro_com_arquivo_da_orbe(rastro: pd.DataFrame, orbe: pd.DataFrame) -> pd.DataFrame:
    """Os motores marcam toda linha da Orbe como "orbe"; aqui cada ref aponta o arquivo real."""
    if rastro.empty or "arquivo_origem" not in orbe:
        return rastro
    arquivo_por_id = dict(zip(orbe["id_transacao"].astype(str), orbe["arquivo_origem"], strict=True))
    da_orbe = rastro["arquivo_origem"] == "orbe"
    novo = rastro["ref_origem"].astype(str).map(arquivo_por_id)
    return rastro.assign(arquivo_origem=rastro["arquivo_origem"].where(~da_orbe | novo.isna(), novo))


def run_closing(dados: Path, saida: Path, competencia: str | None = None) -> ClosingResult:
    t0 = time.perf_counter()
    sources = load_all(dados)
    t_load = time.perf_counter() - t0
    if competencia is None:
        competencia = inferir_competencia(sources)
        log.info("competência inferida dos dados: %s", competencia)

    hashes = {
        f.name: _hash(f)
        for padrao in [*FILES.values(), *OPCIONAIS.values()]
        for f in sorted(dados.glob(padrao))
    }
    commit = _git_commit(dados.parent.parent)

    t = time.perf_counter()
    r_ck = checkout.run(sources["orbe"], sources["taxas"], competencia)
    t_ck = time.perf_counter() - t

    t = time.perf_counter()
    r_rm = remessa.run(sources["ponte"], sources["taxas"], competencia)
    t_rm = time.perf_counter() - t

    t = time.perf_counter()
    r_ex = extratos.run(sources["aurora"], sources["meridiano"], sources["plano"], competencia)
    t_ex = time.perf_counter() - t

    t = time.perf_counter()
    r_sn = sinais.run(sources["taxas"], competencia, sinais.classificador_padrao())
    t_sn = time.perf_counter() - t

    comissoes = _mesclar([r_ck.comissoes, r_rm.comissoes])
    divergencias = _mesclar([r_ck.divergencias, r_rm.divergencias])
    notas = _mesclar([r_ck.notas, r_rm.notas])
    lancamentos = r_ex.lancamentos
    pendencias = _mesclar([r_ck.pendencias, r_rm.pendencias, r_ex.pendencias, r_sn.pendencias])
    rastro = _rastro_com_arquivo_da_orbe(
        _mesclar([r_ck.rastro, r_rm.rastro, r_ex.rastro, r_sn.rastro]), sources["orbe"]
    )

    # Validação de rastro por saída monetária (igualdade exata em centavos).
    problemas = []
    for df, col in [
        (comissoes, "comissao_brl"),
        (divergencias, "diferenca_brl"),
        (notas, "valor_brl"),
        (pendencias, "valor_brl"),
    ]:
        if df.empty:
            continue
        q_rastro = rastro.dropna(subset=["id_saida"])
        gap = output.check_rastro(df, col, q_rastro)
        if not gap.empty:
            gap = gap.assign(coluna=col)
            problemas.append(gap)
    # Lançamentos: cada id_saida tem exatamente uma linha de rastro com o próprio valor.
    if not lancamentos.empty:
        gap = output.check_rastro(lancamentos.assign(valor=lancamentos["valor"]), "valor", rastro)
        if not gap.empty:
            gap = gap.assign(coluna="valor_lancamento")
            problemas.append(gap)
    problemas_df = _mesclar(problemas)

    # IDs únicos entre as saídas monetárias.
    ids_saidas = set()
    for df in [comissoes, divergencias, notas, lancamentos, pendencias]:
        if not df.empty:
            ids_saidas.update(df["id_saida"].tolist())
    saidas = [comissoes, divergencias, notas, lancamentos, pendencias]
    duplicados = (
        pd.concat([df["id_saida"] for df in saidas if not df.empty]).value_counts()
    )
    duplicados = duplicados[duplicados > 1]
    integridade = output.validate_rastro_integrity(rastro, ids_saidas)
    if len(duplicados):
        integridade.append({"codigo": "ID_SAIDA_DUPLICADO", "ids": duplicados.index.tolist()})

    # Cobertura: toda entrada relevante tem que ter saída (comissão, divergência, pendência ou lançamento).
    entradas_esperadas = {
        **{
            arquivo: set(grupo["id_transacao"].astype(str))
            for arquivo, grupo in sources["orbe"].groupby("arquivo_origem")
        },
        "ponte": set(sources["ponte"]["n_operacao"].astype(str).unique()),
        "aurora": set(sources["aurora"]["ref_origem"].astype(str).unique()),
        "meridiano": set(sources["meridiano"]["ref_origem"].astype(str).unique()),
    }
    integridade.extend(output.validate_cobertura_entradas(entradas_esperadas, rastro))

    # Diretório da execução (timestamp) + symlink `latest`.
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = saida / competencia / f"exec_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    output.write_output(comissoes, "comissoes_por_lojista.csv", out_dir)
    output.write_output(divergencias, "divergencias_taxa.csv", out_dir)
    output.write_output(notas, "notas_a_emitir.csv", out_dir)
    output.write_output(lancamentos, "lancamentos_classificados.csv", out_dir)
    output.write_output(pendencias, "pendencias.csv", out_dir)
    output.write_output(rastro, "rastro.csv", out_dir)

    latest = saida / competencia / "latest"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(out_dir.name, target_is_directory=True)

    duracoes = {
        "load": round(t_load, 3),
        "checkout": round(t_ck, 3),
        "remessa": round(t_rm, 3),
        "extratos": round(t_ex, 3),
        "sinais": round(t_sn, 3),
        "total": round(time.perf_counter() - t0, 3),
    }

    # Persistência: registra execução; se o hash mudou, marca decisões afetadas.
    execucao_id = persistencia.registrar_execucao(
        saida=saida,
        competencia=competencia,
        commit=commit,
        hashes=hashes,
        rules_version=rules.VERSION,
        contagens={
            "comissoes": len(comissoes),
            "divergencias": len(divergencias),
            "notas": len(notas),
            "lancamentos": len(lancamentos),
            "pendencias": len(pendencias),
            "rastro": len(rastro),
        },
        duracoes_s=duracoes,
    )

    log.info("fechamento gravado em %s (execucao #%s)", out_dir, execucao_id)
    return ClosingResult(
        competencia=competencia,
        execucao_id=execucao_id,
        out_dir=out_dir,
        comissoes=comissoes, divergencias=divergencias, notas=notas,
        lancamentos=lancamentos, pendencias=pendencias, rastro=rastro,
        problemas_rastro=problemas_df, problemas_integridade=integridade,
        duracoes_s=duracoes, hashes=hashes, commit=commit,
    )
