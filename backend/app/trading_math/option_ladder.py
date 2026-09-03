"""CR197 — the sized-option ladder the Chief Investment Officer chooses from.

The RISK phase's measured job is not persuasion. Replaying 136 committed convenes
with the debate stripped from the CIO's prompt dropped approvals from 16.3% to 7.4%
(p=0.004), and reading the transcripts showed why: without the risk officers the CIO
sees only the Execution Desk's single take-it-or-leave-it size, finds the risk/reward
wanting, and passes. With them it has a menu — and it picks off that menu, landing on
a computed ladder value in 32 of 43 baseline approvals (74%), interpolating in the
rest.

So the debate's contribution to the DECISION is a table: a few candidate sizes with
their consequences attached. That is arithmetic, and this module does it.

Why move it out of the prompt entirely: the sizes were never the model's to invent —
`risk_debator_sizes` computes them in code and hands each officer the figure to argue.
What the model added was the arithmetic *about* them, and it has been getting that
wrong for four defects running (DEF066's ~20x stop-distance-vs-cap overstatement that
made 16 of 64 benchmark names un-buyable; DEF235; DEF241; CR166 Tier D). CR154's
hand-read found 4 of 9 numeric cap-consumption claims wrong, one reproducing DEF066's
exact error with DEF066's own warning rendered in the same prompt. `failure_patterns`
P5 is explicit that an LLM asked to compute a number it presents as fact is the defect,
not the agent that happened to do it.

Every figure here is computed from the same functions the safety floor enforces
against, so the menu cannot drift from the ceilings that will judge the choice.

This module decides nothing. It offers options; `enforce_safety_floor` remains the
only vetoer (DEF059), and the risk-tier clamp still bounds whatever the CIO picks.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.trading_math.risk import drawdown_contribution
from app.trading_math.sizing import SINGLE_NAME_ABSOLUTE_CAP_PCT, risk_debator_sizes


@dataclass(frozen=True)
class LadderOption:
    """One rung: a size, and what taking it costs against the mandate's ceilings."""

    label: str
    size_pct: float
    contribution_pts: float | None = None
    share_of_cap_pct: float | None = None
    headroom_after_pts: float | None = None
    reward_risk: float | None = None
    # CR219 R59-§13(a) — the SAME rung's risk, in dollars against the run's own
    # portfolio value, so no downstream agent has to multiply `contribution_pts`
    # by a portfolio value it was handed separately (and has repeatedly gotten
    # wrong doing so by hand — DEF066/DEF235/DEF241/CR166 Tier D). None, never
    # 0.0, when either factor is unusable: see `build_option_ladder`'s docstring.
    dollar_risk_usd: float | None = None


def reward_to_risk(entry: float, stop: float, target: float) -> float | None:
    """Reward-to-risk at a given level triple, or None when the triple is incoherent.

    Deliberately returns None rather than a large number for a stop at or above
    entry: that is a malformed proposal, and a ratio computed from it would be a
    fabricated reassurance rather than a measurement.
    """
    if not (entry > 0 and 0 < stop < entry and target > entry):
        return None
    return (target - entry) / (entry - stop)


def build_option_ladder(
    *,
    reference_size_pct: float,
    entry: float,
    stop: float,
    target: float | None = None,
    cap_pts: float,
    current_drawdown_pct: float | None = None,
    backstop_pct: float = SINGLE_NAME_ABSOLUTE_CAP_PCT,
    portfolio_value: float | None = None,
) -> list[LadderOption]:
    """The candidate sizes plus their computed consequences, smallest first.

    The rungs are exactly `risk_debator_sizes` — the same spread the three risk
    officers are handed to argue — so the menu and the debate cannot disagree about
    what the options are, and swapping one for the other changes only who does the
    arithmetic.

    `current_drawdown_pct` is honoured the way `_headroom_after_clause` honours it
    (CR040/DEF053): None means the caller never supplied what has already been spent,
    so `headroom_after_pts` stays None rather than assuming a flat book. A fabricated
    "effectively empty" reading is exactly what DEF292 found.

    `portfolio_value` is optional and follows the SAME discipline (CR219 R59-§13(a)):
    a figure this function cannot honestly compute stays None rather than defaulting
    to a fabricated $0 — see `_cap_in_shares_clause` (`room_prompts.py`) for the
    identical "missing/zero input renders nothing" call made for the same reason.
    When supplied and positive, `dollar_risk_usd` is `portfolio_value *
    contribution_pts / 100` per rung — the same expression already computed once,
    for one size only, at `room_runner.py`'s option-strategist budget site — so every
    rung carries its own dollar risk and no downstream agent has to multiply it out
    by hand.
    """
    spread = risk_debator_sizes(reference_size_pct, backstop=backstop_pct)
    rr = reward_to_risk(entry, stop, target) if target is not None else None
    has_portfolio_value = portfolio_value is not None and portfolio_value > 0

    rows: list[LadderOption] = []
    for label, size in (
        ("trim", spread.conservative),
        ("reference", spread.neutral),
        ("press", spread.aggressive),
    ):
        dc = drawdown_contribution(size, entry, stop)
        contribution = dc.contribution_pts if dc else None
        share = (
            (contribution / cap_pts * 100)
            if (contribution is not None and cap_pts > 0)
            else None
        )
        headroom = (
            (cap_pts - float(current_drawdown_pct) - contribution)
            if (contribution is not None and cap_pts > 0 and current_drawdown_pct is not None)
            else None
        )
        dollar_risk = (
            round(float(portfolio_value) * contribution / 100.0, 2)
            if (contribution is not None and has_portfolio_value)
            else None
        )
        rows.append(
            LadderOption(
                label=label,
                size_pct=size,
                contribution_pts=contribution,
                share_of_cap_pct=share,
                headroom_after_pts=headroom,
                # R:R is a property of the level triple, not of the size — it is
                # carried on each row because the row is what the reader compares,
                # and repeating it is cheaper than a footnote they must join.
                reward_risk=rr,
                dollar_risk_usd=dollar_risk,
            )
        )
    return rows


# The rendering half deliberately lives in `room_prompts`, not here: the share-of-cap
# wording is owned by `_share_of_cap_phrase`, whose one-decimal floor is DEF292's fix
# for a `:.0f` that printed "(~0% of it)" for 40 nonzero contributions — the line an
# Aggressive debator read as "the risk budget is effectively empty and ours to fill".
# A second formatter here would be a second chance to reintroduce exactly that.
