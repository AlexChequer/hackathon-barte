# Contexto do problema: a Tarvo, explicada

Documento para o time ter o contexto completo do negócio, saber onde está o problema e entender por que cada pergunta ao financeiro importa. Os números são de set/2026.

## A Tarvo em 30 segundos

A Tarvo é uma **subadquirente**, um intermediário de pagamentos. Ela atende ~25 lojistas do mercado de intercâmbio (agências, escolas de idiomas) e ganha dinheiro de duas formas.

### 1. Checkout (cartão e Pix)

```
Aluno paga R$ 1.000 ──► Orbe (a "maquininha") ──► Tarvo ──► repassa ao lojista R$ 973,10
                                                   └── fica com 2,69% = R$ 26,90 (MDR)
```

- **MDR**: a taxa que o lojista paga por venda. Varia por modalidade (débito, crédito à vista, parcelado 2–6x, parcelado 7–12x, Pix) e por lojista, porque cada um negociou a sua.
- **Antecipação**: o lojista quer receber hoje uma venda parcelada que só cairia em meses, e a Tarvo cobra 2,10% para adiantar o dinheiro.
- **Estorno**: o aluno cancelou a compra, então a venda é desfeita.

### 2. Remessa internacional

```
Lojista manda R$ 50.000 ──► Tarvo ──► Ponte Câmbio converte e paga a escola lá fora
                                       └── spread do câmbio (~1,5%): a Ponte repassa 50% à Tarvo
```

## Onde está o problema

Cada sistema conta **uma parte** da história, e ninguém cruza as partes:

| Fonte | O que diz | Problema |
|---|---|---|
| Relatório Orbe | O que **foi cobrado** de cada lojista | Ninguém confere contra o contrato |
| Planilha de taxas | O que **foi combinado** | Mantida à mão ("última atualização: 02/09 - Bia"), com formatos misturados e ECs faltando |
| E-mail da Ponte | As remessas do mês | Vem com operação duplicada e spread negativo, e o time não sabe se aceita |
| Extratos bancários | O dinheiro que **de fato entrou e saiu** | Precisa ser classificado no plano de contas à mão |

A frase que resume a **causa raiz** é esta: *"No mês passado um lojista reclamou que pagou taxa a mais. Ele tinha razão, e a gente só descobriu porque ele reclamou."*

- **Por que acontece:** a Orbe cobra uma taxa, a planilha diz outra, e ninguém compara as duas linha a linha. São ~2.000 transações por mês e 3 pessoas.
- **Por que piora:** as regras só existem na cabeça de uma pessoa ("Se eu sair de férias, o mês não fecha").

Automatizar o processo como ele é hoje não resolve. O sistema precisa **confrontar contrato × cobrança × banco**, mostrar onde não bate e entregar as exceções para uma pessoa decidir.

## Os 6 entregáveis, em português claro

1. **Comissões por lojista**: quanto a Tarvo ganhou de cada um, separado em checkout e remessa. É a receita do mês.
2. **Divergências de taxa**: cada transação em que o cobrado ≠ o contratado, com o valor em R$. Isso é o dinheiro a devolver ao lojista e a cobrar da Orbe.
3. **Notas fiscais**: a Tarvo precisa faturar a receita. O arquivo diz para quem, de qual linha e de quanto.
4. **Lançamentos classificados**: cada linha dos extratos ganha uma conta contábil (ex.: "TED da Orbe" → Recebíveis de adquirente).
5. **Pendências**: o que o sistema **não pode decidir sozinho**, com o motivo e quem decide.
6. **Rastro**: cada número aponta para as linhas de origem e a soma tem que bater. Sem isso, o número "não conta".

## Quanto dinheiro está em jogo

| Item | Valor (taxa que a Orbe cobrou) |
|---|---|
| Taxas cobradas no checkout (líquido) | **R$ 231.880** |
| ↳ vendas (1.840) | R$ 214.558 |
| ↳ antecipações (38) | R$ 30.491 |
| ↳ estornos (59) e reversões de antecipação (6) | −R$ 13.169 |
| Spread total das remessas (233 operações, como a Ponte reportou) | R$ 78.074, dos quais 50% = **R$ 39.037** para a Tarvo |

A comissão oficial é calculada pela taxa **contratada** (resposta R1), então vai diferir desses totais justamente no valor das divergências.

## As dúvidas e por que importam

Todas as decisões abaixo estão hoje em `HIPOTESES.md` (R1–R9, P1–P15). Esta seção explica o porquê de cada regra.

### ✅ Base da comissão (R1, R8)
Contratada: bruto × taxa da planilha, linha a linha, com `Decimal` e `ROUND_HALF_UP` por linha. Divergência existe quando a **taxa** aplicada é diferente da contratada; centavo de truncamento da Orbe não gera divergência. Divergência vira pendência; a decisão de devolver/cobrar é do financeiro e não altera o reconhecimento.

### ✅ Estornos (R2)
Entram na competência do estorno, com modalidade e taxa da data da venda original. Em setembro, 9 dos 59 estornos têm venda em agosto. Resolve também a vigência da Bridge (2,59% até 14/09 / 2,19% a partir de 15/09) e a isenção da Casa (estornos de venda de agosto usam a taxa histórica).

### ✅ Rota Global (R6, P9)
O contrato não mudou. O desvio está em **crédito** a partir de 12/09. Débito e Pix batem no histórico. O motor **compara por modalidade**: qualquer modalidade pode gerar divergência, não aplicamos reajuste automático em modalidade sem desvio.

### ✅ ECs faltando na planilha (R3, P10)
Três têm linha correspondente na aba vigente: `1043300981`, `1043396662`, `1038867654`. **Atlas (1076801732) não tem contrato vigente** — ninguém sabe a taxa. O motor **não inventa taxa nem comissão zero fictícia**: deixa as 57 transações visíveis como pendência para o Comercial, com `valor_brl` representando a cobrança observada (exposição bruta).

### ✅ Antecipação e reversão (R4, P13)
Antecipação usa a taxa contratada da antecipação do lojista (2,10% nos dados). Reversão **anula a comissão contratual arredondada da antecipação original**, localizada por `id_referencia`; não cobra pela taxa atual. Referência ausente/conflitante → pendência.

### ✅ Remessa (R5, R7, P5, P7, P12, P14)
- Duplicada PC-0926-0162 conta 1×, com evidência preservada.
- Quatro negativos (0210, 0326, 0491, 0545) ficam fora da comissão/nota e abrem pendência de contestação (R5). Isso vale **para essas quatro operações**; não é regra automática para o futuro.
- Participação = `round(spread_brl × 0,5)` **por operação**, somada por lojista; nota única para a Ponte Câmbio (75374179000146).
- Divergência de spread: valor cheio por operação, (aplicado − contratado) × PTAX × valor ME. "Padrão"/vazio = 1,5%. Mundo Aberto = 1,20%. Texto inválido no campo não vira default silencioso.
- Tolerância 0,01 p.p. (P7, critério do time, documentado com motivo). O relatório de avaliação mostra o somatório absoluto dos desvios suprimidos por lojista.

### ✅ Casa do Estudante (R6, P6)
Tarifa 0% entre 01/09 e 31/12. Durante a vigência não há comissão (nota não emitida). Estorno em setembro de venda de agosto usa a taxa histórica. Exemplo: `TX88445133` (estorno −369,39 em 07/09, venda 21/08, débito 1,49%) tem comissão −5,50 e **nenhuma** divergência.

### ✅ Extratos (R6, R9)
`conta_codigo` é a contrapartida, só contas que aceitam lançamento. Folha, tributos de 08 e repasse Ponte 08/2026 baixam passivo/recebível. Tarifas, aluguel, cloud, assinaturas, serviços entram direto na despesa de setembro. PIX L50 (7.350), devolução Mundo Aberto L65 (+12.400) e transferência de 300 mil 30/09 → 01/10 ficam pendentes com classificação de "não identificado"/"em trânsito".

## A lógica por trás de tudo

O case avalia "perguntar antes de construir" (10%) e "correção dos números" (25%), e alarmes falsos contam contra. Onde não há resposta direta, registramos premissa fundamentada; onde falta informação para calcular, abrimos pendência e não faturamos. **Comissão contratada + divergência ≠ cobrança da Orbe** (truncamento), e **comissão mensal ≠ soma dos repasses no banco** (competência, elegibilidade). Cada saída fecha com o próprio rastro.
