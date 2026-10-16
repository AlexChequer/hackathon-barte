# CLAUDE.md: hackathon Barte / case Tarvo

Contexto: fechamento mensal de uma subadquirente fictícia. Leia `docs/MAPA_DADOS.md` e `HIPOTESES.md` antes de mexer em regra de negócio.

## Regras para a IA neste repo

- **Nunca editar nada em `data/raw/`.** Toda limpeza é feita em código.
- **Não inventar regra de negócio.** Se a regra não estiver em `HIPOTESES.md` (respondida ou premissa escrita), pare e sugira uma pergunta para o financeiro em vez de escolher sozinho.
- **Nada de casamento aproximado de nomes.** Casar lojista por EC Orbe ou CNPJ normalizado. Se não casar, gerar pendência.
- Todo número de saída precisa de linhas em `rastro.csv` cuja soma bate com ele (`output.check_rastro`).
- Dinheiro em `Decimal`, nunca `float`. Arredondamento só na saída, explicitado.
- Formato de saída fixo: ver `src/tarvo/output.py::SCHEMAS`.
- Exceção de dado é **pendência para uma pessoa**, não erro silencioso nem `dropna`.

## Comandos

```bash
source .venv/bin/activate
python -m tarvo --dados data/raw/set2026 --saida saida
pytest -q && ruff check .
```

## Estrutura

- `src/tarvo/parse.py`: parsers pt-BR (número, taxa, data, CNPJ)
- `src/tarvo/loaders/`: um loader por arquivo do data pack
- `src/tarvo/engines/`: motores por entregável (a criar)
- `src/tarvo/output.py`: schemas e escrita de `saida/`
