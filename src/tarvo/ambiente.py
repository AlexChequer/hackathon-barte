"""Lê o `.env` da raiz do projeto (chaves de API) sem sobrescrever o que já está no ambiente.

O `.env` é ignorado pelo git; o modelo de configuração fica em `.env.example`.
"""

from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def carregar_env(caminho: Path = RAIZ / ".env") -> None:
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        os.environ.setdefault(chave.strip(), valor.strip().strip('"').strip("'"))
