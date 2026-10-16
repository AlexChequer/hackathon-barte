#!/usr/bin/env bash
# Copia os transcripts do Claude Code deste projeto para PROMPTS/sessoes/<github-user>/
# Uso: ./scripts/export_prompts.sh <github-user>
set -euo pipefail

user="${1:?uso: $0 <github-user>}"
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
project_key="$(echo "$repo_root" | sed 's#[/_.]#-#g')"
src="$HOME/.claude/projects/$project_key"
dest="$repo_root/PROMPTS/sessoes/$user"

if [[ ! -d "$src" ]]; then
  echo "não achei transcripts em $src" >&2
  echo "procure em ~/.claude/projects/ a pasta que termina com o nome do repo" >&2
  exit 1
fi

mkdir -p "$dest"
cp -p "$src"/*.jsonl "$dest"/
echo "copiados $(ls "$dest"/*.jsonl | wc -l | tr -d ' ') transcripts para $dest"

if grep -lE "sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}" "$dest"/*.jsonl; then
  echo "ATENÇÃO: possível chave de API nos arquivos acima. Remova antes de commitar." >&2
  exit 2
fi
