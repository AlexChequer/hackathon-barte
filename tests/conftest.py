"""Testes não carregam o modelo Laya (lento); o classificador é testado com um falso em test_sinais."""

import os

os.environ.setdefault("TARVO_CLASSIFICADOR", "nenhum")
