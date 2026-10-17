"""Loaders: leem cada arquivo do data pack como ele vem, sem aplicar regra de negócio.

Cada loader devolve um DataFrame novo com colunas normalizadas e uma coluna de rastro
(`linha_origem` ou o id natural da fonte) para que todo número de saída aponte para a origem.
Interpretação (vigência, 'padrão', duplicadas, spread negativo...) fica no motor, não aqui.
"""

from fnmatch import fnmatch
from pathlib import Path

import pandas as pd

from tarvo.loaders.aurora import load_aurora
from tarvo.loaders.meridiano import load_meridiano
from tarvo.loaders.orbe import load_orbe
from tarvo.loaders.plano import load_plano
from tarvo.loaders.ponte import load_ponte
from tarvo.loaders.taxas import load_taxas

FILES = {
    "orbe": "01_orbe_relatorio_comissoes_*.csv",
    "taxas": "02_tabela_taxas_contratadas*.xlsx",
    "ponte": "03_email_ponte_cambio_relatorio_*.eml",
    "plano": "04_plano_de_contas_*.csv",
    "aurora": "05a_extrato_banco_aurora_*.csv",
    "meridiano": "05b_extrato_banco_meridiano_*.ofx",
}
# Opcionais, zero ou mais arquivos: ajustes que a Orbe manda depois do relatório (17/10 13h10, R34).
# Mesmo formato do 01; entram na mesma base da Orbe com `arquivo_origem = "orbe_ajustes"`.
OPCIONAIS = {
    "orbe_ajustes": "*_orbe_ajustes_*.csv",
}


# Lista única dos arquivos do mês (o que a tela pede e o que o upload confere).
ESPERADOS = [
    {"chave": "orbe", "padrao": FILES["orbe"], "obrigatorio": True,
     "nome": "Relatório da Orbe", "descricao": "uma linha por transação (CSV)"},
    {"chave": "taxas", "padrao": FILES["taxas"], "obrigatorio": True,
     "nome": "Tabela de taxas contratadas", "descricao": "planilha do financeiro (XLSX)"},
    {"chave": "ponte", "padrao": FILES["ponte"], "obrigatorio": True,
     "nome": "E-mail da Ponte Câmbio", "descricao": "relatório de remessas em anexo (EML)"},
    {"chave": "plano", "padrao": FILES["plano"], "obrigatorio": True,
     "nome": "Plano de contas", "descricao": "exportado do ERP Fênix (CSV)"},
    {"chave": "aurora", "padrao": FILES["aurora"], "obrigatorio": True,
     "nome": "Extrato Aurora", "descricao": "conta principal (CSV)"},
    {"chave": "meridiano", "padrao": FILES["meridiano"], "obrigatorio": True,
     "nome": "Extrato Meridiano", "descricao": "conta de remessas (OFX)"},
    {"chave": "orbe_ajustes", "padrao": OPCIONAIS["orbe_ajustes"], "obrigatorio": False,
     "nome": "Ajustes tardios da Orbe",
     "descricao": "se a Orbe mandar depois do relatório; zero ou mais (CSV)"},
]
IGNORADOS = ["00_LEIA-ME*"]


def validar_lote(nomes: list[str]) -> list[str]:
    """Problemas de um lote de upload: obrigatório faltando ou repetido, arquivo desconhecido."""
    problemas = []
    for nome in nomes:
        conhecido = any(fnmatch(nome, e["padrao"]) for e in ESPERADOS)
        if not conhecido and not any(fnmatch(nome, p) for p in IGNORADOS):
            problemas.append(f"{nome}: não é um arquivo do fechamento")
    for e in (e for e in ESPERADOS if e["obrigatorio"]):
        achados = [n for n in nomes if fnmatch(n, e["padrao"])]
        if not achados:
            problemas.append(f"faltando: {e['nome']} ({e['padrao']})")
        elif len(achados) > 1:
            problemas.append(f"mais de um {e['nome']}: {', '.join(achados)}")
    return problemas


def find_file(data_dir: Path, key: str) -> Path:
    matches = sorted(data_dir.glob(FILES[key]))
    if len(matches) != 1:
        raise FileNotFoundError(f"esperava 1 arquivo '{FILES[key]}' em {data_dir}, achei {len(matches)}")
    return matches[0]


def find_opcionais(data_dir: Path, key: str) -> list[Path]:
    return sorted(data_dir.glob(OPCIONAIS[key]))


def _load_orbe_completa(data_dir: Path) -> pd.DataFrame:
    """Relatório 01 + arquivos de ajuste da Orbe, cada linha marcada com o arquivo de origem."""
    partes = [load_orbe(find_file(data_dir, "orbe")).assign(arquivo_origem="orbe")]
    partes += [load_orbe(f).assign(arquivo_origem="orbe_ajustes")
               for f in find_opcionais(data_dir, "orbe_ajustes")]
    return pd.concat(partes, ignore_index=True)


def load_all(data_dir: Path) -> dict:
    return {
        "orbe": _load_orbe_completa(data_dir),
        "taxas": load_taxas(find_file(data_dir, "taxas")),
        "ponte": load_ponte(find_file(data_dir, "ponte")),
        "plano": load_plano(find_file(data_dir, "plano")),
        "aurora": load_aurora(find_file(data_dir, "aurora")),
        "meridiano": load_meridiano(find_file(data_dir, "meridiano")),
    }
