"""Daily portfolio-value snapshot job + Tier-2 realised reads (CR136 M03) — one row per (portfolio, trading day); rolling 252-day max drawdown, equity curve, F16 bias-test helper.

Tier 2 is the realised history that accumulates behind Tier 1's forward-looking
estimates, and — per Rev 4 F16 — the layer that validates them. Every row stores
the Tier-1 predicted volatility beside the realised value, so the model is
permanently auditable rather than merely plausible: `bias_z_stats` computes
z = realised return / predicted vol and expects sd(z) ≈ 1. That check is
unreconstructible unless the prediction is written down at the moment it is made,
which is the whole reason the columns live on the snapshot row.

**The max drawdown here is ROLLING over a trailing 252-snapshot window, never
expanding.** An expanding-window maximum is a monotone ratchet: once a user has
taken a 40% drawdown, no amount of de-risking can ever move the number again
(measured: minimum day-over-day change exactly 0.0). The rolling window restores
improvability on 87.4% of paths, so the number the user is being taught to manage
is one their behaviour can actually change.

Two quantities in this codebase have been called "drawdown", and conflating them
was a real defect: `SnapshotPoint.drawdown_pct` is the sim's vs-STARTING-CAPITAL
figure ($10k → $15k → $12k reads 0.0), while the Tier-2 block is peak-to-trough
over stored `total_value` ($10k → $15k → $12k reads 20.0). Nothing in the Tier-2
computation below reads `drawdown_pct`.
"""

from __future__ import annotations

import statistics
from datetime import date, datetime, timezone
from typing import Callable, NamedTuple, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.logging import logger
from app.db import get_session
from app.db.models import PortfolioValueSnapshotRow, SimPortfolioRow
from app.services.portfolio_health_constants import (
    BASIS_TOTAL_VALUE,
    ENGINE_VERSION,
    TIER2_MDD_WINDOW_SNAPSHOTS,
    TIER2_MIN_SNAPSHOTS,
)
from app.trading_math import TRADING_DAYS_PER_YEAR, max_drawdown_pct


class SnapshotPoint(NamedTuple):
    """One stored snapshot, as the Tier-2 reads consume it.

    `drawdown_pct` is carried through for callers that already show it; it is
    the vs-starting-capital number and is NOT what the Tier-2 max-drawdown block
    computes. See the module docstring.
    """

    as_of: date
    total_value: float
    cash: float
    invested_value: float
    drawdown_pct: float
    source: str
    predicted_vol_ann: float | None


class BiasStats(NamedTuple):
    n: int
    mean_z: float | None
    sd_z: float | None


# ── The tick ────────────────────────────────────────────────────────────────


def _default_trading_day() -> date | None:
    from app.services.price_history import latest_trading_day

    return latest_trading_day()


def _default_vol_provider(user_id: UUID):
    from app.services.portfolio_health import predicted_vol_for_snapshot

    return predicted_vol_for_snapshot(user_id)


def run_portfolio_snapshot_tick(
    *,
    now: datetime | None = None,
    trading_day: Callable[[], date | None] | None = None,
    vol_provider: Callable[[UUID], object | None] | None = None,
) -> dict[str, object]:
    """One sweep: at most one row per sim portfolio per trading day.

    Idempotent by design, like every other background tick here — a tick that
    finds today's row already stored does nothing, so a restart cannot miss a
    boundary and a Saturday tick cannot invent a Saturday.

    The trading day comes from the benchmark's own candle grid (M01's
    `latest_trading_day`), never from calendar arithmetic. If the data layer
    cannot serve it, this is a loud no-op rather than a fabricated date: writing
    a row stamped with a guessed date would put a hole in the very series the
    bias test is supposed to validate.
    """
    now = now or datetime.now(timezone.utc)
    resolve_day = trading_day or _default_trading_day
    resolve_vol = vol_provider or _default_vol_provider

    as_of = resolve_day()
    if as_of is None:
        logger.warn(
            "portfolio_snapshot_no_trading_day",
            reason="benchmark daily history unavailable — no row written",
        )
        return {
            "as_of": "none", "portfolios": 0, "written": 0,
            "skipped_existing": 0, "vol_null": 0,
        }

    from app.services.sim_engine import get_sim_engine

    sim = get_sim_engine()
    with get_session() as session:
        portfolio_rows = session.execute(select(SimPortfolioRow)).scalars().all()
        targets = [(row.id, row.user_id) for row in portfolio_rows]

    written = 0
    skipped = 0
    vol_null = 0
    for portfolio_id, user_id in targets:
        try:
            with get_session() as session:
                exists = session.execute(
                    select(PortfolioValueSnapshotRow.id).where(
                        PortfolioValueSnapshotRow.portfolio_id == portfolio_id,
                        PortfolioValueSnapshotRow.as_of == as_of,
                    )
                ).first()
            if exists is not None:
                skipped += 1
                continue

            portfolio, _marks, total_value, drawdown_pct, source = (
                sim.portfolio_marks_snapshot(user_id)
            )
            cash = float(portfolio.current_cash)

            predicted = None
            try:
                predicted = resolve_vol(user_id)
            except Exception:
                # The value row is never hostage to the vol engine: realised
                # history is the thing that cannot be recovered later, and a
                # missing prediction is honestly representable as null. The
                # exception log every tick is what keeps the failure loud.
                logger.exception("portfolio_snapshot_vol_failed", user_id=str(user_id))
            if predicted is None:
                vol_null += 1

            try:
                with get_session() as session:
                    session.add(PortfolioValueSnapshotRow(
                        user_id=user_id,
                        portfolio_id=portfolio_id,
                        as_of=as_of,
                        total_value=round(float(total_value), 2),
                        cash=round(cash, 2),
                        invested_value=round(float(total_value) - cash, 2),
                        drawdown_pct=float(drawdown_pct),
                        source=source,
                        captured_at=now,
                        predicted_vol_ann=(
                            float(predicted.predicted_vol_ann) if predicted else None
                        ),
                        n_observations=(
                            int(predicted.n_observations) if predicted else None
                        ),
                        engine_version=(
                            str(predicted.engine_version) if predicted else None
                        ),
                    ))
                written += 1
            except IntegrityError:
                # The unique constraint is the backstop behind the check above;
                # a concurrent tick losing this race is a skip, not a failure.
                skipped += 1
        except Exception:
            logger.exception(
                "portfolio_snapshot_portfolio_failed",
                portfolio_id=str(portfolio_id), user_id=str(user_id),
            )

    return {
        "as_of": as_of.isoformat(),
        "portfolios": len(targets),
        "written": written,
        "skipped_existing": skipped,
        "vol_null": vol_null,
    }


# ── Tier-2 reads ────────────────────────────────────────────────────────────


def equity_curve(portfolio_id: UUID, *, limit: int = 504) -> list[SnapshotPoint]:
    """The trailing `limit` snapshots for one portfolio, ascending by date.

    Keyed to `portfolio_id`, so the series never spans a reset."""
    with get_session() as session:
        rows = session.execute(
            select(PortfolioValueSnapshotRow)
            .where(PortfolioValueSnapshotRow.portfolio_id == portfolio_id)
            .order_by(PortfolioValueSnapshotRow.as_of.desc())
            .limit(limit)
        ).scalars().all()
    return [
        SnapshotPoint(
            as_of=row.as_of,
            total_value=float(row.total_value),
            cash=float(row.cash),
            invested_value=float(row.invested_value),
            drawdown_pct=float(row.drawdown_pct),
            source=row.source,
            predicted_vol_ann=(
                float(row.predicted_vol_ann)
                if row.predicted_vol_ann is not None else None
            ),
        )
        for row in reversed(rows)
    ]


def _tier2_block(
    metric: str, *, value: float | None, sufficient: bool, n_observations: int,
    window_days: int,
) -> dict:
    """A Tier-2 block in the same uncertainty contract every Tier-1 block uses.

    `standard_error` is null always — Tier 2 is descriptive, not estimated —
    and `backcast` is false, because this is history that actually happened
    rather than today's weights applied to past returns.
    """
    return {
        "metric": metric,
        "value": value if sufficient else None,
        "standard_error": None,
        "n_observations": n_observations,
        "t_eff": None,
        "window_days": window_days,
        "sufficient": sufficient,
        "partial": False,
        "dropped_holdings": [],
        "low_explanatory_power": None,
        "contains_etfs": False,
        "backcast": False,
        "basis": BASIS_TOTAL_VALUE,
        "engine_version": ENGINE_VERSION,
        "insufficient_cause": None if sufficient else "short_window",
    }


def tier2_blocks(points: Sequence[SnapshotPoint]) -> dict[str, dict]:
    """`realised_max_drawdown` + `realised_return` over the trailing window.

    Pure over the points — no DB. The window is always stated, because a
    drawdown figure without its window is not interpretable and F10's whole
    point is that the window is what makes the number improvable.
    """
    window = list(points[-TIER2_MDD_WINDOW_SNAPSHOTS:])
    values = [p.total_value for p in window]

    mdd_sufficient = len(window) >= TIER2_MIN_SNAPSHOTS
    mdd_value = max_drawdown_pct(values) if mdd_sufficient else None
    if mdd_value is None:
        # A non-positive value anywhere leaves no meaningful peak denominator.
        mdd_sufficient = False

    return_sufficient = len(window) >= 2 and values[0] > 0.0
    return_value = (
        round((values[-1] / values[0] - 1.0) * 100.0, 2) if return_sufficient else None
    )

    return {
        "realised_max_drawdown": _tier2_block(
            "realised_max_drawdown",
            value=mdd_value,
            sufficient=mdd_sufficient,
            n_observations=len(window),
            window_days=len(window),
        ),
        "realised_return": _tier2_block(
            "realised_return",
            value=return_value,
            sufficient=return_sufficient,
            n_observations=len(window),
            window_days=len(window),
        ),
    }


# ── The F16 bias test ───────────────────────────────────────────────────────


def bias_z_stats(points: Sequence[SnapshotPoint]) -> BiasStats:
    """sd of z = realised daily return / predicted daily vol (Rev 4 F16).

    The denominator is the PRIOR point's prediction — a forecast is only
    testable one step ahead, and using the same day's prediction would let the
    model see the return it is being scored on.

    Units cancel only because both sides are decimal fractions, which is why
    `predicted_vol_ann` is pinned as a fraction rather than a percentage.

    Reports `n` and never verdicts: Rev 4's [0.911, 1.089] band applies AT
    T=252, and quoting it against a handful of observations would be exactly the
    over-confident reading the whole uncertainty contract exists to prevent.
    """
    daily = TRADING_DAYS_PER_YEAR ** 0.5
    z_values: list[float] = []
    for prev, cur in zip(points, points[1:]):
        if prev.predicted_vol_ann is None or prev.predicted_vol_ann <= 0.0:
            continue
        if prev.total_value <= 0.0 or cur.total_value <= 0.0:
            continue
        realised = cur.total_value / prev.total_value - 1.0
        z_values.append(realised / (prev.predicted_vol_ann / daily))

    n = len(z_values)
    return BiasStats(
        n=n,
        mean_z=statistics.fmean(z_values) if n >= 1 else None,
        sd_z=statistics.stdev(z_values) if n >= 2 else None,
    )
