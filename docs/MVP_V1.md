# Tarvo — MVP v1

Primeira versão executável do fechamento mensal. Commit `9d97b1c`.

## Problema

A Tarvo (subadquirente fictícia) fecha o mês em oito dias manuais, cruzando quatro
sistemas desalinhados: a Orbe (adquirência), a Ponte Câmbio (remessa), extrato do
Aurora e extrato do Meridiano. O trabalho vai em três entregas (comissão por
lojista, divergência de taxa, nota fiscal) + três subprodutos operacionais
(classificação contábil, pendências para humanos, rastro para auditoria). O
objetivo deste MVP é produzir essas seis saídas em um comando, com rastro em
centavos exatos e sem inventar valor quando falta informação.

Escopo deliberado desta v1: dados reais de `set/2026`, regras R1-R9 do financeiro
e premissas P1-P15 do time (ver `HIPOTESES.md`). Nada de ML, nada de competência
futura, nada de integração externa.

## Garantias que a arquitetura precisa dar

1. **Rastro em centavos exatos.** Toda linha monetária de saída tem linhas em
   `rastro.csv` cuja soma bate com ela usando `==`, não aproximação. Diferença
   de 0,01 é falha; valor zero sem origem é falha; `id_saida` sem rastro é
   falha. Validado em `output.check_rastro`.
2. **Nunca inventar valor.** Sem contrato/CNPJ/taxa resolvível → pendência,
   não fatura. Nenhum motor "estima" ou "aproxima" taxa. Casamento por EC Orbe
   ou CNPJ normalizado; nome textual nunca.
3. **Arredondamento por linha/operação.** Decimal com `ROUND_HALF_UP` aplicado
   em cada venda/operação (`money.q`, `money.q_mul`). Totais somam valores já
   arredondados (`money.sum_q`). Arredondar só no total gera drift de 0,01 e
   quebra o rastro.
4. **Rodada reprocessável.** Rodar duas vezes com o mesmo input gera duas
   execuções no SQLite, cada uma em seu diretório. Se o hash do data pack ou
   `rules.VERSION` mudou, decisões humanas gravadas antes ficam marcadas
   `precisa_reavaliar`, não sobrescritas silenciosamente.
5. **Nenhuma coluna de saída depende de interpretação.** O schema de cada CSV
   está fixo em `output.SCHEMAS`; o formatador só serializa Decimal/date. CSV
   com `;`, decimal `.`, data ISO, CNPJ 14 dígitos.

## Arquitetura

```
data/raw/set2026/*         →  loaders/        →  DataFrames puros (sem regra)
                              engines/        →  3 motores por entregável
                              orquestrador.py →  consolida + valida rastro
                              output.py       →  escreve 6 CSVs
                              persistencia.py →  SQLite (execucoes, decisoes)
                              avaliacao.py    →  compara vs referência manual
__main__.py (CLI)  ↑        ui/app.py (Streamlit) ↑
```

### Camadas

| Camada | Arquivo | Papel | Não faz |
|---|---|---|---|
| Parse | `parse.py` | número/taxa/data/CNPJ pt-BR | regra de negócio |
| Load | `loaders/*.py` | 1 por arquivo do data pack | regra de negócio |
| Dinheiro | `money.py` | `q`, `q_mul`, `sum_q`, `pct` | i/o |
| Regras | `rules.py` | constantes + de-para R3 + 4 negativos set/2026 | lógica |
| Motor | `engines/{checkout,remessa,extratos}.py` | 1 por entregável | leitura de disco |
| Orquestrador | `orquestrador.py` | cola + valida rastro + grava | regra de negócio |
| Saída | `output.py` | SCHEMAS fixos + `check_rastro` | cálculo |
| Persistência | `persistencia.py` | SQLite execucoes + decisoes | regra |
| Avaliação | `avaliacao.py` | compara vs `referencia_<comp>.json` | gerar baseline |
| UI | `ui/app.py` | Streamlit por cima do mesmo orquestrador | lógica própria |

### Fluxo

1. CLI/UI chama `orquestrador.run_closing(dados, saida, competencia)`.
2. `loaders.load_all` lê os seis arquivos do data pack.
3. Em sequência: `checkout.run`, `remessa.run`, `extratos.run`.
4. Orquestrador consolida DataFrames, roda `check_rastro` por saída monetária,
   verifica `id_saida` único entre saídas, verifica rastro órfão.
5. Grava `saida/<competencia>/exec_<timestamp>/*.csv` e symlink `latest`.
6. `persistencia.registrar_execucao` grava execução no SQLite e marca decisões
   antigas para reavaliar se o hash dos dados ou a versão das regras mudou.
7. `avaliacao.avaliar_e_persistir` compara contra
   `tests/fixtures/referencia_<comp>.json` e grava `avaliacao.json` no diretório
   da execução.

### Resultado atual (`set/2026`)

| Saída | Linhas |
|---|---|
| `comissoes_por_lojista.csv` | 35 (21 checkout + 14 remessa) |
| `divergencias_taxa.csv` | 233 |
| `notas_a_emitir.csv` | 21 |
| `lancamentos_classificados.csv` | 184 (100% com conta) |
| `pendencias.csv` | 66 |
| `rastro.csv` | 4592 |

Avaliação vs referência manual: 14/14 casos OK. Falhas de rastro: 0. Duração
total: ~0,3s.

## Decisões não óbvias (e por que)

### Um `id_saida` nunca aparece em dois CSVs de saída

Divergência é divergência; não vira pendência. A linha em `divergencias_taxa.csv`
já é a sinalização para o Financeiro. Duplicar em `pendencias.csv` dobraria o
rastro e quebraria o check de unicidade. Pendência existe para o que **não cabe
em outra saída**: EC sem contrato, taxa ausente, PIX sem id, devolução sem motivo,
reversão sem referência, nota negativa.

### `competencia` em formato ISO (`2026-09`)

A CLI aceita `--competencia 2026-09`. Os engines aceitam `2026-09` ou `set2026`
onde é relevante (ex.: exclusão dos 4 negativos). O formatador de nota entende
os dois. Caminhos de dados continuam `data/raw/set2026/` por acidente histórico
do data pack.

### Rastro em pendência também

`check_rastro` exige origem válida mesmo quando o valor é zero. Isso obriga
que toda pendência aponte para a linha física que a motivou (banco, EC, operação).
Sem isso é fácil criar pendência "do nada" que ninguém sabe explicar depois.

### Casa do Estudante: isenção por data da venda

EC 1018325654 tem MDR + antecipação 0% de 01/09 a 31/12/2026 (R6/P6). A isenção
é aplicada pela **data da venda**, não pela data do movimento. Estorno em 07/09
de uma venda de agosto usa a taxa histórica da vigência de agosto, não 0%. Por
isso TX88445133 fecha com comissão −5,50 e sem divergência. Vendas de setembro
têm contratada 0% e aplicada > 0% → viram divergência (R$ 15.397,42 agregado).

### Bridge: colapso por CNPJ, não por nome

Bridge tem duas linhas na planilha de taxas (vigências "até 15/09" e "a partir
de 15/09") para o mesmo CNPJ. R4 pede uma nota por CNPJ: `_canonical_lojista`
escolhe o nome mais longo. O motor por si decide qual vigência usar transação
a transação.

### Atlas: pendência, não fatura

EC 1076801732 não tem contrato vigente. R3 lista o que **tem** contrato; o resto
que apareça na Orbe vira pendência `SEM_CONTRATO` com valor da cobrança da Orbe
(exposição bruta). Nunca fatura, nunca cria nota, nunca estima taxa.

### Ponte Câmbio: todo spread negativo fica fora (R5)

Qualquer operação com `spread_brl < 0`, em qualquer mês, fica fora da comissão e da nota e vira
pendência `SPREAD_NEGATIVO_CONTESTAR` (valor cheio, `quem_decide = Financeiro`), com a observação da
Ponte no motivo. Antes era uma lista fixa dos 4 ids de setembro (P12), o que violava O1 ("nada fixo
para setembro"). A pergunta R-1 confirma a regra geral com a Helena.
Status compliance "APROVADO C/ RESSALVA" entra como válido (R5).

### Reversão de antecipação anula a comissão arredondada original

P13: `REVERSAO ANTECIPACAO` lê a comissão da antecipação original (já
arredondada) e grava o negativo exato. Não recalcula com a taxa atual; não
re-arredonda. Se a antecipação original está fora do lote, abre pendência
`REVERSAO_SEM_REFERENCIA`.

### Classificação contábil determinística

`extratos.py` é um encadeamento de `if desc contém X`. Zero magia. Lançamento
sem regra vira pendência `LANCAMENTO_SEM_REGRA` com `conta_codigo=None`. Em
set/2026 isso bateu 184/184 sem IA; isso pode mudar em outras competências e é
o lugar natural para experimentar sugestão de modelo depois.

### Transferência Aurora → Meridiano em 30/09

R6: o Meridiano só credita no dia útil seguinte. A saída do Aurora em 30/09 é
classificada em `1.1.09.001` (transferência própria) e abre pendência
`TRANSFERENCIA_EM_TRANSITO` para o Financeiro conferir o crédito em 01/10.

### Ponte Aérea ≠ Ponte Câmbio

Ambas aparecem em "PIX RECEB" no Meridiano. O motor normaliza acentos
(`_ascii`) e trata "PONTE AEREA" como lojista remessa, "PONTE CAMBIO" como
contrapartida da liquidação.

## O que o MVP NÃO faz

- Não sugere classificação quando a regra falha (hoje só pendência).
- Não valida regras de retenção de ISS/IR na nota (R4 é só o emissor, não a
  retenção).
- Não emite nota real; só a tabela com valores para o faturamento.
- Não lê planilha de taxas futura (só o formato de set/2026).
- Não tem autenticação na UI; qualquer um que rodar `streamlit run` escreve
  decisão no SQLite.
- Não exporta `avaliacao.json` em formato aceito por BI; é artefato de debug.

## Testes

- `tests/test_loaders.py`: integração contra o data pack real.
- `tests/test_parse.py`: parsers pt-BR.
- `tests/test_raw_integrity.py`: data pack não foi editado à mão.
- `tests/test_engines.py` (novo): 20 testes para casos críticos — Casa isenta,
  estorno TX88445133, Bridge colapsado, Atlas, Rota Global, 4 negativos,
  duplicata PC-0926-0162, transferência em trânsito, PIX sem id, rastro exato,
  reprocessamento idempotente, reavaliação por mudança de regra.

Rodar: `pytest -q` (43 testes, ~5s). Lint: `ruff check .`.

## Avaliação

Protocolo em `docs/AVALIACAO.md`. Referência manual (derivada à mão) em
`tests/fixtures/referencia_set2026.json`. O orquestrador grava
`avaliacao.json` ao lado dos CSVs. Toda métrica tem numerador/denominador;
nenhuma é 100% implícita.

## Como estender

A estrutura separa parse / regra / orquestração / i/o para que mudanças
caiam no lugar certo:

- Regra nova do financeiro → `rules.py` + motor relevante + `HIPOTESES.md`
  (bump `rules.VERSION` se afeta cálculo retroativo).
- Nova fonte de dado → `loaders/<nome>.py` + entrada em `loaders.FILES`.
- Nova saída → `output.SCHEMAS` + motor que a produz + rastro + teste.
- Nova pendência → tipo novo em um dos engines + referência manual em
  `tests/fixtures/`.
- Nova métrica → `avaliacao.py` com num/den explícito.
- UI → `ui/app.py` só adiciona visualização; nunca lógica.

O arquivo `AGENTS.md` (ou `CLAUDE.md`) traz as regras invioláveis para
qualquer agente que mexer no repo.
