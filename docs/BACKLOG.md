# Backlog do motor (17/10, ~09h40)

Base: motor v1 do Helio (`main`), conferido contra R1–R14 e O1. O que já funciona está em `docs/MVP_V1.md`. Aqui fica só o que falta.

Legenda: 🔒 depende de resposta · 🟢 pode fazer já · 📋 entra no relatório de pendências

## Transversal (bloqueia a entrega, O1)

- [ ] 🟢 **`saida/` com os 6 CSVs commitados na raiz.** Hoje `saida/` está no `.gitignore` e o motor grava em `saida/<comp>/exec_*/`. A banca compara com o `saida/` entregue.
- [ ] 🟢 **Nada fixo para setembro.** `rules.PONTE_NEGATIVOS_EXCLUIR_SET2026` (ids), `extratos.py:34` (data 30/09), `--competencia` com default `2026-09` (inferir dos dados), textos "de agosto" nos motivos (derivar de competência − 1).
- [ ] 🟢 **README**: um comando, onde pôr os arquivos do mês, onde configurar a chave de API (`.env`).
- [ ] 🟢 **Relatório de pendências** (ver seção abaixo).
- [ ] 🔒 Colunas extras (`rastro.metadata`, `lancamentos.motivo`): perguntar à organização se pode ou se tira.
- [ ] 🟢 Mergear `feat/ec-cnpj-direto` (R3 por CNPJ direto).

## Checkout

- [ ] 🔒 📋 **Divergência vira pendência para a Helena?** R1 diz que ela decide caso a caso; na remessa ela pediu pendência (R10, R12). Esperar Barteman P3; depois a nossa C2 (por transação ou por lojista).
- [ ] 🔒 **Estorno de venda divergente** gera divergência negativa (5 casos, −107,53). Esperar Barteman P2 (é a nossa C1).
- [ ] 🔒 **Orbe cobrando abaixo do contrato** (P4, sem caso em setembro). Esperar Barteman P4.
- [ ] 🔒 📋 **Antecipação acima das vendas** (Atlas, R$ 179,6 mil × R$ 55,4 mil). Esperar Barteman P8; se for alerta, vira pendência com regra genérica (Σ antecipado > Σ vendido no mês).
- [ ] 🔒 **Atlas confirmada depois**: puxa linhas de meses anteriores? Esperar Nader (MN AI). Afeta o desenho de outubro.

## Remessa

- [ ] 🟢 📋 **Pendência de contestação da Mundo Aberto** (R10, R12): uma por operação (23, R$ 1.418,85), com valor cheio e `ref_origem`.
- [ ] 🟢 📋 **Pendência da duplicata `PC-0926-0162`** (R12): entra na lista para a Ponte corrigir o relatório.
- [ ] 🟢 **`quem_decide` = Financeiro** (R11, R12) em `remessa.py:72`, `:106`, `:124`, `:251`. A Ponte é destinatária da contestação, não quem decide.
- [ ] 🟢 📋 **`RM-CONTEST`** vira "conferir o TED de repasse quando cair" (R11), sem supor desconto da Ponte.
- [ ] 🔒 **Negativos sem lista fixa**: regra genérica precisa de resposta (pergunta R-1 abaixo).
- [ ] 🔒 Negativos também em `divergencias_taxa`? Esperar MN AI / Barteman P5 / Desbravadores.

## Extratos

- [ ] 🟢 📋 **Transferência em trânsito genérica**: saída "TRANSF ENTRE CONTAS" sem crédito correspondente no outro banco dentro do mês → pendência. Tira a data fixa.
- [ ] 🔒 📋 **PIX sem remessa correspondente** (`MRD2026090425`, R$ 18.240,00): casar PIX da Ponte Aérea × operações da Ponte (valor + IOF); sem par → pendência. Esperar Barteman P6 / Desbravadores.
- [ ] 🔒 Devolução L65: 2.1.01.001 ou 2.1.01.002? Esperar Desbravadores.
- [ ] 🔒 Provisionamento de folha/impostos é sempre ou só agosto? Esperar Desbravadores. Afeta outubro.
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
