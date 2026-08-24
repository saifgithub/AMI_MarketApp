"""Per-structure option strategy arithmetic — CR046 M17, opened for CR172 §5.

Max loss, max gain, break-evens, net debit/credit, collateral requirement
and net greeks for a set of same-expiry option legs. CR172 §10's candidate
generator (`option_strategist`, a later slice) is built on this module: every
number on the yes/no card the user sees traces back here, never to the LLM.

The engine is generic, not per-structure: an expiry payoff over legs is
piecewise linear in the underlying price, so max/min live at the kinks (the
strikes, plus S=0) or at infinity via the terminal slope. That one analysis
covers every same-expiry structure exactly — verticals, condors, straddles,
covered calls — instead of fifteen formulas that can each drift.

**Unbounded is a flag, never a number and never a None-that-means-missing.**
A net-short-call position has unbounded loss; `unbounded_loss=True` says so
explicitly, and CR172 §8 forbids feeding it into any percentage cap. Under
the D3 ruling (2026-08-20) an uncovered short call is FORBIDDEN outright —
this module *marks* it (`has_uncovered_short_call`) so the refusal can
explain why; enforcement belongs to the safety floor, not the math.

Collateral follows CR172 §6's table:
  * long-only structures post nothing (the premium already left);
  * covered calls lock shares, not cash (`shares_locked`);
  * cash-secured puts post `strike × multiplier × contracts` — the premium
    is NOT netted, per the table row, so assignment is fully pre-funded;
  * defined-risk credit structures post worst-case settlement liability
    minus the net credit received (reproduces `width − credit` for a
    vertical and the wider wing for an iron condor);
  * anything containing an uncovered short call has NO collateral figure —
    None plus the flag, because no cash number contains an unbounded loss.

Multi-expiry structures (calendars/diagonals) return None: an expiry payoff
does not exist for them and pretending with the near leg would be a
fabricated figure (CR172 §10 defers them to a term-structure model).

Pure, stdlib-only. Money figures are totals in dollars, rounded to 2 dp;
break-evens are underlying prices, 2 dp.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Iterable, NamedTuple, Sequence

from .greeks import Greeks

_RIGHTS = ("call", "put")


class StrategyLeg(NamedTuple):
    """One leg: signed contract count, premium per share, one expiry."""

    right: str          # "call" | "put"
    strike: float
    quantity: float     # SIGNED contracts: positive long, negative short
    premium: float      # per share, >= 0
    multiplier: float = 100.0
    expiry: str = ""    # ISO date; every leg of a structure must share it


class StrategyMetrics(NamedTuple):
    """The §10 card figures for one structure. Dollars are totals."""

    net_cost: float                    # > 0 debit paid, < 0 credit received
    max_loss: float | None             # None ⇔ unbounded_loss or covered_by_shares
    max_gain: float | None             # None ⇔ unbounded_gain
    unbounded_loss: bool
    unbounded_gain: bool
    break_evens: tuple[float, ...]
    collateral_required: float | None  # None ⇔ has_uncovered_short_call
    has_uncovered_short_call: bool
    shares_locked: float               # shares committed covering short calls
    covered_by_shares: bool            # short calls covered ⇒ loss bounded by
                                       # the stock, not computable from legs alone


def _legs_valid(legs: Sequence[StrategyLeg]) -> bool:
    if not legs:
        return False
    expiries = set()
    for leg in legs:
        values = (leg.strike, leg.quantity, leg.premium, leg.multiplier)
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            return False
        if leg.right not in _RIGHTS or leg.strike <= 0 or leg.premium < 0:
            return False
        if leg.quantity == 0 or leg.multiplier <= 0:
            return False
        if not leg.expiry:
            return False
        expiries.add(leg.expiry)
    return len(expiries) == 1


def _intrinsic(right: str, strike: float, price: float) -> float:
    if right == "call":
        return max(0.0, price - strike)
    return max(0.0, strike - price)


def payoff_at_expiry(
    legs: Sequence[StrategyLeg], price_at_expiry: float
) -> float | None:
    """Total P&L in dollars at expiry, premiums included, or None."""
    if not _legs_valid(legs) or price_at_expiry < 0:
        return None
    return sum(
        leg.quantity * leg.multiplier
        * (_intrinsic(leg.right, leg.strike, price_at_expiry) - leg.premium)
        for leg in legs
    )


def net_cost(legs: Sequence[StrategyLeg]) -> float | None:
    """Cash to open, total dollars: positive = debit paid, negative = credit."""
    if not _legs_valid(legs):
        return None
    return sum(leg.quantity * leg.multiplier * leg.premium for leg in legs)


def combine_greeks(
    leg_greeks: Sequence[tuple[float, float, Greeks]],
) -> Greeks | None:
    """Net position greeks: Σ quantity × multiplier × per-share greeks.

    Input is (signed contract quantity, multiplier, per-share Greeks) per
    leg. Returns None on an empty input — an empty sum is 0.0 exposure, a
    confident claim no caller should get for free.
    """
    if not leg_greeks:
        return None
    totals = [0.0] * len(Greeks._fields)
    for quantity, multiplier, greeks in leg_greeks:
        if not (math.isfinite(quantity) and math.isfinite(multiplier)
                and multiplier > 0):
            return None
        for i, g in enumerate(greeks):
            totals[i] += quantity * multiplier * g
    return Greeks(*totals)


def _terminal_call_slope(legs: Sequence[StrategyLeg]) -> float:
    """dPayoff/dS above every strike: only calls contribute, 1:1."""
    return sum(
        leg.quantity * leg.multiplier for leg in legs if leg.right == "call"
    )


def shares_needed_to_cover_calls(legs: Iterable[StrategyLeg]) -> float:
    """Shares of stock a set of call legs needs in order not to be naked.

    Long calls cover short calls first, one for one; whatever is still short
    after that needs `contracts × multiplier` shares. `0.0` when nothing is
    net short.

    **Extracted so there is exactly one renderer of this rule (DEF098).** It
    was `_collateral`'s opening paragraph, computed once per STRUCTURE — which
    is the right scope for costing a card and the wrong one for asking whether
    a book is covered, because two structures each measured against the same
    100 shares are each individually covered while the portfolio is short 100
    (DEF356, instance 2). `_collateral` still calls it for the per-structure
    figure; `sim_options.uncovered_call_shares` calls it across every open call
    leg on an underlying. Neither re-derives it.

    `legs` need not share an expiry: a short January call is not covered by a
    long March one for *margin* purposes, but this function answers the
    narrower share-cover question the §6 table asks, and both callers pass a
    set that is either one expiry (the structure) or deliberately all of them
    (the book). Multiplier is the max across the call legs — the conservative
    read when a chain has served an adjusted contract.
    """
    call_legs = [leg for leg in legs if leg.right == "call"]
    if not call_legs:
        return 0.0
    short_contracts = -sum(leg.quantity for leg in call_legs if leg.quantity < 0)
    long_contracts = sum(leg.quantity for leg in call_legs if leg.quantity > 0)
    net_short = max(0.0, short_contracts - long_contracts)
    if net_short <= 0:
        return 0.0
    multiplier = max(leg.multiplier for leg in call_legs)
    return net_short * multiplier


def _collateral(
    legs: Sequence[StrategyLeg],
    shares_held: float,
    total_credit: float,
) -> tuple[float | None, bool, float, bool]:
    """(cash_collateral, has_uncovered_short_call, shares_locked, covered).

    Implements the §6 table via one joint worst-case-settlement analysis —
    see the module docstring for how each row falls out of it.

    `shares_held` is what the CALLER says is available to cover, not what the
    portfolio holds. DEF356: a book with two covered calls against one lot has
    100 shares and 0 available to the second of them, and this function cannot
    tell the difference — it sees one structure at a time by design.
    """
    # ── Call cover: long calls first, then held shares, else forbidden ──
    short_call_contracts = -sum(
        leg.quantity for leg in legs if leg.right == "call" and leg.quantity < 0
    )
    long_call_contracts = sum(
        leg.quantity for leg in legs if leg.right == "call" and leg.quantity > 0
    )
    net_short_calls = max(0.0, short_call_contracts - long_call_contracts)
    shares_locked = 0.0
    covered = False
    if net_short_calls > 0:
        shares_needed = shares_needed_to_cover_calls(legs)
        if shares_held + 1e-9 >= shares_needed:
            shares_locked = shares_needed
            covered = True
        else:
            return None, True, 0.0, False

    # ── Cash-secured puts: uncovered short puts post the full strike ──
    # Conservative assignment: the HIGHEST-strike short puts are deemed the
    # uncovered ones, so the posted figure can only over-secure, never under.
    short_puts = sorted(
        (leg for leg in legs if leg.right == "put" and leg.quantity < 0),
        key=lambda leg: leg.strike, reverse=True,
    )
    long_put_contracts = sum(
        leg.quantity for leg in legs if leg.right == "put" and leg.quantity > 0
    )
    uncovered_put_contracts = max(
        0.0, sum(-leg.quantity for leg in short_puts) - long_put_contracts
    )
    csp_cash = 0.0
    csp_exclusion: dict[int, float] = {}  # index in `legs` → contracts excluded
    remaining = uncovered_put_contracts
    for leg in short_puts:
        if remaining <= 0:
            break
        take = min(remaining, -leg.quantity)
        csp_cash += leg.strike * leg.multiplier * take
        csp_exclusion[id(leg)] = take
        remaining -= take

    # ── Share cover allocation: cover the HIGHEST-strike short calls ──
    # (the least liable), so the liability left in the paired set is the
    # maximum — the posted figure can only over-secure, never under.
    share_cover: dict[int, float] = {}  # id(leg) → contracts settled by shares
    if covered:
        cover_remaining = net_short_calls
        for leg in sorted(
            (leg for leg in legs if leg.right == "call" and leg.quantity < 0),
            key=lambda leg: leg.strike, reverse=True,
        ):
            if cover_remaining <= 0:
                break
            take = min(cover_remaining, -leg.quantity)
            share_cover[id(leg)] = take
            cover_remaining -= take

    # ── Paired remainder: worst-case settlement liability minus credit ──
    def paired_settlement(price: float) -> float:
        total = 0.0
        for leg in legs:
            quantity = (
                leg.quantity
                + share_cover.get(id(leg), 0.0)
                + csp_exclusion.get(id(leg), 0.0)
            )
            if quantity == 0:
                continue
            total += quantity * leg.multiplier * _intrinsic(
                leg.right, leg.strike, price,
            )
        return total

    strikes = sorted({leg.strike for leg in legs})
    probes = [0.0, *strikes, strikes[-1] * 2.0]
    worst_liability = max(0.0, max(-paired_settlement(p) for p in probes))
    spread_cash = max(0.0, worst_liability - max(0.0, total_credit))
    return csp_cash + spread_cash, False, shares_locked, covered


def strategy_metrics(
    legs: Sequence[StrategyLeg], shares_held: float = 0.0
) -> StrategyMetrics | None:
    """Every §10 card figure for one same-expiry structure, or None.

    None means the legs are invalid or span multiple expiries — the caller
    renders `not_evaluated`, never a partial card.
    """
    if not _legs_valid(legs):
        return None
    if not (isinstance(shares_held, (int, float)) and math.isfinite(shares_held)
            and shares_held >= 0):
        return None

    cost = net_cost(legs)
    assert cost is not None  # _legs_valid already held

    strikes = sorted({leg.strike for leg in legs})
    kinks = [0.0, *strikes]
    values = [payoff_at_expiry(legs, s) for s in kinks]
    slope = _terminal_call_slope(legs)

    unbounded_gain = slope > 0
    unbounded_loss_raw = slope < 0

    collateral, has_uncovered_short_call, shares_locked, covered = _collateral(
        legs, shares_held, -cost,
    )
    # Share cover converts the unbounded upside loss into stock opportunity
    # cost — bounded, but not computable from the option legs alone (§6).
    unbounded_loss = unbounded_loss_raw and not covered

    finite_values = [v for v in values if v is not None]
    max_loss: float | None
    max_gain: float | None
    if unbounded_loss or covered:
        max_loss = None
    else:
        max_loss = round(max(0.0, -min(finite_values)), 2)
    if unbounded_gain:
        max_gain = None
    else:
        max_gain = round(max(0.0, max(finite_values)), 2)

    # ── Break-evens: zero crossings of the piecewise-linear payoff ──
    break_evens: list[float] = []
    for i in range(1, len(kinks)):
        lo_s, hi_s = kinks[i - 1], kinks[i]
        lo_v, hi_v = values[i - 1], values[i]
        if lo_v is None or hi_v is None or hi_s == lo_s:
            continue
        if lo_v == 0.0 and i == 1:
            break_evens.append(lo_s)
        if (lo_v < 0 < hi_v) or (hi_v < 0 < lo_v):
            crossing = lo_s + (hi_s - lo_s) * (-lo_v) / (hi_v - lo_v)
            break_evens.append(crossing)
        elif hi_v == 0.0:
            break_evens.append(hi_s)
    if slope != 0 and values[-1] is not None and values[-1] != 0.0:
        beyond = strikes[-1] - values[-1] / slope
        if beyond > strikes[-1] and (values[-1] < 0) == (slope > 0):
            break_evens.append(beyond)

    unique_bes = sorted({round(be, 2) for be in break_evens})

    return StrategyMetrics(
        net_cost=round(cost, 2),
        max_loss=max_loss,
        max_gain=max_gain,
        unbounded_loss=unbounded_loss,
        unbounded_gain=unbounded_gain,
        break_evens=tuple(unique_bes),
        collateral_required=(
            None if collateral is None else round(collateral, 2)
        ),
        has_uncovered_short_call=has_uncovered_short_call,
        shares_locked=shares_locked,
        covered_by_shares=covered,
    )


def option_leg_value(
    collateral_posted: float, quantity: float, multiplier: float, mark: float
) -> float:
    """What one OPEN option leg is worth to the portfolio that holds it.

    `collateral + signed_contracts × multiplier × mark`, the exact shape
    `shorts.short_leg` uses and for the identical reason: the cash that left
    at open has to come back somewhere, or opening a position changes
    `total_value` by itself.

    The identity this has to hold, and the whole reason the collateral term
    is here rather than netted somewhere else — at open, cash falls by
    `net_cost + collateral` and this term rises by exactly the same amount,
    because `Σ q × multiplier × premium` IS `net_cost`. So a structure opened
    at its own mid leaves the portfolio's total unchanged, and a NAV series
    does not show a loss for having traded. At settlement the same identity
    runs backwards: `option_lifecycle.settlement_effect` credits
    `collateral_posted + sign × value_total` and closes the leg, which
    removes precisely this term.

    Signed quantity carries the short side, so no branch is needed: a short
    leg's term is negative and grows more negative as the mark rises, which
    is what being short costs.
    """
    return collateral_posted + quantity * multiplier * mark


def option_legs_value(
    legs: Iterable[tuple[float, float, float, float]]
) -> float:
    """Σ `option_leg_value` over (collateral, quantity, multiplier, mark)."""
    return sum(option_leg_value(c, q, m, k) for c, q, m, k in legs)


# ── CR172 §9 — the portfolio-level option caps (D5: four of six) ────────────
#
# Each is a BOOK-level figure: the proposed structure plus everything already
# open. A cap applied to one structure at a time is not a cap — a user refused
# one 5%-of-NAV position opens five of them.
#
# `max_portfolio_delta` and `max_portfolio_vega` are deliberately NOT here.
# They need full-portfolio greek aggregation, which does not exist, and D5
# (ruled 2026-08-24) defers them to their own CR rather than shipping two caps
# that cannot be computed beside four that can.


class OptionBookExposure(NamedTuple):
    """The three dollar figures the §9 percentage caps are measured against.

    Dollars, not percentages: the cap compares them to NAV, and keeping the
    division at the comparison site means there is exactly one place a zero or
    negative NAV has to be handled.
    """

    premium_at_risk: float
    """Net debit paid across the book. A credit structure contributes 0 rather
    than a negative: premium *received* is not premium *at risk*, and letting
    it offset a debit elsewhere would let a user fund an unlimited long book by
    writing options — which is the opposite of what a theta cap is for."""

    gross_notional: float
    """`Σ |quantity| × strike × multiplier` — the §9 formula verbatim. Gross,
    so a long and a short leg on the same strike do not cancel: both can be
    assigned or exercised, and the cap asks how much contract the user is
    standing behind, not what nets out on paper."""

    assignment_exposure: float
    """Cash required if every SHORT PUT were assigned today.

    Short calls are excluded, and that is not an omission: an uncovered short
    call is refused outright by D3, and a covered one needs no cash — the
    shares are already posted. So the only assignment that can demand money is
    a short put, at `strike × multiplier × |contracts|`."""


def _leg_notional(leg: StrategyLeg) -> float:
    return abs(float(leg.quantity)) * float(leg.strike) * float(leg.multiplier)


def book_exposure(
    proposed: Sequence[StrategyLeg],
    existing: Sequence[Sequence[StrategyLeg]] = (),
) -> OptionBookExposure:
    """The book's option exposure if `proposed` were opened on top of `existing`.

    `existing` is a sequence of STRUCTURES (each a sequence of legs), not a
    flat leg list, because `premium_at_risk` is only meaningful per structure.
    Netting debit against credit across the whole book would let a user fund a
    long position by writing options elsewhere — the exact thing a theta cap
    exists to stop — while netting *within* a structure is simply correct: a
    bull call spread's premium at risk IS its net debit, not its long leg's
    full premium.

    Pure. Takes legs rather than a portfolio so the floor, the strategist's
    candidate marking and any test ask the same question of the same
    arithmetic — one derivation, per CR046.
    """
    structures: list[Sequence[StrategyLeg]] = [*existing, proposed]
    all_legs = [leg for s in structures for leg in s]

    def _net_debit(legs: Sequence[StrategyLeg]) -> float:
        return math.fsum(
            float(l.quantity) * float(l.premium) * float(l.multiplier) for l in legs
        )

    return OptionBookExposure(
        # Each structure floored at zero INDEPENDENTLY, then summed.
        premium_at_risk=math.fsum(max(0.0, _net_debit(s)) for s in structures),
        gross_notional=math.fsum(_leg_notional(l) for l in all_legs),
        assignment_exposure=math.fsum(
            _leg_notional(l)
            for l in all_legs
            if l.right == "put" and float(l.quantity) < 0
        ),
    )


def min_days_to_expiry(
    legs: Sequence[StrategyLeg], today: date,
) -> int | None:
    """Days to the SOONEST expiry among `legs`, or None if none parses.

    The soonest, because that is the leg that stops existing first — judging a
    calendar spread by its far leg would wave through a structure half of which
    expires tomorrow. None (not 0) when no leg carries a readable expiry, so a
    caller cannot mistake "unknown" for "expires today"; the 0DTE cap then has
    to say it could not evaluate rather than refuse or permit on a guess.
    """
    days: list[int] = []
    for leg in legs:
        raw = (leg.expiry or "").strip()
        if not raw:
            continue
        try:
            days.append((date.fromisoformat(raw) - today).days)
        except ValueError:
            continue
    return min(days) if days else None
