# Tarvo: fechamento mensal

Hackathon Barte AI (17/10/2026). Time **Fox AI**: [@AlexChequer](https://github.com/AlexChequer), [@hhenriqueN](https://github.com/hhenriqueN), [@andrespleite](https://github.com/andrespleite).

A Tarvo leva 8 dias para fechar o mês. Boa parte das regras só existe na cabeça da Helena: as condições que o comercial combinou, qual nome da Orbe é qual CNPJ, o que se contesta com a Ponte. Elas são aplicadas à mão, linha por linha. Este projeto faz o fechamento com **um comando**: lê os arquivos do mês como eles chegam e aplica as regras confirmadas com o financeiro, cada uma registrada em `HIPOTESES.md` com a resposta que a sustenta. Tudo o que uma regra não consegue decidir vira pendência, com o motivo e quem decide.

## Rodar

Requer Python 3.11 ou mais novo. **Não precisa de chave de API nem de Node.** A chave da OpenAI é opcional e só serve para os rascunhos de mensagens (abaixo).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m tarvo --dados data/raw/set2026
```

O comando fecha setembro e grava os 6 arquivos na raiz de `saida/`. São esses que estão no repositório. Cada execução também fica guardada em `saida/<competência>/exec_<hora>/`, fora do git, junto com um `avaliacao.json` que compara a saída com a referência manual.

### Painel (tela)

```bash
python -m tarvo.web --dados data/raw/set2026
```

Abre `http://127.0.0.1:8000` (para outra porta, use `--porta 8010`). A tela usa o mesmo motor da linha de comando.

| Aba | O que mostra |
|---|---|
| **Pendências** | A fila do mês por quem decide (Helena, Helena com o comercial, comercial). Cada item tem o motivo e, quando cabe, a ação |
| **Comissões e notas** | Totais do mês e tabelas por lojista |
| **Divergências** | Separadas por natureza: a Orbe cobrou diferente do contrato (cobrar da Orbe), condição comercial não avisada (devolver ao lojista) e spread acima do contrato (contestar com a Ponte) |
| **Lançamentos** | Extratos Aurora e Meridiano com a conta de contrapartida |
| **Rastro** | O `rastro.csv` inteiro, com filtro |
| **Condições comerciais** | Acordos fora da planilha (ex.: Casa do Estudante com 0% até 31/12). Formulário para registrar uma nova, que vale nos meses seguintes |

- **Rastro:** **qualquer valor é clicável** e abre as linhas de origem que somam até ele, no centavo.
- **Enviar arquivos do mês:** fecha um mês novo por upload, sem mexer na pasta.

### Outro mês

Aponte `--dados` para a pasta com os arquivos do mês, no mesmo formato. Pode ser pela linha de comando ou pelo upload da tela.

- **Competência:** é deduzida das datas dos arquivos. Para forçar, use `--competencia AAAA-MM`.
- **Nomes dos arquivos:** reconhecidos pelo padrão (`01_orbe_relatorio_comissoes_*.csv`, ...). Se o nome vier diferente, o arquivo é reconhecido pelo conteúdo.
- **Ajustes tardios da Orbe** (`*_orbe_ajustes_*.csv`) entram junto com o relatório principal.
- **Faltou arquivo?** O fechamento roda o que der e marca o resto como bloqueado. Sem a Ponte, por exemplo, checkout e extratos fecham, e a remessa vira a pendência "falta o relatório de remessas".
- **Layout mudou?** Se um arquivo vier com coluna renomeada, ele não é usado e a pendência diz qual coluna faltou e quais vieram. As partes que não dependem dele fecham normalmente.

### Configuração opcional

Nenhuma variável é obrigatória. As opcionais ficam no arquivo `.env` da raiz (copie de `.env.example`; o `.env` não vai para o git):

- `OPENAI_API_KEY` (e `OPENAI_MODEL`, padrão `gpt-6-luna`) liga os **rascunhos de envio a terceiros** no fim da página de pendências: uma mensagem por destinatário (Orbe, Ponte Câmbio, cada lojista, Comercial), juntando as pendências dele. A IA só redige: recebe marcadores (`{VALOR_1}`, `{LOJISTA_1}`…) no lugar de nomes, CNPJs, valores e ids, e os valores reais são preenchidos e conferidos na máquina. Um validador reprova texto com número escrito pelo modelo, marcador inventado, assinatura ou promessa de prazo (P36). Sem a chave, a seção mostra "Rascunhos indisponíveis" e nada mais muda.
- `TARVO_CLASSIFICADOR=laya` liga o classificador open source local [Laya](https://laya-ai.com/) para achar anotações de condição especial na planilha de taxas. Requer `pip install -e ".[classificador]"`. Vem **desligado**: palavras-chave acertaram 14 de 15 num conjunto rotulado, contra 13 de 15 com o Laya (`scripts/avaliar_sinais.py`).

## O que sai em `saida/`

Todos os arquivos usam separador `;`, decimal `.`, datas `AAAA-MM-DD` e CNPJ com 14 dígitos. Nenhum campo tem `;` dentro, então os arquivos abrem sem aspas.

| Arquivo | Conteúdo | Setembro |
|---|---|---|
| `comissoes_por_lojista.csv` | Comissão por lojista e linha (CHECKOUT/REMESSA), pela taxa **contratada** | 35 linhas · checkout R$ 203.735,34 · remessa R$ 39.543,45 |
| `divergencias_taxa.csv` | Transação a transação, quando a taxa cobrada difere da contratada. O `id_saida` diz a natureza (`CK-DIV`, `CK-COND`, `RM-DIV`) e `causa_divergencia` diz o porquê no checkout | 233 linhas |
| `notas_a_emitir.csv` | Uma nota por lojista no checkout e uma única para a Ponte Câmbio; saldo ≤ 0 não emite | 21 notas |
| `lancamentos_classificados.csv` | Cada movimento dos extratos com a conta de contrapartida no plano | 184 linhas, todas por regra |
| `pendencias.csv` | O que precisa de uma pessoa: tipo, valor em jogo, motivo e quem decide | 16 pendências |
| `rastro.csv` | Para cada número de saída, as linhas de origem que somam até ele | 4.981 linhas |

### Garantias, verificadas a cada execução

- **Rastro exato:** a soma do rastro de cada número é igual ao número, em centavos.
- **Cobertura:** toda linha de entrada aparece em alguma saída.
- **Ids únicos** entre os arquivos de saída.
- **Arredondamento:** dinheiro em `Decimal`, arredondado por linha, meio centavo para longe do zero (R8).
- **Nada inventado:** lojista sem contrato não fatura, e taxa ausente vira pendência. Lojista é identificado por EC ou CNPJ, nunca por nome.
- **Dados originais intactos:** os arquivos de `data/raw/` nunca são editados. Um teste confere o checksum de cada um.

Validação em setembro: 210 testes automatizados, 14 de 14 casos de uma referência montada à mão e uma implementação independente do checkout (branch `solucao_minimo`) chegando aos mesmos valores por lojista.

## Como funciona

```
data/raw/<mês>/  →  loaders  →  motores (checkout · remessa · extratos · sinais)  →  orquestrador  →  saida/
                                         ↑                                             ↓
                     rules.py + config/condicoes_comerciais.json        validações + SQLite + painel
```

1. **Loaders** (`src/tarvo/loaders/`): leem cada arquivo como ele vem. Tratam números e datas pt-BR, CNPJ sem zero à esquerda, latin-1, OFX, e-mail com anexo e comentários de célula do Excel. Guardam a referência da linha de origem. Não aplicam nenhuma regra de negócio.
2. **Motores** (`src/tarvo/engines/`):
   - **Checkout:** a taxa contratada vem da planilha, pela vigência na data da venda, ou de uma condição comercial registrada. Estorno usa a taxa da venda original. Reversão anula a antecipação de origem. O motor separa o que a Orbe cobrou errado (contestar) do que a Tarvo concedeu sem avisar a Orbe (devolver).
   - **Remessa:** 50% do spread realizado, por operação. Duplicata conta uma vez. Spread negativo fica fora e vira contestação.
   - **Extratos:** classificação por regra sobre a descrição, sempre pela contrapartida.
   - **Sinais:** lê obs e comentários da planilha procurando condições comerciais escondidas.
3. **Regras** (`src/tarvo/rules.py`, `config/condicoes_comerciais.json`, `config/cadastro_ec.json`): cada uma cita a resposta do financeiro (R#) ou a premissa (P#) de `HIPOTESES.md`. Condições comerciais registram quem aprovou e quando.
4. **Orquestrador** (`src/tarvo/orquestrador.py`): roda as frentes que os arquivos permitem, valida e grava. Registra cada execução no SQLite e marca para reavaliar as decisões tomadas sobre dados ou regras que mudaram depois.

### Rodar os testes

```bash
pip install -e ".[dev]"
pytest -q && ruff check .
```

Os testes incluem um **outubro sintético** de ponta a ponta (`tests/test_outubro_sintetico.py`). O pacote é gerado a partir de setembro, com datas de outubro, um lojista novo, uma anotação nova na planilha, o repasse de 09/2026 e um ajuste da Ponte, e não é dado real. Para gerar o pacote numa pasta e testar pelo painel: `python scripts/gerar_outubro_sintetico.py <pasta>`. Também há casos sintéticos para arquivo faltando, layout quebrado, nome de arquivo trocado, duplicata e spread acima do contrato.

O front fica em `web/` (React + TypeScript + Vite + Tailwind + motion) e já vai compilado em `src/tarvo/web/static/`. Para mexer nele: `cd web && npm install && npm run dev`, com a API rodando em `:8000`. Para regenerar o build: `npm run build`.

## Documentação

| Arquivo | Para quê |
|---|---|
| `HIPOTESES.md` | Fatos, premissas (P1–P25) e todas as perguntas e respostas do financeiro (R1–R34), com hora e quem perguntou |
| `docs/STATUS.md` | Estado atual: regras × motor, branches, quem fez o quê |
| `docs/CONTEXTO.md` | O negócio explicado e por que cada dúvida importa |
| `docs/MAPA_DADOS.md` | O que tem em cada arquivo e as armadilhas encontradas |
| `docs/MVP_V1.md` | Arquitetura e decisões do motor |
| `docs/ESTUDO_MAIN_X_SOLUCAO_MINIMO.md` | Dicionário das colunas e a comparação com a implementação independente |
| `docs/BACKLOG.md` | Gaps numerados, com dono |
| `PROMPTS/` | Histórico das sessões de IA (`scripts/exportar_sessoes.py`) e `MOMENTOS.md` |

## Limitações conhecidas

- **Memória entre meses (R18, P33, P34):** outubro relê as transações sem contrato e os lojistas de setembro a partir do histórico de `saida/<competência>/`. Isso só funciona se os dois meses forem fechados na mesma pasta de saída (o histórico não vai para o git).
- **Provisão de folha e impostos do próprio mês:** não é gerada; o pacote não traz os valores.
- **Colunas extras** além das pedidas: `causa_divergencia` nas divergências, `motivo` nos lançamentos e `metadata` no rastro. As colunas obrigatórias estão todas presentes, na ordem pedida, e a Helena confirmou que coluna extra não atrapalha (R36).
