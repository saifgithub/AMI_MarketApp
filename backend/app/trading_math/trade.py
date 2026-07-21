"""Trade-geometry math — the numbers that follow from an entry/stop/target.

Everything here is a finished figure derived from the three price levels a long
setup is defined by. The Room used to let the LLM assert these (a Trader claiming
"R:R = 3:1" whose own levels implied 1.5:1; a Research Manager stating a fixed
"28% upside vs 18% downside" for every ticker) — CR046 M06 (`risk_reward`) and M08
(`trade_asymmetry`) compute them instead, and `rr_is_coherent` lets a caller check
a *stated* ratio against the one the levels actually imply.

Long setups only (the app is buy-side): a valid setup has `stop < entry < target`.
Anything else returns None so the caller omits the figure rather than emitting a
negative or nonsensical ratio.

Pure — floats in, a float or a small NamedTuple out.
"""

from __future__ import annotations

from typing import NamedTuple


def risk_reward(
    entry: float | None, stop: float | None, target: float | None
) -> float | None:
    """Reward-to-risk ratio (the R in "R:R = R:1") for a long setup, 1 dp.

    `(target − entry) / (entry − stop)`. Returns None unless both the reward
    (target above entry) and the risk (stop below entry) are positive — a setup
    with a stop at/above entry or a target at/below entry has no meaningful R:R.
    """
    if entry is None or stop is None or target is None:
        return None
    reward = target - entry
    risk = entry - stop
    if reward <= 0 or risk <= 0:
        return None
    return round(reward / risk, 1)


class TradeAsymmetry(NamedTuple):
    """Upside/downside of a long setup, each as a percent of entry."""

    upside_pct: float  # (target − entry) / entry × 100
    downside_pct: float  # (entry − stop) / entry × 100


def trade_asymmetry(
    entry: float | None, stop: float | None, target: float | None
) -> TradeAsymmetry | None:
    """Upside% and downside% of a long setup, relative to entry (1 dp each).

    Returns None unless `0 < stop < entry < target`, so the figure is only stated
    for a coherent long setup.
    """
    if entry is None or stop is None or target is None:
        return None
    if not (0 < stop < entry < target):
        return None
    upside = round((target - entry) / entry * 100, 1)
    downside = round((entry - stop) / entry * 100, 1)
    return TradeAsymmetry(upside, downside)


def rr_is_coherent(
    entry: float | None,
    stop: float | None,
    target: float | None,
    stated_rr: float | None,
    tol: float = 0.3,
) -> bool:
    """Does a *stated* R:R match the one `entry/stop/target` actually imply?

    True only when both the implied ratio and the stated ratio exist and differ by
    no more than `tol`. A caller uses this to flag a verdict whose narrated R:R
    contradicts its own levels. A missing stated ratio or an incoherent setup is
    not coherent (False), never a silent pass.
    """
    implied = risk_reward(entry, stop, target)
    if implied is None or stated_rr is None:
        return False
    return abs(implied - stated_rr) <= tol
