# Backlog do motor (17/10, ~09h40)

Base: motor v1 do Helio (`main`), conferido contra R1–R14 e O1. O que já funciona está em `docs/MVP_V1.md`. Aqui fica só o que falta.

**Linha do tempo (organização, 10h28 de 17/10):**

| Hora | Marco |
|---|---|
| 11h45 | Checkpoint 1 (opcional): o plano |
| 16h00 | Checkpoint 2 (opcional): a reta final |
| **17h45** | **Fim do atendimento do financeiro** |
| **18h30** | **Link do repositório por e-mail** (commits depois são ignorados) |
| 19h00 | Link do pitch por e-mail |
| 19h30 | Apresentação dos finalistas |
| 20h30 | Premiação |

Checkpoints: **uma pessoa do time** manda por mensagem privada para o Manuel Freitas, começando com o nome do time. Recebe devolutiva curta da banca.
- **Checkpoint 1:** causa raiz em até 2 frases; nível (mínimo, alvo ou extra); plano até 18h30 em 2 a 4 marcos com horário; 3 premissas não confirmadas e o que muda se estiverem erradas; o que fica de fora de propósito; quem faz o quê.
- **Checkpoint 2:** o que já roda ponta a ponta; o que mudou desde a manhã e por quê; o que vão cortar; maior risco e o que estão fazendo; onde a banca pode ajudar.

Dúvidas: no canal, com `[Financeiro]` ou `[Logística]` e o nome do time, uma por thread.

## Divisão de 17/10, ~12h15 (gaps do MVP × dono)

Fonte da situação de cada regra: `docs/STATUS.md`, seção "Regras do financeiro × motor". Uma branch por pessoa, a partir do `main`: `feat/checkout-pendencias` (Alex), `feat/remessa-pendencias` (Helio), `feat/entrega` (André). Cada um mexe só nos seus arquivos.

| # | Gap | Regra | Dono | Bloqueia entrega? |
|---|---|---|---|---|
| 1 | Gravar os 6 CSVs de setembro **na raiz** de `saida/` e commitar (hoje vão para `saida/2026-09/exec_*`, e `saida/` está no `.gitignore`) | R26, O1 | **André** | **Sim** |
| 2 | README: um comando, onde pôr os arquivos, `.env`, Laya experimental | O1 | **André** | **Sim** |
| 3 | Perguntar à organização: colunas extras (`rastro.metadata`, `lancamentos.motivo`) e L9 × L10 do Aurora | P1 | **André** | Talvez |
| 4 | Extratos: `confianca` do PIX L50 < 1; motivo "remessa de outubro" no `MRD2026090425` | R6, R16.5 | **André** | Não |
| 5 | Provisão de folha/impostos de setembro (aguarda resposta à Datarmos) | R19 | **André** | Não |
| 6 | Pendência de contestação **Ponte × Mundo Aberto** por lojista, 23 operações no rastro | R10, R12, R24.1 | **Helio** | Não |
| 7 | Duplicata `PC-0926-0162` como pendência (Ponte corrigir o relatório) | R12 | **Helio** | Não |
| 8 | `quem_decide` = Financeiro em `RM-CONTEST`, duplicata e status desconhecido | R11, R12 | **Helio** | Não |
| 9 | Negativo com dois valores: spread do relatório + diferença até o contrato | R28.3, P23 | **Helio** | Não |
| 10 | Ajuste `AJUSTE REF PC-…` da Ponte no mês em que aparece (teste sintético) | R27, P21 | **Helio** | Não |
| 11 | Pendência de contestação **Orbe × Rota** e **Orbe × Bridge** por lojista | R24.1, R28.1 | **Alex** | Não |
| 12 | Alerta de antecipação para lojista sem histórico (Atlas) | R16.6, R28.2, P22 | **Alex** | Não |
| 13 | CNPJ 39566044000119 da Atlas na pendência (só identidade) | R30 | **Alex** | Não |
| 14 | Atlas confirmada depois: outubro puxa as linhas pendentes de setembro | R18 | **Alex** | Não |
| 15 | Relatório de pendências por quem decide | R1, R24.1 | **Alex** | Não |
| 16 | Formulário na tela que grava condições comerciais e sinais resolvidos | P19, P20 | **Alex** | Não |

A partir das 17h: André confere a saída final contra a `solucao_minimo` (validação independente; essa branch **não** é mergeada).

Legenda: 🔒 depende de resposta · 🟢 pode fazer já · 📋 entra no relatório de pendências

## Transversal (bloqueia a entrega, O1)

- [ ] 🟢 Cada regra em `rules.py` cita a resposta e quem aprovou (R20: Comercial para taxa/condição, Financeiro para regra de fechamento).

- [ ] 🟢 **`saida/` com os 6 CSVs commitados na raiz.** Hoje `saida/` está no `.gitignore` e o motor grava em `saida/<comp>/exec_*/`. A banca compara com o `saida/` entregue.
- [x] 🟢 **Nada fixo para setembro** (branch `feat/generalizar-meses`): negativos por regra geral (P12), trânsito por cruzamento Aurora × Meridiano, competência inferida das datas, repasse da Ponte por "mês anterior", textos sem "agosto". Antes: `rules.PONTE_NEGATIVOS_EXCLUIR_SET2026` (ids), `extratos.py:34` (data 30/09), `--competencia` com default `2026-09` (inferir dos dados), textos "de agosto" nos motivos (derivar de competência − 1).
- [ ] 🟢 **README**: um comando, onde pôr os arquivos do mês, onde configurar a chave de API (`.env`).
- [ ] 🟢 **Relatório de pendências** (ver seção abaixo).
- [ ] 🔒 Colunas extras (`rastro.metadata`, `lancamentos.motivo`): perguntar à organização se pode ou se tira.
- [ ] 🟢 Mergear `feat/generalizar-meses` (inclui `feat/ec-cnpj-direto`, R3 por CNPJ direto).

## Checkout

- [x] 📋 **Casa do Estudante como condição comercial** (P19): 118 linhas `CK-COND-*` + 1 pendência `CONDICAO_NAO_INFORMADA_ORBE` (R$ 15.397,42, Financeiro + Comercial). A cobrar da Orbe: só `CK-DIV-*` (R$ 1.576,23).
- [x] 📋 **Detector de sinais** (`tarvo.sinais`): obs + comentários da planilha → palavras-chave **ou** Laya `noul` (open source, local, `laya==0.4.8`, modelo `multilingual`, corte 0,5, só sim/não). Sinal sem condição registrada nem resolução → pendência `CONDICAO_ESPECIAL_A_CONFIRMAR` (Comercial, valor 0, rastro na linha da planilha). Sem o pacote ou com `TARVO_CLASSIFICADOR=nenhum`: só palavras-chave. Em set/2026 marca Bridge L6, Casa L13 (×2) e Mundo Aberto L15, todos AMBOS; todos cobertos (COND-0001 ou `sinais_resolvidos`) → 0 pendências novas.
- [ ] 🟢 **Tela: responder pendência de condição** grava em `config/condicoes_comerciais.json` (campos estruturados + texto; classificador binário decide se o texto é útil para guardar).
- [ ] 🟢 Condição ativa mas planilha/Orbe ainda na taxa antiga → pendência "atualizar planilha e avisar a Orbe" (já sai no motivo); alerta de vencimento (≤ 30 dias).

- [x] ~~Divergência vira pendência?~~ R16: divergência de contrato fica em `divergencias_taxa` (Helena decide caso a caso); **Casa é outra natureza** (item abaixo).
- [x] **Estorno de venda divergente** (R16.3: venda e estorno se anulam, cobra só o líquido). Já é o que o motor faz.
- [x] **Orbe cobrando abaixo do contrato** (R16.7: é divergência, caso a caso; sem caso em setembro).
- [ ] 🟢 📋 **Alerta de antecipação acima das vendas** (R16.6): Σ antecipado > Σ vendido do lojista no mês → pendência para Financeiro + Comercial.
- [ ] 🟢 **Atlas confirmada depois** (R18): taxa vale desde 10/09; outubro puxa as linhas pendentes de setembro. Persistir as linhas de EC sem contrato para o próximo fechamento.

## Remessa

- [ ] 🟢 CNPJ da Ponte fora da planilha (P16): calcula a metade e abre pendência de cadastro (Comercial). Sem caso em setembro.

- [ ] 🟢 📋 **Pendência de contestação da Mundo Aberto** (R10, R12): uma por operação (23, R$ 1.418,85), com valor cheio e `ref_origem`.
- [ ] 🟢 📋 **Pendência da duplicata `PC-0926-0162`** (R12): entra na lista para a Ponte corrigir o relatório.
- [ ] 🟢 **`quem_decide` = Financeiro** (R11, R12): negativos já feitos; faltam duplicata conflitante, status desconhecido e `RM-CONTEST`. A Ponte é destinatária da contestação, não quem decide.
- [ ] 🟢 📋 **`RM-CONTEST`** vira "conferir o TED de repasse quando cair" (R11), sem supor desconto da Ponte.
- [x] **Negativos sem lista fixa**: regra geral pela R5 (P12 atualizada); a pergunta R-1 só confirma.
- [x] Negativos **não** entram em `divergencias_taxa` (R15: lojista não pagou a mais). Já está assim.

## Extratos

- [x] 🟢 📋 **Transferência em trânsito genérica**: saída "TRANSF ENTRE CONTAS" sem crédito correspondente no outro banco dentro do mês → pendência. Tira a data fixa.
- [x] **PIX `MRD2026090425`** (R16.5, R17): recurso de lojista para remessa de outubro, 2.1.02.001. Já está assim. Opcional: casar PIX × operação e anotar "remessa futura" no motivo.
- [x] Devolução L65 em 2.1.01.001 (R19, P17).
- [x] Folha/impostos sempre provisionados (R19). Regra já generalizada.
- [ ] 🟢 **Fallback LLM** para descrição sem regra: sugere conta com `metodo = LLM` e `confianca` < 1, sempre com pendência de revisão. Hoje 184/184 por regra; o caminho LLM precisa existir para outubro (e é o que a chave de API do O1 sugere).
- [ ] 🟢 `confianca` do L50 (PIX não identificado) não pode ser 1,00.

## Relatório de pendências 📋

Sempre que a Helena respondeu "coloca como pendência para mim" ou "fica comigo", o item precisa sair num **relatório legível para quem decide**, além da linha em `pendencias.csv`.

| Resposta | O que entra no relatório | Quem decide |
|---|---|---|
| R1 | Divergências de checkout: devolver ao lojista / cobrar da Orbe, caso a caso | Financeiro |
| R3 | Atlas sem contrato: transações e valor cobrado pela Orbe | Comercial |
| R4 | Lojista com comissão ≤ 0 (Casa, −5,50): tratar com o lojista | Financeiro |
| R5, R12 | 4 spreads negativos: lista de contestação com valor e operações | Financeiro → Ponte |
| R10, R12 | Excesso da Mundo Aberto (23 operações): lista de contestação | Financeiro → Ponte |
| R12 | Duplicata `PC-0926-0162`: pedir correção do relatório | Financeiro → Ponte |
| R11 | Conferir o TED de repasse quando cair (nota × total declarado) | Financeiro |
| R6 | PIX sem id (L50), devolução Mundo Aberto (L65), transferência de 300 mil em trânsito (L92) | Financeiro |
| R13 | (fora) Conciliação Orbe × banco parcela a parcela: não é pendência, fica para a agenda de recebíveis | — |

Desenho:
1. **Determinístico primeiro.** Agrupar `pendencias.csv` por `quem_decide` e `tipo`; cada tipo conhecido tem um template fixo (o que é, valor total, operações/linhas, ação esperada, resposta que sustenta). Valores e ids vêm só do CSV/rastro.
2. **LLM só de fallback.** Para `tipo` sem template (caso novo em outubro), o LLM redige o texto do item a partir das colunas da pendência. Nunca altera valor nem id; o item sai marcado "texto gerado por IA".
3. Saída: `saida/relatorio_pendencias.md` (extra, fora dos 6 CSVs obrigatórios).

## Nossas perguntas (mandar só depois das respostas acima)

Uma por vez, formato `[financeiro] Fox AI:`.

- **R-1 (remessa, desbloqueia "nada fixo para setembro")**: `[financeiro] Fox AI: spread negativo em outros meses. Em setembro os 4 negativos (ex.: PC-0926-0210) têm obs "Taxa travada no pedido (D-1)", e você disse que passaram da trava de 2h. Propomos regra geral: todo spread negativo fica fora da comissão e da nota e vira pendência de contestação, sem precisar checar o prazo. Confere?`
- **R-2 (remessa)**: `[financeiro] Fox AI: colunas "IOF R$" e "Spread Estimado R$ (D-1)" do relatório da Ponte. Propomos ignorar as duas no cálculo: IOF é do cliente e o estimado é só referência; a comissão sai do Spread R$ realizado. Confere?`
- **C2 (checkout)**, se Barteman P3 não resolver: ver `docs/PERGUNTAS_FINANCEIRO.md`.
- **Extratos (André)**: tabela de classificação proposta, de uma vez (rascunho em `docs/STATUS.md`).
- **Organização** (`[hackathon]`): colunas extras nos CSVs de saída são aceitas? `ref_origem` do Aurora conta da linha 1 (primeira transação = L9)?
