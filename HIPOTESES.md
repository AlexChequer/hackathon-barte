# Hipóteses, premissas e perguntas

Separamos três coisas: o que **sabemos** (está no dado ou foi respondido pelo financeiro), o que **assumimos** (premissa escrita, que pode mudar) e o que **perguntamos**.

## Fatos (observados nos arquivos)

Ver `docs/MAPA_DADOS.md`. Destaques:
- F1. O relatório da Ponte tem a operação `PC-0926-0162` duplicada (obs "reprocessada"). O total declarado (R$ 78.073,59) conta as duas.
- F2. A Ponte tem 4 operações com spread negativo, todas com obs "Taxa travada no pedido (D-1)".
- F3. A planilha de taxas tem CNPJ que perdeu o zero à esquerda e taxas em dois formatos. Os ECs `1043300981`, `1043396662`, `1076801732` e `1038867654` não aparecem na planilha vigente.
- F4. Nomes de estabelecimento variam para o mesmo EC na Orbe. O casamento é feito por EC/CNPJ, nunca por nome.

## Premissas assumidas

| # | Premissa | Por quê | Status |
|---|---|---|---|
| P1 | `ref_origem` do Aurora = número da linha física do arquivo, contando a partir de 1 (a primeira transação é a `L9`) | O case pede "número da linha física (L10, L11…)". Lemos o "L10" como exemplo, já que a contagem a partir de 1 dá L9 | a confirmar no #hackathon-duvidas |
| P2 | Os dados de `data/raw/` nunca são editados; toda limpeza acontece no código | Regra do case | fixa |

## Perguntas feitas ao financeiro

| Hora | Canal | Pergunta | Resposta | Impacto no código |
|---|---|---|---|---|
| | | | | |

Rascunhos em `docs/PERGUNTAS_FINANCEIRO.md`.
