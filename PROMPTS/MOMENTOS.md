# Momentos que importaram

De 2 a 4 momentos. Para cada um, em uma ou duas frases: o que pedimos, o que a IA devolveu e o que fizemos com isso. **Pelo menos um em que a IA errou.**

## 1. Setup: a IA assumiu o exemplo "L10" como regra (candidato)
- **Pedido:** montar os loaders e testes do data pack.
- **IA:** escreveu um teste esperando que a primeira linha do Aurora fosse `L10`, porque o texto do case dá "L10, L11…" como exemplo. O teste falhou: na contagem física a partir de 1, a primeira transação está na `L9`.
- **O que fizemos:** conferimos o arquivo com `cat -n`, mantivemos a contagem física e registramos a premissa P1 para confirmar com a organização.

## 2. Setup: hipótese "a Orbe usa a tabela antiga" era falsa (candidato)
- **Pedido:** mapear as armadilhas dos dados.
- **IA:** olhou só a contagem de taxas distintas e concluiu que a Orbe aplicava a tabela de 2025 para alguns lojistas.
- **O que fizemos:** comparamos taxa aplicada × contratada por EC e modalidade. A divergência real é concentrada: Rota Global com +0,5 p.p. em todo crédito, Bridge por causa da vigência, e 4 ECs fora da planilha. Corrigimos o `MAPA_DADOS.md`.

## 3. Setup: o loader da IA ignorava os comentários da planilha (candidato)
- **Pedido:** ler a planilha de taxas "como ela vem".
- **IA:** usou o openpyxl em `read_only`, que lê só os valores das células. Por isso o comentário da Bia na Casa do Estudante ("conversar com Diego (comercial) sobre condição especial") ficou de fora. Essa era a pista de uma tarifa zerada que vale R$ 15,4 mil em divergências.
- **O que fizemos:** soubemos pela pergunta pública de outro time (R6), checamos se havia comentários e linhas ou colunas ocultas em todos os xlsx e mudamos o loader para ler comentários, com teste.

## 4. Pré-construção: a IA propôs a fórmula de divergência "mais elegante", e o cliente queria outra (candidato)
- **Pedido:** revisar a pergunta do Helio sobre o truncamento da Orbe.
- **IA:** confirmou o truncamento nas 1.943 linhas (bom) e sugeriu propor divergência = `valor_taxa` − comissão, porque assim "Σ comissão + Σ divergência = Σ cobrado, sem sobra de centavo".
- **O que fizemos:** mantivemos a pergunta aberta. A Helena respondeu o oposto (R8): arredondamento comum, divergência = bruto × (aplicada − contratada), e centavo de truncamento **não** é divergência. Pela fórmula da IA, as 1.001 linhas em que o truncamento muda o centavo gerariam diferença mesmo com a taxa certa, e os valores das divergências reais sairiam diferentes do que a Helena quer.

## 5. Construção: "instrução mais longa = mais consistente" não valeu para o Laya (candidato)
- **Pedido:** usar o Laya (classificador open source, local, só sim/não) para achar anotações de condição comercial escondidas na planilha, com uma instrução grande e cheia de guardrails para ficar consistente.
- **IA:** escreveu a instrução longa, mas antes de integrar rodou num conjunto rotulado de 15 anotações (`tests/fixtures/sinais_rotulados.json`). A instrução longa respondeu "sim" para quase tudo (8/15); a curta acertava 9/15.
- **O que fizemos:** trocamos por um comitê de 3 instruções curtas com voto majoritário (10/15), em união com palavras-chave (14/15 sozinhas). Como a união (13/15) ficou pior que as palavras-chave sozinhas (14/15), **desligamos o Laya por padrão**: ficou como opção experimental, medida por `scripts/avaliar_sinais.py`.
