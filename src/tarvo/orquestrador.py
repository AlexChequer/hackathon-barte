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
import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from tarvo import casos as casos_mod
from tarvo import condicoes as cond_mod
from tarvo import controle, decisoes, frentes, output, persistencia, rules, sinais
from tarvo import pendencias as pend_mod
from tarvo.engines import EngineResult, checkout, extratos, remessa
from tarvo.loaders import FILES, OPCIONAIS, load_disponiveis
from tarvo.loaders.orbe import ARQUIVO_PENDENTES, NOME_PENDENTES, escrever_orbe, load_orbe

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
    bloqueios: list[dict] = field(default_factory=list)
    controle: dict = field(default_factory=dict)
    casos: dict = field(default_factory=dict)                   # id_saida -> Caso
    aplicacoes_decisoes: list[dict] = field(default_factory=list)


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


SAIDAS = [
    "comissoes_por_lojista.csv",
    "divergencias_taxa.csv",
    "notas_a_emitir.csv",
    "lancamentos_classificados.csv",
    "pendencias.csv",
    "rastro.csv",
]

# Fonte e coluna de data que definem a competência de cada arquivo (R2: data do movimento;
# R5: data de contratação).
DATAS_COMPETENCIA = {"orbe": "data_movimento", "ponte": "data_contratacao"}
# Sem Orbe e sem Ponte (R34: fecha o que der), a competência vem das datas dos extratos.
DATAS_RESERVA = {"aurora": "data", "meridiano": "data"}


def inferir_competencia(sources: dict[str, pd.DataFrame]) -> str:
    """AAAA-MM mais frequente nas datas da Orbe e da Ponte. Sem datas → ValueError."""
    colunas = {k: c for k, c in DATAS_COMPETENCIA.items() if sources.get(k) is not None}
    if not colunas:
        colunas = {k: c for k, c in DATAS_RESERVA.items() if sources.get(k) is not None}
    if not colunas:
        raise ValueError("não foi possível inferir a competência: arquivos sem datas")
    meses = pd.concat([
        sources[k][col].dropna().map(lambda d: f"{d.year:04d}-{d.month:02d}") for k, col in colunas.items()
    ])
    if meses.empty:
        raise ValueError("não foi possível inferir a competência: arquivos sem datas")
    contagem = meses.value_counts()
    if len(contagem) > 1:
        log.warning("datas de mais de um mês nos arquivos: %s", contagem.to_dict())
    return str(contagem.index[0])


def _ou_vazio(df: pd.DataFrame | None) -> pd.DataFrame:
    """Banco ausente entra como extrato sem linhas (R34: classifica o banco que veio)."""
    return df if df is not None else pd.DataFrame(columns=["ref_origem", "data", "descricao", "valor"])


def _rastro_com_arquivo_da_orbe(rastro: pd.DataFrame, orbe: pd.DataFrame | None) -> pd.DataFrame:
    """Os motores marcam toda linha da Orbe como "orbe"; aqui cada ref aponta o arquivo real."""
    if rastro.empty or orbe is None or "arquivo_origem" not in orbe:
        return rastro
    arquivo_por_id = dict(zip(orbe["id_transacao"].astype(str), orbe["arquivo_origem"], strict=True))
    da_orbe = rastro["arquivo_origem"] == "orbe"
    novo = rastro["ref_origem"].astype(str).map(arquivo_por_id)
    return rastro.assign(arquivo_origem=rastro["arquivo_origem"].where(~da_orbe | novo.isna(), novo))


def _mes_anterior(competencia: str) -> str:
    ano, mes = int(competencia[:4]), int(competencia[5:7])
    return f"{ano - 1}-12" if mes == 1 else f"{ano}-{mes - 1:02d}"


def _historico_anterior(saida: Path, competencia: str) -> tuple[pd.DataFrame | None, set[str] | None, Path]:
    """O que o fechamento do mês anterior (mesma pasta de saída) deixou para este (R18, P33).

    - transações de EC sem contrato, no layout do 01, para faturar se o contrato apareceu;
    - CNPJs com comissão de checkout, para o alerta de antecipação saber quem tem histórico.
    Sem fechamento anterior (ex.: setembro, o primeiro), nada muda: (None, None).
    """
    pasta = saida / _mes_anterior(competencia) / "latest"
    pendentes = None
    if (pasta / NOME_PENDENTES).exists():
        pendentes = load_orbe(pasta / NOME_PENDENTES).assign(arquivo_origem=ARQUIVO_PENDENTES)
    cnpjs = None
    if (pasta / "comissoes_por_lojista.csv").exists():
        anteriores = pd.read_csv(pasta / "comissoes_por_lojista.csv", sep=";", dtype=str)
        cnpjs = set(anteriores.loc[anteriores["linha_negocio"] == "CHECKOUT", "cnpj"])
    return pendentes, cnpjs, pasta


def run_closing(
    dados: Path, saida: Path, competencia: str | None = None, condicoes_path: Path | None = None
) -> ClosingResult:
    t0 = time.perf_counter()
    sources, ausentes, layout = load_disponiveis(dados)
    presentes = set(FILES) - set(ausentes)
    bloqueios = frentes.bloqueios(presentes, layout)
    if not any(frentes.roda(f, presentes) for f in frentes.FRENTES):
        faltam = ", ".join(frentes.NOME_ARQUIVO[a] for a in ausentes)
        detalhes = " ".join(layout.values())
        raise FileNotFoundError(f"nenhuma parte do fechamento pode rodar; faltam: {faltam}. {detalhes}")
    for b in bloqueios:
        log.warning("frente %s %s: falta %s", b["frente"], "parcial" if b["parcial"] else "bloqueada",
                    ", ".join(b["faltando"]))
    for mensagem in layout.values():
        log.warning("layout: %s", mensagem)
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

    # R18 + P33: o fechamento anterior (mesma pasta de saída) passa as transações sem contrato guardadas
    # e os lojistas que já tinham histórico. Entram como mais um arquivo da Orbe, com rastro próprio.
    pendentes, cnpjs_mes_anterior, pasta_anterior = _historico_anterior(saida, competencia)
    if pendentes is not None and frentes.roda("checkout", presentes):
        # A Orbe não repete id entre meses. Se repetir, vale a linha do arquivo do mês e a guardada sai.
        repetidas = pendentes["id_transacao"].isin(set(sources["orbe"]["id_transacao"]))
        if repetidas.any():
            log.warning("%d transações guardadas reaparecem no arquivo do mês; vale a do mês",
                        int(repetidas.sum()))
        sources["orbe"] = pd.concat([sources["orbe"], pendentes[~repetidas]], ignore_index=True)
        hashes[f"{pasta_anterior.parent.name}/{NOME_PENDENTES}"] = _hash(pasta_anterior / NOME_PENDENTES)

    t = time.perf_counter()
    caminho_condicoes = condicoes_path or cond_mod.CAMINHO_PADRAO
    condicoes = cond_mod.carregar(caminho_condicoes)
    r_ck = (checkout.run(sources["orbe"], sources["taxas"], competencia, condicoes, cnpjs_mes_anterior)
            if frentes.roda("checkout", presentes) else EngineResult())
    t_ck = time.perf_counter() - t

    t = time.perf_counter()
    r_rm = (remessa.run(sources["ponte"], sources["taxas"], competencia)
            if frentes.roda("remessa", presentes) else EngineResult())
    t_rm = time.perf_counter() - t

    t = time.perf_counter()
    r_ex = (extratos.run(_ou_vazio(sources["aurora"]), _ou_vazio(sources["meridiano"]), sources["plano"],
                         competencia, conferir_transito={"aurora", "meridiano"} <= presentes)
            if frentes.roda("extratos", presentes) else EngineResult())
    t_ex = time.perf_counter() - t

    t = time.perf_counter()
    r_sn = (sinais.run(sources["taxas"], competencia, sinais.classificador_padrao(), condicoes,
                       cond_mod.carregar_sinais_resolvidos(caminho_condicoes))
            if "taxas" in presentes else EngineResult())
    r_bl = frentes.pendencias_bloqueio(bloqueios, competencia)
    t_sn = time.perf_counter() - t

    comissoes = _mesclar([r_ck.comissoes, r_rm.comissoes])
    divergencias = _mesclar([r_ck.divergencias, r_rm.divergencias])
    notas = _mesclar([r_ck.notas, r_rm.notas])
    lancamentos = r_ex.lancamentos
    # P29: toda pendência sai com o próximo passo (R26: "motivo e próximo passo").
    pendencias = pend_mod.com_proximo_passo(_mesclar(
        [r_ck.pendencias, r_rm.pendencias, r_ex.pendencias, r_sn.pendencias, r_bl.pendencias]
    ))
    rastro = _rastro_com_arquivo_da_orbe(
        _mesclar([r_ck.rastro, r_rm.rastro, r_ex.rastro, r_sn.rastro, r_bl.rastro]), sources["orbe"]
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
    entradas_esperadas: dict[str, set[str]] = {}
    if frentes.roda("checkout", presentes):
        entradas_esperadas |= {arquivo: set(grupo["id_transacao"].astype(str))
                               for arquivo, grupo in sources["orbe"].groupby("arquivo_origem")}
    if frentes.roda("remessa", presentes):
        entradas_esperadas["ponte"] = set(sources["ponte"]["n_operacao"].astype(str).unique())
    if frentes.roda("extratos", presentes):
        for banco in ("aurora", "meridiano"):
            if banco in presentes:
                entradas_esperadas[banco] = set(sources[banco]["ref_origem"].astype(str).unique())
    integridade.extend(output.validate_cobertura_entradas(entradas_esperadas, rastro))

    # Origem: cada linha do rastro aponta para uma linha que existe no arquivo (não CNPJ nem rótulo).
    refs_por_arquivo: dict[str, set[str]] = {}
    if sources.get("orbe") is not None:
        refs_por_arquivo |= {arquivo: set(grupo["id_transacao"].astype(str))
                             for arquivo, grupo in sources["orbe"].groupby("arquivo_origem")}
    if sources.get("ponte") is not None:
        refs_por_arquivo["ponte"] = set(sources["ponte"]["n_operacao"].astype(str))
    for banco in ("aurora", "meridiano"):
        if sources.get(banco) is not None:
            refs_por_arquivo[banco] = set(sources[banco]["ref_origem"].astype(str))
    if sources.get("taxas") is not None:
        refs_por_arquivo["taxas"] = {f"L{n}" for n in sources["taxas"]["linha_origem"]}
    integridade.extend(output.validate_refs_origem(rastro, refs_por_arquivo, set(ausentes)))

    # Fechamento contra a fonte: o total de cada arquivo é explicado pelas saídas.
    relatorio_controle: dict = {"competencia": competencia}
    pontes = []
    if frentes.roda("checkout", presentes):
        pontes.append(("orbe", controle.ponte_orbe(sources["orbe"], rastro)))
    if frentes.roda("remessa", presentes):
        pontes.append(("ponte", controle.ponte_ponte(sources["ponte"], rastro, competencia)))
    if frentes.roda("extratos", presentes):
        pontes += [(banco, controle.ponte_banco(banco, sources[banco], lancamentos))
                   for banco in ("aurora", "meridiano") if banco in presentes]
    for fonte, (relatorio, problemas_fonte) in pontes:
        relatorio_controle[fonte] = relatorio
        integridade.extend(problemas_fonte)

    # Diretório da execução (timestamp) + symlink `latest`.
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = saida / competencia / f"exec_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    tabelas = dict(zip(SAIDAS, [comissoes, divergencias, notas, lancamentos, pendencias, rastro],
                       strict=True))
    for nome, df in tabelas.items():
        output.write_output(df, nome, out_dir)
    # R18: transações de EC sem contrato ficam guardadas para o mês seguinte (só no histórico).
    sem_contrato_ids = set(rastro.loc[rastro["id_saida"].astype(str).str.startswith("CK-SEMCONTRATO-"),
                                      "ref_origem"].astype(str)) if not rastro.empty else set()
    if sem_contrato_ids:
        orbe = sources["orbe"]
        escrever_orbe(orbe[orbe["id_transacao"].astype(str).isin(sem_contrato_ids)].drop_duplicates("id_transacao"),
                      out_dir / NOME_PENDENTES)
    # Só no histórico da execução: saida/ da raiz é só dos 6 CSVs.
    (out_dir / "controle_fechamento.json").write_text(
        json.dumps(relatorio_controle, ensure_ascii=False, indent=2), encoding="utf-8")
    # R26: a entrega é a pasta saida/ da raiz com os 6 CSVs do último fechamento; o histórico
    # de cada execução fica em saida/<competência>/exec_*/ (fora do git).
    for nome in SAIDAS:
        shutil.copyfile(out_dir / nome, saida / nome)

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

    # Ciclo de decisão: registra casos e aplica decisões aprovadas aplicáveis.
    casos_por_id = casos_mod.construir_lote(pendencias, rastro, competencia)
    aplicacoes_registradas: list[dict] = []
    for _, caso in casos_por_id.items():
        decisoes.registrar_caso(saida, caso)
        aprovada = decisoes.encontrar_decisao_para_caso(saida, caso)
        if aprovada is None:
            aprovada = decisoes.encontrar_condicao_aplicavel(saida, caso, competencia)
        if aprovada is not None:
            aplicacoes_registradas.append({
                "caso_hash": caso.caso_hash,
                "decisao_id": aprovada["id"],
                "escopo": aprovada["escopo"],
                "acao_tipo": aprovada["acao_tipo"],
            })
            decisoes.registrar_aplicacao(
                saida,
                decisao_id=aprovada["id"],
                caso_hash=caso.caso_hash,
                execucao_id=execucao_id,
                competencia=competencia,
                efeito="RECONHECIDA_NO_FECHAMENTO",
            )

    log.info("fechamento gravado em %s (execucao #%s); decisões aplicadas: %d",
             out_dir, execucao_id, len(aplicacoes_registradas))
    return ClosingResult(
        competencia=competencia,
        execucao_id=execucao_id,
        out_dir=out_dir,
        comissoes=comissoes, divergencias=divergencias, notas=notas,
        lancamentos=lancamentos, pendencias=pendencias, rastro=rastro,
        problemas_rastro=problemas_df, problemas_integridade=integridade,
        duracoes_s=duracoes, hashes=hashes, commit=commit, bloqueios=bloqueios,
        controle=relatorio_controle,
        casos=casos_por_id,
        aplicacoes_decisoes=aplicacoes_registradas,
    )
