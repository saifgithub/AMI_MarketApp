"""CR136 M04 — deterministic Portfolio Health metrics engine: one EWMA Σ per evaluation, every block wrapped in the Rev 4 uncertainty contract.

The whole point of this layer is that an LLM consumes its output. An agent will
confidently narrate whatever it is handed, so the uncertainty contract is
structural rather than advisory: `sufficient: false` forces `value` and
`standard_error` to `null` — never `0.0` — and the context builder strips
insufficient blocks before prompt assembly, so the model never even sees the
metric's name. There is nothing to narrate, which is the only enforcement that
survives contact with a model (CR038: prompt instructions are not controls).

Σ is built ONCE per evaluation over the surviving risky holdings plus the SPY
benchmark leg, and everything else is derived from it — σₚ, beta, R², tracking
error, DR², Euler risk shares, MCR. The benchmark is a leg of that same matrix
rather than a separately-estimated series, so the two sides can never come from
different windows. Cash is appended as an exact zero row AFTER estimation, which
makes its effect exact rather than approximate: it scales σₚ and beta by exactly
(1−c) and leaves risk shares, DR² and R² exactly invariant.

Two bases run through everything, and no sentence or figure may mix them
(Rev 4's SHARE/LEVEL rule): LEVEL quantities (σₚ, beta, TE, bad month,
scenarios) are total-book; SHARE quantities (risk shares, MCR, weight
concentration) are invested-sleeve. Every block carries its `basis` so the rule
is machine-readable downstream rather than a convention someone has to remember.

This module ships ZERO user-visible strings — machine states and reasons only.
All copy, including the "our data limit, not your book" phrasing that
`insufficient_cause` keys, is M06/M09's.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Callable, Iterable, Sequence
from uuid import UUID

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import TickerReferenceRow
from app.services import price_history
from app.services.price_history import _MOCK_SOURCE
from app.services.portfolio_health_constants import (
    BAD_PRINT_HARD_ABS_RETURN,
    BAD_PRINT_MIN_ABS_RETURN,
    BAD_PRINT_REVERSAL_MIN_FRACTION,
    BAD_PRINT_SIGMA_MULT,
    BASIS_INVESTED_SLEEVE,
    BASIS_TOTAL_VALUE,
    BASIS_WEIGHTS,
    BENCHMARK_TICKER,
    DATA_QUALITY_DROP_REASON,
    DROPPED_WEIGHT_MAX,
    FEED_UNAVAILABLE_DROP_REASON,
    INSUFFICIENT_FEED_UNAVAILABLE,
    ENGINE_VERSION,
    INSUFFICIENT_BENCHMARK_MISALIGNED,
    INSUFFICIENT_DROPPED_WEIGHT,
    INSUFFICIENT_SHORT_WINDOW,
    INSUFFICIENT_T_OVER_N,
    INSUFFICIENT_ZERO_VARIANCE,
    LOW_R2_THRESHOLD,
    MAX_RETURNS,
    RULE_R2B_MIN_PAIR_WEIGHT_PCT,
    SCENARIO_EPISODES,
    SHORT_HISTORY_DROP_REASON,
    STATUS_NO_HOLDINGS,
    STATUS_OK,
    STATUS_REFUSED_MOCK_DATA,
    T_MIN,
    T_OVER_N_MIN,
)
from app.services.sector_allocation import default_sector_map
from app.trading_math import (
    EWMA_LAMBDA,
    annualize_vol,
    append_zero_row,
    bad_month,
    beta_r2,
    dr_squared,
    euler_contributions,
    ewma_covariance,
    hhi_effective_n,
    mcr,
    portfolio_sigma,
    scenario_replay,
    se_beta,
    se_sigma,
    t_eff,
    tracking_error,
)

_ISO = "%Y-%m-%d"


@dataclass(frozen=True)
class PredictedVol:
    """The Tier-1 predicted volatility a Tier-2 snapshot row stores beside its
    realised value (Rev 4 F16), so the model is permanently auditable.

    `predicted_vol_ann` is a DECIMAL FRACTION, not a percentage — the F16 bias
    test divides a realised return by it and expects the units to cancel.
    """

    predicted_vol_ann: float
    n_observations: int
    engine_version: str


@dataclass(frozen=True)
class _Position:
    ticker: str
    quantity: float
    price: float
    value: float


# ── Block assembly ──────────────────────────────────────────────────────────


def _block(
    metric: str,
    *,
    value: float | None,
    standard_error: float | None,
    basis: str,
    sufficient: bool,
    insufficient_cause: str | None,
    n_observations: int,
    window_days: int,
    t_eff_value: float | None = None,
    partial: bool = False,
    dropped_holdings: Sequence[dict] = (),
    backcast: bool = True,
    low_explanatory_power: bool | None = None,
    contains_etfs: bool = False,
    **extensions,
) -> dict:
    """One metric block in Rev 4's uncertainty contract.

    The null-forcing below is the contract's teeth, applied here rather than at
    each call site: an insufficient block cannot leak a value, an SE, or a
    T_eff no matter what the caller computed, because `null` has exactly one
    meaning downstream and a second meaning would make it unenforceable.
    """
    if not sufficient:
        value = None
        standard_error = None
        t_eff_value = None
    block = {
        "metric": metric,
        "value": value,
        "standard_error": standard_error,
        "n_observations": n_observations,
        "t_eff": t_eff_value,
        "window_days": window_days,
        "sufficient": sufficient,
        "partial": partial,
        "dropped_holdings": [dict(d) for d in dropped_holdings],
        "low_explanatory_power": low_explanatory_power,
        "contains_etfs": contains_etfs,
        "backcast": backcast,
        "basis": basis,
        "engine_version": ENGINE_VERSION,
        "insufficient_cause": insufficient_cause,
    }
    block.update(extensions)
    return block


# ── Series helpers ──────────────────────────────────────────────────────────


def _prepare(pairs: Sequence[tuple[str, float]]) -> tuple[list[str], dict[str, float]]:
    """(ascending iso dates, date → close), trimmed to the newest window."""
    by_date: dict[str, float] = {}
    for iso, close in pairs:
        by_date[iso] = float(close)
    dates = sorted(by_date)[-(MAX_RETURNS + 1):]
    return dates, {d: by_date[d] for d in dates}


def _returns_on(dates: Sequence[str], closes: dict[str, float]) -> list[float]:
    return [
        closes[dates[i]] / closes[dates[i - 1]] - 1.0
        for i in range(1, len(dates))
    ]


def _window_days(dates: Sequence[str]) -> int:
    if len(dates) < 2:
        return 0
    first = datetime.strptime(dates[0], _ISO).date()
    last = datetime.strptime(dates[-1], _ISO).date()
    return (last - first).days


def _flagged_bad_print(closes: Sequence[float]) -> bool:
    return bool(price_history.detect_bad_print_days(
        list(closes),
        sigma_mult=BAD_PRINT_SIGMA_MULT,
        min_abs_return=BAD_PRINT_MIN_ABS_RETURN,
        reversal_min_fraction=BAD_PRINT_REVERSAL_MIN_FRACTION,
        hard_abs_return=BAD_PRINT_HARD_ABS_RETURN,
    ))


# ── The engine ──────────────────────────────────────────────────────────────


def compute_health(
    *,
    holdings: list[tuple[str, float]],
    marks: dict[str, float],
    cash: float,
    series: dict[str, list[tuple[str, float]]],
    sector_of: Callable[[str], str],
    etf_tickers: frozenset[str],
    as_of: str,
    feed_failed: frozenset[str] = frozenset(),
) -> dict:
    """The whole Tier-1 evaluation, pure and deterministic.

    `feed_failed` names tickers whose provider fetch failed this evaluation.
    Without it a data-feed outage is indistinguishable from a genuinely young
    security, and the report would tell the user "not enough price history for
    this holding" when the truth is "our feed is down" — the CR040 question
    answered the wrong way, and the same mis-statement M01's own audit caught
    one layer down.

    No I/O, no clock beyond `generated_at`, JSON-serialisable return — so the
    thing under test is the thing that ships.
    """
    generated_at = datetime.now(timezone.utc).isoformat()
    positions = [
        _Position(
            ticker=t.upper().strip(),
            quantity=float(q),
            price=float(marks.get(t.upper().strip(), 0.0)),
            value=float(q) * float(marks.get(t.upper().strip(), 0.0)),
        )
        for t, q in holdings
        if float(q) > 0.0
    ]
    full_invested = math.fsum(p.value for p in positions)
    if not positions or full_invested <= 0.0:
        return {
            "status": STATUS_NO_HOLDINGS,
            "as_of": as_of,
            "generated_at": generated_at,
            "engine_version": ENGINE_VERSION,
        }

    cash = float(cash)
    total_value = full_invested + cash
    contains_etfs = any(p.ticker in etf_tickers for p in positions)

    # ── Prepared series + the two drop rules (bad print first, per Rev 4's
    # pipeline order — a spike-and-reversal series is a data fault whatever its
    # length, and the recorded reason must say so).
    prepared: dict[str, tuple[list[str], dict[str, float]]] = {}
    for ticker, pairs in series.items():
        prepared[ticker.upper().strip()] = _prepare(pairs)

    dropped: list[dict] = []
    survivors: list[_Position] = []
    for p in positions:
        dates, closes = prepared.get(p.ticker, ([], {}))
        if dates and _flagged_bad_print([closes[d] for d in dates]):
            dropped.append({"ticker": p.ticker, "reason": DATA_QUALITY_DROP_REASON})
            continue
        if len(dates) - 1 < T_MIN:
            dropped.append({
                "ticker": p.ticker,
                "reason": (
                    FEED_UNAVAILABLE_DROP_REASON if p.ticker in feed_failed
                    else SHORT_HISTORY_DROP_REASON
                ),
            })
            continue
        survivors.append(p)

    partial = bool(dropped)
    dropped_value = math.fsum(
        p.value for p in positions if any(d["ticker"] == p.ticker for d in dropped)
    )
    dropped_weight_exceeded = (dropped_value / full_invested) > DROPPED_WEIGHT_MAX

    # ── Benchmark usability, then alignment. The benchmark is never re-gridded:
    # a series that does not share dates with the book is unusable, not
    # approximable (Rev 4 estimator pin 5 — the existing `beta()` validates
    # length rather than dates, which is how a silently wrong beta happens).
    bench_dates, bench_closes = prepared.get(BENCHMARK_TICKER, ([], {}))
    bench_feed_failed = BENCHMARK_TICKER in feed_failed
    bench_clean = bool(bench_dates) and not _flagged_bad_print(
        [bench_closes[d] for d in bench_dates]
    )

    def _join(tickers: Sequence[str]) -> list[str]:
        sets = [set(prepared.get(t, ([], {}))[0]) for t in tickers]
        if not sets or any(not s for s in sets):
            return []
        common = set.intersection(*sets)
        return sorted(common)[-(MAX_RETURNS + 1):]

    survivor_tickers = [p.ticker for p in survivors]
    benchmark_usable = False
    dates: list[str] = []
    if survivor_tickers:
        if bench_clean:
            joint = _join([*survivor_tickers, BENCHMARK_TICKER])
            if len(joint) - 1 >= T_MIN:
                benchmark_usable = True
                dates = joint
        if not benchmark_usable:
            dates = _join(survivor_tickers)

    t_obs = max(0, len(dates) - 1)
    window_days = _window_days(dates)
    n_risky = len(survivors)

    if t_obs < T_MIN:
        estimator_cause: str | None = INSUFFICIENT_SHORT_WINDOW
    elif dropped_weight_exceeded:
        estimator_cause = INSUFFICIENT_DROPPED_WEIGHT
    else:
        estimator_cause = None
    estimator_ok = estimator_cause is None

    # ── One Σ, then slices. cov[i][j] depends only on rows i and j, so the
    # top-left risky block of the joint matrix IS the risky-only estimate —
    # sliced, never re-estimated.
    cov_joint: list[list[float]] | None = None
    cov_risky: list[list[float]] | None = None
    b_index: int | None = None
    if estimator_ok:
        matrix_tickers = list(survivor_tickers)
        if benchmark_usable:
            b_index = len(matrix_tickers)
            matrix_tickers.append(BENCHMARK_TICKER)
        returns = [
            _returns_on(dates, prepared[t][1]) for t in matrix_tickers
        ]
        cov_joint = ewma_covariance(returns, EWMA_LAMBDA)
        cov_risky = [row[:n_risky] for row in cov_joint[:n_risky]]
        # A book whose adjusted closes never move has zero variance. M02
        # documents that as the caller's precondition and raises on it; the
        # honest answer here is "we cannot measure this", not a 500 and not a
        # confident volatility of exactly zero.
        if all(cov_risky[i][i] <= 0.0 for i in range(n_risky)):
            estimator_ok = False
            estimator_cause = INSUFFICIENT_ZERO_VARIANCE
            cov_joint = None
            cov_risky = None
            b_index = None
            benchmark_usable = False

    covered_invested = math.fsum(p.value for p in survivors)
    covered_total = covered_invested + cash
    cash_fraction = cash / total_value if total_value > 0.0 else 0.0

    # Invested-sleeve weights (SHARE basis) and total-book weights (LEVEL).
    v_weights = (
        [p.value / covered_invested for p in survivors]
        if covered_invested > 0.0 else []
    )
    w_level = (
        [p.value / covered_total for p in survivors]
        if covered_total > 0.0 else []
    )

    teff_value = t_eff(EWMA_LAMBDA, t_obs) if estimator_ok else None
    tn_ok = estimator_ok and n_risky > 0 and (t_obs / n_risky) >= T_OVER_N_MIN
    share_cause = estimator_cause if not estimator_ok else (
        None if tn_ok else INSUFFICIENT_T_OVER_N
    )

    common = {
        "n_observations": t_obs,
        "window_days": window_days,
        "partial": partial,
        "dropped_holdings": dropped,
    }

    # ── LEVEL: portfolio volatility ─────────────────────────────────────────
    vol_ann: float | None = None
    var_p_daily: float | None = None
    w_full: list[float] | None = None
    cov_full: list[list[float]] | None = None
    if estimator_ok and cov_joint is not None and w_level:
        w_full = list(w_level)
        if b_index is not None:
            w_full.append(0.0)              # benchmark: an estimation leg, never a holding
        # Cash appended AFTER estimation, as an exact zero row — which is what
        # makes its effect exact rather than approximate.
        cov_full = append_zero_row(cov_joint)
        w_full.append(cash / covered_total if covered_total > 0.0 else 0.0)
        sigma_daily = portfolio_sigma(w_full, cov_full)
        var_p_daily = sigma_daily * sigma_daily
        vol_ann = annualize_vol(sigma_daily)

    blocks: dict[str, dict] = {}
    vol_sufficient = vol_ann is not None
    blocks["portfolio_volatility"] = _block(
        "portfolio_volatility",
        value=vol_ann,
        standard_error=(
            se_sigma(vol_ann, teff_value)
            if vol_sufficient and teff_value else None
        ),
        basis=BASIS_TOTAL_VALUE,
        sufficient=vol_sufficient,
        insufficient_cause=None if vol_sufficient else estimator_cause,
        t_eff_value=teff_value,
        **common,
    )

    # ── LEVEL: beta + R², and everything that inherits from it ──────────────
    beta_value: float | None = None
    r2_value: float | None = None
    beta_se: float | None = None
    benchmark_vol_ann: float | None = None
    beta_cause = estimator_cause
    if estimator_ok and not benchmark_usable:
        beta_cause = (
            INSUFFICIENT_FEED_UNAVAILABLE if bench_feed_failed
            else INSUFFICIENT_BENCHMARK_MISALIGNED
        )
    if (
        estimator_ok and benchmark_usable and cov_full is not None
        and w_full is not None and b_index is not None and var_p_daily
    ):
        beta_value, r2_value = beta_r2(w_full, cov_full, b_index)
        var_b_daily = cov_joint[b_index][b_index]
        beta_se = se_beta(var_p_daily, var_b_daily, beta_value, teff_value)
        benchmark_vol_ann = annualize_vol(math.sqrt(var_b_daily))
        beta_cause = None
    beta_sufficient = beta_value is not None

    blocks["beta"] = _block(
        "beta",
        value=beta_value,
        standard_error=beta_se,
        basis=BASIS_TOTAL_VALUE,
        sufficient=beta_sufficient,
        insufficient_cause=None if beta_sufficient else beta_cause,
        t_eff_value=teff_value,
        low_explanatory_power=(
            (r2_value < LOW_R2_THRESHOLD) if r2_value is not None else None
        ),
        r_squared=r2_value if beta_sufficient else None,
        **common,
    )

    te_value = (
        tracking_error(vol_ann, benchmark_vol_ann, beta_value)
        if beta_sufficient and vol_ann is not None and benchmark_vol_ann is not None
        else None
    )
    blocks["tracking_error"] = _block(
        "tracking_error",
        value=te_value,
        standard_error=None,           # derived; its components each carry theirs
        basis=BASIS_TOTAL_VALUE,
        sufficient=te_value is not None,
        insufficient_cause=None if te_value is not None else beta_cause,
        **common,
    )

    # ── SHARE: the invested sleeve ──────────────────────────────────────────
    dr2_value: float | None = None
    contributions: list[float] = []
    mcr_values: list[float] = []
    sigma_inv_ann: float | None = None
    if tn_ok and cov_risky is not None and v_weights:
        sigma_inv_ann = annualize_vol(portfolio_sigma(v_weights, cov_risky))
        dr2_value = dr_squared(v_weights, cov_risky)
        contributions = euler_contributions(v_weights, cov_risky)
        mcr_values = [annualize_vol(m) for m in mcr(v_weights, cov_risky)]

    blocks["effective_bets"] = _block(
        "effective_bets",
        value=dr2_value,
        standard_error=None,           # null by decision; rules gate via hysteresis
        basis=BASIS_INVESTED_SLEEVE,
        sufficient=dr2_value is not None,
        insufficient_cause=None if dr2_value is not None else share_cause,
        **common,
    )

    per_holding = [
        {
            "ticker": survivors[i].ticker,
            "invested_weight": v_weights[i],
            "risk_share": contributions[i],
        }
        for i in range(len(contributions))
    ]
    per_sector: list[dict] = []
    top: dict | None = None
    if per_holding:
        by_sector: dict[str, float] = {}
        for entry in per_holding:
            sector = sector_of(entry["ticker"])
            by_sector[sector] = by_sector.get(sector, 0.0) + entry["risk_share"]
        per_sector = [
            {"sector": s, "risk_share": w}
            for s, w in sorted(by_sector.items(), key=lambda kv: -kv[1])
        ]
        best = max(per_holding, key=lambda e: e["risk_share"])
        top = {
            "ticker": best["ticker"],
            "risk_share": best["risk_share"],
            "invested_weight": best["invested_weight"],
        }

    blocks["risk_contribution"] = _block(
        "risk_contribution",
        value=top["risk_share"] if top else None,
        standard_error=None,
        basis=BASIS_INVESTED_SLEEVE,
        sufficient=top is not None,
        insufficient_cause=None if top is not None else share_cause,
        per_holding=per_holding,
        per_sector=per_sector,
        top=top,
        **common,
    )

    mcr_per_holding = [
        {"ticker": survivors[i].ticker, "mcr": mcr_values[i]}
        for i in range(len(mcr_values))
    ]
    blocks["mcr"] = _block(
        "mcr",
        value=max((e["mcr"] for e in mcr_per_holding), default=None),
        standard_error=None,
        basis=BASIS_INVESTED_SLEEVE,
        sufficient=bool(mcr_per_holding),
        insufficient_cause=None if mcr_per_holding else share_cause,
        per_holding=mcr_per_holding,
        **common,
    )

    # ── Accounting: weight concentration over the FULL invested sleeve ──────
    # No history is needed to count weights, so dropped holdings stay in — this
    # block is never insufficient and never partial.
    full_weights = [p.value / full_invested for p in positions]
    hhi = math.fsum(w * w for w in full_weights)
    blocks["weight_concentration"] = _block(
        "weight_concentration",
        value=hhi,
        standard_error=None,
        basis=BASIS_WEIGHTS,
        sufficient=True,
        insufficient_cause=None,
        backcast=False,                # today's weights, no past returns
        contains_etfs=contains_etfs,
        n_observations=t_obs,
        window_days=window_days,
        partial=False,
        dropped_holdings=[],
        effective_n=hhi_effective_n(full_weights),
        holdings_count=len(positions),
    )

    # ── Derived, inheriting their parents' sufficiency ──────────────────────
    bad_month_value = bad_month(vol_ann) if vol_sufficient else None
    blocks["typical_bad_month"] = _block(
        "typical_bad_month",
        value=bad_month_value,
        standard_error=None,
        basis=BASIS_TOTAL_VALUE,
        sufficient=bad_month_value is not None,
        insufficient_cause=None if bad_month_value is not None else estimator_cause,
        **common,
    )

    episodes: list[dict] = []
    if beta_sufficient:
        for episode in SCENARIO_EPISODES:
            episodes.append({
                **episode,
                "implied_portfolio_return": scenario_replay(
                    beta_value, episode["benchmark_return"],
                ),
            })
    blocks["scenario_panel"] = _block(
        "scenario_panel",
        value=(
            min(e["implied_portfolio_return"] for e in episodes) if episodes else None
        ),
        standard_error=None,
        basis=BASIS_TOTAL_VALUE,
        sufficient=bool(episodes),
        insufficient_cause=None if episodes else beta_cause,
        episodes=episodes,
        **common,
    )

    # ── Precomputed comparisons (Rev 4 prompt contract pt 2): if it is not in
    # the payload, it may not be said.
    correlation_pairs: list[dict] = []
    if cov_risky is not None and v_weights:
        for i in range(n_risky):
            for j in range(i + 1, n_risky):
                # The threshold is stored in percentage points (M05's rule API
                # works in those); the weights here are fractions.
                floor = RULE_R2B_MIN_PAIR_WEIGHT_PCT / 100.0
                if v_weights[i] < floor or v_weights[j] < floor:
                    continue
                denom = math.sqrt(cov_risky[i][i] * cov_risky[j][j])
                if denom <= 0.0:
                    continue
                correlation_pairs.append({
                    "a": survivors[i].ticker,
                    "b": survivors[j].ticker,
                    "rho": cov_risky[i][j] / denom,
                    "weight_a": v_weights[i],
                    "weight_b": v_weights[j],
                })

    return {
        "status": STATUS_OK,
        "as_of": as_of,
        "generated_at": generated_at,
        "engine_version": ENGINE_VERSION,
        "benchmark": BENCHMARK_TICKER,
        "contains_etfs": contains_etfs,
        "partial": partial,
        "dropped_holdings": dropped,
        "holdings_count": len(positions),
        "risky_holdings_count": n_risky,
        "total_value": total_value,
        "invested_value": full_invested,
        "covered_invested_value": covered_invested,
        "cash_fraction": cash_fraction,
        "context": {
            "benchmark_vol_ann": benchmark_vol_ann,
            "correlation_pairs": correlation_pairs,
        },
        "blocks": blocks,
    }


# ── Orchestration ───────────────────────────────────────────────────────────


def _etf_ticker_set(tickers: Iterable[str]) -> frozenset[str]:
    """Which of `tickers` the reference table marks as ETFs.

    First production reader of `TickerReferenceRow.is_etf`. A missing row means
    "not an ETF" rather than an error: the disclosure it drives is an addition
    to the weight tile, and a stale reference row must not be able to fail an
    evaluation.
    """
    wanted = sorted({t.upper().strip() for t in tickers if t and t.strip()})
    if not wanted:
        return frozenset()
    with get_session() as session:
        rows = session.execute(
            select(TickerReferenceRow.symbol).where(
                TickerReferenceRow.symbol.in_(wanted),
                TickerReferenceRow.is_etf.is_(True),
            )
        ).scalars().all()
    return frozenset(rows)


def _gather_inputs(user_id: UUID, sim) -> dict | None:
    """Every load the engine needs, synchronously, in one place.

    Deliberately one function rather than the four separate hops the module doc
    sketched: callers cross the sync boundary exactly once
    (`asyncio.to_thread`), which is the DEF116/DEF120 rule, and the snapshot
    path reuses it without duplicating the load order. `default_sector_map()`
    rather than the doc's `default_sector_map_async()` for the same reason —
    inside a worker thread the sync accessor IS the async one's body.

    Returns `None` when the MARKS are fabricated. This is the other half of the
    mock refusal and it was missing: the engine refuses fabricated price
    HISTORY, but `portfolio_marks_snapshot` resolves through
    `FallbackProvider(cache(yfinance) → mock_walk)`, so a Yahoo rate-limit puts
    random-walk prices into every weight in the payload — risk shares, HHI,
    cash fraction, the LEVEL denominator, all of it — while the report still
    says `status: "ok"`. Refusing costs a blank card during an outage; not
    refusing publishes a confident risk analysis of a book that does not exist.
    """
    portfolio, marks, _total, _dd, price_source = sim.portfolio_marks_snapshot(user_id)
    holdings = [(h.ticker, float(h.quantity)) for h in portfolio.holdings]
    tickers = [t for t, _q in holdings]

    if tickers and _MOCK_SOURCE in str(price_source):
        logger.warn(
            "portfolio_health_refused_mock_marks",
            user_id=str(user_id), price_source=price_source,
        )
        return None

    series: dict[str, list[tuple[str, float]]] = {}
    feed_failed: set[str] = set()
    if tickers:
        fetched = price_history.get_daily_series(
            [*tickers, BENCHMARK_TICKER], min_days=T_MIN + 1,
        )
        for ticker, daily in fetched.items():
            series[ticker] = [
                (d.isoformat(), px) for d, px in zip(daily.dates, daily.adj_closes)
            ]
            if daily.fetch_failed:
                feed_failed.add(ticker)

    sector_map = default_sector_map()
    return {
        "holdings": holdings,
        "marks": marks,
        "cash": float(portfolio.current_cash),
        "series": series,
        "sector_of": sector_map.sector,
        "etf_tickers": _etf_ticker_set(tickers),
        "as_of": date.today().isoformat(),
        "feed_failed": frozenset(feed_failed),
    }


def _refusal_payload(reason: str) -> dict:
    return {
        "status": STATUS_REFUSED_MOCK_DATA,
        "reason": reason,
        "engine_version": ENGINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_health_context(user_id: UUID, *, sim=None) -> dict:
    """The engine entry point (build/README.md seam register, M04 → M06/M07).

    Exactly one of `refused_mock_data`, `no_holdings` or `ok`; side-effect free
    — no journal writes, no snapshot rows. Synchronous, so an async caller wraps
    it once in `asyncio.to_thread(build_health_context, user_id)`, which is the
    form M07's own plan pins and the DEF116/DEF120 rule requires.

    `sim` is injectable for tests only; production resolves the engine here so
    the pinned single-argument call form works.

    The mock refusal comes FIRST and loads nothing. Serving mock-walk prices as
    a risk analysis would be the CR040 question answered the wrong way: the
    numbers would look entirely plausible and mean nothing at all.
    """
    if not settings.use_real_market_data:
        logger.warn("portfolio_health_refused_mock_data", user_id=str(user_id))
        return _refusal_payload("use_real_market_data=false")

    if sim is None:
        from app.services.sim_engine import get_sim_engine

        sim = get_sim_engine()
    inputs = _gather_inputs(user_id, sim)
    if inputs is None:
        return _refusal_payload("marks_source=mock_walk")
    return compute_health(**inputs)


def predicted_vol_for_snapshot(user_id: UUID) -> PredictedVol | None:
    """The Tier-1 predicted volatility for M03's daily snapshot row (Rev 4 F16).

    Returns `None` whenever the engine cannot publish a volatility — mock mode,
    an empty book, or an insufficient window — because a snapshot row with a
    fabricated prediction would corrupt the bias test that exists to validate
    the model. Synchronous: the snapshot job is a background task, already off
    the request path.
    """
    payload = build_health_context(user_id)
    if payload.get("status") != STATUS_OK:
        return None
    block = payload["blocks"]["portfolio_volatility"]
    if not block["sufficient"] or block["value"] is None:
        return None
    return PredictedVol(
        predicted_vol_ann=float(block["value"]),
        n_observations=int(block["n_observations"]),
        engine_version=ENGINE_VERSION,
    )
