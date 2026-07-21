"""Portfolio-level arithmetic — value, drawdown, weight, and size→shares.

CR046 M05. These were computed in three places with the same shapes: the sim
portfolio's `total_value`/`total_drawdown_pct` (`schemas/trade.py`), the safety
floor's percent-of-portfolio weight (`agents/safety_floor.py`), and the Room's
size%→share-quantity conversion (`services/room_runner.py`). Centralised here so
the drawdown denominator (the number the whole risk debate is sized against) and
the position weight (the number the single-name cap is enforced on) have one
definition and one guard test.

Pure — primitives in, primitives out. The caller marshals its own objects
(holdings, verdicts) into these shapes; nothing here knows about pydantic models.
"""

from __future__ import annotations

from collections.abc import Iterable


def total_value(cash: float, positions: Iterable[tuple[float, float]]) -> float:
    """Cash + Σ(quantity × mark) over positions. `positions`: (quantity, price) pairs."""
    return cash + sum(quantity * price for quantity, price in positions)


def drawdown_pct(starting_capital: float, current_value: float) -> float:
    """Drawdown vs starting capital as a positive percent (0 when up or flat).

    0.0 when `starting_capital` is non-positive — no meaningful denominator.
    """
    if starting_capital <= 0:
        return 0.0
    return max(0.0, (starting_capital - current_value) / starting_capital * 100)


def position_pct(value: float, portfolio_value: float) -> float:
    """A position's weight as a percent of the portfolio. 0 when total ≤ 0."""
    if portfolio_value <= 0:
        return 0.0
    return value / portfolio_value * 100


def shares_for_size(portfolio_value: float, size_pct: float, entry: float) -> int:
    """Whole shares to put `size_pct`% of the portfolio into a name priced at `entry`.

    `int((portfolio_value × size_pct/100) / entry)`, floored at 1 share so a
    non-zero target size never rounds down to a no-op order. 0 when `entry` is
    non-positive (an unusable price), rather than raising.
    """
    if entry <= 0:
        return 0
    return max(1, int((portfolio_value * size_pct / 100) / entry))
