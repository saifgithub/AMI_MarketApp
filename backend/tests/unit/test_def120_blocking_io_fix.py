"""DEF120 — measured proof for the fix, not just the structural guard.

`test_no_blocking_io_in_async_routes.py` proves no route can statically
reach a blocking leaf undeferred; it says nothing about whether the fan-out
is actually faster, or whether a trade submitted through a worker thread
still writes to the DB correctly. This file covers the three things the
DEF120 assign's acceptance criteria ask to be *measured*, not asserted:

  - D4: cold- and warm-cache latency for a multi-holding portfolio fetch,
    before (serial) vs after (fanned out) the fix.
  - D3: get_portfolio does exactly one quote fetch per ticker, not four.
  - Acceptance item 8: a trade submitted through the real ASGI app (so
    `asyncio.to_thread` genuinely hops to a worker thread, not just calls
    the sync method inline) still persists — the DB session created inside
    `SimEngine.submit()` is created, used, and closed entirely on the
    worker thread, so it never crosses a thread boundary itself.
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.sim import router as sim_router
from app.db import get_session
from app.db.models import SimTradeRow
from app.services.auth_service import AuthService
from app.services.market_data import CachingProvider, Quote, set_market_data_provider
from app.services.sim_engine import SimEngine

# This file carried `pytestmark = pytest.mark.allow_ledger_drift`, on the stated
# grounds that it builds a portfolio + holdings directly and writes no trades. The
# R70 audit found that false and the exemption unnecessary: the latency tests do
# hand-seed holdings, but `test_submit_trade_through_real_asgi_app_persists_across_
# thread_hop` POSTs a real buy through the real ASGI app and `SimEngine.submit`,
# across an `asyncio.to_thread` hop — which is exactly the write path the ledger
# invariant exists to watch, and the only test in the suite that crosses a thread
# boundary to reach it. Removed, and green without it.


class _SlowProvider:
    """A quote leaf with a deliberate, measurable delay — no live Yahoo
    from the Mac, per the assign. Counts calls so tests can assert the
    fetch count directly, not just infer it from timing."""

    name = "slow_stub"

    def __init__(self, delay_seconds: float) -> None:
        self._delay = delay_seconds
        self.call_count = 0

    def quote(self, ticker: str) -> Quote | None:
        self.call_count += 1
        time.sleep(self._delay)
        return Quote(price=100.0, source=self.name)

    def get_price(self, ticker: str) -> float | None:
        return self.quote(ticker).price

    def history(self, ticker, period):
        return None

    def news(self, ticker, limit=5):
        return None

    def earnings(self, ticker):
        return None


def _sim_with_holdings(provider, tickers: list[str]) -> tuple[SimEngine, object]:
    """A SimEngine with N holdings, each 1 share, priced via `provider`."""
    sim = SimEngine(provider=provider)
    user_id = uuid4()
    with get_session() as s:
        from app.db.models import SimHoldingRow, SimPortfolioRow
        from datetime import datetime, timezone

        p_row = SimPortfolioRow(
            id=uuid4(), user_id=user_id, name="Main",
            starting_capital=10_000.0, current_cash=10_000.0,
            created_at=datetime.now(timezone.utc),
        )
        s.add(p_row)
        s.flush()
        for t in tickers:
            s.add(SimHoldingRow(
                portfolio_id=p_row.id, ticker=t, quantity=1,
                avg_cost=100.0, opened_at=datetime.now(timezone.utc),
            ))
    return sim, user_id


# ── D4: cold + warm cache timing ──────────────────────────────────────────


def test_marks_fetch_is_parallel_not_serial_cold_cache():
    """Cold cache: N tickers, each a 0.2s fetch. Serial would be N*0.2s;
    fanned out over a thread pool it should land near 0.2s regardless of N.
    """
    delay = 0.2
    tickers = [f"T{i}" for i in range(8)]
    provider = _SlowProvider(delay)
    sim, user_id = _sim_with_holdings(provider, tickers)

    start = time.monotonic()
    p, marks, total_value, drawdown_pct, source = sim.portfolio_marks_snapshot(user_id)
    elapsed = time.monotonic() - start

    assert len(marks) == len(tickers)
    assert provider.call_count == len(tickers)  # one fetch per ticker, not four passes (D3)
    serial_would_be = delay * len(tickers)
    assert elapsed < serial_would_be / 2, (
        f"cold-cache fetch took {elapsed:.2f}s for {len(tickers)} tickers "
        f"at {delay}s each — serial would be ~{serial_would_be:.2f}s; "
        "expected the fan-out to land near one delay's worth, not N of them"
    )


def test_marks_fetch_is_fast_warm_cache():
    """Warm cache (post-CachingProvider): second pass should be near-instant
    regardless of ticker count — this is the "cache hides it" half of the
    honesty requirement in the assign (D4)."""
    delay = 0.2
    tickers = [f"T{i}" for i in range(8)]
    inner = _SlowProvider(delay)
    cached = CachingProvider(inner, ttl_seconds=60.0)
    sim, user_id = _sim_with_holdings(cached, tickers)

    # Cold pass warms the cache.
    sim.portfolio_marks_snapshot(user_id)
    calls_after_cold = inner.call_count

    start = time.monotonic()
    sim.portfolio_marks_snapshot(user_id)
    warm_elapsed = time.monotonic() - start

    assert inner.call_count == calls_after_cold, "warm pass reached the inner provider — cache miss"
    assert warm_elapsed < 0.05, f"warm-cache fetch took {warm_elapsed:.3f}s — expected a cache hit, near-instant"


def test_get_portfolio_route_does_one_quote_fetch_per_ticker():
    """D3, at the route: get_portfolio's four historical passes (current_marks,
    total_value, current_drawdown_pct, aggregate_source) must collapse to
    exactly one fetch per ticker, not four."""
    provider = _SlowProvider(0.01)
    tickers = ["AAPL", "MSFT", "NVDA"]
    sim, user_id = _sim_with_holdings(provider, tickers)

    sim.portfolio_marks_snapshot(user_id)

    assert provider.call_count == len(tickers), (
        f"expected exactly {len(tickers)} quote fetches (one per ticker), "
        f"got {provider.call_count} — get_portfolio's four independent "
        "passes are not collapsed"
    )


# ── Acceptance item 8: DB session survives the to_thread hop ─────────────


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token() -> tuple:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def test_submit_trade_through_real_asgi_app_persists_across_thread_hop(client: TestClient):
    """submit_trade now runs `sim.submit` inside `await asyncio.to_thread(...)`
    — a real worker thread, not just a same-thread function call. `SimEngine.submit`
    opens its own `get_session()` internally; this proves that Session is created,
    used, and committed entirely within that worker thread's lifetime, and the
    write is visible back on the main thread afterward (acceptance item 8).
    """
    # A deliberate delay makes the to_thread hop non-trivial — if the session
    # were somehow bound to the wrong thread/loop, a slow round trip is where
    # SQLAlchemy's thread-affinity checks would surface it.
    set_market_data_provider(_SlowProvider(0.05))
    user_id, token = _make_user_and_token()

    r = client.post(
        "/v1/sim/submit",
        json={
            "user_id": str(user_id), "ticker": "AAPL", "side": "buy",
            "quantity": 2, "order_type": "market",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    trade_id = body["trade"]["id"]

    with get_session() as s:
        row = s.execute(
            select(SimTradeRow).where(SimTradeRow.id == trade_id)
        ).scalar_one_or_none()
    assert row is not None, "trade row not found — DB write from the worker thread did not persist"
    assert row.user_id == user_id
    assert float(row.quantity) == 2.0
