# CLAUDE.md: hackathon Barte / case Tarvo

Contexto: fechamento mensal de uma subadquirente fictícia. Leia `docs/MAPA_DADOS.md` e `HIPOTESES.md` antes de mexer em regra de negócio.

## Regras para a IA neste repo

- **Nunca editar nada em `data/raw/`.** Toda limpeza é feita em código.
- **Não inventar regra de negócio, mas também não paralisar o motor por detalhes já delegados.** Para decisão sem resposta direta do financeiro: se Helena pediu que o time decida ("decisão sua", "me digam como vocês tratariam"), registre uma **premissa fundamentada** em `HIPOTESES.md` e siga. Se não há informação suficiente para calcular (contrato/CNPJ/taxa ausente), **gere pendência** e **não fature**. **Nunca inventar contrato, taxa ou identidade** para desbloquear faturamento.
- **Nada de casamento aproximado de nomes.** Casar lojista por EC Orbe ou CNPJ normalizado. Se não casar, gerar pendência.
- Todo número de saída precisa de linhas em `rastro.csv` cuja soma bate com ele **em centavos exatos**, inclusive quando a saída é zero. `output.check_rastro` exige igualdade e origem válida.
- Dinheiro em `Decimal`, nunca `float`. **Arredondamento ocorre por linha/operação** com `ROUND_HALF_UP` (0,005 → 0,01; −0,005 → −0,01), e os totais somam valores já arredondados. O exportador apenas formata os valores já calculados.
- Formato de saída fixo: ver `src/tarvo/output.py::SCHEMAS`. Taxas em `*_pct` saem como percentuais (2.69 = 2,69%).
- Exceção de dado é **pendência para uma pessoa**, não erro silencioso nem `dropna`.

## Comandos

```bash
source .venv/bin/activate
python -m tarvo --dados data/raw/set2026 --saida saida
pytest -q && ruff check .
python -m tarvo.web --dados data/raw/set2026   # painel web fino sobre o mesmo motor
```

## Estrutura

- `src/tarvo/parse.py`: parsers pt-BR (número, taxa, data, CNPJ)
- `src/tarvo/loaders/`: um loader por arquivo do data pack
- `src/tarvo/rules.py`: constantes de negócio; de-para de EC (R3) em `config/cadastro_ec.json`, condições comerciais (R6) em `config/condicoes_comerciais.json`
- `src/tarvo/engines/`: motores por entregável (checkout, remessa, extratos)
- `src/tarvo/orquestrador.py`: cola motores + rastro + validação
- `src/tarvo/output.py`: schemas e escrita de `saida/`
- `src/tarvo/persistencia.py`: SQLite de execuções e decisões
- `src/tarvo/ui/app.py`: Streamlit fino sobre o motor
