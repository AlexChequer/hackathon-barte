"""Mede o detector de sinais no conjunto rotulado: python scripts/avaliar_sinais.py"""

import json
from pathlib import Path

from tarvo import sinais

ROTULOS = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "sinais_rotulados.json"


def main() -> None:
    rotulos = json.loads(ROTULOS.read_text(encoding="utf-8"))["textos"]
    textos = list(rotulos)
    regra = [bool(sinais.PALAVRAS_CHAVE.search(t)) for t in textos]
    clf = sinais.classificador_padrao()
    modelo = clf.relevantes(textos) if clf else [False] * len(textos)
    for nome, pred in [("palavras-chave", regra), (f"modelo ({clf.nome if clf else 'nenhum'})", modelo),
                       ("união", [a or b for a, b in zip(regra, modelo, strict=True)])]:
        acertos = sum(int(p) == rotulos[t] for t, p in zip(textos, pred, strict=True))
        erros = [t for t, p in zip(textos, pred, strict=True) if int(p) != rotulos[t]]
        print(f"{nome:32} {acertos}/{len(textos)}  erros: {erros}")


if __name__ == "__main__":
    main()
