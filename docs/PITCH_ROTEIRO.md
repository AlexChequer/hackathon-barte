# Roteiro do pitch (10 min + 5 de perguntas)

Deck: https://claude.ai/artifact/FWpN8fx9K2fdwmPceE1sEM (13 slides; as notas de cada slide têm o mesmo texto).
Público: Helena, o financeiro e o CFO da Tarvo. **Falar como quem vai fechar outubro, não como quem escreveu o código.** Sem "loader", "engine" ou "endpoint".

Fio da história: **sintoma** (8 dias) → **causa** (o fechamento é a Helena) → **onde quebra** (5 etapas) → **quanto custa** → **a virada** (tirar o fechamento da cabeça dela) → prova (rastro, Casa, outubro) → limites (IA, falhas, confiança) → próximo mês.

| Slides | Quem | Tempo | Acumulado |
|---|---|---|---|
| 1–5 | Alex | 3 min 40 | 3:40 |
| 6–8 | Helio | 3 min | 6:40 |
| 9–13 | André | 2 min 50 | 9:30 |

Sobram 30 s de folga para a demo atrasar.

---

## Alex

**1. Capa (15 s).** "Somos a Fox AI: Alex, Helio e André. A gente fechou setembro da Tarvo com um comando, e cada número que vamos mostrar tem o caminho até a linha do arquivo de onde ele veio."

**2. O problema: o fechamento é a Helena (60 s).** "Hoje a Tarvo leva 8 dias para fechar o mês. Não é por falta de esforço: é porque o fechamento não é um processo, é a Helena. As regras que decidem quanto a Tarvo fatura, quanto devolve e o que contesta não estão escritas. Estão na cabeça dela, e parte nem lá. A prova é a nossa experiência: fizemos 34 perguntas ao financeiro para fechar um único mês, e cada resposta era uma regra que não estava em arquivo nenhum. O 0% da Casa do Estudante só existia num comentário de célula. A Mundo Aberto paga 1,20% desde julho, e a Ponte nunca foi avisada. Quem é quem na Orbe, a Helena sabe de cabeça. Se ela sai de férias, o mês não fecha. Se entra uma analista nova, não tem por onde começar. Se um auditor pergunta de onde veio um número, a resposta é 'pergunta pra Helena'."

**3. Cinco etapas, cinco armadilhas (60 s).** Um exemplo por etapa, não a tabela inteira:
- "**Juntar os arquivos:** o relatório da Ponte chega anexado num e-mail, e a Orbe mandou 14 ajustes depois do relatório."
- "**Saber quem é quem:** a Orbe não manda CNPJ, e a Atlas só aparecia numa aba de 2025."
- "**Saber qual taxa vale:** vale a data da venda, não a do pagamento. A Bridge mudou de taxa em 15/09, e a Orbe seguiu cobrando a velha."
- "**Conferir a cobrança:** a Orbe trunca o centavo em mil linhas, o que não é erro, e no meio disso a Rota Global pagou meio ponto a mais em 87 vendas, o que é."
- "**Explicar o banco:** um PIX recebido de lojista é dinheiro dele para a remessa, não receita."
- Fecho: "Nada disso é difícil sozinho. O difícil é que são dezenas de armadilhas, todo mês, e a única lista delas é a memória da Helena."

**4. O que se perde (55 s).** "Quando a regra mora na cabeça de alguém, ela não chega a quem cobra nem a quem confere. Em setembro, isso deu: R$ 15.396,77 cobrados da Casa do Estudante que precisam ser devolvidos, porque o acordo nunca chegou à Orbe. R$ 7.876,05 de comissão da Atlas sem contrato. R$ 1.576,23 que a Orbe cobrou a mais e R$ 1.418,85 de spread acima do contrato na Ponte. E R$ 300 mil em trânsito esperando alguém lembrar. Nenhum desses números aparece no total do mês. Só aparece para quem sabe onde olhar, e hoje só a Helena sabe."

**5. A virada (30 s).** "O que a gente fez foi tirar o fechamento da cabeça da Helena. Os arquivos entram como chegam, e cada regra está escrita com a resposta dela que a sustenta. Saem as notas, as divergências separadas entre cobrar, devolver e contestar, os lançamentos, as pendências com dono e o rastro de cada centavo. Lojista sem contrato não fatura: a gente não inventa taxa para fechar a conta. O Helio mostra como isso funciona."

## Helio

**6. Um número até a origem (75 s, demo se der).** "R$ 1.546,28 a cobrar da Orbe pela Rota Global. Clico no valor [painel, aba Pendências] e abrem as 87 transações que somam até ele, no centavo. Uma delas é a TX88423890, linha 727 do relatório da Orbe: crédito em 8 vezes, R$ 6.449,10, cobrado a 4,09% quando o contrato é 3,59%. Meio ponto de R$ 6.449,10 dá R$ 32,25. E o fechamento achou o padrão: todo crédito, +0,50 p.p., desde 12/09, com débito e Pix certos. A Orbe recebe a lista pronta para contestar."
- *Plano B sem painel:* abrir `saida/rastro.csv` filtrando `CK-CONTEST-2026-09-95927868000148`.

**7. Condição escondida (40 s).** "O caso mais caro estava num comentário de célula: 'conversar com o Diego sobre condição especial'. A Helena confirmou 0% de setembro a dezembro. A Orbe não sabia e cobrou 2,69% em 118 vendas: são R$ 15.396,77 a devolver, sem cobrar da Orbe. Agora, todo mês, o fechamento relê os comentários da planilha. Anotação nova vira pendência para o Comercial, e nenhuma taxa muda sozinha."

**8. Outubro (65 s).** "Em outubro, a Helena sobe os arquivos com o nome que vierem. Se a Ponte atrasar o e-mail, o checkout e os extratos fecham, e só a remessa espera. Ela trabalha a fila por quem decide. Cada decisão tem dono: o Comercial aprova taxa, ela aprova regra, e a decisão aprovada vale no mês seguinte para o mesmo caso. Quando o contrato da Atlas entrar, as transações de setembro, que ficaram guardadas, são faturadas sozinhas. Testamos com um outubro sintético, com lojista novo, anotação nova e ajuste da Ponte, sem mudar uma linha de código."

## André

**9. IA onde errar é barato (60 s).** "A pergunta que fizemos não foi 'onde dá para usar IA', foi 'onde errar custa pouco'. No cálculo, custa muito. Um modelo de linguagem pode alucinar ou trocar um dígito, e no financeiro um dígito errado é uma nota errada, uma devolução a mais ou uma cobrança que não se faz. E ninguém vê, porque o número parece certo. Aqui nem precisa: toda conta do fechamento tem regra, confirmada com a Helena, e um algoritmo acerta sempre, igual em toda execução, com a origem de cada centavo. Até testamos IA para achar anotações na planilha, e ela perdeu para palavras-chave. Onde a IA faz sentido é depois da conta: recuperar o dinheiro. Cada pendência vira um e-mail para a Orbe, a Ponte ou o lojista, e escrever isso é lento. A IA redige uma mensagem por destinatário, sem ver nome, CNPJ nem valor: ela recebe marcadores, e a máquina preenche os valores reais. Se ela escrever um número, o texto é reprovado. E se a redação sair estranha, a Helena corrige antes de enviar. Erro de redação é barato. Erro de dígito vira prejuízo."
- *Demo, se sobrar tempo:* rolar até "Rascunhos de envio a terceiros" na aba Pendências (só aparece com `OPENAI_API_KEY` no ambiente).

**10. Onde falha (45 s).** "Quando não sabe, o fechamento para e avisa quem decide. Se falta um arquivo, fecha o resto. Se a Orbe muda o layout, diz qual coluna sumiu. Se o lojista não tem contrato, não fatura e guarda as transações. Se o nome não casa, vira pendência: a gente só casa por código ou CNPJ, nunca por nome parecido. O que ainda é manual: a provisão de folha e impostos, porque os valores não vêm nos arquivos."

**11. Por que confiar (35 s).** "Conferimos de quatro jeitos: 14 de 14 casos de uma referência feita à mão; uma segunda implementação, feita separada, que chega no mesmo valor por lojista; o fechamento se recusa a gravar se algum número não bate com o rastro no centavo; e 210 testes automáticos."

**12. Com mais um mês (30 s).** "Provisão de folha e impostos, login de verdade para quem aprova, os rascunhos revisados saindo direto para a Orbe e a Ponte, e o principal: rodar outubro lado a lado com a Helena e medir quantos dias o fechamento passa a levar."

**13. Fecho (10 s).** "Setembro: 21 notas, 16 pendências com dono e nenhum centavo sem origem. E nenhuma regra que só a Helena saiba. Obrigado."

---

## Perguntas prováveis

| Pergunta | Resposta curta |
|---|---|
| A IA vê dados dos lojistas? | Não. Recebe marcadores ({VALOR_1}, {LOJISTA_1}); nomes, CNPJs e valores são preenchidos na máquina, e um validador reprova número escrito pelo modelo (P36) |
| Por que não usar IA no cálculo? | Pode alucinar ou trocar um dígito, e no financeiro isso é prejuízo que ninguém vê. Aqui toda conta tem regra, então um algoritmo determinístico acerta sempre e é auditável. Medimos, e a regra simples ganhou |\n| Então por que usar IA nos e-mails? | É texto e é lento, e é o que recupera o dinheiro. Um erro de redação é barato: a Helena revisa antes de enviar. E a IA não escreve número nenhum |
| E se a Orbe mudar o layout? | O arquivo não é usado, a pendência diz qual coluna sumiu e as frentes que não dependem dele fecham |
| Quanto tempo economiza? | Não prometemos número sem rodar um mês real com a Helena. É o primeiro item do próximo mês |
| E se a Helena sair? | É o ponto do projeto: as regras estão em `HIPOTESES.md` com a resposta que as sustenta, e as decisões novas ficam registradas com quem decidiu |
| Como o painel sabe quem aprovou? | Hoje é identificação (quem decide diz quem é), não login com senha. Login entra com mais um mês |
| E a Atlas? | Não fatura sem contrato (R3). As 57 transações ficam guardadas e entram no mês em que o Diego confirmar a taxa |
| Por que R$ 15.396,77, e não R$ 15.397,42? | É o que a Orbe descontou de fato (R33/R36). A diferença é o truncamento de centavos da Orbe, que a Helena pediu para não tratar como divergência |
| Nota da Ponte de R$ 39.543,45 ou o líquido da Ponte? | A nossa regra: spread negativo fora e duplicata uma vez (R39). A diferença vai para a contestação |
| Detalhe de uma etapa (taxa, Ponte, banco) | Ver a explicação longa das 5 etapas abaixo |

## As 5 etapas em detalhe (para perguntas)

- **Qual taxa vale:** 1.943 linhas da Orbe (1.840 vendas, 59 estornos, 38 antecipações e 6 reversões) em 22 lojistas. A taxa depende do lojista, da modalidade, das parcelas e da data da venda. 9 estornos são de vendas de agosto e usam a taxa da venda original. A Fluente tem 0,79% no Pix, que é condição negociada (R37), não erro.
- **Conferir a cobrança:** a Orbe trunca o centavo em 1.001 linhas, o que não é divergência (R8). A Rota Global tem +0,50 p.p. em três faixas de crédito desde 12/09. A Ponte manda 232 operações num anexo, com uma duplicada (PC-0926-0162), 4 spreads negativos (−R$ 1.834,05) e a Mundo Aberto acima do contrato (23 operações, R$ 1.418,85). A Tarvo fica com 50% do spread, o IOF é do cliente e sai uma nota única.
- **Explicar o banco:** 184 lançamentos (84 do Aurora em CSV e 100 do Meridiano em OFX) em 22 das 32 contas que aceitam lançamento. Um PIX a lojista é repasse; um PIX à contabilidade é despesa; um PIX de lojista é recurso para remessa; o CDB não afeta o resultado; o rendimento é receita.

## Antes de apresentar
- Painel aberto em `python -m tarvo.web --dados data/raw/set2026`, na aba Pendências, com a Rota Global à vista.
- `saida/rastro.csv` aberto como plano B.
- Cronometrar um ensaio. Se passar de 10 min, cortar primeiro a demo (fica só o slide 6), depois encurtar o slide 3 para dois exemplos. **Não cortar o slide 12:** "o que fariam com mais um mês" é item obrigatório da organização.
