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
- ECs na Orbe que **não estão** na planilha de taxas (linhas sem EC): `1043300981 HORIZONTE INTERCAMBIO`, `1043396662 HORIZONTE VIAGENS TURISMO`, `1076801732 ATLAS IDIOMAS`, `1038867654 KIWI EXPERIENCE`.
  - **Resolvido (R3):** `1043300981` → Novo Horizonte Intercâmbio (66564512000199); `1043396662` → Horizonte Viagens (78576234000179); `1038867654` → Kiwi Experience (07752116000126). `1076801732` Atlas **não fatura** até o Comercial confirmar: vira pendência por transação. No código: `src/tarvo/rules.py` (`EC_PARA_CNPJ`, `EC_SEM_CONTRATO`).
- Três resolvidos por R3 via de-para explícito: Novo Horizonte, Horizonte Viagens e Kiwi têm CNPJ e taxas nas respectivas linhas da aba vigente. **Atlas segue sem contrato vigente** (P10): o motor não fatura, não emite nota, não inventa taxa.
- Esses 4 ECs somam **290 transações** (Kiwi 85, Horizonte Intercâmbio 73, Horizonte Viagens Turismo 75, Atlas 57).
- Comparação exploratória entre a taxa aplicada e a contratada por EC + modalidade, **sem considerar a vigência**:
  - **Rota Global (1074504011)**: +0,50 p.p. em **todo crédito** (vista 2,49→2,99, 2–6x 2,99→3,49, 7–12x 3,59→4,09), em 87 transações. Débito e Pix batem. **Começa em 12/09**: até 11/09 o crédito bate com a planilha. A planilha foi atualizada pela última vez em 02/09. Hipóteses: renegociação que não entrou na planilha **ou** erro de cadastro na Orbe.
  - **Bridge (1075624862)**: com a vigência pela data da venda (R2/P3), as vendas a 2,19% de 23/09 em diante estão corretas. **Mas de 15/09 a 18/09 a Orbe ainda cobrou 2,59%** (5 vendas): divergência real, porque a Orbe demorou a atualizar.
  - Todos os outros ECs da planilha batem 100%.
  - _Correção:_ a primeira leitura (feita pela IA) dizia que a Orbe usava a tabela antiga de 2025. Isso estava errado. Ver `PROMPTS/MOMENTOS.md`.

## 02 Planilha de taxas (mantida à mão)

- Taxas ora decimais (`0.0259`), ora texto (`'2,59%'`, Oxford e Sol Nascente). O loader normaliza.
- CNPJ ora formatado, ora só dígitos, ora **número** (perde o zero à esquerda: Fluente `3229837000103`, Campus Global `8780784000120`). O loader recupera com `zfill(14)`.
- **Bridge tem 2 linhas**: crédito à vista 2,59% até 14/09 e 2,19% a partir de 15/09.
- **EC vazio**: Horizonte Viagens, Kiwi (`EC pendente`), Novo Horizonte, Ponte Aérea e Nórdica (as duas últimas são "só remessa").
- **Nomes parecidos e perigosos**: `Horizonte Viagens` × `Novo Horizonte Intercambio` × Orbe `HORIZONTE INTERCAMBIO` / `HORIZONTE VIAGENS TURISMO`.
- `Spread remessa`: vazio = "padrão" (rodapé), Canguru = texto `'padrão'`. Resolvido em R5: padrão = 1,5% sobre PTAX. Texto inválido fora de `padrão`/vazio continua pendência técnica, não default silencioso.
- Globo Trotter: `INATIVO desde jul/26`, sem vigência.
- Atlas Idiomas está **só** na aba antiga, mas transaciona na Orbe.
- `Casa do Estudante`: obs "cliente estratégico - ver c/ comercial".
- Mundo Aberto: "spread negociado em jul/26" = 1,2%, **mas a Ponte cobrou ~1,5%** em todas as operações → possível divergência de remessa.

## 03 Ponte Câmbio

- O e-mail diz: **repasse de 50% do spread realizado**, crédito em 06/10, **mediante nota fiscal de intermediação**. Confirmado em R4: a nota é única, para a Ponte (CNPJ 75.374.179/0001-46), com a soma das participações por operação. Diferença contra o total declarado da Ponte não é somada à nota — vira pendência (P14).
- O e-mail também diz que "APROVADO C/ RESSALVA" segue para liquidação (16 operações).
- Rodapé: 233 operações, spread total R$ 78.073,59, e **a soma das linhas bate**. Só que:
  - `PC-0926-0162` (Bagagem Livre) aparece **2 vezes**, idêntica, com obs `reprocessada`. O total da Ponte conta as duas.
  - **4 spreads negativos** com obs `Taxa travada no pedido (D-1)`: PC-0926-0210, 0326, 0491, 0545.
- Coluna `Spread Estimado R$ (D-1)` diferente do realizado.
- Algumas operações liquidam em **outubro** (ex.: PC-0926-0002, contratada em 30/09, liquida em 01/10).
- `Ponte Aérea Estudantil` é lojista (só remessa). Não confundir com a Ponte Câmbio.

## 05 Extratos

- **Aurora** (conta principal): 21 TEDs da Orbe, 4 transferências para o Meridiano, 2 PIX enviados por lojista (repasses?), folha, impostos (DARF PIS/COFINS/IRRF, ISS, INSS, FGTS), tarifas, AWS, Google, condomínio, contabilidade, `PIX RECEBIDO … SEM IDENTIFICACAO`, `DEVOLUCAO PIX - MUNDO ABERTO`. **Saldo final negativo: −1.920.088,60.**
- Aurora `L65`: `DEVOLUCAO PIX - MUNDO ABERTO INTERC` é um **crédito** de +12.400,00 (entrada, não saída). Mundo Aberto recebeu PIX de −48.714,59 (L26) e −88.746,05 (L76).
- Aurora `L50`: `PIX RECEBIDO 38686002000180 SEM IDENTIFICACAO` de +7.350,00.
- **Meridiano: armadilha de nome.** `PIX RECEB PONTE AÉREA ESTUDANTIL` é o **lojista** Ponte Aérea, não a Ponte Câmbio. Regra por palavra-chave "PONTE" erra.
- Meridiano `MRD2026090132`: `TED RECEB PONTE CAMBIO SA REPASSE COMISSAO 08/2026` de +61.884,12 é a comissão de **agosto** recebida em setembro (baixa de 1.1.03.002, não receita de setembro?).
- **Meridiano** (conta de câmbio): PIX recebidos de lojistas (recurso para remessa), 21 TEDs enviadas à Ponte, PIX/TED recebidos da Ponte, aplicação/resgate CDB, rendimento, IOF, tarifas, seguro, TEDs recebidas da própria Tarvo.

## Sinais de condição especial (varredura de 17/10)

A isenção da Casa do Estudante **não está em nenhuma tabela**. Só apareceu por dois sinais de texto na planilha (obs "cliente estratégico - ver c/ comercial" e o comentário de célula A13 "conversar com Diego (comercial) sobre condição especial") e foi confirmada pela Helena na R6. O loader original nem lia o comentário (MOMENTOS, momento 3).

Varredura de todos os textos livres do data pack de setembro:

| Onde | Sinal | Situação |
|---|---|---|
| Taxas, cabeçalho | "atualizar sempre que o comercial fechar!!" · "última atualização: 02/09 - Bia" | Contexto: a planilha depende de alguém lembrar |
| Taxas L13 (Casa) | obs "cliente estratégico - ver c/ comercial" + comentário A13 "condição especial" | **Condição fora da planilha** (R6: 0% set–dez). Resolvida |
| Taxas L6/L7 (Bridge) | "renegociado - ver linha de baixo" / "a partir de 15/09" / "só mudou o crédito à vista" | Registrada na planilha. Orbe cobrou a antiga até 18/09 (aguarda resposta: Orbe foi avisada?) |
| Taxas L15 (Mundo Aberto) | "spread negociado em jul/26" (1,2%) | Registrada na planilha. Ponte não aplicou (R5) |
| Taxas L9 (Kiwi) | "EC pendente" | Cadastro incompleto. Resolvida (R3) |
| Taxas L16/L23 (Ponte Aérea, Nórdica) | "só remessa", taxas de checkout vazias | Coerente: 0 transações na Orbe |
| Taxas L30 (Globo Trotter) | "INATIVO desde jul/26", sem vigência | Coerente: 0 transações na Orbe e na Ponte |
| Aba "ANTIGO 2025 - nao usar" | Tabela 2025 de 12 lojistas, **incluindo Atlas (CNPJ 39566044000119)**, que não está na aba vigente | Não usada (R3: Atlas não fatura até o Comercial confirmar). Fato útil para o Comercial |
| E-mail da Ponte | Repasse de 50% em 06/10 "mediante nota fiscal"; ressalva segue normal; divergência em até 5 dias úteis | Coberto (R4, R5, R12) |
| Ponte, coluna Obs. | "Taxa travada no pedido (D-1)" ×4; "reprocessada" ×1 | Negativos e duplicata. Cobertos (R5, R12) |
| Linhas/colunas ocultas, outras abas | Nenhuma além da aba 2025 | — |

**Conclusão:** em setembro, a Casa é o único caso de condição comercial fora da planilha. Mas o padrão ("ver c/ comercial", "condição especial", "negociado", "renegociado") é texto livre e pode voltar em outubro com outro lojista.

## Arquivo 06: ajustes tardios da Orbe (chegou 17/10 13h10)

`06_orbe_ajustes_tardios_set2026.csv`: mesmo formato do 01, 14 linhas de 30/09 que ficaram fora do relatório: 10 estornos de vendas de setembro, 3 reversões de antecipação (Oxford ×2, Maple) e 1 venda (Kiwi). Conferido: ids novos (nenhum repetido com o 01), todas as 13 referências existem no 01, nenhuma antecipação já revertida, ECs conhecidos (incluindo Bridge 1075624862). Nenhuma divergência de taxa nova.

O loader trata `*_orbe_ajustes_*.csv` como opcional (zero ou mais arquivos), junta com o 01 e marca `arquivo_origem = orbe_ajustes` no rastro. Efeito no checkout: R$ 207.039,73 → **R$ 203.735,34** (−3.304,39; Oxford −2.232,19, Maple −845,01, Edu Abroad −212,01, Bridge −146,28, Dublin −29,71, Mundo Aberto −14,00, Kiwi +174,81).
