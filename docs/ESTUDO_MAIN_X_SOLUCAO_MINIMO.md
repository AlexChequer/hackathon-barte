# Estudo: `main` × `solucao_minimo`

> **Leia antes.** Este estudo foi escrito sobre o commit `0305e74` (17/10, ~12h40), sem alterar código. O `main` mudou depois. O que está diferente hoje (`4558863`, ~13h45):
>
> | Item no estudo | Hoje no `main` | Commit |
> |---|---|---|
> | Comissão de checkout Σ R$ 207.039,73 | **R$ 203.735,34**: o arquivo 06 (ajustes tardios da Orbe, 13h10) entra no fechamento (10 estornos, 3 reversões, 1 venda) | `29fa7c9` |
> | 13 pendências | **14**: + `ALERTA_ANTECIPACAO` da Atlas (lojista sem histórico, pelo pico; R16.6, R28.2, R32) | `4697b6e` |
> | Devolução da Casa = R$ 15.397,42 | Pendência de devolução = **R$ 15.396,77**, o que a Orbe descontou de fato (R33). As linhas `CK-COND` seguem a fórmula (R$ 15.397,42) | `4697b6e` |
> | Rastro com 4.802 linhas; `arquivo_origem` `orbe`/`ponte`/`aurora`/`meridiano` | 4.835 linhas; + `orbe_ajustes` | `29fa7c9` |
> | Comparação com a `solucao_minimo` (21 comissões batem) | Bate só lendo o 01. A `solucao_minimo` ainda não lê o arquivo 06 | — |
> | Itens marcados **[stash]** (`causa_divergencia`, sem `;` dentro de campo) | **Ainda não estão no `main`** | — |
>
> O risco apontado no fim (saída ignorada pelo git) continua aberto: gap 1 do `docs/BACKLOG.md`.

Base: para a `main`, o commit `0305e74` e a saída gerada a partir dele. As duas mudanças que estavam só no stash (sem `;` dentro de campo e coluna `causa_divergencia`) estão marcadas com **[stash]**.

## 1. O que o case pede em cada nível

| Nível | O que entrega (texto do case) |
|---|---|
| **Mínimo** | Comissão de checkout por lojista, com rastro |
| **Alvo** | Comissão das duas linhas (checkout e remessa), divergências de taxa, notas a emitir e lançamentos classificados |
| **Extra** | Rastro completo de todos os números, pendências explicadas e solução que roda em outubro sem retrabalho |

O case ainda diz: "É melhor entregar o nível mínimo certo do que o nível extra com números que não fecham."

**Onde cada branch chega:**
- **`main`:** entrega o Mínimo e o Alvo inteiros e boa parte do Extra (rastro de tudo, pendências explicadas, nada fixo de setembro).
- **`solucao_minimo`:** entrega o Mínimo e, do Alvo, só as divergências do checkout. Não tem remessa, notas nem lançamentos.

## 2. Como a `main` funciona

O comando `python -m tarvo --dados data/raw/set2026 --saida saida` passa por quatro etapas:

1. **Leitura:** há um loader por arquivo em `src/tarvo/loaders/`. Eles convertem número pt-BR em `Decimal`, CNPJ em 14 dígitos, datas e taxas. Os arquivos brutos não são alterados.
2. **Motores independentes**, em `src/tarvo/engines/`:
   - `checkout.py`: Orbe + planilha de taxas.
   - `remessa.py`: Ponte + planilha.
   - `extratos.py`: Aurora + Meridiano + plano de contas.
   - `sinais.py`: procura condição comercial escondida em observações da planilha.
3. **Orquestrador** (`orquestrador.py`): junta tudo e valida:
   - a soma do rastro bate em centavos com cada número;
   - não há id duplicado;
   - não há rastro apontando para saída inexistente;
   - toda linha de entrada caiu em alguma saída.

   Se algo falhar, a execução termina com erro.
4. **Escrita e avaliação:** grava em `saida/<competência>/exec_<hora>/` com o atalho `latest`, registra a execução em SQLite e compara com os 14 casos de referência e as 184 classificações.

### Nível Mínimo: comissão de checkout com rastro

Para cada transação da Orbe:

1. **Identificar o lojista:** pelo EC da Orbe, usando a coluna "EC Orbe" da planilha ou o de-para confirmado pela Helena (R3). Nunca pelo nome.
2. **Achar a linha de taxa vigente na data certa:** na venda, a data da venda; no estorno, a data da venda original (R2/P3). É isso que separa as duas vigências da Bridge.
3. **Escolher a coluna da taxa:** débito, crédito à vista, 2–6x, 7–12x, Pix ou antecipação.
4. **Aplicar a condição comercial, se houver:** `config/condicoes_comerciais.json` sobrepõe a taxa da planilha. É o caso da Casa: 0% de 01/09 a 31/12.
5. **Calcular:** `comissão = bruto × taxa contratada`, arredondada por linha (HALF_UP), e depois somada.
6. **Reversão de antecipação:** anula exatamente a comissão da antecipação original (P13).
7. **Casos sem cálculo viram pendência e não faturam:** EC sem contrato (Atlas), sem taxa, sem vigência, fora da competência, duplicata conflitante.

Resultado: 21 lojistas, Σ R$ 207.039,73 (hoje R$ 203.735,34 com o arquivo 06). Cada um tem o id `CK-CM-2026-09-<cnpj>`, e o rastro traz uma linha por transação.

### Nível Alvo

- **Comissão de remessa:**
  - participação = 50% × spread R$, por operação e arredondada;
  - operação repetida com os mesmos dados entra uma vez só;
  - spread negativo fica fora e vira pendência de contestação (R5).

  Resultado: 14 lojistas, Σ R$ 39.543,45.
- **Divergências:**
  - Checkout, quando a taxa aplicada difere da contratada, em duas categorias:
    - `CK-DIV`: a Orbe cobrou diferente da planilha (Rota, Bridge); a Tarvo contesta com a Orbe.
    - `CK-COND`: a Orbe cobrou certo pela planilha, mas valia uma condição comercial que ela não conhecia (Casa); a Tarvo devolve ao lojista do próprio bolso (R28).
    - Total: 210 linhas, Σ R$ 16.973,65.
  - Remessa: só conta como divergência um desvio acima de 0,01 p.p. (P7). Total: 23 linhas `RM-DIV`, Σ R$ 1.418,85.
- **Notas:**
  - checkout: uma por CNPJ, só se o saldo for positivo. São 20, porque a Casa fechou negativa e não tem nota;
  - remessa: uma única nota para a Ponte Câmbio, de R$ 39.543,45.
- **Lançamentos:** 184 linhas (84 Aurora, 100 Meridiano) classificadas por regra sobre a descrição, só em contas que aceitam lançamento. Sem regra, a conta fica vazia e vira pendência; nunca se inventa conta.

### O que já chega ao Extra

- **Rastro em tudo:** 4.802 linhas (hoje 4.835), inclusive para pendências e lançamentos.
- **13 pendências explicadas** (hoje 14), cada uma com quem decide.
- **Pronta para outubro:** competência inferida das datas, arquivos achados por padrão de nome, regras em `rules.py` e na configuração.
- **Interface Streamlit** sobre o mesmo motor.

## 3. Dicionário das colunas (como a `main` preenche)

### `comissoes_por_lojista.csv`

| Coluna | Significado | Na `main` |
|---|---|---|
| `id_saida` | Id do número | `CK-CM-<comp>-<cnpj>` ou `RM-CM-<comp>-<cnpj>` |
| `cnpj` | Lojista, 14 dígitos | Da planilha, via EC ou de-para |
| `lojista` | Nome | O nome mais longo entre as linhas do CNPJ (a Bridge tem duas) |
| `linha_negocio` | CHECKOUT ou REMESSA | Uma linha por CNPJ × linha de negócio. A Mundo Aberto aparece nas duas |
| `comissao_brl` | O que a Tarvo ganha pelo contrato | Soma das comissões por transação ou operação, já arredondadas |

### `divergencias_taxa.csv`

| Coluna | Significado | Na `main` |
|---|---|---|
| `id_saida` | Id | `CK-DIV-<tx>`, `CK-COND-<tx>` ou `RM-DIV-<op>` |
| `cnpj`, `linha_negocio` | Lojista e linha | |
| `ref_origem` | Linha de origem | `id_transacao` da Orbe ou `Nº Operação` da Ponte |
| `taxa_contratada_pct` | Taxa que deveria valer | Em `CK-COND`, é a condição comercial (0% na Casa) |
| `taxa_aplicada_pct` | Taxa cobrada | Em `CK-COND`, é a taxa da planilha, que a Orbe aplicou corretamente |
| `diferenca_brl` | Valor da diferença | bruto × (aplicada − contratada), arredondado por linha. Na remessa: Δspread × PTAX × valor ME |
| `causa_divergencia` **[stash]** | Por que divergiu | 118 Condição comercial não informada à Orbe, 87 Degrau sistêmico, 5 Taxa de outra vigência. Remessa vazia |

### `notas_a_emitir.csv`

| Coluna | Significado | Na `main` |
|---|---|---|
| `id_saida` | Id | `CK-NT-<comp>-<cnpj>` ou `RM-NT-<comp>-PONTE` |
| `tomador_cnpj`, `tomador` | Para quem emitir | No checkout, o lojista. Na remessa, a Ponte Câmbio (R4) |
| `linha_negocio` | | |
| `valor_brl` | Valor da nota | É a comissão. Saldo zero ou negativo não gera nota e vira pendência |
| `discriminacao` | Texto da nota | "Intermediação de pagamentos (checkout)…" ou "Intermediação de câmbio…" |

### `lancamentos_classificados.csv`

| Coluna | Significado | Na `main` |
|---|---|---|
| `id_saida` | Id | `EX-LC-<banco>-<ref>` |
| `banco` | AURORA ou MERIDIANO | |
| `ref_origem` | Linha de origem | Linha física na Aurora (`L10`) e FITID no Meridiano |
| `data`, `descricao`, `valor` | Copiados do extrato | |
| `conta_codigo` | Conta do plano | Pela regra; vazia se nenhuma regra casar |
| `metodo` | REGRA, IA ou HUMANO | Hoje tudo REGRA |
| `confianca` | 0 a 1 | 1,00 com regra e 0,00 quando fica pendente |
| `motivo` (extra) | Por que essa conta | Cita a regra R# |

### `pendencias.csv`

| Coluna | Significado | Na `main` |
|---|---|---|
| `id_saida` | Id | Ex.: `CK-CONTEST-…`, `RM-NEG-…`, `EX-PN-…` |
| `tipo` | Categoria | Ex.: `CONTESTACAO_ORBE`, `SEM_CONTRATO`, `NOTA_NEGATIVA`, `PIX_NAO_IDENTIFICADO` |
| `ref_origem` | O que está pendente | Transação, operação, CNPJ ou linha do extrato |
| `valor_brl` | Quanto está em jogo | Também tem rastro |
| `motivo` | Explicação para uma pessoa | Inclui a ação. **[stash]** acrescenta causa e prevenção na Rota e na Bridge |
| `quem_decide` | Financeiro, Comercial ou os dois | |

As 13 pendências de setembro (hoje 14, com o alerta de antecipação):
- **Checkout (5):** nota negativa da Casa, devolução da Casa, contestação da Rota, contestação da Bridge e Atlas sem contrato.
- **Remessa (5):** os 4 spreads negativos e a diferença contra o relatório da Ponte.
- **Extratos (3):** PIX sem identificação, devolução da Mundo Aberto e transferência em trânsito.

### `rastro.csv`

| Coluna | Significado | Na `main` |
|---|---|---|
| `id_saida` | Qual número da saída | |
| `arquivo_origem` | De onde veio | `orbe`, `orbe_ajustes`, `ponte`, `aurora` ou `meridiano` |
| `ref_origem` | Qual linha | |
| `valor` | Contribuição dessa linha | A soma por `id_saida` é igual ao número da saída |
| `metadata` (extra) | Contexto | Ex.: `tipo=VENDA,taxa_contratada=2.69` (com `,` no **[stash]**) |

## 4. Comparação com a `solucao_minimo`

### Onde as duas concordam

São implementações independentes e chegam aos mesmos números do checkout (lendo só o arquivo 01):
- **Comissão de checkout:** 21 lojistas, Σ R$ 207.039,73. A Casa fica em −5,50 nas duas.
- **Divergências do checkout:** 210 linhas, Σ R$ 16.973,65, com a mesma repartição 118 / 87 / 5.
- **Atlas:** não fatura e vira pendência de R$ 7.876,05, o que a Orbe cobrou.
- **Regras de base iguais:**
  - bruto × taxa com HALF_UP por linha;
  - estorno pela taxa da venda original;
  - reversão anulando a antecipação referenciada;
  - EC ligado por planilha ou de-para, nunca por nome.

Na prática, isso confirma o checkout da `main`.

### Onde diferem

| Tema | `main` | `solucao_minimo` |
|---|---|---|
| Escopo | Mínimo + Alvo + parte do Extra | Mínimo + divergências do checkout |
| Remessa, notas, lançamentos | Sim | Não |
| **Casa** | `CK-COND`, "Condição comercial não informada à Orbe": a Orbe cobrou certo pela planilha, e a Tarvo devolve sem cobrar da Orbe (R28) | `DIV-`, "Isenção ignorada": o rótulo sugere que a Orbe errou, mas ela nunca foi avisada |
| Comissão negativa da Casa | Pendência `NOTA_NEGATIVA` e nenhuma nota | Reporta −5,50 sem pendência (o README deixa isso para o Alvo) |
| Atlas | `SEM_CONTRATO`, identificada pelo CNPJ (R30) | `EC_SEM_CNPJ`, identificada só pelo EC |
| Pendências | 13 (hoje 14) | 1 (só a Atlas) |
| Ids | Prefixo por linha e tipo (`CK-DIV`, `CK-COND`, `RM-…`) | `CHK-`, `DIV-`, `GRP-`, `PEND-…` |
| Taxa em `*_pct` | 4 casas (`2.1900`) | 2 casas (`2.19`) |
| Causas | 3 + Não determinada **[stash]** | 5 + Não determinada: inclui "Outra faixa de parcelas" e "Modalidade trocada", testadas com dados sintéticos |
| "Não determinada" | Só rótulo | Vira pendência com as causas possíveis |
| Confiança por causa | Não | Sim: isenção 1,0, outra vigência 0,9, degrau 0,7 |
| Explicação no `comissoes_por_lojista` | Não; fica em divergências e pendências | Sim: 8 colunas extras (`causas_divergencia`, `leitura_causa`, `mitigacao_sugerida`…) |
| Agrupamento | Por lojista, na pendência | Arquivo próprio `divergencias_grupos.csv` (10 grupos por CNPJ × causa × produto, com janela de datas) |
| `id_transacao` repetido | Dados iguais: entra 1× (R24.1). Diferentes: pendência | Qualquer repetição vira pendência e não fatura |
| Verificações | Soma do rastro por id, ids únicos, toda entrada com saída, 14 casos de referência | Soma do rastro por id, cada transação em exatamente um destino, `controle.json` com diferença de fechamento 0,00 contra o total da Orbe |
| Rastro | 5 colunas + `metadata`. `arquivo_origem` curto (`orbe`) | 9 colunas, com tipo, bruto, valor cobrado pela Orbe e taxa contratada. `arquivo_origem` é o nome do arquivo |
| Onde ficam as regras | `rules.py` + `condicoes_comerciais.json` + detector de sinais na planilha | Tudo em `premissas.json`, cada regra citando a resposta da Helena |
| Saída no git | Em `saida/<comp>/exec_*/`, **ignorada pelo git** | Direto em `saida/`, versionada |
| Interface e histórico | Streamlit + SQLite | Só linha de comando |

Uma sutileza nos números da `solucao_minimo`: `diferenca_total_brl` no arquivo de comissões soma a divergência e o truncamento da Orbe. Por isso a Bridge aparece com 29,44, e não 29,95, e a Rota com 1.545,56, e não 1.546,28. A divergência propriamente dita é a mesma nas duas branches.

### Leitura para o estudo

- **O que a `solucao_minimo` faz melhor:**
  - explica cada lojista no próprio arquivo de comissões;
  - tem taxonomia de causas mais completa e confiança por causa;
  - tem agrupamento em arquivo próprio;
  - fecha o total contra a Orbe (`controle.json`);
  - deixa as regras como dados;
  - já tem a saída versionada.
- **O que a `main` faz melhor:**
  - cobre as duas linhas de negócio e todo o Alvo;
  - separa erro da Orbe de concessão da Tarvo, que é o ponto de R28 e muda quem paga;
  - transforma comissão negativa em pendência;
  - identifica a Atlas pelo CNPJ;
  - verifica que nenhuma entrada ficou sem saída.
- **O risco que a comparação mostra:** como `saida/` é ignorada pelo git na `main`, hoje nenhum CSV dela seria entregue. A `solucao_minimo` já resolve isso.
