# Tarvo: fechamento mensal

Hackathon Barte AI (17/10/2026). Time: [@AlexChequer](https://github.com/AlexChequer), [@hhenriqueN](https://github.com/hhenriqueN), [@andrespleite](https://github.com/andrespleite).

Motor que fecha o mês da Tarvo Pagamentos a partir dos arquivos **como eles chegam** (portal da Orbe, e-mail da Ponte Câmbio, planilha de taxas, extratos Aurora/Meridiano, plano de contas Fênix). Ele gera em `saida/`:

| Arquivo | Conteúdo | Status |
|---|---|---|
| `comissoes_por_lojista.csv` | Comissão por lojista e linha de negócio | 🚧 |
| `divergencias_taxa.csv` | Taxa contratada × aplicada, transação por transação | 🚧 |
| `notas_a_emitir.csv` | Notas fiscais: tomador, linha e valor | 🚧 |
| `lancamentos_classificados.csv` | Extratos classificados no plano de contas | 🚧 |
| `pendencias.csv` | O que exige uma pessoa: motivo e quem decide | 🚧 |
| `rastro.csv` | Liga cada número de saída às linhas de origem | 🚧 |

## Como rodar do zero

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m tarvo --dados data/raw/set2026 --saida saida
pytest
```

Para outubro, basta apontar `--dados` para a pasta com os arquivos novos, no mesmo formato. Os arquivos são localizados por padrão de nome (`src/tarvo/loaders/__init__.py`).

**Chaves necessárias:** nenhuma por enquanto. Se a classificação por IA entrar, ver `.env.example`.

## Como funciona

1. **Loaders** (`src/tarvo/loaders/`): leem cada fonte sem regra de negócio. Eles normalizam números pt-BR, datas, CNPJ (14 dígitos) e encoding, e guardam a referência da linha de origem.
2. **Motores** (`src/tarvo/engines/`, 🚧): aplicam as regras confirmadas com o financeiro (`HIPOTESES.md`).
3. **Saída** (`src/tarvo/output.py`): escreve no formato fixo do case e confere que cada total bate com a soma do rastro.

## Documentação

- `HIPOTESES.md`: fatos, premissas e perguntas/respostas do financeiro.
- `docs/MAPA_DADOS.md`: o que tem em cada arquivo e as armadilhas encontradas.
- `docs/PERGUNTAS_FINANCEIRO.md`: rascunho das perguntas.
- `docs/PLANO.md`: divisão do time e linha do tempo.
- `docs/case/`: instruções originais do case.
- `PROMPTS/`: histórico das sessões de IA e `MOMENTOS.md`.

## Limitações conhecidas

- _a preencher_
