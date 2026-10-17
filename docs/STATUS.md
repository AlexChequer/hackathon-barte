# Status: 16/10, ~21h15

## Onde estamos

- ✅ Repo, loaders das 6 fontes (com testes e checksums dos dados brutos), formato de saída e CI.
- ✅ 9 respostas do financeiro registradas em `HIPOTESES.md` (R1–R9) e premissas P1–P8.
- ⏳ Motores (`src/tarvo/engines/`): **nenhum começado**. É o trabalho de amanhã.

## Regras já fechadas (resumo de `HIPOTESES.md`)

| Tema | Regra | Fonte |
|---|---|---|
| Comissão checkout | Σ bruto × taxa **contratada**, linha a linha (vendas + antecipações − estornos − reversões) | R1, R2, R4 |
| Vigência | Pela data da venda. Estorno usa a taxa da venda original e abate no mês do estorno | R2 |
| ECs | 1043300981 = Novo Horizonte; 1043396662 = Horizonte Viagens; 1038867654 = Kiwi. **Atlas não fatura** → pendência para o Comercial | R3 |
| Casa do Estudante | Checkout com **taxa 0%** de set a dez (MDR e antecipação). Tudo o que foi cobrado é divergência | R6 |
| Rota Global | +0,5 p.p. a partir de 12/09 é **divergência**. O contrato não mudou | R6 |
| Divergência checkout | Só quando a **taxa** aplicada ≠ contratada; valor = bruto × (aplicada − contratada). Centavo de truncamento não conta. Também vira pendência por transação (`quem_decide = Financeiro`) | R1, P8 |
| Notas checkout | 1 por lojista por mês, com valor > 0. Valor ≤ 0 → pendência | R4 |
| Comissão remessa | 50% × Spread R$ realizado. Duplicada conta 1×. Negativo fica fora (vira pendência). Ressalva entra normal. Competência = data de contratação | R5 |
| Divergência remessa | (spread % − contratado) × PTAX × ME, valor cheio. Vazio/"padrão" = 1,5%. Tolerância de 0,01 p.p. | R5, R7, P5, P7 |
| Nota remessa | **1 nota** para a Ponte Câmbio (75374179000146) com o total da participação | R4 |
| Arredondamento | Arredondamento comum (meio centavo para longe do zero) **por linha**, depois soma. A Orbe trunca, nós não | R8 |
| Extratos | `conta_codigo` = **contrapartida**. Já registrado (folha, tributos de 08, repasse Ponte 08) → baixa a conta onde estava. Tarifas, aluguel, cloud, assinaturas e serviços → despesa direta. Sem clareza → premissa escrita | R9 |
| Extratos (casos) | Folha e impostos de 08 = baixa de passivo provisionado. Repasse Ponte 08 = baixa de 1.1.03.002. PIX sem id, devolução da Mundo Aberto e transferência de 300 mil em trânsito → pendências | R6 |

## Frentes (proposta; trocar à vontade)

| Frente | Dono | Entrega | Mínimo/Alvo |
|---|---|---|---|
| A. Checkout | **Alex** | `engines/checkout.py` → comissões CHECKOUT, divergências CHECKOUT, notas checkout, pendências checkout, rastro | **Mínimo** |
| B. Remessa | **Helio** | `engines/remessa.py` → comissões REMESSA, divergências REMESSA, nota da Ponte, pendências remessa, rastro | Alvo |
| C. Extratos | **André** | `engines/extratos.py` → `lancamentos_classificados.csv` (regra primeiro, IA só no resto), pendências de extrato, rastro | Alvo |

Ponto de integração: cada motor devolve DataFrames com as colunas de `output.SCHEMAS`. O `__main__.py` concatena e escreve. **`id_saida` com prefixo por frente** (`CK-`, `RM-`, `EX-`) para não colidir.

## Perguntas ainda abertas (para o plantão de amanhã, 9h30–17h30, ou hoje até 22h30)

A Helena pediu que a gente **proponha o tratamento e pergunte se está certo**. Formato: `[financeiro] Fox AI: <tema>`, direto, sem "olá" nem "obrigado", com o id da linha como exemplo.

### Alex (checkout)
- ✅ Arredondamento respondido (R8). Nada aberto. Começar o motor.

### Helio (remessa)
1. **Total da nota da Ponte × relatório da Ponte**: a Ponte reporta R$ 78.073,59 de spread (50% = R$ 39.036,80), mas isso inclui a `PC-0926-0162` duplicada e os 4 negativos. Proposta: nota pelo nosso valor (sem a duplicada e sem os negativos) e uma pendência com a diferença para contestar com a Ponte. Confere?
2. Coluna `IOF R$` e `Spread Estimado R$ (D-1)`: proposta de ignorar as duas no cálculo (o IOF é custo do cliente, e o estimado só serve de referência). Confere?

### André (extratos)
1. O critério já foi respondido (R9, contrapartida). Ainda vale mandar a **tabela de classificação proposta** (descrição → conta) e pedir confirmação de uma vez. Rascunho: TED Orbe → 1.1.03.001; PIX enviado a lojista → 2.1.01.001; TAR/TARIFA → 4.2.01; AWS → 4.2.03; Google Workspace → 4.2.04; condomínio → 4.2.02; contabilidade → 4.2.06; seguro → 4.2.05; folha → 2.1.04.001; INSS → 2.1.04.002; FGTS → 2.1.04.003; ISS → 2.1.03.003; DARF PIS/COFINS/IRRF → 2.1.03.001/002/004; transferência entre contas → 1.1.09.001; PIX RECEB de lojista (Meridiano) → 2.1.02.001; TED ENVIADA PONTE LIQ OPERACOES → 2.1.02.001; CDB → 1.1.02.001; rendimento → 3.2.01; IOF → 4.3.01; repasse da Ponte 08/2026 → 1.1.03.002.
2. O saldo do Aurora termina em **−R$ 1,92 mi**. Antes de perguntar, **conferir se o saldo anterior mais a soma dos lançamentos bate com a coluna de saldo** linha a linha. Se não bater, é achado. Se bater, perguntar se a conta tem limite.
3. Cuidado: `PIX RECEB PONTE AÉREA ESTUDANTIL` é **lojista**, não a Ponte Câmbio.
