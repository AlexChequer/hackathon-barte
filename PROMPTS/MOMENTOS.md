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

## 3. _a preencher_

## 3. _a preencher_
