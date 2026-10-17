"""Gera o pacote SINTÉTICO de outubro/2026 numa pasta, para testar o motor ou o painel.

Uso: python scripts/gerar_outubro_sintetico.py <pasta>
Depois: python -m tarvo --dados <pasta> --saida <outra pasta>   (ou envie os arquivos pelo painel)
Não grave a saída em saida/ da raiz: ela é a entrega oficial de setembro.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.sinteticos.outubro import gerar_outubro  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    pasta = gerar_outubro(Path(sys.argv[1]))
    print(f"pacote sintético de outubro em {pasta}:")
    for f in sorted(pasta.iterdir()):
        print(f"  {f.name}")
