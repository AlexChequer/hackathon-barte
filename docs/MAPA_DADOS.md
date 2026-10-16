# Mapa dos dados: set/2026

Tudo que está aqui foi **observado** nos arquivos (exploração inicial em 16/10, ~19h40).
O que é *interpretação* está marcado como **hipótese** e precisa ir para `HIPOTESES.md` ou virar pergunta.

| # | Arquivo | Formato | Linhas | Loader | Rastro (`ref_origem`) |
|---|---|---|---|---|---|
| 01 | Orbe comissões | CSV `;`, decimal `,`, UTF-8, CRLF | 1943 | `loaders/orbe.py` | `id_transacao` |
| 02 | Taxas contratadas | xlsx, aba `Taxas vigentes` (cabeçalho na linha 5) | 25 lojistas | `loaders/taxas.py` | linha da planilha |
| 03 | Ponte Câmbio | `.eml` com xlsx em anexo, aba `Operações` (cabeçalho na linha 5) | 233 | `loaders/ponte.py` | `Nº Operação` |
| 04 | Plano de contas Fênix | CSV `;`, **latin-1** | 52 contas | `loaders/plano.py` | `COD_CONTA` |
| 05a | Extrato Aurora | CSV com cabeçalho de banco e rodapé, UTF-8 | 84 lançamentos | `loaders/aurora.py` | linha física `L9`…, contando a partir de 1 |
| 05b | Extrato Meridiano | OFX 1.02 SGML, **cp1252** | 100 | `loaders/meridiano.py` | `FITID` |

## 01 Orbe

- `tipo_lancamento`: VENDA 1840, ESTORNO 59, ANTECIPACAO 38, REVERSAO ANTECIPACAO 6.
- `modalidade`: CREDITO PARCELADO 951, CREDITO A VISTA 591, PIX 183, DEBITO 174.
- ESTORNO tem `id_referencia` + `data_venda_original`, e **várias vendas originais são de agosto**.
- ANTECIPACAO (`AN…`) não tem modalidade nem bandeira. Taxa aplicada 2,10%.
- **Mesmo EC com nomes diferentes**: `Mundo Aberto` / `MUNDO ABERTO INTERCAMBIO`, `EDU ABROAD CONSULTORIA` / `EDUABROAD`, `BEM-VINDO` / `BEM VINDO`… → casar por **EC**, nunca por nome.
- ECs na Orbe que **não estão** na planilha de taxas: `1043300981 HORIZONTE INTERCAMBIO`, `1043396662 HORIZONTE VIAGENS TURISMO`, `1076801732 ATLAS IDIOMAS`, `1038867654 KIWI EXPERIENCE`.
- Esses 4 ECs somam **290 transações** sem taxa contratada (Kiwi 85, Horizonte Intercâmbio 73, Horizonte Viagens Turismo 75, Atlas 57).
- Comparação exploratória entre a taxa aplicada e a contratada por EC + modalidade, **sem considerar a vigência**:
  - **Rota Global (1074504011)**: +0,50 p.p. em **todo crédito** (vista 2,49→2,99, 2–6x 2,99→3,49, 7–12x 3,59→4,09), em 87 transações. Débito e Pix batem. Forte candidata a divergência real.
  - **Bridge (1075624862)**: 9 transações a 2,19% contra 2,59%. Provavelmente é só a vigência nova a partir de 15/09, a confirmar no motor.
  - Todos os outros ECs da planilha batem 100%.
  - _Correção:_ a primeira leitura (feita pela IA) dizia que a Orbe usava a tabela antiga de 2025. Isso estava errado. Ver `PROMPTS/MOMENTOS.md`.

## 02 Planilha de taxas (mantida à mão)

- Taxas ora decimais (`0.0259`), ora texto (`'2,59%'`, Oxford e Sol Nascente). O loader normaliza.
- CNPJ ora formatado, ora só dígitos, ora **número** (perde o zero à esquerda: Fluente `3229837000103`, Campus Global `8780784000120`). O loader recupera com `zfill(14)`.
- **Bridge tem 2 linhas**: crédito à vista 2,59% até 14/09 e 2,19% a partir de 15/09.
- **EC vazio**: Horizonte Viagens, Kiwi (`EC pendente`), Novo Horizonte, Ponte Aérea e Nórdica (as duas últimas são "só remessa").
- **Nomes parecidos e perigosos**: `Horizonte Viagens` × `Novo Horizonte Intercambio` × Orbe `HORIZONTE INTERCAMBIO` / `HORIZONTE VIAGENS TURISMO`.
- `Spread remessa`: vazio = "padrão" (rodapé), Canguru = texto `'padrão'`. **O valor do padrão não está escrito.** As operações da Ponte sugerem 1,5%, mas isso é **hipótese**.
- Globo Trotter: `INATIVO desde jul/26`, sem vigência.
- Atlas Idiomas está **só** na aba antiga, mas transaciona na Orbe.
- `Casa do Estudante`: obs "cliente estratégico - ver c/ comercial".
- Mundo Aberto: "spread negociado em jul/26" = 1,2%, **mas a Ponte cobrou ~1,5%** em todas as operações → possível divergência de remessa.

## 03 Ponte Câmbio

- O e-mail diz: **repasse de 50% do spread realizado**, crédito em 06/10, **mediante nota fiscal de intermediação** → a nota da REMESSA provavelmente é para a **Ponte** (CNPJ 75.374.179/0001-46), não para o lojista. **Hipótese; confirmar.**
- O e-mail também diz que "APROVADO C/ RESSALVA" segue para liquidação (16 operações).
- Rodapé: 233 operações, spread total R$ 78.073,59, e **a soma das linhas bate**. Só que:
  - `PC-0926-0162` (Bagagem Livre) aparece **2 vezes**, idêntica, com obs `reprocessada`. O total da Ponte conta as duas.
  - **4 spreads negativos** com obs `Taxa travada no pedido (D-1)`: PC-0926-0210, 0326, 0491, 0545.
- Coluna `Spread Estimado R$ (D-1)` diferente do realizado.
- Algumas operações liquidam em **outubro** (ex.: PC-0926-0002, contratada em 30/09, liquida em 01/10).
- `Ponte Aérea Estudantil` é lojista (só remessa). Não confundir com a Ponte Câmbio.

## 05 Extratos

- **Aurora** (conta principal): 21 TEDs da Orbe, 4 transferências para o Meridiano, 2 PIX enviados por lojista (repasses?), folha, impostos (DARF PIS/COFINS/IRRF, ISS, INSS, FGTS), tarifas, AWS, Google, condomínio, contabilidade, `PIX RECEBIDO … SEM IDENTIFICACAO`, `DEVOLUCAO PIX - MUNDO ABERTO`. **Saldo final negativo: −1.920.088,60.**
- **Meridiano** (conta de câmbio): PIX recebidos de lojistas (recurso para remessa), 21 TEDs enviadas à Ponte, PIX/TED recebidos da Ponte, aplicação/resgate CDB, rendimento, IOF, tarifas, seguro, TEDs recebidas da própria Tarvo.
