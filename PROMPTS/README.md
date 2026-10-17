# Histórico de prompts

O case exige o histórico **de todas as sessões de IA**, sem edição. Só podemos remover chaves de API e dados pessoais.

- `sessoes/<github-user>/`: transcripts de cada pessoa.
  - **Claude Code**: `python scripts/exportar_sessoes.py <github-user> --email <seu e-mail>` lê os `.jsonl` deste projeto em `~/.claude/projects/`, mascara o e-mail e para se achar algo com cara de chave de API.
    - Padrão: `.jsonl` legível, sem os prints colados (base64) e sem os registros `api-request` (cópia da requisição a cada turno, sem conversa nova). Uma sessão de 88 MB vira ~12 MB.
    - `--completo`: nada removido além do e-mail, gravado como `.jsonl.gz` (versão "sem edição").
  - **ChatGPT/Claude.ai/Cursor**: link compartilhado ou export colado em `sessoes/<github-user>/links.md`.
- `MOMENTOS.md`: de 2 a 4 momentos-chave.

Exportem **antes das 18h** e rodem `grep -riE "sk-|api[_-]?key" PROMPTS/` antes do commit.
