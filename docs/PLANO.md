# Plano do time

## Regra de ouro
**Mínimo certo > extra errado.** Às 15h30, a comissão de checkout tem que estar fechando com rastro. Senão, todo mundo larga o que está fazendo e ajuda nisso.

## Entregáveis × níveis

| Nível | Entrega | Arquivo em `saida/` |
|---|---|---|
| Mínimo | Comissão de checkout por lojista, com rastro | `comissoes_por_lojista.csv`, `rastro.csv` |
| Alvo | + comissão de remessa, divergências, notas, lançamentos classificados | `divergencias_taxa.csv`, `notas_a_emitir.csv`, `lancamentos_classificados.csv` |
| Extra | + pendências explicadas, rastro completo, roda em outubro sem retrabalho | `pendencias.csv` |

## Divisão sugerida (frentes independentes, juntam no `rastro.csv`)

| Frente | Dono | Escopo | Módulo |
|---|---|---|---|
| A. Checkout | _a definir_ | Orbe × taxas: casar o EC, achar a taxa contratada e a vigência, calcular comissão e divergências | `src/tarvo/engines/checkout.py` |
| B. Remessa | _a definir_ | Ponte: duplicadas, spread negativo, spread contratado, comissão de 50%, notas | `src/tarvo/engines/remessa.py` |
| C. Extratos + entrega | _a definir_ | Classificar Aurora/Meridiano no plano (regra primeiro, IA só no resto), pendências, README, pitch | `src/tarvo/engines/extratos.py` |

Quem fecha uma frente revisa os números da outra. **Ninguém aceita um número sem conferir uma amostra na mão.**

## Linha do tempo (17/10)

| Hora | Marco |
|---|---|
| 16/10, 20h30–22h30 | Mandar as perguntas P0/P1 no #tarvo-financeiro (`docs/PERGUNTAS_FINANCEIRO.md`) |
| 8h | Credenciamento (pontualidade conta **por pessoa**) |
| 9h30 | Construção. Repassar as respostas da noite para `HIPOTESES.md` |
| **11h** | **Checkpoint 1** no thread: o que vamos atacar, hipóteses principais, o que fica de fora |
| 13h | Mínimo pronto: `comissoes_por_lojista.csv` CHECKOUT + rastro batendo |
| **15h30** | **Checkpoint 2**: o que funciona, o que mudou |
| 17h | Congelar features. Só correção, README, MOMENTOS.md e export dos prompts |
| 17h30 | Fim do atendimento do financeiro |
| **18h15** | Último commit + push + checar se o repo está público. **Nada depois das 18h30** |
| 18h30–19h | Pitch (PDF/slides) no #hackathon-entregas |

## Fluxo git
- `main` sempre roda (`python -m tarvo` + `pytest`).
- Branch por frente (`feat/checkout`, `feat/remessa`, `feat/extratos`), PR pequeno, merge rápido.
- **Nunca** editar `data/raw/` (penalizado). Um teste garante que o loader lê o arquivo como ele vem.
