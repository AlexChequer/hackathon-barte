# Momentos que importaram

Três momentos. Em dois a IA errou, e o erro só apareceu porque conferimos com o dado ou com o financeiro. O terceiro decidiu onde a IA **não** entra no fechamento.

## 1. O loader da IA não via os comentários da planilha, e era ali que estavam R$ 15,4 mil
- **Pedido:** ler a planilha de taxas "como ela vem".
- **IA:** usou o openpyxl em `read_only`, que lê só o valor das células. O comentário da Bia na Casa do Estudante ("conversar com Diego (comercial) sobre condição especial") ficou de fora, e com ele a isenção de 0% que gera R$ 15.396,77 de devolução.
- **O que fizemos:** a pista veio da pergunta pública de outro time (R6). Varremos todos os xlsx atrás de comentários e de linhas e colunas ocultas, mudamos o loader para ler comentários (com teste) e criamos o detector de sinais, que relê obs e comentários todo mês e abre pendência para o Comercial.

## 2. A IA propôs a fórmula de divergência "mais elegante", e a Helena queria outra
- **Pedido:** revisar a pergunta do Helio sobre o truncamento de centavos da Orbe.
- **IA:** confirmou o truncamento nas 1.943 linhas e sugeriu divergência = `valor_taxa` − comissão, porque assim "Σ comissão + Σ divergência = Σ cobrado, sem sobra de centavo".
- **O que fizemos:** não implementamos antes de perguntar. A Helena respondeu o oposto (R8): divergência = bruto × (aplicada − contratada), e centavo de truncamento **não** é divergência. Pela fórmula da IA, 1.001 linhas com a taxa certa apareceriam como divergência.

## 3. Medimos o classificador de IA antes de ligar, e ele perdeu para palavras-chave
- **Pedido:** usar o Laya (classificador open source, local, só sim/não) para achar anotações de condição comercial na planilha, com uma instrução longa e cheia de guardrails.
- **IA:** antes de integrar, rodou num conjunto rotulado de 15 anotações (`tests/fixtures/sinais_rotulados.json`). A instrução longa dizia "sim" para quase tudo (8/15). Um comitê de 3 instruções curtas chegou a 10/15, mas a união com palavras-chave (13/15) ficou pior que as palavras-chave sozinhas (14/15).
- **O que fizemos:** desligamos o Laya por padrão (opção experimental, medida por `scripts/avaliar_sinais.py`). O fechamento roda só com regra escrita e auditável. A IA ficou na construção, não no cálculo.

## Outros candidatos (não escolhidos)
- **"L10" como regra:** a IA escreveu um teste esperando que a primeira linha do Aurora fosse `L10`, pelo exemplo do case. Mantivemos a contagem física (`L9`), e a organização confirmou (O7).
- **"A Orbe usa a tabela antiga":** a IA concluiu isso pela contagem de taxas distintas. Comparando taxa aplicada × contratada, a divergência real era concentrada: Rota Global +0,5 p.p., Bridge pela vigência e 4 ECs fora da planilha.
