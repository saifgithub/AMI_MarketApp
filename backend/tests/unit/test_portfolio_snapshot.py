"""CR136 M03 — snapshot tick idempotency, trading-day gate, reset boundary, rolling-MDD windowing + 21-day floor, drawdown-conflation guard, bias helper.

Two of these tests are the reason the module exists in the shape it does. T8
pins the F10 finding — an expanding-window max drawdown is a ratchet a
de-risking user can never improve, so the number they are being taught to manage
has to be the rolling one. T9 pins the Rev 2 defect: two different quantities in
this codebase were both called "drawdown", and the Tier-2 block must compute its
own rather than read the stored column.
"""

from __future__ import annotations

import math
import random
from datetime import date, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select

from app.db import get_session
from app.db.models import PortfolioValueSnapshotRow
from app.services.portfolio_health import PredictedVol
from app.services.portfolio_health_constants import (
    BIAS_SD_BAND,
    ENGINE_VERSION,
    SNAPSHOT_SOURCE_CASH_ONLY,
    TIER2_MDD_WINDOW_SNAPSHOTS,
    TIER2_MIN_SNAPSHOTS,
)
from app.services.portfolio_snapshot import (
    SnapshotPoint,
    bias_z_stats,
    equity_curve,
    run_portfolio_snapshot_tick,
    tier2_blocks,
)
from app.services.sim_engine import get_sim_engine
from app.trading_math import max_drawdown_pct

_DAY = date(2026, 8, 3)


def _vol(sigma: float = 0.262, n: int = 126):
    return lambda _user_id: PredictedVol(
        predicted_vol_ann=sigma, n_observations=n, engine_version=ENGINE_VERSION,
    )


def _tick(**kwargs):
    kwargs.setdefault("trading_day", lambda: _DAY)
    kwargs.setdefault("vol_provider", _vol())
    return run_portfolio_snapshot_tick(**kwargs)


def _rows() -> list[PortfolioValueSnapshotRow]:
    with get_session() as session:
        return list(session.execute(
            select(PortfolioValueSnapshotRow)
            .order_by(PortfolioValueSnapshotRow.as_of)
        ).scalars().all())


def _row_count() -> int:
    with get_session() as session:
        return session.execute(
            select(func.count()).select_from(PortfolioValueSnapshotRow)
        ).scalar_one()


def _points(
    values: list[float], *, start: date = date(2026, 1, 5),
    vol: float | None = 0.262, drawdown_sentinel: float = 99.0,
) -> list[SnapshotPoint]:
    """`drawdown_pct` is a SENTINEL on purpose — if any Tier-2 number ever reads
    that field, 99.0 shows up in the output and the test fails."""
    return [
        SnapshotPoint(
            as_of=start + timedelta(days=i),
            total_value=v,
            cash=0.0,
            invested_value=v,
            drawdown_pct=drawdown_sentinel,
            source="yahoo",
            predicted_vol_ann=vol,
        )
        for i, v in enumerate(values)
    ]


# ── T1-T5. The tick ─────────────────────────────────────────────────────────


def test_one_row_per_portfolio_per_trading_day() -> None:
    sim = get_sim_engine()
    users = [uuid4(), uuid4()]
    for user_id in users:
        sim.ensure_portfolio(user_id)

    stats = _tick()
    assert stats["as_of"] == _DAY.isoformat()
    assert stats["portfolios"] == 2
    assert stats["written"] == 2
    assert stats["skipped_existing"] == 0
    assert stats["vol_null"] == 0

    rows = _rows()
    assert len(rows) == 2
    for row in rows:
        assert row.as_of == _DAY
        assert float(row.invested_value) == 0.0, "a cash-only book holds nothing"
        assert float(row.drawdown_pct) == 0.0
        assert row.predicted_vol_ann == pytest.approx(0.262)
        assert row.n_observations == 126
        assert row.engine_version == ENGINE_VERSION
        assert row.source
        assert float(row.total_value) == pytest.approx(float(row.cash))


def test_tick_is_idempotent_within_a_trading_day() -> None:
    sim = get_sim_engine()
    for _ in range(2):
        sim.ensure_portfolio(uuid4())

    _tick()
    second = _tick()
    assert second["written"] == 0
    assert second["skipped_existing"] == 2
    assert _row_count() == 2


def test_no_trading_day_is_a_loud_no_op() -> None:
    """Writing a row stamped with a guessed date would put a hole in the very
    series the bias test exists to validate."""
    get_sim_engine().ensure_portfolio(uuid4())
    stats = _tick(trading_day=lambda: None)
    assert stats["as_of"] == "none"
    assert stats["written"] == 0
    assert _row_count() == 0

    # The weekend shape: Friday's row exists and Saturday's tick still resolves
    # to Friday, so nothing new is written.
    _tick()
    assert _row_count() == 1
    _tick()
    assert _row_count() == 1


def test_a_vol_engine_failure_never_blocks_the_value_row() -> None:
    """Realised history is the thing that cannot be recovered later. A missing
    prediction is honestly representable as null; a missing row is not."""
    get_sim_engine().ensure_portfolio(uuid4())

    def _boom(_user_id):
        raise RuntimeError("engine down")

    stats = _tick(vol_provider=_boom)
    assert stats["written"] == 1
    assert stats["vol_null"] == 1

    row = _rows()[0]
    assert row.predicted_vol_ann is None
    assert row.n_observations is None
    assert row.engine_version is None


def test_a_none_prediction_is_stored_as_null_not_zero() -> None:
    """Mock mode, an insufficient window, or an empty book all yield None. 0.0
    would read as a confident prediction of no risk at all."""
    get_sim_engine().ensure_portfolio(uuid4())
    stats = _tick(vol_provider=lambda _u: None)
    assert stats["vol_null"] == 1
    assert _rows()[0].predicted_vol_ann is None


# ── T6. Reset boundary ──────────────────────────────────────────────────────


def test_a_reset_starts_a_fresh_series() -> None:
    sim = get_sim_engine()
    user_id = uuid4()
    old_id = sim.ensure_portfolio(user_id).id

    _tick()
    assert len(equity_curve(old_id)) == 1

    sim.reset_portfolio(user_id)
    new_id = sim.ensure_portfolio(user_id).id
    assert new_id != old_id
    assert equity_curve(old_id) == [], (
        "the destroyed portfolio takes its snapshots with it — explicitly, "
        "because sqlite does not enforce the FK cascade"
    )

    _tick()
    assert len(equity_curve(new_id)) == 1
    assert _row_count() == 1


# ── T7-T8. Rolling max drawdown ─────────────────────────────────────────────


def test_rolling_mdd_floor_at_twenty_one_snapshots() -> None:
    """The old "≥2 snapshots" floor was vacuous — a two-point series always has
    a drawdown of either 0 or whatever the second point is."""
    just_under = tier2_blocks(_points([100.0] * (TIER2_MIN_SNAPSHOTS - 1)))
    block = just_under["realised_max_drawdown"]
    assert block["sufficient"] is False
    assert block["value"] is None
    assert block["standard_error"] is None
    assert block["n_observations"] == TIER2_MIN_SNAPSHOTS - 1

    at_floor = tier2_blocks(_points([100.0] * TIER2_MIN_SNAPSHOTS))
    block = at_floor["realised_max_drawdown"]
    assert block["sufficient"] is True
    assert block["value"] == 0.0


def test_rolling_window_restores_improvability() -> None:
    """Rev 4 F10, the whole reason the window is rolling: after a crash and a
    long recovery the rolling figure returns to 0 while an expanding-window
    maximum is stuck at the crash forever, so a de-risking user watches a number
    that their behaviour cannot move."""
    values = [100.0 - (40.0 * i / 29.0) for i in range(30)]          # 100 → 60
    values += [60.0 + (15.0 * i / 269.0) for i in range(1, 271)]     # 60 → 75
    assert len(values) == 300

    at_100 = tier2_blocks(_points(values[:101]))["realised_max_drawdown"]
    assert at_100["value"] == pytest.approx(40.0, abs=0.05)

    at_end = tier2_blocks(_points(values))["realised_max_drawdown"]
    assert at_end["n_observations"] == TIER2_MDD_WINDOW_SNAPSHOTS
    assert at_end["value"] == 0.0, "the trailing window has left the crash behind"

    expanding = max_drawdown_pct(values)
    assert expanding == pytest.approx(40.0, abs=0.05)
    assert at_end["value"] < expanding


def test_the_window_is_always_stated() -> None:
    blocks = tier2_blocks(_points([100.0] * 400))
    for name in ("realised_max_drawdown", "realised_return"):
        block = blocks[name]
        assert block["window_days"] == TIER2_MDD_WINDOW_SNAPSHOTS
        assert block["n_observations"] == TIER2_MDD_WINDOW_SNAPSHOTS
        assert block["backcast"] is False, "realised history is not a backcast"
        assert block["standard_error"] is None, "Tier 2 is descriptive"
        assert block["t_eff"] is None
        assert block["basis"] == "total_value"
        assert block["engine_version"] == ENGINE_VERSION


# ── T9. The drawdown-conflation guard ───────────────────────────────────────


def test_the_two_drawdowns_are_never_conflated() -> None:
    """Rev 2 defect 5. On $10k → $15k → $12k the vs-starting-capital column
    reads 0.0 and the Tier-2 peak-to-trough reads 20.0. Both are correct; they
    are different questions."""
    sim = get_sim_engine()
    user_id = uuid4()
    sim.ensure_portfolio(user_id)
    _tick()
    stored = _rows()[0]
    assert float(stored.drawdown_pct) == 0.0, (
        "a cash-only book at starting capital has not drawn down at all"
    )

    values = [10_000.0] * 19 + [15_000.0, 12_000.0]
    assert len(values) == TIER2_MIN_SNAPSHOTS
    blocks = tier2_blocks(_points(values, drawdown_sentinel=99.0))
    assert blocks["realised_max_drawdown"]["value"] == pytest.approx(20.0)

    # The sentinel: if any Tier-2 number ever read the stored column, 99.0 would
    # surface here.
    assert 99.0 not in [
        blocks[name][key]
        for name in blocks for key in ("value", "n_observations", "window_days")
    ]


def test_realised_return_is_window_labelled() -> None:
    blocks = tier2_blocks(_points([100.0] * 20 + [110.0]))
    block = blocks["realised_return"]
    assert block["sufficient"] is True
    assert block["value"] == pytest.approx(10.0)
    assert block["window_days"] == 21

    single = tier2_blocks(_points([100.0]))["realised_return"]
    assert single["sufficient"] is False
    assert single["value"] is None


# ── T10-T11. The F16 bias helper ────────────────────────────────────────────


def test_bias_helper_is_calibrated() -> None:
    """Built so sd(z) must land in the band by construction: 252 daily returns
    drawn at exactly the volatility the rows claim to predict."""
    rnd = random.Random(42)
    sigma_ann = 0.262
    daily = sigma_ann / math.sqrt(252)
    values = [10_000.0]
    for _ in range(252):
        values.append(values[-1] * (1.0 + rnd.gauss(0.0, daily)))

    stats = bias_z_stats(_points(values, vol=sigma_ann))
    assert stats.n == 252
    low, high = BIAS_SD_BAND
    assert low <= stats.sd_z <= high, stats.sd_z

    # Half the volatility claimed ⇒ z roughly doubles, and the band catches it.
    understated = bias_z_stats(_points(values, vol=sigma_ann / 2.0))
    assert understated.sd_z == pytest.approx(2.0 * stats.sd_z, rel=1e-9)
    assert not (low <= understated.sd_z <= high)


def test_bias_helper_skips_pairs_without_a_prior_prediction() -> None:
    """M03 r1 m1 — this test used to be unable to tell PRIOR from CURRENT.

    The old fixture nulled `predicted_vol_ann` on alternating indices, so a
    prev-guard yields pairs from {0,2} and a cur-guard yields {2,4}: `n == 2`
    either way. The count was the only assertion, so it distinguished nothing,
    and the lane doc's claim that QA-D proved "two independent assertions" on
    one-step-ahead alignment was wrong — the second kill was this test CRASHING
    on a `None` divisor, not asserting anything.

    Nulling only the LAST point is what separates the two: a prev-guard is
    unaffected (the last point is never a divisor) and a cur-guard loses a pair.
    """
    values = [100.0, 101.0, 102.0, 103.0, 104.0]
    points = _points(values, vol=0.262)
    holed = [
        p._replace(predicted_vol_ann=None) if i % 2 else p
        for i, p in enumerate(points)
    ]
    stats = bias_z_stats(holed)
    assert stats.n == 2, "only pairs whose PRIOR point carries a prediction count"

    tail_only = [*points[:-1], points[-1]._replace(predicted_vol_ann=None)]
    assert bias_z_stats(tail_only).n == 4, (
        "the FINAL point's prediction is never a divisor — every one of the 4 "
        "pairs still has a prior. A cur-guard reads 3 here, which is the whole "
        "point of pinning it this way"
    )

    head_only = [points[0]._replace(predicted_vol_ann=None), *points[1:]]
    assert bias_z_stats(head_only).n == 3, (
        "the FIRST point's prediction is the divisor for pair 0 and nothing "
        "else, so exactly one pair drops"
    )

    assert bias_z_stats(_points([100.0, 101.0], vol=None)).n == 0
    assert bias_z_stats(_points([100.0, 101.0], vol=None)).sd_z is None
    assert bias_z_stats(_points([100.0, 101.0], vol=0.262)).sd_z is None, (
        "one z value has no sample standard deviation"
    )


def test_bias_uses_the_prior_prediction_not_the_current_one() -> None:
    """A forecast is only testable one step ahead; scoring a return against the
    prediction made after it would let the model see its own answer."""
    points = [
        SnapshotPoint(date(2026, 1, 5), 100.0, 0.0, 100.0, 0.0, "yahoo", 0.262),
        SnapshotPoint(date(2026, 1, 6), 110.0, 0.0, 110.0, 0.0, "yahoo", 999.0),
    ]
    stats = bias_z_stats(points)
    assert stats.n == 1
    expected = 0.10 / (0.262 / math.sqrt(252))
    assert stats.mean_z == pytest.approx(expected)


# ── T12. The database backstop ──────────────────────────────────────────────


def test_the_unique_constraint_is_the_backstop() -> None:
    from sqlalchemy.exc import IntegrityError

    sim = get_sim_engine()
    user_id = uuid4()
    portfolio_id = sim.ensure_portfolio(user_id).id

    def _insert() -> None:
        with get_session() as session:
            session.add(PortfolioValueSnapshotRow(
                user_id=user_id, portfolio_id=portfolio_id, as_of=_DAY,
                total_value=1.0, cash=1.0, invested_value=0.0,
                drawdown_pct=0.0, source="yahoo",
            ))

    _insert()
    with pytest.raises(IntegrityError):
        _insert()


# ── T13-T16. DEF217 — provenance ────────────────────────────────────────────
#
# The tick's existing guard resolves the trading DAY from SPY and aborts the
# whole sweep; nothing checked whether an individual book's own tickers were
# priced for real. Tier 1 has made exactly this refusal per portfolio since it
# shipped (`portfolio_health.py:756`) — these pin that Tier 2 now matches it.


class _MarkedHolding:
    ticker, quantity = "AAA", 10.0


class _MarkedSim:
    """A sim whose valuations carry a chosen provenance.

    `holdings` is the axis under test, not incidental detail: the empty case is
    what the live measurement actually found (92 of 92 mock-labelled rows had
    `invested_value = 0`), and a fix that refused those would throw away exact
    history.
    """

    def __init__(self, source: str, *, holdings: bool) -> None:
        self._source = source
        self._holdings = [_MarkedHolding()] if holdings else []

    def portfolio_marks_snapshot(self, _user_id):
        class _Portfolio:
            holdings = self._holdings
            current_cash = 100.0

        total = 1_100.0 if self._holdings else 100.0
        return _Portfolio(), {"AAA": 100.0}, total, 0.0, self._source


def _tick_with(monkeypatch, source: str, *, holdings: bool, real_data: bool = True):
    from app.core.config import settings

    monkeypatch.setattr(settings, "use_real_market_data", real_data)
    monkeypatch.setattr(
        "app.services.sim_engine.get_sim_engine",
        lambda: _MarkedSim(source, holdings=holdings),
    )
    return _tick()


def test_a_book_priced_from_mock_marks_writes_no_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valuation drawn from a random walk is a fabricated point in the very
    series F16 validates the model against. `realised_return` needs only two
    snapshots, so it would publish almost immediately."""
    get_sim_engine().ensure_portfolio(uuid4())

    stats = _tick_with(monkeypatch, "mock_walk", holdings=True)
    assert stats["written"] == 0
    assert stats["mock_refused"] == 1
    assert _row_count() == 0


def test_a_real_priced_book_is_still_written(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The vacuity guard: a refusal that fires on everything is not a refusal."""
    get_sim_engine().ensure_portfolio(uuid4())

    stats = _tick_with(monkeypatch, "yfinance", holdings=True)
    assert stats["written"] == 1
    assert stats["mock_refused"] == 0
    assert _rows()[0].source == "yfinance"


def test_an_all_cash_book_is_labelled_cash_only_not_mock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MEASURED on live Alpha 2026-08-05: all 92 rows labelled `mock_walk` had
    `invested_value = 0` — all-cash books whose total_value is EXACT, mislabelled
    because `_aggregate_source_from_quotes({})` returns `mock_walk` for an empty
    quote dict. No quote was consulted, so there was nothing to fabricate. The
    label had to stop colliding before anything could filter on it."""
    get_sim_engine().ensure_portfolio(uuid4())

    stats = _tick_with(monkeypatch, "mock_walk", holdings=False)
    assert stats["written"] == 1
    assert stats["mock_refused"] == 0

    row = _rows()[0]
    assert row.source == SNAPSHOT_SOURCE_CASH_ONLY
    assert float(row.invested_value) == 0.0
    assert len(equity_curve(row.portfolio_id)) == 1, (
        "an exact cash valuation belongs in the curve"
    )


def test_the_curve_excludes_stored_mock_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read-side defence in depth, the same filter `price_history` applies at
    `:175` and `:499`. Covers rows written before the tick's guard existed, and
    whatever a non-real-data environment produces — where the row is still
    written for the record but can never become a realised number."""
    sim = get_sim_engine()
    user_id = uuid4()
    portfolio_id = sim.ensure_portfolio(user_id).id

    with get_session() as session:
        for i, source in enumerate(("yfinance", "mock_walk", "cash_only")):
            session.add(PortfolioValueSnapshotRow(
                user_id=user_id, portfolio_id=portfolio_id,
                as_of=_DAY - timedelta(days=i),
                total_value=100.0, cash=100.0, invested_value=0.0,
                drawdown_pct=0.0, source=source,
            ))

    assert _row_count() == 3
    sources = {p.source for p in equity_curve(portfolio_id)}
    assert sources == {"yfinance", "cash_only"}


def test_mock_mode_still_records_but_never_serves(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The refusal is gated on `use_real_market_data`, exactly like Tier 1's:
    in a mock environment mock IS the intended source, so the row is kept for
    the record — and the read filter is what stops it reaching a user."""
    get_sim_engine().ensure_portfolio(uuid4())

    stats = _tick_with(monkeypatch, "mock_walk", holdings=True, real_data=False)
    assert stats["written"] == 1
    assert stats["mock_refused"] == 0
    assert equity_curve(_rows()[0].portfolio_id) == []


def test_equity_curve_is_ascending_and_portfolio_scoped() -> None:
    sim = get_sim_engine()
    a, b = uuid4(), uuid4()
    id_a = sim.ensure_portfolio(a).id
    id_b = sim.ensure_portfolio(b).id

    for offset in (2, 0, 1):
        _tick(trading_day=lambda o=offset: _DAY - timedelta(days=o))

    curve = equity_curve(id_a)
    assert [p.as_of for p in curve] == sorted(p.as_of for p in curve)
    assert len(curve) == 3
    assert len(equity_curve(id_b)) == 3
    assert equity_curve(UUID(int=0)) == []
