"""CR109 slices 2+3 — the game's tunable constants and their pure functions.

implementation_plan.md §5: this module owns EVERY tunable constant the game
economy needs, each documented with why that number — nothing anywhere else
hand-copies it — and §18 of the design is meant to be generated from here
rather than five documents agreeing by hand.

Slice 2 shipped one family: the trading cost. Slice 3 (this file) adds the
finish stipend, the alpha->points curve, the achievable-benchmark discount,
cadence weighting, and the pure math behind the two private mirrors
(wildness index, the "held your first picks" counterfactual) — everything
the SETTLING -> CLOSED scoring pass (`games_scoring_pass.py`) needs that has
no business touching the DB itself.

Pure — no DB, no network — matching `trading_math/twr.py`'s contract. Every
TWR/alpha value in and out of this module is a FRACTION (0.02, not 2.0 or
"2%"); callers convert to a percent only at the point they store or render
one, matching `trading_math/twr.time_weighted_return`'s own convention.
"""

from __future__ import annotations

import statistics
from datetime import date
from typing import Mapping, NamedTuple, Sequence

# ── Trading cost (Amendment D) ──────────────────────────────────────────
#
# 10 bps of notional, floored at 1.00 AMI Cash, charged on BOTH sides of a
# fill (buy AND sell) — never on a training-path trade. BURNED: the fee
# reduces the trader's own cash and is credited to nothing. No table, no
# counter, no field total may ever accumulate it (§7.2 fence of the
# implementation plan — a pool of forfeited/farmed fees is a wagered
# stake, and that is the thing that would break CR109 §15's simulation-
# only legal position). `SimEngine._execute_fill()`'s `fee` parameter
# defaults to 0.0 and only `games_service.py`'s game trade path ever
# passes a non-zero value — see `test_games_trading_cost.py`.
FEE_BPS = 10.0
FEE_MIN = 1.00


def trade_fee(notional: float) -> float:
    """FEE_BPS of `notional`, floored at FEE_MIN, rounded to cents.

    `notional` is expected non-negative (fill_price * quantity); `abs()`
    is defensive only — there is no such thing as a free or negative cost,
    so a malformed caller still pays the floor rather than nothing.
    """
    bps_fee = abs(notional) * (FEE_BPS / 10_000.0)
    return round(max(bps_fee, FEE_MIN), 2)


# ── Short-selling cost (Amendment G) ────────────────────────────────────
#
# 30 bps — Saiful, 2026-08-11: *"we will need to add a 'fee' for short
# selling. lets set it at 0.3% for now."* Charged ONCE, on the leg that
# OPENS the short, and REPLACING the ordinary `FEE_BPS` on that leg rather
# than stacking on top of it: a short's open pays 0.3%, not 0.4%.
#
# Why a one-time charge and not a daily borrow accrual. In the real market
# this cost is a rate per year on stock that must be located and lent, and
# there is no free source that publishes a per-ticker number — inventing
# one would be exactly the fabrication CR040 exists to prevent. A flat
# charge at open is the honest version: it is not pretending to be a
# measured borrow rate, and over a one-week run a rate-based accrual on a
# liquid name would round to pennies anyway. The number that matters to a
# player is that shorting costs THREE TIMES what going long costs, and
# they see it on the ticket before they confirm.
#
# BURNED, exactly like `trade_fee` — see that constant's fence.
#
# The COVER pays the ordinary `FEE_BPS`: closing a short is economically an
# ordinary fill, and charging the short premium twice would make the round
# trip cost 0.6% for no stated reason.
SHORT_FEE_BPS = 30.0


def short_open_fee(notional: float) -> float:
    """SHORT_FEE_BPS of `notional`, floored at FEE_MIN, rounded to cents.

    Shares `trade_fee`'s floor deliberately — the $1 minimum is a
    per-fill cost floor, not a property of going long, so a tiny short
    does not become the cheapest way to trade.
    """
    bps_fee = abs(notional) * (SHORT_FEE_BPS / 10_000.0)
    return round(max(bps_fee, FEE_MIN), 2)


# ── Cadence weighting (§6.3) ────────────────────────────────────────────────
#
# Gains scale with committed time; losses with its SQUARE ROOT. The asymmetry
# is the design's, and it is deliberate in both directions: a long *bad* run is
# mostly market conditions, a long *good* run is hard to fake, and a player
# should not be crushed for having stayed invested through a bear half-year.
#
# The loss row is sqrt of the gain row — sqrt(52) ~ 7.2 — so it is one number
# retunable from real data without touching anything else.
#
# Balance check from §6.3, which is what stops either cadence becoming a farm:
#   win the year at Analyst  = 100 x 52 x 1.4 = +7,280
#   win 52 weeks at Analyst  = 100 x  1 x 1.4 x 52 = +7,280
CADENCE_GAIN_WEIGHT: dict[str, float] = {
    "week": 1.0, "month": 4.0, "quarter": 13.0, "half": 26.0, "year": 52.0,
}
CADENCE_LOSS_WEIGHT: dict[str, float] = {
    "week": 1.0, "month": 2.0, "quarter": 3.6, "half": 5.1, "year": 7.2,
}


def cadence_weight(cadence: str, *, negative: bool) -> float:
    """The §6.3 asymmetric cadence multiplier — gains scale with committed
    time, losses with its square root. Unknown cadences default to 1.0
    rather than raising: this is a scoring detail, not a validation gate,
    and slice 3 only ever calls it with "week"."""
    table = CADENCE_LOSS_WEIGHT if negative else CADENCE_GAIN_WEIGHT
    return float(table.get(cadence, 1.0))


# ── Duel deltas (§11.1, slice 3b) ───────────────────────────────────────
#
# §21's "numbers still to set" list carries *"Duel career-point deltas by
# cadence"* — the design deliberately left the magnitude open. These are the
# first values, and the shape matters more than the numbers:
#
# **Symmetric.** The winner gains exactly what the loser loses. §4.1's
# one-live-run-per-cadence rule exists to close the parallel-entry farm, and
# that farm is created by placement's `+100 / −40` ASYMMETRY — parallel
# entries are +EV only because a win pays 2.5× what a loss costs. A
# zero-sum delta makes a parallel duel exactly EV-neutral, which is what
# lets a duel run ALONGSIDE an open-field run instead of consuming its slot.
# Any future retune must keep win and loss equal, or that argument fails and
# the one-per-cadence cap becomes load-bearing for integrity rather than for
# attention.
#
# **Modest, and far below placement.** A weekly duel pays 10 against
# placement's ~100 ceiling. The duel is the format that WORKS at alpha field
# sizes (§11.1), which means most early points would come from it — and a
# format that pays more than the open board would teach players to avoid the
# board this game is actually about.
#
# **Monotonic in committed time, and MUCH flatter than the gain row above.**
# `CADENCE_GAIN_WEIGHT` runs 1 -> 52; applying that here would pay 520 for
# one annual duel, five times the maximum in the game. A duel is one
# comparison against one opponent no matter how long it ran, so its value
# grows with commitment but nothing like linearly.
DUEL_POINTS: dict[str, int] = {
    "week": 10, "month": 20, "quarter": 30, "half": 40, "year": 50,
}


def duel_points(cadence: str) -> int:
    """The symmetric delta for one settled duel. Unknown cadences fall to the
    weekly value rather than raising — same posture as `cadence_weight`, and
    a duel that scored zero because of an unrecognised string would be a
    silent no-op on a result the player watched happen."""
    return int(DUEL_POINTS.get(cadence, DUEL_POINTS["week"]))


def cadence_period_key(cadence: str, starts_on: date) -> str:
    """The finish-stipend's "once per cadence PERIOD, not once per entry"
    guard (design §6.5's fourth condition) needs a key that is the SAME for
    every field of one cadence covering the same calendar period, and
    DIFFERENT across periods.

    Each cadence keys off its OWN period boundary. Using ISO week for
    everything would collapse twelve monthly periods a year into fifty-two
    keys — the stipend would then be claimable weekly on a monthly run, which
    is exactly the farm this guard exists to close.
    """
    if cadence == "month":
        return f"{cadence}:{starts_on.year}-{starts_on.month:02d}"
    if cadence == "quarter":
        return f"{cadence}:{starts_on.year}-Q{(starts_on.month - 1) // 3 + 1}"
    if cadence == "half":
        return f"{cadence}:{starts_on.year}-H{1 if starts_on.month <= 6 else 2}"
    if cadence == "year":
        return f"{cadence}:{starts_on.year}"
    iso_year, iso_week, _ = starts_on.isocalendar()
    return f"{cadence}:{iso_year}-W{iso_week:02d}"


# ── The finish stipend (§6.5) — ships WITH the fee, never without. ~5 per
# weekly finish; scaled by the SAME cadence weight the fee's pair (alpha)
# uses, so a longer cadence's stipend scales the same way its points do.
FINISH_STIPEND = 5


def finish_stipend(cadence: str) -> int:
    """Fixed career-point award for FINISHING a run. The four eligibility
    guards (entered, >= 1 executed trade, not forfeited, held to close) and
    the fifth (once per cadence period) are the CALLER's job
    (`games_scoring_pass.py` / `career_ledger.post_career_event`) — this
    function only answers "how much", never "is this run eligible"."""
    return round(FINISH_STIPEND * cadence_weight(cadence, negative=False))


# ── The achievable benchmark (§6.6.2) — correcting the fee's hidden tax.
# Holding the index INSIDE the game costs exactly one fill (runs end
# marked, not liquidated — §5.2), so the fair SCORING yardstick is the
# benchmark bearing that same one-fill cost. Reuses FEE_BPS rather than a
# second constant: at the fixed $10,000 stake every run opens with, 10bps
# of notional is $10.00 — comfortably clear of FEE_MIN's $1 floor — so the
# haircut is exactly FEE_BPS expressed as a fraction, independent of the
# benchmark's own return. The Close DISPLAYS the gross comparison — see
# `alpha_display_pct` in `games_scoring_pass.py` — this function is the
# SCORING leg only.
def achievable_benchmark(benchmark_twr: float) -> float:
    """The benchmark's TWR net of the one entry fee a player pays to hold
    it. `benchmark_twr` and the return are both FRACTIONS."""
    return benchmark_twr - (FEE_BPS / 10_000.0)


# ── The alpha -> points formula (§6.6.1). Same 2.5:1 asymmetry as
# placement (never built this slice — see the `n < 8` fence in
# implementation_plan.md §7.2), same convex-top/shallow-linear shape,
# clamped at +/-1 so no alpha outcome ever pays more than winning a field
# outright (placement's own base tops out at +100 for p=1.0).
#
# ALPHA_FULL is the alpha that pays a FULL win (a=1.0, base=100) — sized so
# a "typical good week" (design's own phrase, ~+1-2% excess) pays in the
# placement table's "good finish" range rather than either trivially or
# maximally: at ALPHA_FULL=0.03, +1% excess -> a=0.333 -> base ~= 19.2
# (between placement's rank-15 and rank-10 rows); +2% excess -> a=0.667 ->
# base ~= 54.4 (matches placement's rank-6 row, +53). Retuning this one
# constant is the ENTIRE mechanism for shifting that calibration.
ALPHA_FULL = 0.03


def alpha_to_points(alpha: float) -> float:
    """Alpha (a FRACTION, e.g. 0.02 for +2% excess) -> base career points,
    BEFORE cadence weight, the negative-TWR partial-credit multiplier, and
    title multiplier (title multiplier is 1.0 through slice 4 — titles
    don't exist yet)."""
    if ALPHA_FULL <= 0:
        return 0.0
    a = max(-1.0, min(1.0, alpha / ALPHA_FULL))
    if a >= 0:
        return 100.0 * (a ** 1.5)
    return -40.0 * abs(a)


# ── §6.5's ×0.5 partial-credit rule: top of the field in a bear run still
# scores, at half — progression never stalls through a downturn, but
# losing money never pays like winning. Gated on the RUN's own absolute
# TWR, independent of alpha's sign (a run can beat the benchmark while
# still being underwater).
NEGATIVE_TWR_PARTIAL_CREDIT = 0.5


def apply_negative_twr_partial_credit(points: float, run_twr: float) -> float:
    """`run_twr` is a FRACTION. Halves `points` (whatever its sign) when the
    run's own absolute TWR is negative; a no-op otherwise."""
    return points * NEGATIVE_TWR_PARTIAL_CREDIT if run_twr < 0 else points


# ── Placement (§6.2, slice 4) — the scoring basis the whole design was
# built around, and the one the alpha path above stands in for until a
# field is big enough to carry it.
#
# `p = (n - rank) / (n - 1)`, over the WHOLE open field. 1.0 = first,
# 0.0 = last. Points off placement rather than off the percentage because
# placement cancels the market out for free: everyone in a field faced the
# same one, so the Record stores skill instead of *when you happened to
# play* (§6.2's "load-bearing choice").
#
# The two thresholds below are the design's own first cut (§6.6), and they
# are FENCES, not preferences:
#
# `PLACEMENT_MIN_FIELD = 8` — §6.6 problem 1 is that the formula is
# UNDEFINED at n=1 (division by zero) and degenerate at n=2, where it is
# exactly 1.0 or 0.0: maximum payout or maximum debit on a coin flip. And
# problem 2 is that first-of-one pays the largest prize in the game for
# beating nobody. `placement_p` refuses below the threshold rather than
# returning a number, because every caller that could ask is a caller that
# would otherwise write that number into a permanent Record.
#
# `TITLE_MIN_FIELD = 20` — "prestige needs witnesses" (§6.6). A thin field
# still SCORES (via the alpha path); it just cannot advance a title.
PLACEMENT_MIN_FIELD = 8
TITLE_MIN_FIELD = 20


def placement_p(rank: int, n: int) -> float:
    """Position in the field as a [0, 1] fraction — 1.0 first, 0.0 last.

    Raises below `PLACEMENT_MIN_FIELD` rather than degrading. This is the
    one function in the module that refuses instead of falling back, and
    deliberately so: `cadence_weight` and `duel_points` default on an
    unknown *string* (a scoring detail), whereas an out-of-range `n` here
    is the design's own named hole. A silent fallback would put a maximum
    win on a field of one — the exact farm §6.6 exists to close — and it
    would do it invisibly, which is the CR040 class.
    """
    if n < PLACEMENT_MIN_FIELD:
        raise ValueError(
            f"placement needs n >= {PLACEMENT_MIN_FIELD}, got {n} — "
            "thin fields score on the benchmark path (§6.6)"
        )
    if not 1 <= rank <= n:
        raise ValueError(f"rank {rank} outside a field of {n}")
    return (n - rank) / (n - 1)


def placement_to_points(p: float) -> float:
    """`p` -> base career points, BEFORE cadence weight, the ×0.5
    partial-credit rule and the title multiplier.

        p >= 0.5   +100 x ((p - 0.5) x 2) ^ 1.5     convex — the very top
                                                     is worth a lot
        p <  0.5   - 40 x ((0.5 - p) x 2)           linear and shallow

    Winning is worth 2.5x what losing costs, and the damping lives in the
    curve rather than being bolted on afterwards. Same shape and same
    2.5:1 asymmetry as `alpha_to_points`, which is what makes the two
    bases comparable when a player's history crosses the `n >= 8`
    threshold mid-career.
    """
    p = max(0.0, min(1.0, p))
    if p >= 0.5:
        return 100.0 * (((p - 0.5) * 2.0) ** 1.5)
    return -40.0 * ((0.5 - p) * 2.0)


# ── Titles (§6.4) — thresholds on the RUNNING career-point total, never a
# promotion event. Saiful spotted why: with rolling starts there is no
# synchronized boundary to promote on, which is precisely what the shipped
# `league_service.weekly_roll()` relied upon. Relegation is just the total
# falling back through a threshold — no roll, no cohort assembly, no event.
#
# Rung 2 is a MILESTONE, not a number (Amendment D correction 3): three
# finished runs, none forfeited. The review found the goal gradient never
# engages otherwise — a consistently-75th-percentile player needs ~14 weeks
# to reach Analyst and the median player never arrives at all — and its own
# proposed 100-point rung would have been twenty finishes at the stipend's
# sizing. Lowering the gate beats raising the stipend, which would break the
# anti-farm guard. It fires once, so it cannot be farmed.
#
# NAMING: the design left rung 2 deliberately unnamed (§6.4's table reads
# *"(new rung — unnamed, §18.1)"*). Saiful named it **`runner`**, 2026-08-12,
# choosing it over `associate` and `junior` — both of which name a seniority
# step. `runner` names the BEHAVIOUR the rung actually rewards: finishing
# what you start. It is the one rung on the ladder that is not a rank, and
# the only one earned by a milestone rather than a number, so breaking the
# desk register here is the point rather than a cost.
TITLE_APPRENTICE = "apprentice"
TITLE_RUNG_TWO = "runner"

TITLE_MULTIPLIER: dict[str, float] = {
    "apprentice": 1.0,
    "runner": 1.2,
    "analyst": 1.4,
    "trader": 1.6,
    "senior": 1.8,
    "floor_veteran": 2.0,
}

# Points thresholds for rungs 3+. Rung 2 is absent on purpose — it is the
# milestone above, and putting a number here would let it be reached two
# different ways.
TITLE_POINT_THRESHOLDS: list[tuple[int, str]] = [
    (30_000, "floor_veteran"),
    (10_000, "senior"),
    (2_500, "trader"),
    (500, "analyst"),
]

MILESTONE_FINISHED_RUNS = 3


def title_for(
    *,
    career_points: int,
    finished_runs: int,
    forfeits: int,
    qualifying_finishes: int = 0,
) -> str:
    """The title a player holds RIGHT NOW, derived from their totals — never
    stored as a promotion, so there is nothing to roll and nothing to keep
    in sync.

    Points thresholds win over the milestone when both are met, because the
    ladder must be monotonic in points: a player at 600 who happens to have
    forfeited once is an Analyst, and demoting them to Apprentice for it
    would make the ×1.4 multiplier depend on a fact the points already
    priced.

    `qualifying_finishes` is the count of finished runs in fields that
    cleared `TITLE_MIN_FIELD` — §6.6's *"a thin field can score, but a title
    needs a minimum field. Prestige needs witnesses."* The NAMED rungs
    require one; **the milestone rung does not**, and that exemption is a
    reading rather than a quotation, so it is stated here rather than
    buried: Amendment D created rung 2 specifically for the early player in
    a thin field, whose goal gradient never engages otherwise. Gating it on
    a 20-entrant field would freeze every alpha player at apprentice — the
    exact outcome the rung was added to prevent — while gating the named
    rungs is what §6.6's sentence is actually about.
    """
    if qualifying_finishes >= 1:
        for threshold, title in TITLE_POINT_THRESHOLDS:
            if career_points >= threshold:
                return title
    if finished_runs >= MILESTONE_FINISHED_RUNS and forfeits == 0:
        return TITLE_RUNG_TWO
    return TITLE_APPRENTICE


def next_title_goal(
    *,
    career_points: int,
    finished_runs: int,
    forfeits: int,
    qualifying_finishes: int = 0,
) -> dict | None:
    """The rung above the one currently held and what it still needs, or
    `None` at the top of the ladder.

    Exists because of Amendment D correction 3's actual finding: the problem
    was never that progression was slow, it was that the median player could
    not SEE one. A running total that moves on placement noise tells them
    nothing about where they are going; this states the target and the
    distance in the unit that closes it.
    """
    held = title_for(
        career_points=career_points, finished_runs=finished_runs,
        forfeits=forfeits, qualifying_finishes=qualifying_finishes,
    )
    if held == TITLE_APPRENTICE and forfeits == 0:
        return {
            "title": TITLE_RUNG_TWO,
            "requirement": "finished_runs",
            "remaining": max(0, MILESTONE_FINISHED_RUNS - finished_runs),
        }
    ladder = sorted(TITLE_POINT_THRESHOLDS)  # ascending by threshold
    for threshold, title in ladder:
        if career_points < threshold:
            return {
                "title": title,
                "requirement": "career_points",
                "remaining": threshold - career_points,
            }
    return None


def title_multiplier(title: str | None) -> float:
    """Unknown or missing title -> 1.0, the apprentice value. A run whose
    stored multiplier could not be resolved must score as though it had no
    title, never as zero: zeroing it would silently delete a real result."""
    return float(TITLE_MULTIPLIER.get(title or "", 1.0))


# ── The minimum forfeit debit (§18's churn hole) ──────────────────────────
#
# The debit for forfeiting is placement-based, so forfeiting from mid-field
# (`p ~= 0.5`) costs approximately NOTHING — and with rolling starts there
# is always another field to join. The zero floor makes it worse for exactly
# the players most likely to churn: at 0 points there is nothing to debit.
#
# Sized against §6.2's own table so that "one forfeit stays cheaper than a
# genuinely bad finish" — the mercy rule has to stay merciful. A last-place
# weekly finish is -40; this is -10, a quarter of it. Scaled by the LOSS
# cadence weight (not the gain row), so an annual forfeit costs 7.2x a
# weekly one rather than 52x — a player abandoning a year is not 52 times
# worse than one abandoning a week, and the sqrt row is the design's own
# answer to that asymmetry everywhere else it appears.
MIN_FORFEIT_DEBIT = 10


def forfeit_debit(cadence: str) -> int:
    """The floor a forfeit costs regardless of standing. Returned POSITIVE;
    the caller applies the sign, the same convention `finish_stipend` uses."""
    return round(MIN_FORFEIT_DEBIT * cadence_weight(cadence, negative=True))


# ── The wildness index (design §10.4) — a PRIVATE mirror, never scored,
# never rendered on a board. Four normalised [0, 1] components, averaged:
#   concentration  — HHI over ending-position weights (all-in one name = 1)
#   narrowness     — 1 minus the (capped) effective position count; an
#                     all-cash book (no holdings) contributes 0, not 1 — an
#                     empty book isn't concentrated risk, it's no risk
#   turnover       — total notional traded vs starting capital, capped
#   volatility     — stdev of the run's own daily returns, capped
# All four caps are named constants so a retune is one line, same
# discipline as the fee/stipend/alpha family above.
WILDNESS_TURNOVER_CAP = 5.0        # 5x starting capital traded = max turnover contribution
WILDNESS_VOL_CAP = 0.05            # 5% daily stdev = max volatility contribution
WILDNESS_WIDE_POSITION_COUNT = 5.0  # 5+ effective positions = zero narrowness contribution


def wildness_index(
    *,
    holding_weights: Sequence[float],
    total_notional_traded: float,
    starting_capital: float,
    daily_returns: Sequence[float],
) -> float:
    """A 0.0-1.0 composite, higher = wilder. `holding_weights` are ending
    position values as a fraction of total run value (cash excluded, so
    they need not sum to 1); `daily_returns` are the run's own per-day
    FRACTION returns (from consecutive NAV points)."""
    if holding_weights:
        hhi = sum(w * w for w in holding_weights)
        effective_count = (1.0 / hhi) if hhi > 0 else 0.0
        narrowness = 1.0 - min(effective_count / WILDNESS_WIDE_POSITION_COUNT, 1.0)
    else:
        hhi = 0.0
        narrowness = 0.0

    turnover = 0.0
    if starting_capital > 0:
        capped = min(total_notional_traded / starting_capital, WILDNESS_TURNOVER_CAP)
        turnover = capped / WILDNESS_TURNOVER_CAP

    vol = statistics.pstdev(daily_returns) if len(daily_returns) >= 2 else 0.0
    vol_component = min(vol / WILDNESS_VOL_CAP, 1.0)

    return round((hhi + narrowness + turnover + vol_component) / 4.0, 4)


class TradeLeg(NamedTuple):
    """One fill, reduced to what the "first picks" counterfactual needs.
    `opened_at` is a plain `date` (the caller collapses the fill's
    timestamp) — grouping is by TRADING DAY, not by instant."""

    ticker: str
    side: str  # "buy" / "sell"
    quantity: float
    price: float
    opened_at: date


def counterfactual_hold_first_picks_pct(
    trades: Sequence[TradeLeg],
    final_marks: Mapping[str, float],
    starting_capital: float,
) -> float | None:
    """"If you'd held your first picks untouched" (design §10.4) — the
    position(s) bought on the run's FIRST trading day, held unchanged (no
    later buys/sells/rebalancing) to the final marks. `None` when there
    were no trades at all — there is nothing to have held.

    Pays the same entry fee those first-day fills actually paid (a real,
    unavoidable cost of establishing the position) but no fee thereafter —
    the counterfactual is "never traded again", not "never paid to enter".
    """
    buys = [t for t in trades if t.side == "buy"]
    if not buys or starting_capital <= 0:
        return None

    first_day = min(t.opened_at for t in buys)
    first_day_buys = [t for t in buys if t.opened_at == first_day]

    spent = 0.0
    qty_by_ticker: dict[str, float] = {}
    for t in first_day_buys:
        notional = t.quantity * t.price
        spent += notional + trade_fee(notional)
        qty_by_ticker[t.ticker] = qty_by_ticker.get(t.ticker, 0.0) + t.quantity

    leftover_cash = starting_capital - spent
    value_at_close = leftover_cash + sum(
        qty * final_marks.get(ticker, 0.0) for ticker, qty in qty_by_ticker.items()
    )
    return round((value_at_close / starting_capital - 1.0) * 100, 2)
