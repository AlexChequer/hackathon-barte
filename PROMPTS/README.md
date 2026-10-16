# Histórico de prompts

O case exige o histórico **de todas as sessões de IA**, sem edição. Só podemos remover chaves de API e dados pessoais.

- `sessoes/<github-user>/`: transcripts de cada pessoa.
  - **Claude Code**: `./scripts/export_prompts.sh <github-user>` copia os `.jsonl` desta pasta de projeto em `~/.claude/projects/`.
  - **ChatGPT/Claude.ai/Cursor**: link compartilhado ou export colado em `sessoes/<github-user>/links.md`.
- `MOMENTOS.md`: de 2 a 4 momentos-chave.

Exportem **antes das 18h** e rodem `grep -riE "sk-|api[_-]?key" PROMPTS/` antes do commit.
