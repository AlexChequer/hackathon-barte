"""Painel: python -m tarvo.web --dados <pasta do mês> [--saida saida] [--porta 8000]"""

import argparse
import logging
import webbrowser
from pathlib import Path

import uvicorn

from tarvo.web.api import criar_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="tarvo.web", description="Painel do fechamento Tarvo")
    parser.add_argument("--dados", type=Path, required=True, help="pasta com os arquivos do mês")
    parser.add_argument("--saida", type=Path, default=Path("saida"))
    parser.add_argument("--porta", type=int, default=8000)
    parser.add_argument("--sem-navegador", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not args.sem_navegador:
        webbrowser.open(f"http://127.0.0.1:{args.porta}")
    uvicorn.run(criar_app(args.dados, args.saida), host="127.0.0.1", port=args.porta)


if __name__ == "__main__":
    main()
