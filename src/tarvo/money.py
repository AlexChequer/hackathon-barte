"""Utilidades monetárias: tudo com Decimal, ROUND_HALF_UP por linha/operação (R8).

A regra: 0,005 → 0,01; -0,005 → -0,01 (meio centavo arredonda para longe de zero
nos dois sentidos). Arredondamos *por linha/operação* e depois somamos.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
ZERO = Decimal("0")


def q(value: Decimal | int | float | str) -> Decimal:
    """Arredonda monetário para 2 casas, ROUND_HALF_UP (R8)."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def q_mul(amount: Decimal, rate: Decimal) -> Decimal:
    """`round(bruto × taxa, 2)` com HALF_UP. amount já tem sinal; rate é fração (0.0269)."""
    return q(amount * rate)


def sum_q(values) -> Decimal:
    """Soma de valores já arredondados. Preserva Decimal exato."""
    total = ZERO
    for v in values:
        total += v if isinstance(v, Decimal) else Decimal(str(v))
    return total


def pct(fraction: Decimal | None) -> Decimal | None:
    """Fração → percentual exibido (0.0269 → Decimal('2.69'))."""
    if fraction is None:
        return None
    return (fraction * Decimal("100")).quantize(Decimal("0.0001"))
