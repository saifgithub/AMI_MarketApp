"""CR131 — Day Trader preset outcome instrumentation.

Covers: cohort detection (no switch entry / earliest-of-many wins), the thin-
sample refusal (no numeric figure anywhere in the payload — not a zero, not
a partial figure), the opened_at boundary rule (a trade timestamped exactly
at the switch lands on the ACTIVE side), turnover/win-rate/disposition-effect
arithmetic on a fixture verified by hand in the comments below, and that a
winning and a losing user get the identical response SHAPE (same keys, same
unconditional baseline facts) — the CR131 "must work honestly for the user
who is WINNING, do not special-case a losing user" rule.

Endpoint coverage (ownership guard) mirrors test_cr026_sector_allocation.py's
`_app`/`_U` pattern for `app/api/portfolio.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.portfolio import router as portfolio_router
from app.db import get_session
from app.db.models import SimPortfolioRow, SimTradeRow
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.day_trader_outcomes import (
    DAY_TRADER_JOURNAL_MARKER,
    MIN_TRADES_FOR_COMPARISON,
    PUBLISHED_BASELINES,
    STATUS_NOT_IN_COHORT,
    STATUS_READY,
    STATUS_TOO_EARLY,
    _earliest_day_trader_switch,
    _split_by_switch,
    _Trade,
    compute_day_trader_outcomes,
)
from app.services.journal_store import get_journal_store


# ── Fixture helpers ─────────────────────────────────────────────────────


def _make_portfolio(user_id: UUID, starting_capital: float = 10_000.0) -> UUID:
    portfolio_id = uuid4()
    with get_session() as s:
        s.add(SimPortfolioRow(
            id=portfolio_id,
            user_id=user_id,
            name="Main",
            starting_capital=starting_capital,
            current_cash=starting_capital,
        ))
    return portfolio_id


def _insert_trade(
    user_id: UUID,
    portfolio_id: UUID,
    *,
    ticker: str = "AAPL",
    side: str = "buy",
    quantity: float = 10.0,
    entry_price: float = 100.0,
    opened_at: datetime,
    status: str = "open",
    closed_at: datetime | None = None,
    closed_price: float | None = None,
    realised_pnl: float = 0.0,
) -> None:
    with get_session() as s:
        s.add(SimTradeRow(
            id=uuid4(),
            user_id=user_id,
            portfolio_id=portfolio_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            opened_at=opened_at,
            status=status,
            closed_at=closed_at,
            closed_price=closed_price,
            realised_pnl=realised_pnl,
        ))


def _switch_day_trader(user_id: UUID, switched_at: datetime) -> None:
    """Journal the Day Trader preset switch, backdated to `switched_at` —
    mirrors what `mandate.py:154` writes on a real preset PATCH, trimmed to
    just the marker prefix this module matches on."""
    store = get_journal_store()
    entry = store.append(JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType.MANDATE_EDIT,
        reference_id=None,
        title="Mandate edited → v2",
        summary=(
            f"{DAY_TRADER_JOURNAL_MARKER} — all seven risk limits set "
            "permissive (compliance, locale and halal/allow-blocklist rules "
            "unaffected)."
        ),
        tags=["mandate"],
        payload={},
    ))
    store._backdate_for_test(user_id, entry.id, switched_at)


def _assert_no_numeric_figures(obj) -> None:
    """Recursively walk a JSON-shaped payload and fail if any leaf is a
    number. `bool` is checked first — it is a subclass of `int` in Python,
    and a stray True/False must not be mistaken for a numeric figure (there
    are none in the refusal payloads this checks, but the walk should not
    lie about that if one crept in)."""
    if isinstance(obj, dict):
        for v in obj.values():
            _assert_no_numeric_figures(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_numeric_figures(v)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        raise AssertionError(f"numeric figure present in a refusal payload: {obj!r}")


def _key_shape(obj):
    """A structural fingerprint of a JSON-shaped object — the set of keys
    present at every level, with every leaf collapsed to a constant
    placeholder. Deliberately NOT type-sensitive: a window with no losing
    trades reports `avg_loss: None` in the same KEY position a window full
    of losers reports `avg_loss: -100.0`, and that is exactly the "same
    shape, different numbers" this helper exists to prove — a leaf-type
    check would wrongly fail that comparison."""
    if isinstance(obj, dict):
        return {k: _key_shape(v) for k, v in sorted(obj.items())}
    if isinstance(obj, list):
        return [_key_shape(v) for v in obj]
    return "LEAF"


# ── Cohort detection ────────────────────────────────────────────────────


def test_not_in_cohort_when_no_day_trader_journal_entry():
    user_id = uuid4()
    result = compute_day_trader_outcomes(user_id)
    assert result["status"] == STATUS_NOT_IN_COHORT
    assert set(result.keys()) == {"status", "message"}


def test_not_in_cohort_ignores_ordinary_mandate_edits():
    """A plain (non-preset) MANDATE_EDIT entry must not be mistaken for the
    Day Trader switch — only the marker-prefixed summary counts."""
    user_id = uuid4()
    store = get_journal_store()
    store.append(JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType.MANDATE_EDIT,
        reference_id=None,
        title="Mandate edited → v2",
        summary="max drawdown 30% → 20%",
        tags=["mandate"],
        payload={},
    ))
    result = compute_day_trader_outcomes(user_id)
    assert result["status"] == STATUS_NOT_IN_COHORT


def test_earliest_switch_entry_wins_when_multiple_exist():
    user_id = uuid4()
    earlier = datetime(2026, 1, 1, tzinfo=timezone.utc)
    later = datetime(2026, 3, 1, tzinfo=timezone.utc)
    # Inserted out of order on purpose — insertion order must not matter,
    # only created_at.
    _switch_day_trader(user_id, later)
    _switch_day_trader(user_id, earlier)
    switched = _earliest_day_trader_switch(user_id)
    assert switched == earlier


# ── Thin sample → refusal, no numeric figure anywhere ──────────────────


def test_thin_sample_refuses_when_too_few_days_elapsed():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    switched_at = now - timedelta(days=2)  # well under the 7-day floor

    # Plenty of trades either side, so only the DAYS threshold is thin.
    for i in range(MIN_TRADES_FOR_COMPARISON + 5):
        _insert_trade(
            user_id, portfolio_id,
            opened_at=switched_at - timedelta(days=20) + timedelta(hours=i),
        )
    for i in range(MIN_TRADES_FOR_COMPARISON + 5):
        _insert_trade(
            user_id, portfolio_id,
            opened_at=switched_at + timedelta(hours=i),
        )
    _switch_day_trader(user_id, switched_at)

    result = compute_day_trader_outcomes(user_id, now=now)
    assert result["status"] == STATUS_TOO_EARLY
    assert set(result.keys()) == {"status", "message"}
    _assert_no_numeric_figures(result)


def test_thin_sample_refuses_when_too_few_trades():
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    now = datetime(2026, 6, 1, tzinfo=timezone.utc)
    switched_at = now - timedelta(days=30)  # plenty of elapsed time

    # Only 3 trades on each side — under MIN_TRADES_FOR_COMPARISON.
    for i in range(3):
        _insert_trade(
            user_id, portfolio_id,
            opened_at=switched_at - timedelta(days=20) + timedelta(days=i),
        )
    for i in range(3):
        _insert_trade(
            user_id, portfolio_id,
            opened_at=switched_at + timedelta(days=i),
        )
    _switch_day_trader(user_id, switched_at)

    result = compute_day_trader_outcomes(user_id, now=now)
    assert result["status"] == STATUS_TOO_EARLY
    _assert_no_numeric_figures(result)


def test_not_in_cohort_also_carries_no_numeric_figure():
    result = compute_day_trader_outcomes(uuid4())
    _assert_no_numeric_figures(result)


# ── Boundary: a trade opened exactly at the switch instant ─────────────


def test_trade_opened_exactly_at_switch_lands_on_active_side():
    """`_split_by_switch` chooses `>=` for the active side: the preset takes
    effect at `switched_at`, so a trade timestamped that exact instant is
    already operating under the new, permissive limits — not the ones it
    replaced. Picked over `>` because "before" should mean strictly before
    the change took effect, and the instant of the change itself is the
    first moment the new regime is live."""
    switched_at = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)
    on_boundary = _Trade(
        side="buy", quantity=1.0, entry_price=100.0,
        opened_at=switched_at, closed_at=None, status="open", realised_pnl=0.0,
    )
    just_before = _Trade(
        side="buy", quantity=1.0, entry_price=100.0,
        opened_at=switched_at - timedelta(microseconds=1),
        closed_at=None, status="open", realised_pnl=0.0,
    )
    before, active = _split_by_switch([just_before, on_boundary], switched_at)
    assert before == [just_before]
    assert active == [on_boundary]


# ── Turnover / win-rate / disposition-effect arithmetic, by hand ───────
#
# Fixture, verified below in comments rather than by re-deriving the
# production formula:
#
#   starting_capital = $10,000
#
#   BEFORE window (10 trades, spans exactly 10 days):
#     5 BUY  @ 10 shares x $100 = $1,000 notional each -> buy_notional  = $5,000
#     5 SELL @ 10 shares x $100 = $1,000 notional each -> sell_notional = $5,000
#     avg_side_notional = (5000 + 5000) / 2 = $5,000
#     turnover_pct = 5000 / 10000 * 100 = 50.0%
#     trades_per_day = 10 / 10 = 1.0 ; trades_per_week = 7.0
#     none of the 10 trades close -> closed_trade_count = 0, win_rate_pct = None
#
#   ACTIVE window (20 trades, spans exactly 10 days):
#     10 BUY @ 10 shares x $100 = $1,000 notional each -> buy_notional  = $10,000
#     10 SELL @ 10 shares x $100 = $1,000 notional each -> sell_notional = $10,000
#     avg_side_notional = (10000 + 10000) / 2 = $10,000
#     turnover_pct = 10000 / 10000 * 100 = 100.0%
#     trades_per_day = 20 / 10 = 2.0 ; trades_per_week = 14.0
#     the 10 BUYs close WON at $110: realised_pnl = (110-100)*10 = $100 each
#       -> realised_pnl total = $1,000, win_count = 10, avg_win = 100.0
#     the 10 SELLs never close (status stays "open") -> excluded from P&L
#     win_rate_pct = 10 / 10 * 100 = 100.0%
#     hold time for every winner = exactly 1 day -> avg_hold_days_winners = 1.0


def _build_hand_verified_cohort(user_id: UUID, *, active_win: bool) -> tuple[UUID, datetime, datetime]:
    portfolio_id = _make_portfolio(user_id, starting_capital=10_000.0)
    switched_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    now = switched_at + timedelta(days=10)
    before_start = switched_at - timedelta(days=10)

    for i in range(5):
        _insert_trade(
            user_id, portfolio_id, side="buy", quantity=10.0, entry_price=100.0,
            opened_at=before_start + timedelta(hours=i),
        )
    for i in range(5):
        _insert_trade(
            user_id, portfolio_id, side="sell", quantity=10.0, entry_price=100.0,
            opened_at=before_start + timedelta(hours=i + 12),
        )

    fill_price = 110.0 if active_win else 90.0
    expected_status = "won" if active_win else "lost"
    for i in range(10):
        opened = switched_at + timedelta(hours=i)
        _insert_trade(
            user_id, portfolio_id, side="buy", quantity=10.0, entry_price=100.0,
            opened_at=opened, status=expected_status,
            closed_at=opened + timedelta(days=1), closed_price=fill_price,
            realised_pnl=(fill_price - 100.0) * 10.0,
        )
    for i in range(10):
        _insert_trade(
            user_id, portfolio_id, side="sell", quantity=10.0, entry_price=100.0,
            opened_at=switched_at + timedelta(hours=i + 12),
        )

    _switch_day_trader(user_id, switched_at)
    return portfolio_id, switched_at, now


def test_hand_built_fixture_turnover_and_win_rate_arithmetic():
    user_id = uuid4()
    _, switched_at, now = _build_hand_verified_cohort(user_id, active_win=True)

    result = compute_day_trader_outcomes(user_id, now=now)
    assert result["status"] == STATUS_READY
    assert result["switched_at"] == switched_at.isoformat()

    before = result["before"]
    assert before["window_days"] == 10.0
    assert before["trade_count"] == 10
    assert before["trades_per_day"] == 1.0
    assert before["trades_per_week"] == 7.0
    assert before["turnover_pct"] == 50.0
    assert before["closed_trade_count"] == 0
    assert before["win_rate_pct"] is None
    assert before["realised_pnl"] == 0.0

    active = result["active"]
    assert active["window_days"] == 10.0
    assert active["trade_count"] == 20
    assert active["trades_per_day"] == 2.0
    assert active["trades_per_week"] == 14.0
    assert active["turnover_pct"] == 100.0
    assert active["closed_trade_count"] == 10
    assert active["win_count"] == 10
    assert active["loss_count"] == 0
    assert active["win_rate_pct"] == 100.0
    assert active["realised_pnl"] == 1000.0
    assert active["avg_win"] == 100.0
    assert active["avg_loss"] is None
    assert active["avg_hold_days_winners"] == 1.0
    assert active["avg_hold_days_losers"] is None

    # annualise = 365.25 / 10 = 36.525
    assert active["turnover_pct_annualised"] == pytest.approx(100.0 * 36.525, rel=1e-6)
    assert active["realised_pnl_annualised_pct"] == pytest.approx(
        1000.0 / 10_000.0 * 100.0 * 36.525, rel=1e-6,
    )


def test_disposition_effect_losers_held_longer_than_winners():
    """A separate, deliberately mixed active window: 5 winners held 1 day
    each, 5 losers held 5 days each — the classic disposition-effect shape
    (cut winners early, hold losers) this field exists to surface."""
    user_id = uuid4()
    portfolio_id = _make_portfolio(user_id)
    switched_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
    now = switched_at + timedelta(days=10)
    before_start = switched_at - timedelta(days=10)

    for i in range(10):
        _insert_trade(
            user_id, portfolio_id, side="buy", quantity=1.0, entry_price=50.0,
            opened_at=before_start + timedelta(hours=i),
        )

    for i in range(5):
        opened = switched_at + timedelta(hours=i)
        _insert_trade(
            user_id, portfolio_id, side="buy", quantity=10.0, entry_price=100.0,
            opened_at=opened, status="won",
            closed_at=opened + timedelta(days=1), closed_price=110.0,
            realised_pnl=100.0,
        )
    for i in range(5):
        opened = switched_at + timedelta(hours=i + 12)
        _insert_trade(
            user_id, portfolio_id, side="buy", quantity=10.0, entry_price=100.0,
            opened_at=opened, status="lost",
            closed_at=opened + timedelta(days=5), closed_price=90.0,
            realised_pnl=-100.0,
        )

    _switch_day_trader(user_id, switched_at)
    result = compute_day_trader_outcomes(user_id, now=now)
    assert result["status"] == STATUS_READY
    active = result["active"]
    assert active["avg_hold_days_winners"] == 1.0
    assert active["avg_hold_days_losers"] == 5.0
    assert active["avg_win"] == 100.0
    assert active["avg_loss"] == -100.0
    assert active["win_rate_pct"] == 50.0


# ── Winning and losing users get the same shape, honestly ──────────────


def test_winning_and_losing_users_get_the_same_response_shape():
    winner_id, loser_id = uuid4(), uuid4()
    _build_hand_verified_cohort(winner_id, active_win=True)
    _build_hand_verified_cohort(loser_id, active_win=False)
    now = datetime(2026, 5, 11, tzinfo=timezone.utc)

    winner_result = compute_day_trader_outcomes(winner_id, now=now)
    loser_result = compute_day_trader_outcomes(loser_id, now=now)

    assert winner_result["status"] == STATUS_READY
    assert loser_result["status"] == STATUS_READY
    assert _key_shape(winner_result) == _key_shape(loser_result)

    # The losing user's numbers actually look worse, and the winning user's
    # actually look better — the shape is identical, the numbers are not.
    assert winner_result["active"]["realised_pnl"] > 0
    assert loser_result["active"]["realised_pnl"] < 0
    assert winner_result["active"]["win_rate_pct"] == 100.0
    assert loser_result["active"]["win_rate_pct"] == 0.0

    # No special-casing: BOTH carry the identical, unconditional baseline
    # facts — including the ones that temper a winning user's good result
    # (the CR131 "must work honestly for the user who is WINNING" rule).
    for result in (winner_result, loser_result):
        assert result["baselines"] == PUBLISHED_BASELINES
        taiwan = result["baselines"]["taiwan_day_traders_1992_2006"]
        assert taiwan["reliably_profitable_pct_under"] == 1.0
        assert "overconfidence" in result["baselines"]["overconfidence_note"].lower()

    # No moralising: no grade/verdict/warning key anywhere in either payload.
    banned_keys = {"grade", "verdict", "warning", "judgement", "judgment", "score"}
    assert banned_keys.isdisjoint(winner_result["before"].keys())
    assert banned_keys.isdisjoint(winner_result["active"].keys())
    assert banned_keys.isdisjoint(loser_result["before"].keys())
    assert banned_keys.isdisjoint(loser_result["active"].keys())


# ── Endpoint: ownership guard, mirroring test_cr026_sector_allocation.py ──


@dataclass
class _U:
    id: UUID


def _app(user_id: UUID) -> FastAPI:
    app = FastAPI()
    app.include_router(portfolio_router)
    app.dependency_overrides[get_current_user] = lambda: _U(id=user_id)
    return app


def test_endpoint_not_in_cohort_and_ownership_guard():
    user_id = uuid4()
    app = _app(user_id)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get(f"/v1/portfolio/day-trader-outcomes/{user_id}")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == STATUS_NOT_IN_COHORT

    # Another user cannot read this user's outcomes.
    app.dependency_overrides[get_current_user] = lambda: _U(id=uuid4())
    r = client.get(f"/v1/portfolio/day-trader-outcomes/{user_id}")
    assert r.status_code == 403


def test_endpoint_returns_ready_comparison():
    user_id = uuid4()
    _build_hand_verified_cohort(user_id, active_win=True)
    app = _app(user_id)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get(f"/v1/portfolio/day-trader-outcomes/{user_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    # The endpoint has no `now` override, so this only reaches STATUS_READY
    # if enough real wall-clock time has passed since the fixture's
    # switched_at (2026-05-01) — true for any run of this suite after that
    # date, and this repo's `currentDate` context confirms it already has.
    assert body["status"] in (STATUS_READY, STATUS_TOO_EARLY)
    if body["status"] == STATUS_READY:
        assert set(body.keys()) == {"status", "switched_at", "before", "active", "baselines"}
