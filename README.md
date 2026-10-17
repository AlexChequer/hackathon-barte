# Tarvo: comissão de checkout (solução mínima)

Hackathon Barte AI (17/10/2026). Time: [@AlexChequer](https://github.com/AlexChequer), [@hhenriqueN](https://github.com/hhenriqueN), [@andrespleite](https://github.com/andrespleite).

Calcula a **comissão de CHECKOUT de cada lojista** da Tarvo no mês, a partir do relatório da Orbe e da planilha de taxas **como eles chegam**, e liga cada centavo à transação de origem.

| Arquivo em `saida/` | Conteúdo |
|---|---|
| `comissoes_por_lojista.csv` | Uma linha por CNPJ: comissão pela taxa contratada (+ extras `qtd_transacoes`, `ecs`, `cobrado_orbe_brl`) |
| `rastro.csv` | Uma linha por transação da Orbe, com o `id_saida` a que ela pertence. A soma por `id_saida` bate com a saída |
| `pendencias.csv` | O que exige uma pessoa: motivo, valor e quem decide |
| `controle.json` | Totais por tipo, Σ comissões, Σ pendências e diferença de fechamento (tem que ser 0.00) |

## Como rodar do zero

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main --dados data/raw/set2026 --saida saida/
pytest -q
```

**Outubro:** aponte `--dados` para a pasta nova. Os arquivos são achados por padrão de nome (`01_orbe_relatorio_comissoes_*.csv`, `02_tabela_taxas_contratadas*.xlsx`), e o cabeçalho da planilha pela célula "Lojista".

**Chaves necessárias:** nenhuma. Não há IA em tempo de execução; o cálculo é Python com `Decimal`.

## Como o número é calculado

1. **Quem é o lojista:** o EC da Orbe é ligado ao CNPJ pela coluna "EC Orbe" da planilha, ou pelo de-para que o financeiro confirmou (R3). Nunca pelo nome.
2. **Quanto:** valor bruto × taxa contratada vigente na data da venda, arredondado ao centavo por linha (R1, R8). Estorno usa a taxa da venda original (R2); reversão anula a antecipação que ela reverte (R4); Casa do Estudante tem taxa zero de setembro a dezembro (R6).
3. **O que não dá para calcular vira pendência**, com o valor que a Orbe cobrou e quem decide. Não fatura.

As regras ficam em `src/premissas.json`; cada uma cita a resposta do financeiro em `HIPOTESES.md`.

## Código

- `src/leitura.py`: lê Orbe e planilha; normaliza número pt-BR, data, CNPJ e taxa
- `src/cadastro.py`: EC → CNPJ e taxa vigente numa data
- `src/calculo.py`: comissão por linha, pendências, rastro e conferência
- `src/escrita.py`: CSVs no formato fixo
- `src/main.py`: linha de comando
- `tests/test_comissao.py`: controles recalculados a partir do arquivo cru

## Limitações conhecidas

- Só a linha CHECKOUT. Remessa, divergências de taxa, notas fiscais e extratos estão fora deste escopo (a solução completa está na branch `main`).
- Atlas (EC 1076801732) não tem contrato vigente: fica como pendência para o Comercial e não entra na comissão.
- Isenções e de-para de EC estão em `premissas.json`; uma isenção ou EC novo em outubro precisa ser acrescentado lá depois da confirmação do financeiro.
- Comissão negativa (Casa do Estudante, −5,50) é reportada como está; o tratamento na nota (R4) é do nível alvo.
