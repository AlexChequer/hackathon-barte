"""Identificação mínima de operador + perfis (R20).

MVP: identidade por header `X-Tarvo-Usuario`, perfil por `X-Tarvo-Perfil`. Autoriza por
perfil, não aceita `aprovado_por` do formulário como aprovação. Para aprovação **externa**
(ex.: Comercial que aprovou por e-mail/Slack), o fluxo registra separadamente quem
aprovou + evidência; a identidade autenticada permanece sendo quem registrou.

Perfis conhecidos:
- `financeiro`: aprova regras de fechamento (R20).
- `comercial`: aprova taxas e condições comerciais (R20).
- `operador`: só registra propostas; nunca aprova.

Config padrão: `config/usuarios.json`. Arquivo ausente = permite registrar como `cli`
(`operador`) para compatibilidade com a CLI, mas aprovação sempre exige perfil cadastrado.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("tarvo.auth")

PERFIS = frozenset({"financeiro", "comercial", "operador"})
APROVA_REGRAS_FECHAMENTO = frozenset({"financeiro"})
APROVA_CONDICAO_COMERCIAL = frozenset({"comercial"})

CAMINHO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "usuarios.json"


@dataclass(frozen=True)
class Usuario:
    """Identificação autenticada; nunca aceita `aprovado_por` do formulário sem checagem."""

    nome: str
    perfil: str


class ErroAutenticacao(ValueError):
    """Credencial ausente, usuário desconhecido ou perfil inválido."""


class SemPermissao(PermissionError):
    """Autenticado, mas sem permissão para a ação pedida."""


def _ler_arquivo(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_usuarios(caminho: Path = CAMINHO_PADRAO) -> dict[str, str]:
    """Mapa nome -> perfil, a partir de config/usuarios.json."""
    bruto = _ler_arquivo(caminho)
    usuarios = {}
    for item in bruto.get("usuarios", []):
        nome = str(item.get("nome", "")).strip()
        perfil = str(item.get("perfil", "")).strip().lower()
        if nome and perfil in PERFIS:
            usuarios[nome] = perfil
    return usuarios


def resolver(nome: str | None, perfil: str | None, caminho: Path = CAMINHO_PADRAO) -> Usuario:
    """Verifica credencial contra `config/usuarios.json`.

    Com arquivo ausente, aceita como operador CLI (não pode aprovar nada). Com arquivo
    presente, exige que (nome, perfil) estejam cadastrados.
    """
    nome = (nome or "").strip()
    perfil = (perfil or "").strip().lower()
    if not nome:
        raise ErroAutenticacao("informe quem está registrando (X-Tarvo-Usuario)")
    if perfil and perfil not in PERFIS:
        raise ErroAutenticacao(f"perfil desconhecido: {perfil!r}; use {sorted(PERFIS)}")
    usuarios = carregar_usuarios(caminho)
    if not usuarios:
        return Usuario(nome=nome, perfil=perfil or "operador")
    cadastrado = usuarios.get(nome)
    if cadastrado is None:
        raise ErroAutenticacao(f"usuário {nome!r} não cadastrado em {caminho.name}")
    if perfil and perfil != cadastrado:
        raise ErroAutenticacao(
            f"perfil {perfil!r} declarado não bate com o cadastrado ({cadastrado!r})"
        )
    return Usuario(nome=nome, perfil=cadastrado)


def exige(usuario: Usuario, perfis: frozenset[str], motivo: str) -> None:
    """Verifica se o usuário tem um dos perfis necessários para `motivo`."""
    if usuario.perfil not in perfis:
        raise SemPermissao(
            f"{motivo} exige perfil em {sorted(perfis)}; usuário {usuario.nome} é {usuario.perfil}"
        )
