# O que falta para fechar 100% (17/10, ~15h45)

Prazos: **17h** congelar features · **17h45** fim do atendimento do financeiro · **18h30** link do repositório por e-mail (commit depois disso não conta) · **19h** link do pitch.

Estado agora: `main` verde no CI, repositório **público**, 152 testes passando + 1 falha esperada (gap 10), referência manual 14/14, `saida/` de setembro commitada.

## 1. Obrigatório para a entrega

| # | Item | Dono | Quando | Situação |
|---|---|---|---|---|
| E1 | **Escolher 2 a 4 momentos** em `PROMPTS/MOMENTOS.md` (hoje são 5 candidatos; pelo menos 1 com erro da IA). Sugestão: 3 (loader sem comentários de célula), 4 (fórmula de divergência que a Helena contrariou) e 5 (Laya com instrução longa) | time | até 17h30 | ⏳ |
| E2 | **Export das sessões de IA, cada um na própria máquina**: `python scripts/exportar_sessoes.py <github-user> --email <seu e-mail>` e de novo com `--completo`. Quem usou ChatGPT, Cursor ou outra ferramenta coloca os links em `PROMPTS/sessoes/<user>/links.md` | Alex, Helio, André | 17h30–18h | ⏳ |
| E3 | **Saída final**: **uma só pessoa** roda `python -m tarvo --dados data/raw/set2026`, confere 14/14 no log e commita `saida/*.csv`. Ninguém mais regenera depois disso | Alex | depois do congelamento, ~17h15 | ⏳ (a atual está correta, mas pode mudar se o front ou o motor mudarem) |
| E4 | **Último push até 18h15** e conferir no GitHub: repo público, CI verde, `saida/` com os 6 CSVs, README abrindo | Alex | 18h15 | ⏳ |
| E5 | **E-mail com o link do repositório** | Alex | até 18h30 | ⏳ |
| E6 | **Pitch** (PDF ou slides) e e-mail com o link | time | até 19h | ⏳ |

## 2. Para o André mexer no front agora (até 17h)

- O código do front fica em `web/src/`. Para rodar em modo de desenvolvimento: `cd web && npm install && npm run dev`, com a API em outra aba: `python -m tarvo.web --dados data/raw/set2026 --porta 8000 --sem-navegador`.
- **Ao terminar**, rode `npm run build`. Isso regenera `src/tarvo/web/static/`, que é o que a banca usa sem Node. Commite **também** essa pasta.
- Não mexa em `src/tarvo/` fora de `web/api.py`. Se precisar de dado novo na tela, peça um campo na API.
- Antes do push: `pytest -q && ruff check .` na raiz. Os testes da API (`tests/test_web.py`) quebram se um campo da resposta mudar.
- **Não commite `saida/`** a partir do painel. Cada "Fechar" do painel regrava `saida/` (veja E3).

## 3. Opcional, se sobrar tempo (em ordem de valor)

| # | Item | Esforço | Observação |
|---|---|---|---|
| O1 | **Gap 10:** ajuste `AJUSTE REF PC-…` da Ponte abatendo a comissão do mês (R27, P21) | ~30 min | Teste pronto em `tests/test_outubro_sintetico.py` (`xfail` estrito). Pergunta pendente da Desbravadores: o Spread R$ do ajuste vem cheio ou já como a nossa metade |
| O2 | **Perguntas para a organização:** colunas extras nos CSVs (`causa_divergencia`, `motivo`, `metadata`) e Aurora começando em L9 | 1 mensagem cada | Textos prontos em `docs/BACKLOG.md` (gap 3). Se responderem "não pode coluna extra", é tirar 3 colunas no `output.py` |
| O3 | **Gap 15:** relatório de pendências em arquivo (`saida/relatorio_pendencias.md`) | ~30 min | O painel já cumpre esse papel; só vale se a banca não abrir a tela |
| O4 | **Gap 14:** Atlas confirmada depois puxa as linhas de setembro em outubro (R18) | ~45 min+ | Mexe no filtro de competência; risco alto para a hora. Está nas limitações do README |
| O5 | **Gap 5:** provisão de folha e impostos do mês | — | Sem resposta e sem valores no pacote. Fica como limitação |
| O6 | Marcar o PIX de R$ 18.240 (`MRD2026090425`) como "remessa de outubro" | ~45 min | Exige casar PIX com somas de operações; risco de falso alarme |

## 4. Já está pronto (para o pitch e para conferência)

- **Níveis do case:**
  - Mínimo, Alvo e Extra (pendências explicadas e rastro completo) entregues.
  - "Roda em outubro" coberto por um outubro sintético de ponta a ponta, com fechamento parcial quando falta arquivo, aviso de layout e reconhecimento de arquivo pelo conteúdo.
- **Regras:** R1–R34 e O1–O2 registradas com hora e quem perguntou. Premissas P1–P25. Situação regra × motor em `docs/STATUS.md`.
- **Painel:**
  - pendências por quem decide;
  - rastro clicável no centavo;
  - divergências por natureza;
  - condições comerciais com formulário;
  - upload padronizado com fechamento parcial.
- **Validações a cada execução:** rastro exato, cobertura de todas as entradas, ids únicos, checksum dos dados originais.
- **Documentação:**
  - `README.md` (rodar com um comando, sem chave de API);
  - `HIPOTESES.md`, `docs/STATUS.md`, `docs/MAPA_DADOS.md`, `docs/BACKLOG.md`;
  - `docs/ESTUDO_MAIN_X_SOLUCAO_MINIMO.md`.

## 5. Riscos a vigiar

- **`saida/` regenerada por mais de uma pessoa ou pelo painel:** resolve com o E3, uma pessoa e uma vez.
- **Front mexido sem rodar `npm run build`:** a banca veria a versão antiga. Conferir que `src/tarvo/web/static/` mudou no commit do André.
- **Push em cima de push perto das 18h:** combinar que depois de 18h só o Alex faz push.
