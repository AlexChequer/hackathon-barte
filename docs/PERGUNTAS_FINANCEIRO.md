# Rascunho de perguntas para o #tarvo-financeiro

> Atendimento: **hoje 16/10, das 20h30 às 22h30**, e amanhã das 9h30 às 17h30.
> Comece toda mensagem com o nome do time. Uma pergunta por thread, específica e com exemplo (id da linha).
> Ao receber a resposta, copie a pergunta e a resposta para `HIPOTESES.md` (com horário).

Prioridade **P0** = bloqueia o nível mínimo (comissão checkout). P1 = alvo. P2 = extra.

## Checkout (Orbe × planilha)

- **P0**: A comissão de checkout de um lojista é a soma do `valor_taxa` que a Orbe cobrou ou é o bruto × **taxa contratada**? Quando as duas diferem (ex.: lojista com 2,99% aplicado e 2,69% contratado), qual vale para a comissão e para a nota?
- **P0**: Em um ESTORNO (ex.: `TX88444848`, venda original de 22/08), a Tarvo devolve o MDR ao lojista em setembro? Estorno de venda de agosto entra na comissão de setembro?
- **P0**: A taxa de antecipação (2,10%) é fixa sobre o valor antecipado ou depende do prazo? A `REVERSAO ANTECIPACAO` cancela a receita da antecipação original?
- **P0**: Qual é o CNPJ e qual é a tabela de taxas destes ECs, que não estão na planilha vigente: `1043300981 HORIZONTE INTERCAMBIO`, `1043396662 HORIZONTE VIAGENS TURISMO`, `1076801732 ATLAS IDIOMAS`, `1038867654 KIWI EXPERIENCE`? Horizonte Viagens, Novo Horizonte e Kiwi estão com EC vazio na planilha.
- **P1**: Bridge mudou o crédito à vista em 15/09. A taxa nova vale pela **data da venda** ou pela data do movimento/liquidação?
- **P1**: Existe alguma tolerância (arredondamento) abaixo da qual a diferença de taxa não conta como divergência?
- **P1**: A Atlas Idiomas está só na aba "ANTIGO 2025". Ela ainda é cliente ativa? Qual taxa vale?
- **P1**: Parcelado 2–6x × 7–12x: a faixa é pelo número de parcelas da venda (`qtd_parcelas`)?

## Remessa (Ponte)

- **P1**: A comissão de remessa por lojista é 50% do `Spread R$` realizado de cada operação?
- **P1**: Qual é o spread "padrão" (em branco ou "padrão" na planilha)?
- **P1**: Spread negativo com "Taxa travada no pedido (D-1)" (ex.: `PC-0926-0210`): a Tarvo aceita o negativo, usa o spread estimado D-1 ou contesta com a Ponte?
- **P1**: `PC-0926-0162` aparece duas vezes ("reprocessada"). Conta uma vez só e a gente contesta a outra com a Ponte?
- **P1**: Operação contratada em setembro e liquidada em outubro (ex.: `PC-0926-0002`) entra em setembro?
- **P1**: Mundo Aberto negociou spread de 1,2% em jul/26, mas a Ponte cobrou cerca de 1,5%. Essa diferença é divergência a cobrar da Ponte ou a devolver ao lojista?

## Notas fiscais

- **P1**: A nota de checkout é emitida para cada lojista com o valor da comissão (MDR + antecipação − estornos)? Uma nota por lojista por mês?
- **P1**: A nota de remessa é emitida para a **Ponte Câmbio** (o e-mail fala em "nota fiscal de intermediação") ou para cada lojista?
- **P2**: Lojista que fica com comissão líquida negativa no mês: emite nota?

## Extratos e plano de contas

- **P1**: Os 2 PIX enviados para cada lojista no Aurora são repasses (2.1.01.001)? A `DEVOLUCAO PIX - MUNDO ABERTO` é devolução (2.1.01.002)?
- **P2**: As TEDs da Orbe no Aurora são liquidação de recebíveis (1.1.03.001)? Elas deveriam bater com o líquido da Orbe por dia?
- **P2**: O saldo do Aurora termina em −R$ 1,9 mi. Isso é esperado (limite/conta garantida) ou é erro do extrato?
