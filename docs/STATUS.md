# Status: 17/10, ~13h15

Comece aqui. Detalhes: `HIPOTESES.md` (R1–R34, P1–P24, O1), `docs/BACKLOG.md` (gaps numerados e donos), `docs/MVP_V1.md` (arquitetura do motor).

## Níveis do case × o que já entregamos

| Nível | O case pede | Situação |
|---|---|---|
| **Mínimo** | Comissão de checkout por lojista, com rastro | ✅ 21 lojistas, **R$ 203.735,34** com os ajustes tardios da Orbe (era R$ 207.039,73 só com o 01), rastro exato; referência manual 14/14. A validação do André (`solucao_minimo`) bateu no 01 e precisa ler também o 06 |
| **Alvo** | + comissão de remessa | ✅ 14 lojistas, R$ 39.543,45 (50% por operação, sem duplicata e sem negativos) |
| | + divergências de taxa, transação por transação | ✅ 233 linhas: `CK-DIV` (Orbe errou, R$ 1.576,23), `CK-COND` (Casa, concessão fora do contrato), `RM-DIV` (Mundo Aberto, R$ 1.418,85) |
| | + notas a emitir | ✅ 20 checkout + 1 Ponte; ≤ 0 sem nota e com pendência |
| | + lançamentos classificados no plano de contas | ✅ 184/184 por regra, contrapartida (R9), só contas analíticas |
| **Extra** | + pendências com motivo e quem decide | ✅ 14 pendências agregadas por contraparte e lojista (R24.1), cada uma com motivo, fonte (R#) e dono |
| | + rastro completo | ✅ soma exata por `id_saida` + cobertura (toda linha de entrada aparece em alguma saída) |
| | + roda em outubro sem retrabalho | ⚠️ nada fixo de setembro, competência inferida, condições comerciais e sinais versionados. **Falta:** arquivo ausente e layout novo (R34), Atlas confirmada depois (R18), ajuste da Ponte (R27) |
| **Entrega** | `saida/` com os 6 CSVs | ❌ **bloqueia**: hoje ficam em `saida/2026-09/exec_*` e `saida/` está no `.gitignore` (gap 1) |
| | README que diz como rodar | ❌ **bloqueia** (gap 2) |
| | `HIPOTESES.md`, `PROMPTS/MOMENTOS.md` | ✅ (5 momentos, 4 com erro da IA) · ❌ export dos prompts das sessões |

## A solução em uma frase

Um comando (`python -m tarvo --dados <pasta do mês> --saida saida`) lê os 6 arquivos do mês, aplica as regras confirmadas pelo financeiro (cada uma citada em `HIPOTESES.md`), gera os 6 CSVs com rastro exato em centavos e manda para pendência, com quem decide, tudo o que não pode ser decidido por regra.

**Causa raiz que atacamos (R21):** o fechamento leva 8 dias porque as regras só existem na cabeça da Helena (condições do comercial, quem é quem entre nomes e CNPJs, o que se contesta) e são aplicadas à mão (3 dias de checkout, 2 de remessa, 2 de extratos). A solução torna cada regra explícita, versionada e com fonte, e o que é exceção vira pendência com dono.

## Números de set/2026 (`main` após hardening)

| Saída | Linhas | Destaques |
|---|---|---|
| `comissoes_por_lojista` | 35 | Checkout R$ 203.735,34 (21 lojistas, com o arquivo 06) · Remessa R$ 39.543,45 (14) |
| `divergencias_taxa` | 233 | `CK-DIV` 92 (Rota, Bridge: cobrar da Orbe R$ 1.576,23) · `CK-COND` 118 (Casa: devolver, fora da cobrança) · `RM-DIV` 23 (Mundo Aberto R$ 1.418,85) |
| `notas_a_emitir` | 21 | 20 checkout + 1 Ponte Câmbio (R$ 39.543,45) |
| `lancamentos_classificados` | 184 | 184/184 por regra, só contas analíticas |
| `pendencias` | 14 | Atlas sem contrato 1 + alerta de antecipação 1 (Comercial) · contestação Orbe 2 (Rota, Bridge) · Casa devolução 1 (R$ 15.396,77) · Casa nota negativa 1 · negativos da Ponte 4 · conferir TED 1 · extratos 3 |
| `rastro` | 4.802 | Soma exata por `id_saida` |

Validação: 68 testes, `ruff` limpo, referência manual 14/14, e a implementação independente do André bate centavo a centavo nas 21 comissões de checkout.

## Regras do financeiro × motor

| Regra | Situação |
|---|---|
| R1/R8/R14 comissão pela contratada, arredondamento por linha | ✅ |
| R2/R29/R31 estorno pela taxa da venda original, no mês do estorno | ✅ |
| R3/R30 mapa de ECs por CNPJ; Atlas não fatura | ✅ Atlas fora de comissões (P24), 1 pendência com CNPJ 39566044000119 (só identidade) |
| R4 1 nota por lojista; ≤ 0 sem nota + pendência; 1 nota Ponte | ✅ |
| R5/R15 remessa 50% do realizado; negativo fora; duplicata 1×; padrão 1,5% | ✅ negativos por regra geral, sem ids fixos |
| R6/R16.1/R22/R28.1/R33 Casa = concessão fora do contrato → devolução do que a Orbe descontou de fato (R$ 15.396,77), fora da cobrança da Orbe | ✅ `CK-COND` (fórmula, R$ 15.397,42) + pendência; fonte única `config/condicoes_comerciais.json` |
| R6 extratos: PIX sem id, devolução, transferência em trânsito | ✅ trânsito por cruzamento dos bancos, sem data fixa |
| R7/P7 divergência de remessa cheia, tolerância 0,01 p.p. | ✅ |
| R9/R19/R25 contrapartida; provisão baixa no mês seguinte | ✅ |
| R10/R12/R24.1 pendência de contestação por contraparte e lojista | ✅ Orbe × Rota, Orbe × Bridge, Tarvo × Casa · ❌ Ponte × Mundo Aberto, duplicata (Helio) |
| R11/R12 `quem_decide` das pendências da Ponte = Financeiro | ✅ |
| R16.6/R28.2/R32 alerta de antecipação só para lojista sem histórico (P22) | ✅ Atlas, pelo pico |
| R18 Atlas confirmada depois: outubro puxa as linhas de setembro | ❌ |
| R24.3 venda acima de 12x → pendência | ✅ (`SEM_TAXA_CONTRATADA`) |
| R26 `saida/` com os 6 CSVs de setembro **na raiz** | ❌ hoje vai para `saida/2026-09/exec_*` |
| R27 ajuste de contestação da Ponte no mês seguinte (P21) | ❌ sem caso em setembro |
| R28.3 negativo com os dois valores (P23) | ❌ |
| O1 um comando, nada fixo para setembro, README com chave | ✅ código · ❌ README · ❌ `saida/` na raiz |
| R34 avisar quando o layout quebra; arquivo ausente não segura o mês | ❌ gaps 17 e 18 |
| P20 sinais de condição especial na planilha | ✅ palavras-chave (Laya experimental, desligado: não melhorou o acerto) |

## Hardening do pipeline (17/10 tarde, commit `facce8b`)

Antes: o motor dependia da ordem das linhas na Orbe, aceitava transação duplicada em silêncio, não rejeitava data fora da competência, perdia operação de remessa sem spread sem registrar, e agrupava remessa pelo nome do lojista (que varia entre linhas da Ponte). São todos riscos de o faturamento sair errado sem nenhum sinal.

| Mudança | Motivação | O que faz agora |
|---|---|---|
| **Dedup Orbe por `id_transacao`** (checkout) | Transação repetida com dados iguais dobrava a comissão; dados divergentes faziam o motor escolher sozinho | 1× quando os campos financeiros batem; pendência `DUPLICATA_CONFLITANTE` para o Financeiro quando divergem |
| **Two-pass antecipação** (checkout) | `REVERSAO ANTECIPACAO` só funcionava se a antecipação original vinha antes na planilha; inversão abria `REVERSAO_SEM_REFERENCIA` indevida | Pré-pass popula a comissão de todas as `ANTECIPACAO` antes do loop; `REVERSAO` acha em qualquer ordem |
| **Filtro de competência** (checkout + remessa) | Linha de outro mês entrando no fechamento polui comissão e divergência | Data fora de `AAAA-MM` vira pendência `FORA_COMPETENCIA` para o Financeiro, sem distorcer a apuração |
| **`SPREAD_AUSENTE`** (remessa) | `spread_brl is None` sumia a operação sem registro | Pendência `SPREAD_AUSENTE` para a Ponte Câmbio em vez do `continue` silencioso |
| **Agrupar remessa por CNPJ só** | Mesma empresa com variação de nome entre linhas gerava 2 comissões; nome não é identidade | Agrupa por CNPJ; nome representativo escolhido entre as variações |
| **`validate_cobertura_entradas`** (output) | Nada garantia que cada transação de entrada aparecesse em alguma saída | Checagem global: ref de entrada sem rastro em saída = `INPUT_SEM_SAIDA` no relatório de integridade |

Resultado em setembro: 35 comissões, 13 pendências, 184/184 classificação, rastro 4.802 (todas somas em centavos exatos). Nenhuma nova pendência disparada no data pack real (os dados estão limpos), mas as regras agora **defendem** o próximo mês. Testes: 59 → 68 (+6 cobrindo ordem invertida, duplicata, fora-de-competência, spread ausente, nome variável, cobertura).

## Branches

| Branch | Dono | Estado |
|---|---|---|
| `main` | todos | Tudo integrado até 13h06 |
| `solucao_minimo` | André | Validação independente do checkout. **Não mergear** (apaga `src/tarvo/`) |

Nenhuma branch aberta de Helio ou André desde o hardening do Helio (12h33, direto no `main`).

## Quem fez o quê

- **Alex**: repo, loaders e testes de integridade; mapa das armadilhas; perguntas ao financeiro e registro R1–R34; generalização para qualquer mês; R3 por CNPJ; condições comerciais (Casa); detector de sinais; pendências por contraparte (Orbe, Atlas); alerta de antecipação; correção do bug de reversão; backlog e status.
- **Helio**: MVP v1 de ponta a ponta (3 motores, orquestrador, rastro exato, SQLite de execuções e decisões, avaliação contra referência manual, Streamlit) e `MVP_V1.md`; hardening (dedup da Orbe, ordem independente, competência, validação de cobertura). Perguntas R8 e R9. Hardening do pipeline (dedup, two-pass antecipação, filtro de competência, `SPREAD_AUSENTE`, agrupamento por CNPJ, cobertura de entradas).
- **André**: implementação independente do checkout (`solucao_minimo`) que confirmou os números do `main`; premissas M1–M4; pergunta R14.

## Trajetória

1. **16/10 noite**: setup, leitura dos dados, primeiras armadilhas (truncamento da Orbe, duplicata, negativos, ECs sem planilha) e perguntas R1–R9. Helio entrega o MVP v1 às 22h20.
2. **17/10 manhã**: André valida o checkout por fora. Tiramos tudo que era fixo de setembro (O1). As respostas R10–R31 mudam três coisas: a Casa é concessão fora do contrato (devolução nossa, não cobrança da Orbe), pendências passam a ser por contraparte e lojista, e `saida/` vai na raiz.
3. **17/10 tarde**: Helio empurra o hardening (seção acima). O motor passa a ser idempotente a ordem/duplicata, filtra competência, grita quando falta dado em vez de sumir com a linha, e exige que toda entrada tenha saída via rastro.
4. **Erros da IA registrados** (`PROMPTS/MOMENTOS.md`): L10 × L9; "a Orbe usa a tabela antiga"; loader sem comentários de célula; fórmula de divergência errada. Novo candidato: a instrução longa no Laya baixou o acerto para 8/15; medimos e trocamos por um comitê de 3 instruções curtas.

## Próximos passos

Divisão por pessoa (gaps numerados e donos): `docs/BACKLOG.md`, seção "Divisão de 17/10".

### Ordem geral

1. Mergear `feat/condicoes-comerciais`.
2. `saida/` na raiz com os 6 CSVs + README (um comando, `.env`, Laya opcional). **Bloqueia a entrega.**
3. Pendências por contraparte e lojista (Rota, Bridge, Mundo Aberto, duplicata), `quem_decide` = Financeiro, negativo com dois valores.
4. Alerta de antecipação (P22) e CNPJ da Atlas na pendência.
5. Relatório de pendências + formulário na tela que grava condições.
6. 17h: congelar; MOMENTOS, export dos prompts, pitch.
