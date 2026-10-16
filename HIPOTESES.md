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

Canal: `#duvidas-hackathon-ai` (o `#tarvo-financeiro` não foi criado; a organização orientou usar o prefixo `[financeiro]`/`[tarvo]`). Respondente: manuel.freitas, no papel do financeiro.

| # | Hora (16/10) | Quem perguntou | Pergunta | Resposta | Impacto no código |
|---|---|---|---|---|---|
| R1 | ~20h01 → ~20h05 | **Fox AI** (nós) | A comissão de checkout usa o `valor_taxa` cobrado pela Orbe ou bruto × taxa contratada? O que vai na nota? A diferença é devolvida? | "A gente fatura pela taxa **contratada**: valor bruto × taxa da planilha, linha a linha. O `valor_taxa` do relatório é o que a Orbe cobrou e nem sempre bate com o contrato. Na nota fiscal vai a comissão calculada pela taxa contratada. Quando a taxa aplicada é diferente da contratada, é divergência. Se a Orbe cobrou a mais, a diferença volta para o lojista e eu cobro a Orbe. **Isso eu decido, não vai automático.** Preciso ver cada caso com transação e valor." | Comissão = Σ bruto × taxa contratada. Nota = comissão. Cada divergência → linha em `divergencias_taxa.csv` **e** pendência com `quem_decide = Financeiro` |
| R2 | ~20h04 → ~20h06 | MN AI (outro time, resposta pública) | Estorno devolve a taxa e abate a comissão? E se a venda for de agosto? Ex.: `TX88444848` | "Sim. Estorno devolve a taxa ao lojista e abate a comissão do mês. Venda de agosto estornada em setembro **entra em setembro**, que é o mês do estorno. Agosto já está fechado e não reabro. A taxa usada é a que valia **na data da venda original**." | Estorno entra com sinal negativo no mês do `data_movimento`, com a taxa contratada vigente em `data_venda_original` |
| R3 | ~20h16 → ~20h24 | **Fox AI** (nós) | 4 ECs da Orbe sem EC na planilha: qual CNPJ/taxa? Correspondem às linhas com EC em branco? Atlas ainda é ativa? | "Boa pegada, o EC dessas três está faltando na planilha: **1043300981 HORIZONTE INTERCAMBIO é a Novo Horizonte Intercâmbio** (linha 'Novo Horizonte Intercambio'). **1043396662 HORIZONTE VIAGENS TURISMO é a Horizonte Viagens e Turismo** (linha 'Horizonte Viagens'). São duas empresas diferentes. **1038867654 KIWI EXPERIENCE TURISMO é a Kiwi Experience** (linha 'Kiwi Experience'). O CNPJ e as taxas dessas três estão nas linhas delas na aba vigente. A **Atlas** na aba de 2025 eu não sabia. Essa planilha passa por várias mãos. O que eu sei é que ela começou a transacionar com a gente em 10/09 e que não tenho contrato assinado dela na vigente. Não sei qual taxa vale. **Não fatura a Atlas até o comercial confirmar.** — Helena, financeiro da Tarvo" | Mapa EC → linha da planilha para os 3 ECs (de-para explícito no código, com fonte R3). Atlas (57 transações, a partir de 10/09, conferido) fica **fora** de comissão e notas → pendência com `quem_decide = Comercial`. A aba 2025 **não** é usada |

### Premissas derivadas das respostas

| # | Premissa | Base |
|---|---|---|
| P3 | A vigência de taxa é decidida pela **data da venda** (`data_movimento` da VENDA; `data_venda_original` do ESTORNO). Isso resolve a Bridge (2,59% até 14/09, 2,19% a partir de 15/09) | Extensão de R2 |
| P4 | Divergência a **menor** (a Orbe cobrou menos que o contratado) também é reportada como divergência, com `diferenca_brl` negativa | R1 fala de "diferente"; o sinal ainda não foi confirmado |

Rascunhos em `docs/PERGUNTAS_FINANCEIRO.md`.
