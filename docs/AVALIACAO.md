# Avaliação do fechamento

Protocolo mínimo para medir a qualidade do fechamento gerado pelo motor, sem adicionar infraestrutura. Resultado em `saida/<competencia>/avaliacao.json` (legível por máquina) e resumo na interface.

## O que registramos a cada execução

Linha em `execucoes` do SQLite:

- commit do repositório (`git rev-parse HEAD`)
- competência (ex.: `set2026`)
- hash SHA-256 de cada arquivo do data pack
- versão das regras (`rules.VERSION`)
- contagens por saída (comissões, divergências, notas, lançamentos, pendências, rastro)
- duração total e por motor (checkout, remessa, extratos)

## Referência manual

`tests/fixtures/referencia.yaml` lista casos derivados por cálculo independente e leitura de `HIPOTESES.md`, não gerados pelo próprio motor. Cada caso tem:

- `id`, `tipo` (`comissao_tx`, `divergencia_tx`, `nota`, `classificacao`, `pendencia`, `rastro`)
- origem (`arquivo`, `ref_origem`)
- `esperado`: valor em R$ (com sinal), conta contábil ou flag booleana, conforme o tipo
- `base_calculo`: fórmula explícita
- `fonte_regra`: R1-R9 ou P1-P15
- `status_revisao`: `derivado` (nós checamos à mão), `pendente` (sem resposta ainda)

**Nunca** marcamos automaticamente como "aprovado pelo financeiro". Essa etiqueta exige mensagem do financeiro.

### Regressão × generalização

- `regressao`: casos nomeados neste prompt (Casa `TX88445133`, `TX88410932`, Rota Global, Atlas, duplicata Ponte, 4 negativos, etc.). Esperamos cobrir **sempre**.
- `generalizacao`: pequena amostra de classificações bancárias reservada para medir se a regra generaliza, sem usar as mesmas descrições do grupo de regressão.

## Métricas

Cada métrica expõe numerador e denominador. **Sem referência, a métrica fica "não medida".** Não há 100% implícito.

| Métrica | Numerador | Denominador | Observação |
|---|---|---|---|
| Correção monetária por saída | nº de saídas que casam exatamente com a referência | nº de saídas na referência | soma absoluta dos erros em R$ também é reportada, sem compensar sinal |
| Precisão de alertas | alertas confirmados pela referência | alertas emitidos no conjunto da referência | mede falsos positivos no limite da amostra |
| Detecção de divergências | divergências da referência encontradas | divergências esperadas na referência | mede falsos negativos |
| Classificação correta | lançamentos com conta igual à referência | lançamentos avaliados | separado por banco e por categoria |
| Cobertura automática | registros resolvidos sem intervenção | registros processados | por etapa; mostra separadamente pendentes por falta de informação |
| Rastro íntegro | saídas monetárias com origem válida e soma exata | saídas monetárias | aplicado ao conjunto inteiro, não só à amostra |
| Trabalho humano | revisões registradas / correções registradas | execução | mostra tempo ativo quando o campo for preenchido |

A métrica "redução de 8 dias para X segundos" **não é reportada**. Oito dias é o relato do cliente, não uma baseline cronometrada.

## Critérios de aceitação

- Zero erro monetário nos casos da referência (regressão).
- 100% de integridade do rastro.
- Zero caso crítico perdido entre os listados abaixo.

## Casos críticos (regressão)

Lista mínima que o motor precisa acertar. Falha aqui bloqueia aceite.

- Arredondamento HALF_UP positivo/negativo no meio centavo; diferença entre arredondar linha × arredondar agregado.
- `TX88410932`: bruto 608,88 × 2,69% → comissão 16,38, cobrança Orbe 16,37 (truncada), **sem divergência**.
- Casa do Estudante:
  - vendas em setembro com taxa 0% (isenção) → comissão 0, divergência = cobrança da Orbe.
  - `TX88445133`: estorno em 07/09 de venda 21/08 (débito 1,49%) → comissão −5,50 e **sem divergência**.
  - checkout mensal da Casa não emite nota (saldo ≤ 0, com motivo "isento R6"); pendência adicional apenas pelo saldo negativo.
- Bridge antes/depois de 15/09; estorno de venda anterior usa 2,59%.
- Rota Global com taxa errada apenas em crédito; débito/Pix sem divergência.
- 3 ECs mapeados em R3 faturados; Atlas sem comissão e sem nota (pendência).
- Reversão anula a comissão arredondada da antecipação original (não recalcula).
- Ponte: duplicata PC-0926-0162 contada uma vez; 4 negativos fora; status "APROVADO C/ RESSALVA" dentro; operação contratada 30/09 com liquidação 01/10 entra em setembro; nota única para Ponte Câmbio.
- Tolerância de remessa: limiar exatamente no limite, abaixo e acima; unidades corretas (p.p. vs fração).
- Extratos: baixa de passivo folha/tributos/repasse Ponte 08; PIX L50 pendente; devolução L65 pendente; transferência de 300.000 em 30/09 pendente (não cria crédito em setembro no Meridiano); diferenciação Ponte Aérea × Ponte Câmbio.
- Rastro: diferença de 0.01 deve falhar; valor zero sem origem falha; origem inexistente falha; `id_saida` duplicado em saídas falha; várias linhas de rastro com o mesmo `id_saida` são permitidas.
- Reprocessamento sem duplicação; decisão persistida reaproveitada; mudança de hash do data pack marca decisão para reavaliação.

## Experimentos futuros (não implementar agora)

- Jev/SLM como sugestão para classificação quando a regra não resolve, com opção "informação insuficiente".
- Comparação em modo paralelo (não altera resultados oficiais).
- Métricas: acerto × correções × minutos de revisão × custo × latência sobre a mesma amostra de generalização. Confiança do modelo é metadado; não substitui acurácia medida.
