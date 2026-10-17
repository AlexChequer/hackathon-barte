# Plano técnico do MVP

## Arquitetura

```
data/raw/<competencia>/*  ──►  loaders/  ──►  dict de DataFrames normalizados
                                              │
                                              ▼
                                       engines/  (checkout, remessa, extratos)
                                              │
                                              ▼
                                       orquestrador.py (concatena, valida, deduplica rastro)
                                              │
                                      ┌───────┴────────┐
                                      ▼                ▼
                              output.write_output   persistencia.sqlite
                                      │
                                      ▼
                              saida/<competencia>/*.csv (os 6)
                              saida/<competencia>/avaliacao.json
```

- CLI (`python -m tarvo`) e Streamlit (`src/tarvo/ui/app.py`) chamam o **mesmo orquestrador**. Zero duplicação de cálculo na interface.
- Regras de negócio ficam em `src/tarvo/rules.py` (constantes: de-para R3, Casa R6, vigências, Mundo Aberto 1,20%, padrão 1,5%, 4 negativos de setembro).
- `src/tarvo/money.py`: `Decimal` + `ROUND_HALF_UP` em utilitários (`q(valor)`, `q_rate_times_amount(bruto, taxa)`), para que todo lugar arredonde do mesmo jeito.
- SQLite local em `saida/tarvo.sqlite` guarda:
  - `execucoes`: competência, commit git, hashes dos arquivos, versão das regras (`rules.VERSION`), duração.
  - `decisoes`: pendência afetada, responsável, momento, motivo, escopo (lojista/operação/transação), estado atual, hash dos dados de origem usados — reavaliar quando o hash muda.
- Formato de saída preserva o schema existente. IDs têm prefixo por motor (CK-, RM-, EX-) e por tipo (CM-, DIV-, NT-, LC-, PN-).

## Ordem de implementação

1. Reconciliação dos documentos de contexto (CLAUDE.md, HIPOTESES.md, STATUS.md, MAPA_DADOS.md, CONTEXTO.md, PERGUNTAS_FINANCEIRO.md, PLANO.md, README.md, AVALIACAO.md).
2. `rules.py` + `money.py`.
3. `engines/checkout.py` (comissões, divergências, notas, pendências, rastro).
4. `engines/remessa.py` (dedup, exclusões, participação, divergência, nota única).
5. `engines/extratos.py` (classificação por regra + pendências para casos descritos).
6. `orquestrador.py` + `__main__.py` escrevem os 6 CSVs e validam rastro.
7. `persistencia.py` (idempotência + decisões).
8. `avaliacao.py` (métricas por lote de referência).
9. `ui/app.py` (Streamlit fino).
10. Testes dos casos críticos listados em `docs/AVALIACAO.md`.

## Virada de competência

- `--dados data/raw/out2026` basta: loaders localizam arquivos pelo padrão `set2026` → trocar sufixo (ver `src/tarvo/loaders/__init__.py`).
- Vigências estão em `rules.py` por data. A isenção da Casa vale até 31/12/2026; estornos de agosto continuam com taxa histórica.
- O conjunto de 4 negativos (P12) é da competência set/26 e **não se aplica** automaticamente a outubro.
- A persistência marca a execução anterior como superada se o hash do data pack mudar.

## Não entra agora

Jev, SLM, RAG, chatbot, microserviços, filas, autenticação, emissão fiscal real, movimentações bancárias.
