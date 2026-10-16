"""CLI: python -m tarvo --dados data/raw/set2026 --saida saida

Estágio atual: carrega e resume as fontes. Os motores (comissões, divergências, notas,
classificação, pendências) entram aqui conforme forem implementados.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from tarvo.loaders import load_all

log = logging.getLogger("tarvo")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tarvo", description="Fechamento mensal Tarvo")
    parser.add_argument("--dados", type=Path, default=Path("data/raw/set2026"))
    parser.add_argument("--saida", type=Path, default=Path("saida"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    try:
        sources = load_all(args.dados)
    except (FileNotFoundError, ValueError) as exc:
        log.error("falha ao carregar data pack: %s", exc)
        return 1

    for name, df in sources.items():
        log.info("%-10s %5d linhas", name, len(df))
    log.info("motores ainda não implementados; nada escrito em %s", args.saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
