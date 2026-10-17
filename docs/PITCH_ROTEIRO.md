# Roteiro do pitch (10 min + 5 de perguntas)

Deck: https://claude.ai/artifact/FWpN8fx9K2fdwmPceE1sEM (as notas de cada slide têm o mesmo texto).
Público: Helena, o financeiro e o CFO da Tarvo. **Falar como quem vai fechar outubro, não como quem escreveu o código.** Sem "loader", "engine" ou "endpoint".

Divisão sugerida: **Alex** abre e mostra o dinheiro, **Helio** mostra o rastro e o uso em outubro (com demo), **André** fecha com IA, limites e próximo passo.

| Slides | Quem | Tempo | Acumulado |
|---|---|---|---|
| 1–4 | Alex | 3 min | 3:00 |
| 5–7 | Helio | 3 min 30 | 6:30 |
| 8–12 | André | 3 min 30 | 10:00 |

---

## Alex

**1. Capa (20 s).** "A Tarvo leva 8 dias para fechar o mês. A gente fechou setembro com um comando, e cada número que vamos mostrar tem o caminho até a linha do arquivo de onde ele veio. Somos a Fox AI: Alex, Helio e André."

**2. O problema (50 s).** "O fechamento não demora por ser manual. Demora porque a informação certa está em lugares que ninguém cruza. A isenção da Casa do Estudante só existia num comentário de célula. A Orbe cobra meio ponto a mais da Rota Global desde 12/09, e ninguém confere transação por transação. A Ponte manda o relatório por e-mail com operação duplicada. E a Orbe identifica o lojista pelo nome, então a Atlas vendeu R$ 262 mil sem contrato. Cada um desses casos custa dinheiro."

**3. A solução (40 s).** "Os arquivos do mês entram como chegam: o CSV da Orbe, a planilha com comentários, o e-mail da Ponte e os extratos. Saem seis arquivos: o que faturar, as notas a emitir, as divergências separadas entre cobrar da Orbe, devolver ao lojista e contestar com a Ponte, os lançamentos com a contrapartida, as pendências com dono e o rastro de cada centavo. Uma regra que não abrimos mão: lojista sem contrato não fatura. A gente não inventa taxa para fechar a conta."

**4. Dinheiro em jogo (70 s).** "Em setembro, são 21 notas que somam R$ 243 mil. O que o fechamento manual deixaria passar: R$ 15.396,77 a devolver à Casa do Estudante, R$ 7.876,05 de comissão da Atlas que não pode ir para nota sem contrato e R$ 1.576,23 a cobrar da Orbe. Com a Ponte, R$ 1.418,85 de spread acima do contrato e R$ 821,88 de operação duplicada no relatório. E um alerta: a Atlas, sem histórico, antecipou R$ 236 mil no mês, mais do que vendeu. O Helio vai mostrar de onde vem um desses números."

## Helio

**5. Um número até a origem (90 s, demo se der).** "R$ 1.546,28 a cobrar da Orbe pela Rota Global. Clico no valor [painel, aba Pendências] e abrem as 87 transações que somam até ele, no centavo. Uma delas é a TX88423890, linha 727 do relatório da Orbe: crédito em 8 vezes, R$ 6.449,10, cobrado a 4,09% quando o contrato é 3,59%. Meio ponto de R$ 6.449,10 dá R$ 32,25. E o motor achou o padrão: todo crédito, +0,50 p.p., desde 12/09, com débito e Pix certos. A Orbe recebe a lista pronta para contestar."
- *Plano B sem painel:* abrir `saida/rastro.csv` filtrando `CK-CONTEST-2026-09-95927868000148`.

**6. Condição escondida (50 s).** "O caso mais caro estava num comentário de célula: 'conversar com Diego sobre condição especial'. A Helena confirmou 0% de setembro a dezembro. A Orbe não sabia e cobrou 2,69% em 118 vendas, então são R$ 15.396,77 a devolver, sem cobrar da Orbe. Agora, todo mês, o fechamento relê os comentários da planilha. Anotação nova vira pendência para o Comercial, e nenhuma taxa muda sozinha."

**7. Outubro (70 s).** "Em outubro, a Helena sobe os arquivos com o nome que vierem. Se a Ponte atrasar o e-mail, o checkout e os extratos fecham, e só a remessa espera. Ela trabalha a fila por quem decide: ela, ela com o Comercial, ou o Comercial. Cada decisão tem dono: o Comercial aprova taxa, ela aprova regra. A decisão aprovada vale no mês seguinte para o mesmo caso. Quando o contrato da Atlas entrar, as transações de setembro, que ficaram guardadas, são faturadas sozinhas. Testamos com um outubro sintético, com lojista novo, anotação nova e ajuste da Ponte, sem mudar uma linha de código."

## André

**8. Onde está a IA (60 s).** "A IA construiu o motor com a gente, mas não decide o fechamento. Cada valor sai de uma regra escrita e confirmada com o financeiro: são 34 respostas registradas. Mesma entrada, mesma saída, auditável no centavo. Testamos um classificador de IA para achar anotações como a da Casa: palavras-chave acertaram 14 de 15, com a IA 13 de 15. Então desligamos. E a IA errou na construção: ignorou os comentários da planilha e propôs uma fórmula de divergência que a Helena contrariou. Pegamos os dois porque conferimos com o dado e perguntamos antes."

**9. Onde falha (50 s).** "Quando não sabe, o fechamento para e avisa quem decide. Se falta um arquivo, fecha o resto. Se a Orbe muda o layout, diz qual coluna sumiu. Se o lojista não tem contrato, não fatura e guarda as transações. Se o nome não casa, vira pendência, porque a gente só casa por EC ou CNPJ, nunca por nome parecido. O que ainda é manual: a provisão de folha e impostos, porque os valores não vêm nos arquivos."

**10. Por que confiar (40 s).** "Conferimos de quatro jeitos: 14 de 14 casos de uma referência feita à mão; uma segunda implementação, feita separada, que chega no mesmo valor por lojista; o fechamento se recusa a gravar se algum número não bate com o rastro no centavo; e 186 testes automáticos."

**11. Com mais um mês (30 s).** "Provisão de folha e impostos, contestação pronta no formato que a Orbe e a Ponte aceitam, e o principal: rodar outubro lado a lado com a Helena e medir quantos dias o fechamento passa a levar."

**12. Fecho (10 s).** "Setembro: 21 notas, 16 pendências com dono e nenhum centavo sem origem. Obrigado."

---

## Perguntas prováveis

| Pergunta | Resposta curta |
|---|---|
| Por que não usar IA no cálculo? | O CFO precisa defender cada nota. Um número que muda entre execuções não se defende. Medimos e a regra simples ganhou |
| E se a Orbe mudar o layout? | O arquivo não é usado, a pendência diz qual coluna sumiu e as frentes que não dependem dele fecham |
| Quanto tempo economiza? | Não prometemos número sem rodar um mês real com a Helena. É o primeiro item do próximo mês |
| Como o painel sabe quem aprovou? | Hoje é identificação (quem decide diz quem é), não login com senha. Login entra com mais um mês |
| E a Atlas? | Não fatura sem contrato (R3). As 57 transações ficam guardadas e entram no mês em que o Diego confirmar a taxa |
| Por que R$ 15.396,77, e não R$ 15.397,42? | É o que a Orbe descontou de fato (R33/R36). A diferença é o truncamento de centavos da Orbe, que a Helena pediu para não tratar como divergência |
| Nota da Ponte de R$ 39.543,45 ou o líquido da Ponte? | A nossa regra: spread negativo fora e duplicata uma vez (R39). A diferença vai para a contestação |

## Antes de apresentar
- Painel aberto em `python -m tarvo.web --dados data/raw/set2026`, na aba Pendências, com a Rota Global à vista.
- `saida/rastro.csv` aberto como plano B.
- Cronometrar um ensaio. Se passar de 10 min, cortar primeiro o slide 11, depois a demo (fica só o slide 5).
