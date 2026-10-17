"""Motores de fechamento (um por entregável). Cada motor devolve um objeto EngineResult
com as linhas de cada CSV + rastro, para o orquestrador consolidar."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class EngineResult:
    comissoes: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    divergencias: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    notas: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    lancamentos: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    pendencias: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    rastro: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    diagnosticos: list[dict] = field(default_factory=list)
