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

### ✅ Base da comissão: respondida (R1)
É a **contratada**: bruto × taxa da planilha, linha a linha, e a nota usa esse valor. Se a Orbe cobrou a mais, a diferença volta ao lojista e a Tarvo cobra da Orbe, **caso a caso, decidido pelo financeiro**. Consequências:
- Os ~R$ 1.645 cobrados a mais da Rota Global não são receita. São devolução ao lojista, exatamente o caso da reclamação do mês passado.
- Toda divergência também vira **pendência**, com transação, valor e "financeiro" como quem decide.

### ✅ Estornos: respondida (R2, pergunta do time MN AI)
O estorno abate a comissão do mês em que acontece, mesmo que a venda seja de agosto (agosto não reabre). A taxa é a **contratada na data da venda original**.
- Em setembro, 9 dos 59 estornos são de vendas de agosto.
- Isso também resolve parte da vigência da Bridge: um estorno de venda anterior a 15/09 usa 2,59%.

### Rota Global: +0,5 p.p. a partir de 12/09
- **O que se vê:** 83 vendas, R$ 329 mil de volume, ~R$ 1.645 cobrados a mais.
- **Ponto fino:** a planilha foi atualizada em 02/09 e a mudança começa em 12/09. Ou o comercial renegociou e a planilha está desatualizada, ou a Orbe está com cadastro errado.
- **Por que perguntar:** se for renegociação, apontar divergência seria **alarme falso**, que conta contra.

### Os 4 ECs que não estão na planilha
- **Tamanho:** 290 transações, R$ 1,1 mi de volume e R$ 35 mil em taxas, ou seja, **~15% da receita de checkout** sem contrato para conferir.
- **A armadilha:** "Horizonte Viagens" (planilha), "HORIZONTE VIAGENS TURISMO" e "HORIZONTE INTERCAMBIO" (Orbe), mais "Novo Horizonte" (planilha). Casar por nome é exatamente o erro que as instruções citam.
- **Por que perguntar:** sem o mapa EC → CNPJ, não dá para saber de quem é a comissão nem para quem vai a nota.

### Antecipação e reversão
- **O que se vê:** 6 antecipações foram revertidas, somando −R$ 6.061.
- **A dúvida:** a reversão cancela a receita inteira? E os 2,10% são fixos ou dependem do prazo? Se dependerem do prazo, falta um dado e isso vira pendência.

### Remessa (Ponte)
- **Duplicada:** a operação PC-0926-0162 aparece 2× e o total da Ponte conta as duas. Se aceitarmos, faturamos R$ 411 a mais.
- **Spreads negativos:** 4 operações com −R$ 1.834 no total. Aceitar significa que a Tarvo paga pela operação.
- **Mundo Aberto:** negociou 1,2% e a Ponte cobrou ~1,5%.
- **Nota da remessa:** o e-mail diz que o repasse sai "mediante nota fiscal de intermediação". Então a nota parece ser para a **Ponte**, não para os lojistas, e isso muda o arquivo de notas inteiro.
- **Spread "padrão":** o valor não está escrito em lugar nenhum.

## A lógica por trás de tudo

O case avalia "**perguntar antes de construir**" (10%) e "**correção dos números**" (25%), e alarmes falsos contam contra. Cada dúvida acima é uma regra que, se a gente *chutar*, pode gerar um número errado com cara de certo. Onde não vier resposta, escrevemos a premissa em `HIPOTESES.md` e seguimos.
