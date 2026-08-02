"""CR136 M10 — holdings-walk reconstruction, trading-day grid, unadjusted price basis, idempotent insert, reset boundary, terminal-state guard.

The script writes rows a Tier-2 tile later reads as realised history, so the
two properties pinned hardest here are the ones a reader cannot check for
themselves: that the walk reproduces the PRESENT before it is trusted with the
past (the terminal guard), and that a second run inserts nothing.

Rows are seeded directly rather than driven through `SimEngine`, so
`opened_at` / `closed_at` are exact and no quote provider is involved. The one
exception is the reset test, which has to use the real `reset_portfolio` — the
destroy-and-recreate behaviour is the thing under test.
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from app.db.models import (  # noqa: E402
    PortfolioValueSnapshotRow,
    SimHoldingRow,
    SimPortfolioRow,
    SimTradeRow,
    User,
)
from app.db.session import get_sessionmaker  # noqa: E402

from cr136_backfill_portfolio_snapshots import (  # noqa: E402
    _BACKFILL_SOURCE,
    DayValue,
    events_from_trades,
    main,
    reconstruct_daily_values,
    terminal_mismatches,
    trading_day_grid,
)

# A fixed two-week weekday grid, well in the past so "today" never truncates it.
_MON = date(2026, 6, 1)
_GRID = [
    _MON + timedelta(days=offset)
    for week in (0, 7)
    for offset in (week + 0, week + 1, week + 2, week + 3, week + 4)
]


def _ts(day: date, hour: int = 15) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)


class FakeProvider:
    """Canned unadjusted series. `SPY` doubles as the trading-day grid."""

    def __init__(self, series: dict[str, list[tuple[date, float]]]) -> None:
        self.series = series
        self.calls: list[tuple[str, date]] = []

    def unadjusted_daily(self, ticker, start):
        self.calls.append((ticker, start))
        return [(d, c) for d, c in self.series.get(ticker, []) if d >= start]


def _flat(ticker_days: list[date], price: float) -> list[tuple[date, float]]:
    return [(d, price) for d in ticker_days]


def _provider(**tickers: list[tuple[date, float]]) -> FakeProvider:
    return FakeProvider({"SPY": _flat(_GRID, 500.0), **tickers})


# ── Seeding helpers ─────────────────────────────────────────────────────────


def _portfolio(
    session, *, starting_capital: float = 10000.0, cash: float,
    app_version: str | None = None,
) -> SimPortfolioRow:
    user_id = uuid4()
    session.add(User(
        id=user_id, email=None, created_at=datetime.now(timezone.utc),
        last_app_version=app_version,
    ))
    row = SimPortfolioRow(
        id=uuid4(), user_id=user_id, name="Main",
        starting_capital=starting_capital, current_cash=cash,
        created_at=datetime.now(timezone.utc),
    )
    session.add(row)
    session.flush()
    return row


def _trade(
    session, p_row, *, ticker: str, side: str, qty: float, price: float,
    opened: date, status: str = "open", closed: date | None = None,
    closed_price: float | None = None,
) -> SimTradeRow:
    row = SimTradeRow(
        id=uuid4(), user_id=p_row.user_id, portfolio_id=p_row.id, ticker=ticker,
        side=side, quantity=qty, entry_price=price, opened_at=_ts(opened),
        status=status,
        closed_at=_ts(closed) if closed else None,
        closed_price=closed_price,
    )
    session.add(row)
    return row


def _holding(session, p_row, *, ticker: str, qty: float, avg_cost: float) -> None:
    session.add(SimHoldingRow(
        id=uuid4(), portfolio_id=p_row.id, ticker=ticker, quantity=qty,
        avg_cost=avg_cost, opened_at=datetime.now(timezone.utc),
    ))


def _snapshots(portfolio_id: UUID) -> list[PortfolioValueSnapshotRow]:
    with get_sessionmaker()() as s:
        return list(s.execute(
            select(PortfolioValueSnapshotRow)
            .where(PortfolioValueSnapshotRow.portfolio_id == portfolio_id)
            .order_by(PortfolioValueSnapshotRow.as_of)
        ).scalars().all())


# ── T1 — the holdings walk ──────────────────────────────────────────────────


def test_the_walk_reproduces_value_cash_and_holdings_day_by_day() -> None:
    session = get_sessionmaker()()
    # buy 10 @100 on day 1, sell 4 @110 on day 3. The SELL row stays "open"
    # forever (DEF166) — that is what makes it a sell-open event, not a close.
    p_row = _portfolio(session, cash=10000.0 - 1000.0 + 440.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _trade(session, p_row, ticker="AAPL", side="sell", qty=4, price=110.0,
           opened=_GRID[2])
    _holding(session, p_row, ticker="AAPL", qty=6, avg_cost=100.0)
    session.commit()
    session.close()

    provider = _provider(AAPL=[(d, 100.0 + i) for i, d in enumerate(_GRID)])
    assert main(["--apply"], provider=provider) == 0

    rows = _snapshots(p_row.id)
    assert [r.as_of for r in rows] == _GRID
    # day 1: cash 9000 + 10 × 100 ; day 3: cash 9440 + 6 × 102
    assert float(rows[0].total_value) == 10000.0
    assert float(rows[0].cash) == 9000.0
    assert float(rows[0].invested_value) == 1000.0
    assert float(rows[2].cash) == 9440.0
    assert float(rows[2].invested_value) == round(6 * 102.0, 2)
    assert float(rows[2].total_value) == round(9440.0 + 6 * 102.0, 2)


# ── T2 — a close is clamped to what is held (DEF166) ────────────────────────


def test_a_close_sells_only_what_is_still_held() -> None:
    session = get_sessionmaker()()
    # buy 10 @100, sell-open 6 @110, then the BUY row closes for 10 — but only
    # 4 shares remain, so it may sell 4 and be credited for 4.
    cash = 10000.0 - 1000.0 + 660.0 + 4 * 120.0
    p_row = _portfolio(session, cash=cash)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0], status="won", closed=_GRID[4], closed_price=120.0)
    _trade(session, p_row, ticker="AAPL", side="sell", qty=6, price=110.0,
           opened=_GRID[2])
    session.commit()
    session.close()

    provider = _provider(AAPL=_flat(_GRID, 100.0))
    assert main(["--apply"], provider=provider) == 0

    rows = _snapshots(p_row.id)
    assert float(rows[4].cash) == cash
    assert float(rows[4].invested_value) == 0.0, (
        "the close emptied the position; crediting 10 shares would have "
        "invented six that were already sold"
    )


# ── T3 — trading-day grid and carry-forward ─────────────────────────────────


def test_only_grid_days_get_rows_and_a_missing_bar_carries_forward() -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    session.commit()
    session.close()

    # AAPL has no Wednesday bar in week one.
    series = [(d, 100.0 + i) for i, d in enumerate(_GRID) if d != _GRID[2]]
    provider = _provider(AAPL=series)
    assert main(["--apply"], provider=provider) == 0

    rows = _snapshots(p_row.id)
    assert [r.as_of for r in rows] == _GRID
    weekend = date(2026, 6, 6)
    assert weekend not in {r.as_of for r in rows}
    # Wednesday is valued at Tuesday's close (101), not dropped and not zero.
    assert float(rows[2].invested_value) == round(10 * 101.0, 2)


def test_the_grid_is_spys_own_bar_dates() -> None:
    provider = _provider()
    assert trading_day_grid(provider, _GRID[0]) == _GRID
    assert provider.calls[0][0] == "SPY"


# ── T4 — idempotence, and live rows are never overwritten ───────────────────


def test_a_second_apply_inserts_nothing_and_never_touches_a_live_row() -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    # A live-shaped row already sitting in range: real marks, a real F16
    # prediction. The backfill must leave it exactly as it is.
    session.add(PortfolioValueSnapshotRow(
        id=uuid4(), user_id=p_row.user_id, portfolio_id=p_row.id,
        as_of=_GRID[1], total_value=12345.67, cash=1.0, invested_value=12344.67,
        drawdown_pct=0.0, source="yahoo",
        captured_at=datetime.now(timezone.utc),
        predicted_vol_ann=0.262, n_observations=140, engine_version="cr136.v1",
    ))
    session.commit()
    session.close()

    provider = _provider(AAPL=_flat(_GRID, 100.0))
    assert main(["--apply"], provider=provider) == 0
    first = _snapshots(p_row.id)
    assert len(first) == len(_GRID)

    live = next(r for r in first if r.as_of == _GRID[1])
    assert float(live.total_value) == 12345.67
    assert live.source == "yahoo"
    assert float(live.predicted_vol_ann) == 0.262
    assert live.engine_version == "cr136.v1"

    assert main(["--apply"], provider=provider) == 0
    second = _snapshots(p_row.id)
    assert len(second) == len(first)
    assert {r.id for r in second} == {r.id for r in first}, (
        "a second run must insert nothing at all — not even a replacement row"
    )


# ── T5 — a series can never span a reset ────────────────────────────────────


def test_a_reset_destroys_the_history_and_the_new_book_starts_over() -> None:
    from app.services.sim_engine import get_sim_engine

    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0)
    user_id = p_row.user_id
    old_portfolio_id = p_row.id
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    session.commit()
    session.close()

    provider = _provider(AAPL=_flat(_GRID, 100.0))
    assert main(["--apply"], provider=provider) == 0
    assert _snapshots(old_portfolio_id)

    get_sim_engine().reset_portfolio(user_id)
    assert _snapshots(old_portfolio_id) == [], (
        "reset_portfolio deletes the snapshot rows explicitly — sqlite does "
        "not enforce the FK cascade, so the test DB would otherwise disagree "
        "with production about what a reset destroys"
    )

    session = get_sessionmaker()()
    new_row = session.execute(
        select(SimPortfolioRow).where(SimPortfolioRow.user_id == user_id)
    ).scalars().one()
    assert new_row.id != old_portfolio_id
    new_row.current_cash = 9500.0
    _trade(session, new_row, ticker="MSFT", side="buy", qty=5, price=100.0,
           opened=_GRID[5])
    _holding(session, new_row, ticker="MSFT", qty=5, avg_cost=100.0)
    session.commit()
    session.close()

    provider = _provider(MSFT=_flat(_GRID, 100.0))
    assert main(["--apply"], provider=provider) == 0
    rows = _snapshots(new_row.id)
    assert rows[0].as_of == _GRID[5], "the new series starts at the new book's first trade"
    assert _snapshots(old_portfolio_id) == []


# ── T6 — the terminal-state guard ───────────────────────────────────────────


def test_a_walk_that_cannot_reproduce_today_writes_nothing_for_that_book() -> None:
    session = get_sessionmaker()()
    good = _portfolio(session, cash=9000.0)
    _trade(session, good, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, good, ticker="AAPL", qty=10, avg_cost=100.0)

    bad = _portfolio(session, cash=9000.0)
    _trade(session, bad, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, bad, ticker="AAPL", qty=11, avg_cost=100.0)   # phantom share
    session.commit()
    session.close()

    provider = _provider(AAPL=_flat(_GRID, 100.0))
    assert main(["--apply"], provider=provider) == 2

    assert _snapshots(bad.id) == [], "the past is not writable by a walk that got the present wrong"
    assert len(_snapshots(good.id)) == len(_GRID), (
        "one bad portfolio must not cost the others their backfill"
    )


def test_cash_drift_beyond_the_tolerance_also_fails_the_guard() -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0 + 1.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    session.commit()
    session.close()

    assert main(["--apply"], provider=_provider(AAPL=_flat(_GRID, 100.0))) == 2
    assert _snapshots(p_row.id) == []


# ── T7 — the price-basis pin, structurally ──────────────────────────────────


def test_the_default_provider_asks_yahoo_for_unadjusted_daily_bars(monkeypatch) -> None:
    import cr136_backfill_portfolio_snapshots as script

    recorded: dict[str, object] = {}

    class _Recorder:
        def __init__(self, ticker):
            recorded["ticker"] = ticker

        def history(self, **kwargs):
            recorded.update(kwargs)
            return None

    fake_yf = type("yf", (), {"Ticker": _Recorder})
    monkeypatch.setitem(sys.modules, "yfinance", fake_yf)

    script._YfinanceProvider().unadjusted_daily("AAPL", _GRID[0])

    assert recorded["ticker"] == "AAPL"
    assert recorded["auto_adjust"] is False, (
        "an adjusted series rewrites the past; the ledger's share counts do "
        "not, so every pre-adjustment day would be mispriced"
    )
    assert recorded["interval"] == "1d"


def test_the_script_never_reaches_for_the_falling_back_market_provider() -> None:
    """Its `FallbackProvider` ends in a deterministic mock walk, which would
    silently persist fabricated bars as realised history on a transient Yahoo
    failure. Parsed rather than grepped: the module docstring names the symbol
    deliberately, to say why it is not used, and a grep cannot tell an
    explanation from a call."""
    import ast

    source = (
        Path(__file__).resolve().parents[2]
        / "scripts" / "cr136_backfill_portfolio_snapshots.py"
    ).read_text()
    tree = ast.parse(source)

    referenced = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    } | {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert "get_market_data_provider" not in referenced
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "get_market_data_provider" not in imported


# ── T8 — the drawdown column is NOT peak-to-trough ──────────────────────────


def test_the_drawdown_column_is_versus_starting_capital_not_peak_to_trough() -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, starting_capital=10000.0, cash=0.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=100, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=100, avg_cost=100.0)
    session.commit()
    session.close()

    # 10000 → 15000 → 12000: peak-to-trough is 20%, vs-starting-capital is 0.
    closes = [100.0, 150.0, 120.0] + [120.0] * (len(_GRID) - 3)
    provider = _provider(AAPL=list(zip(_GRID, closes)))
    assert main(["--apply"], provider=provider) == 0

    rows = _snapshots(p_row.id)
    assert [float(r.total_value) for r in rows[:3]] == [10000.0, 15000.0, 12000.0]
    assert all(float(r.drawdown_pct) == 0.0 for r in rows), (
        "the Tier-2 tile computes peak-to-trough from total_value and must "
        "never read this column — it would read 20.0 where this stores 0.0"
    )


# ── T9/T10/T11 — skips, provenance, synthetics ──────────────────────────────


def test_a_book_that_never_traded_is_skipped_cleanly() -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=10000.0)
    session.commit()
    session.close()

    assert main(["--apply"], provider=_provider()) == 0
    assert _snapshots(p_row.id) == []


def test_every_backfilled_row_is_identifiable_forever() -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    session.commit()
    session.close()

    assert main(["--apply"], provider=_provider(AAPL=_flat(_GRID, 100.0))) == 0
    for row in _snapshots(p_row.id):
        assert row.source == _BACKFILL_SOURCE
        assert row.predicted_vol_ann is None
        assert row.n_observations is None
        assert row.engine_version is None, (
            "no engine ran historically; a back-dated sigma would be "
            "fabricated auditability, and the F16 bias test skips these rows "
            "precisely because the prediction is null"
        )


def test_synthetic_users_are_backfilled_and_marked(capsys) -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0, app_version="room-benchmark")
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    session.commit()
    session.close()

    assert main(["--apply"], provider=_provider(AAPL=_flat(_GRID, 100.0))) == 0
    assert len(_snapshots(p_row.id)) == len(_GRID), "backfill them too — it keeps the table uniform"
    assert "[synthetic]" in capsys.readouterr().out, (
        "the marker is what stops an operator spot-checking a CR035 benchmark "
        "account and calling it real-user validation"
    )


# ── T12 — a ledger anomaly is loud, and costs that book its backfill ────────


def test_a_close_with_no_price_is_skipped_and_flagged(capsys) -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0], status="won", closed=_GRID[3], closed_price=None)
    session.commit()
    session.close()

    assert main(["--apply"], provider=_provider(AAPL=_flat(_GRID, 100.0))) == 2
    out = capsys.readouterr().out
    assert "close event skipped" in out
    assert "terminal !!" in out
    assert _snapshots(p_row.id) == []


# ── The dry run really is a dry run ─────────────────────────────────────────


def test_a_dry_run_exercises_the_insert_path_and_then_writes_nothing() -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    session.commit()
    session.close()

    assert main([], provider=_provider(AAPL=_flat(_GRID, 100.0))) == 0
    assert _snapshots(p_row.id) == [], "the default is a rollback, not a no-op"


def test_the_spot_check_mode_prints_the_whole_series(capsys) -> None:
    session = get_sessionmaker()()
    p_row = _portfolio(session, cash=9000.0)
    other = _portfolio(session, cash=9000.0)
    _trade(session, p_row, ticker="AAPL", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, p_row, ticker="AAPL", qty=10, avg_cost=100.0)
    _trade(session, other, ticker="MSFT", side="buy", qty=10, price=100.0,
           opened=_GRID[0])
    _holding(session, other, ticker="MSFT", qty=10, avg_cost=100.0)
    session.commit()
    session.close()

    provider = _provider(AAPL=_flat(_GRID, 100.0), MSFT=_flat(_GRID, 100.0))
    assert main(["--user-id", str(p_row.user_id)], provider=provider) == 0

    out = capsys.readouterr().out
    assert str(p_row.user_id) in out
    assert str(other.user_id) not in out, "--user-id scopes the run, not just the printing"
    assert out.count("10000.00") >= len(_GRID)


# ── The pure core, directly ─────────────────────────────────────────────────


def test_events_are_ordered_buy_then_sell_then_close_at_one_timestamp() -> None:
    class _Row:
        def __init__(self, side, status, closed_at, closed_price):
            self.id = uuid4()
            self.ticker = "AAPL"
            self.side = side
            self.quantity = 1.0
            self.entry_price = 10.0
            self.opened_at = _ts(_GRID[0])
            self.status = status
            self.closed_at = closed_at
            self.closed_price = closed_price

    rows = [
        _Row("buy", "won", _ts(_GRID[0]), 12.0),
        _Row("sell", "open", None, None),
    ]
    events, anomalies = events_from_trades(rows)
    assert anomalies == []
    assert [e.kind for e in events] == ["buy", "sell", "close"], (
        "same-timestamp ordering is a rank, not luck: a close before its own "
        "buy would sell shares the walk had not bought yet"
    )


def test_a_ticker_with_no_bars_at_all_is_priced_from_its_own_ledger() -> None:
    class _Row:
        id = uuid4()
        ticker = "DELISTED"
        side = "buy"
        quantity = 10.0
        entry_price = 42.0
        opened_at = _ts(_GRID[0])
        status = "open"
        closed_at = None
        closed_price = None

    events, _ = events_from_trades([_Row()])
    rows, terminal, stats = reconstruct_daily_values(events, _GRID, {}, 10000.0)

    assert stats["ledger_priced"] == len(_GRID)
    assert rows[0] == DayValue(
        as_of=_GRID[0], total_value=10000.0, cash=9580.0, invested_value=420.0,
    )
    assert terminal.holdings == {"DELISTED": 10.0}


def test_terminal_mismatches_names_both_numbers() -> None:
    class _Holding:
        ticker = "AAPL"
        quantity = 11.0

    from cr136_backfill_portfolio_snapshots import TerminalState

    lines = terminal_mismatches(
        TerminalState(holdings={"AAPL": 10.0}, cash=9000.0), [_Holding()], 9000.0,
    )
    assert len(lines) == 1
    assert "10.0000" in lines[0] and "11.0000" in lines[0]

    assert terminal_mismatches(
        TerminalState(holdings={"AAPL": 10.0}, cash=9000.0), [_Holding()], 9000.0,
    ) != []
    assert terminal_mismatches(
        TerminalState(holdings={}, cash=9000.0), [], 9000.02,
    ) == [], "two cents is inside the tolerance the 2 dp rounding leaves"
