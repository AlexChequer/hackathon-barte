"""CLI: python -m tarvo --dados data/raw/set2026 --saida saida

Roda o fechamento completo e grava `comissoes_por_lojista.csv`, `divergencias_taxa.csv`,
`notas_a_emitir.csv`, `lancamentos_classificados.csv`, `pendencias.csv` e `rastro.csv`
em `saida/<competencia>/exec_<timestamp>/`, mantendo o symlink `latest`.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tarvo.avaliacao import avaliar_e_persistir
from tarvo.orquestrador import run_closing

log = logging.getLogger("tarvo")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tarvo", description="Fechamento mensal Tarvo")
    parser.add_argument("--dados", type=Path, default=Path("data/raw/set2026"))
    parser.add_argument("--saida", type=Path, default=Path("saida"))
    parser.add_argument("--competencia", default="2026-09", help="AAAA-MM")
    parser.add_argument(
        "--fixtures", type=Path, default=Path("tests/fixtures"),
        help="diretório com `referencia_<competencia>.json` para avaliar a saída",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        resultado = run_closing(args.dados, args.saida, args.competencia)
    except (FileNotFoundError, ValueError) as exc:
        log.error("falha no fechamento: %s", exc)
        return 1

    log.info("duracoes_s: %s", resultado.duracoes_s)
    log.info(
        "linhas: comissoes=%d divergencias=%d notas=%d lancamentos=%d pendencias=%d rastro=%d",
        len(resultado.comissoes), len(resultado.divergencias), len(resultado.notas),
        len(resultado.lancamentos), len(resultado.pendencias), len(resultado.rastro),
    )
    if not resultado.problemas_rastro.empty:
        log.error("rastro não bate em %d linhas — ver problemas_rastro",
                  len(resultado.problemas_rastro))
        return 2
    if resultado.problemas_integridade:
        log.error("problemas de integridade: %s", resultado.problemas_integridade)
        return 2
    log.info("fechamento OK em %s (execucao #%s)", resultado.out_dir, resultado.execucao_id)

    rel = avaliar_e_persistir(resultado, fixtures_dir=args.fixtures, saida=args.saida)
    if rel is None:
        log.info("sem referência em %s para %s; avaliação não executada",
                 args.fixtures, args.competencia)
    else:
        resumo = rel["resumo"]
        log.info("avaliação: %d/%d casos de referência OK; classificação %d/%d",
                 resumo["casos_referencia_ok"], resumo["casos_referencia_total"],
                 resumo["classificacao_num"], resumo["classificacao_den"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
