"""Escrita no formato fixo do case: CSV ';', ponto decimal com 2 casas, UTF-8, CNPJ só dígitos."""

from __future__ import annotations

import csv
import json
from decimal import Decimal
from pathlib import Path

from src.calculo import Resultado


def _fmt(v) -> str:
    if v is None:
        return ""
    if isinstance(v, Decimal):
        return f"{v:.2f}"
    return str(v)


def _escrever(caminho: Path, cabecalho: list[str], linhas: list[list]) -> None:
    with caminho.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";", lineterminator="\n")
        w.writerow(cabecalho)
        for linha in linhas:
            w.writerow([_fmt(v) for v in linha])


def _pct(v: Decimal | None) -> str:
    return "" if v is None else format(v.normalize(), "f")


def escrever(res: Resultado, saida: Path) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    _escrever(
        saida / "comissoes_por_lojista.csv",
        ["id_saida", "cnpj", "lojista", "linha_negocio", "comissao_brl",
         "qtd_transacoes", "ecs", "cobrado_orbe_brl"],
        [[c.id_saida, c.cnpj, c.lojista, "CHECKOUT", c.comissao_brl,
          c.qtd_transacoes, ",".join(sorted(c.ecs)), c.cobrado_orbe_brl] for c in res.comissoes],
    )
    _escrever(
        saida / "rastro.csv",
        ["id_saida", "arquivo_origem", "ref_origem", "valor",
         "tipo_lancamento", "valor_bruto", "valor_taxa_orbe", "taxa_contratada_pct", "obs"],
        [[r.id_saida, r.arquivo_origem, r.ref_origem, r.valor, r.tipo_lancamento,
          r.valor_bruto, r.valor_taxa_orbe, _pct(r.taxa_contratada_pct), r.obs] for r in res.rastro],
    )
    _escrever(
        saida / "pendencias.csv",
        ["id_saida", "tipo", "ref_origem", "valor_brl", "motivo", "quem_decide"],
        [[p.id_saida, p.tipo, p.ref_origem, p.valor_brl, p.motivo, p.quem_decide] for p in res.pendencias],
    )
    (saida / "controle.json").write_text(json.dumps(res.controle, ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8")
