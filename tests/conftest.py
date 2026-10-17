"""Testes não carregam o modelo Laya (lento) nem chamam a OpenAI; os dois são testados com falsos."""

import os

os.environ.setdefault("TARVO_CLASSIFICADOR", "nenhum")
# Rascunhos (P36): os testes nunca chamam a API da OpenAI, mesmo com chave no .env (o .env não sobrescreve).
os.environ["OPENAI_API_KEY"] = ""
