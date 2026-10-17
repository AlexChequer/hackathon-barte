# Status

Última atualização: 17/10/2026, pós-MVP Fox AI.

## Onde estamos

- ✅ Loaders das 6 fontes (com testes e checksums dos dados brutos), schemas de saída, CI.
- ✅ 9 respostas do financeiro em `HIPOTESES.md` (R1–R9) e premissas P1–P15.
- ✅ **Motores implementados**: `engines/checkout.py`, `engines/remessa.py`, `engines/extratos.py`.
- ✅ Orquestrador + CLI que gera os **6 CSVs reais** em `saida/<competencia>/`.
- ✅ Validação de rastro **exata em centavos**, com origem obrigatória mesmo para saída zero, IDs únicos e refs existentes.
- ✅ Persistência SQLite de execuções e decisões em `saida/tarvo.sqlite` (idempotente; muda-dado → reavaliar).
- ✅ Interface Streamlit (`src/tarvo/ui/app.py`) fina sobre o orquestrador.
- ✅ Protocolo de avaliação em `docs/AVALIACAO.md` + referência manual em `tests/fixtures/referencia.yaml` + relatório em `saida/<competencia>/avaliacao.json`.

## Regras já fechadas (resumo de `HIPOTESES.md`)

| Tema | Regra | Fonte |
|---|---|---|
| Comissão checkout | Σ bruto × taxa **contratada**, linha a linha com ROUND_HALF_UP (vendas + antecipações − estornos − reversões) | R1, R2, R4, R8 |
| Vigência | Pela data da venda. Estorno usa a taxa da venda original e abate no mês do estorno | R2, P3 |
| ECs | 1043300981 = Novo Horizonte; 1043396662 = Horizonte Viagens; 1038867654 = Kiwi. **Atlas não fatura, pendência Comercial, sem taxa inventada e sem comissão zero fictícia** | R3, P10 |
| Casa do Estudante | Checkout taxa 0% de **01/09 a 31/12**. Estorno de venda de agosto usa a taxa histórica (sem isenção) | R6, P6 |
| Rota Global | +0,5 p.p. em crédito a partir de 12/09 é divergência; débito/Pix seguem a comparação por modalidade sem regra artificial | R6, P9 |
| Divergência checkout | Taxa aplicada ≠ contratada → `round(bruto × (aplicada − contratada))`. Centavo de truncamento não é divergência | R1, R8, P8 |
| Notas checkout | 1 por CNPJ/competência com comissão > 0. Zero explicado = sem nota sem alarme; negativo ou inesperado → pendência | R4, P11 |
| Comissão remessa | 50% × Spread R$ realizado, por operação, com ROUND_HALF_UP. Duplicada conta 1×. Quatro negativos de setembro fora (R5+P12), ressalva entra normal. Competência = contratação | R5, R8 |
| Divergência remessa | (spread_pct − contratado) × PTAX × ME, valor cheio, por operação. Vazio = 1,5%; "padrão" literal também. Texto inválido no campo gera pendência técnica, não default silencioso. Tolerância 0,01 p.p. | R5, R7, P5, P7 |
| Nota remessa | **1 nota** para a Ponte Câmbio (75374179000146) com a soma das participações por operação. Diferença contra o total declarado da Ponte vira pendência, não entra na nota | R4, P14 |
| Arredondamento | ROUND_HALF_UP (meio centavo longe de zero, inclusive no negativo) **por linha/operação**, depois soma | R8 |
| Extratos | `conta_codigo` = **contrapartida** (apenas contas analíticas que aceitam lançamento). Baixa de passivos/recebível para folha, tributos de 08 e repasse Ponte 08/2026. Demais despesas → direto no mês. Sem clareza → premissa escrita e/ou pendência | R6, R9 |

## Mudanças de contexto neste MVP

- CLAUDE.md: arredondamento é por linha, não "só na saída"; distinção entre pendência (falta info) e premissa (decisão delegada).
- HIPOTESES.md R6: impacto corrigido (vigência da isenção, estornos de agosto, Casa `TX88445133` com comissão −5,50 sem divergência; totais devem vir do motor, não hard-coded).
- CONTEXTO.md e MAPA_DADOS.md: respostas R1–R9 marcadas como resolvidas; mantidas as descrições das armadilhas.
- PERGUNTAS_FINANCEIRO.md: fila só com perguntas realmente abertas; R8 e R9 marcadas como respondidas.
- Removida a asserção de que "cobrança da Orbe menos comissão contratual = soma das divergências". Truncamento ≠ divergência; cada saída fecha com seu rastro.

## Perguntas ainda materialmente abertas

- **Divergência a menor**: nenhum caso em setembro. Preventivo; motor já reporta com sinal, basta Helena validar.
- **Quem decide por tipo de pendência**: temos defaults (Financeiro, Comercial, Ponte). Confirmar para a próxima rodada.
- Atlas e PIX R$ 7.350 (L50): dependem de informação externa; motor segue abrindo pendência enquanto não chegar.
