"""Exporta os transcripts do Claude Code deste projeto para PROMPTS/sessoes/<usuario>/.

Uso: python scripts/exportar_sessoes.py <github-user> [--email <email a mascarar>] [--completo]

Padrão (legível, .jsonl):
- Imagens (prints colados na conversa) viram "[imagem removida]": mantém o arquivo abaixo do
  limite do GitHub sem perder o texto das conversas.
- Registros "api-request" (cópia da requisição inteira a cada turno, sem conversa nova) saem.
- E-mails informados são mascarados.
- Para se encontrar algo com cara de chave de API (não grava nada nesse caso).

--completo: nada é removido além dos e-mails; grava .jsonl.gz (o case pede o histórico sem edição).
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
IMAGEM = re.compile(r'"data":"[A-Za-z0-9+/=]{200,}"')
CHAVE = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}")


def pasta_do_projeto() -> Path:
    chave = re.sub(r"[/_.]", "-", str(REPO))
    return Path.home() / ".claude" / "projects" / chave


def _redundante(linha: str) -> bool:
    try:
        return str(json.loads(linha).get("type", "")).startswith("api-request")
    except (json.JSONDecodeError, AttributeError):
        return False


def mascarar(texto: str, emails: list[str]) -> str:
    for email in emails:
        texto = texto.replace(email, "[email]")
    return texto


def limpar(texto: str, emails: list[str]) -> str:
    linhas = [linha for linha in texto.splitlines(keepends=True) if not _redundante(linha)]
    texto = IMAGEM.sub('"data":"[imagem removida]"', "".join(linhas))
    for email in emails:
        texto = texto.replace(email, "[email]")
    return texto


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("usuario")
    parser.add_argument("--email", action="append", default=[])
    parser.add_argument("--completo", action="store_true", help="sem remover nada além de e-mails; grava .gz")
    args = parser.parse_args()
    origem = pasta_do_projeto()
    arquivos = sorted(origem.glob("*.jsonl"))
    if not arquivos:
        print(f"nenhum transcript em {origem}", file=sys.stderr)
        return 1
    limpos = {}
    for f in arquivos:
        bruto = f.read_text(encoding="utf-8")
        texto = mascarar(bruto, args.email) if args.completo else limpar(bruto, args.email)
        if CHAVE.search(texto):
            print(f"ATENÇÃO: possível chave de API em {f.name}; nada foi gravado", file=sys.stderr)
            return 2
        limpos[f.name] = texto
    destino = REPO / "PROMPTS" / "sessoes" / args.usuario
    destino.mkdir(parents=True, exist_ok=True)
    for nome, texto in limpos.items():
        if args.completo:
            alvo = destino / f"{nome}.gz"
            alvo.write_bytes(gzip.compress(texto.encode("utf-8"), compresslevel=9))
        else:
            alvo = destino / nome
            alvo.write_text(texto, encoding="utf-8")
        print(f"{alvo.name}: {alvo.stat().st_size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
