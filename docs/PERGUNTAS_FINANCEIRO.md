# Perguntas para o financeiro

Canal: `#duvidas-hackathon-ai`, prefixo `[financeiro] Fox AI:`. Uma dúvida por mensagem, com exemplo (id da linha).

## Respondidas (resumo)
- R1: comissão = taxa contratada; divergência caso a caso pelo financeiro.
- R2: estorno abate no mês do estorno, taxa da venda original.
- R3: 3 ECs mapeados; Atlas não fatura (pendência Comercial).
- R4: 1 nota por lojista no checkout, 1 nota para a Ponte no câmbio; comissão ≤ 0 → sem nota + pendência quando houver sinal negativo/inesperado.
- R5: remessa = 50% do spread realizado; padrão 1,5%; Mundo Aberto é divergência; negativos de set/26 fora; duplicada 1×; ressalva normal; competência = contratação.
- R6: Rota Global é divergência em crédito; Casa 0% set-dez; folha/impostos/repasse Ponte 08 são de agosto; PIX sem id, devolução e transferência em trânsito são pendências.
- R7: divergência de remessa cheia; tolerância é critério do time (P7 = 0,01 p.p., com motivo escrito).
- R8: ROUND_HALF_UP por linha; divergência compara taxas, não valores.
- R9: `conta_codigo` = contrapartida; folha/tributos/repasse Ponte 08 baixam passivo/recebível; demais despesas vão direto.
- R10: excesso da Mundo Aberto **entra** na nota de setembro (realizado); a contestação é à parte e vira pendência para a Helena.
- R11: não projetar desconto no repasse da Ponte; conferir o TED quando cair é pendência da Helena.
- R12: nada foi contestado ainda; Mundo Aberto, negativos **e a duplicata** viram pendência de contestação com valor e operações.
- R13: saldo negativo do Aurora = conta garantida; não conciliar Orbe × banco parcela a parcela, só classificar os créditos.
- R14: confirma R1/R2/R4 (pergunta do André).

## Checkout: fila de 17/10 (mandar uma por vez, nesta ordem)

Última respondida: **R14** (André, 16/10 ~22h34). R10–R13 vieram de perguntas de outros times.

- [ ] **C1. Estorno de venda divergente.** `[financeiro] Fox AI: estorno de venda que tinha divergência. Ex.: TX88446419 (Rota Global) foi cobrada a 4,09% e o contrato é 3,59%. No estorno, propomos registrar a divergência com sinal negativo (−52,10), anulando a da venda. São 5 casos em setembro (Rota e Casa), −107,53 no total. Confere?`
- [ ] **C2. Divergência também vira pendência?** (R10/R12 já dizem que sim na remessa; a pergunta agora é só se vale o mesmo no checkout, e se por transação ou por lojista) `[financeiro] Fox AI: divergências de checkout. Hoje cada uma sai só em divergencias_taxa.csv (210 linhas, R$ 16.973,65 líquido), com id e valor por transação. Propomos não repetir em pendencias.csv: a lista de divergências já é a fila para você decidir devolver ao lojista/cobrar da Orbe. Confere, ou quer uma pendência por lojista com o total?`
- [ ] **C3. Divergência a menor (P4).** Só se sobrar tempo: em setembro não há nenhum caso (Orbe nunca cobrou abaixo do contrato). Hoje o motor reportaria com sinal negativo.

Já cobertos e **não precisam** de pergunta: Casa com comissão −5,50 (estornos de agosto pela taxa antiga) → sem nota + pendência para a Helena (R2 + R4); Atlas → pendência Comercial com o valor cobrado pela Orbe (R3 + P10); Bridge 15–18/09 → divergência pela vigência (P3).

## Ainda materialmente abertas

1. **Divergência a menor** (P4): se a Orbe cobrou **menos** que o contratado também é divergência (Tarvo deixou de receber)? Nenhum caso em setembro; o motor já reporta com sinal.
2. **Quem decide por tipo de pendência**: temos defaults no motor (Financeiro, Comercial, Ponte). Confirmar.
3. **Comissão da Ponte: diferença contra o total declarado**: o motor fatura pela soma `round(spread × 0,5)` por operação deduplicada e sem negativos. Esta é a nota. A diferença contra o relatório da Ponte (R$ 39.036,80 - nossa participação após deduplicar e excluir os 4 negativos) vai como pendência para contestar. Confirmar que esse é o fluxo pretendido.
4. **Casos pendentes de extrato**: Atlas (sem contrato), PIX L50 R$ 7.350 (sem identificação), devolução Mundo Aberto L65 (+12.400). O motor abre pendência; precisamos de informação do pagador/comercial para evoluir.
