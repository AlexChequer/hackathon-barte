"""python -m src.main --dados data/raw/set2026 --saida saida/

Fecha a comissão de CHECKOUT do mês: comissoes_por_lojista.csv, rastro.csv, pendencias.csv e controle.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.cadastro import Cadastro
from src.calculo import Resultado, calcular, conferir_rastro
from src.escrita import escrever
from src.leitura import PADRAO_ORBE, PADRAO_TAXAS, achar_arquivo, ler_orbe, ler_taxas

PREMISSAS = Path(__file__).with_name("premissas.json")


def rodar(dados: Path, premissas_path: Path = PREMISSAS) -> Resultado:
    premissas = json.loads(premissas_path.read_text(encoding="utf-8"))
    arq_orbe = achar_arquivo(dados, PADRAO_ORBE)
    cadastro = Cadastro(ler_taxas(achar_arquivo(dados, PADRAO_TAXAS)), premissas)
    return calcular(ler_orbe(arq_orbe), cadastro, premissas, arq_orbe.name)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Comissão de checkout da Tarvo por lojista, com rastro")
    p.add_argument("--dados", type=Path, required=True, help="pasta do data pack do mês")
    p.add_argument("--saida", type=Path, default=Path("saida"))
    args = p.parse_args(argv)

    res = rodar(args.dados)
    problemas = conferir_rastro(res)
    if problemas:
        print("RASTRO NÃO FECHA; nada foi gravado:", *problemas[:20], sep="\n  ", file=sys.stderr)
        return 2
    escrever(res, args.saida)

    c = res.controle
    print(f"Orbe: {c['linhas_orbe']} linhas, Σ valor_taxa {c['soma_valor_taxa_orbe']}")
    print(f"Comissão contratada: {c['qtd_lojistas_com_comissao']} lojistas, Σ {c['soma_comissoes_contratadas']}"
          f" (Orbe cobrou {c['soma_cobrado_orbe_nas_linhas_faturadas']} nessas linhas)")
    print(f"Pendências: {c['qtd_pendencias']}, Σ {c['soma_pendencias']} | fora: {c['soma_fora']}")
    print(f"Diferença de fechamento: {c['diferenca_fechamento']}")
    for pend in res.pendencias:
        print(f"  [{pend.quem_decide}] {pend.id_saida} {pend.valor_brl}: {pend.motivo}")
    print(f"Arquivos em {args.saida}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
