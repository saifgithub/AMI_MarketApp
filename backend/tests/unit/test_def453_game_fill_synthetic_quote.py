"""DEF453 — a scored game fill may never price off a fabricated quote.

Alpha, 2026-10-09: AIXI and DKI shorts were force-covered at 174.62 and
100.48 — exactly what `MockWalkProvider` returns for those tickers — while the
real sessions never left 0.32–2.20. Yahoo failed, `FallbackProvider` fell
through to mock_walk, and the forced buy-in filled on it: a six-figure fake
loss and a bust on a scored contest. These tests pin the structural fix.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, GameShortPositionRow
from app.services import market_data as _md
from app.services import games_record_service as record_service
from app.services.sim_engine import GAME_QUOTE_UNAVAILABLE_REASON, SimEngine
from tests.unit.test_cr109_amendment_i_solvency import (
    _MutableProvider,
    _market_open_moment,
    _open_short_row,
    _seed_live_entry,
    _short,
)
from sqlalchemy import select


class _FallthroughProvider(_MutableProvider):
    """A live stack whose feed is down: quotes carry the mock_walk leaf."""

    def quote(self, ticker: str):
        return _md.Quote(price=self.price, source="mock_walk")


def test_a_game_fill_is_refused_when_only_a_mock_quote_is_left():
    sim = SimEngine(provider=_FallthroughProvider(174.62))
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)

    result = _short(sim, user_id, run_id, qty=10)

    assert not result.accepted
    assert result.reason == GAME_QUOTE_UNAVAILABLE_REASON
    assert _open_short_row(run_id) is None


def test_a_mock_configured_stack_still_fills():
    """Dev/test stacks are mock BY CONFIGURATION — the guard is for a live
    stack that degraded, not for a stack that never claimed to be live."""
    sim = SimEngine(provider=_md.MockWalkProvider())
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)

    assert _short(sim, user_id, run_id, qty=1).accepted


def test_forced_buyin_does_not_fire_on_a_mock_quote_and_labels_real_ones():
    from app.services.games_service import sweep_forced_buyins

    real = _MutableProvider(100.0)
    sim = SimEngine(provider=real)
    user_id, run_id = uuid4(), uuid4()
    _seed_live_entry(user_id, run_id)
    assert _short(sim, user_id, run_id, qty=10).accepted

    sim_down = SimEngine(provider=_FallthroughProvider(7_000.0))
    stats = sweep_forced_buyins(now=_market_open_moment(), sim=sim_down)
    assert stats["bought_in"] == 0
    assert _open_short_row(run_id) is not None, "bought in on a fabricated price"

    real.price = 195.0
    stats = sweep_forced_buyins(now=_market_open_moment(), sim=sim)
    assert stats["bought_in"] == 1
    with get_session() as s:
        row = s.execute(
            select(GameShortPositionRow).where(GameShortPositionRow.run_id == run_id)
        ).scalar_one()
    assert row.close_reason == "buyin"


def test_record_history_carries_the_bust_facts():
    user_id, run_id = uuid4(), uuid4()
    field_id = _seed_live_entry(user_id, run_id, state="bust")
    with get_session() as s:
        e = s.execute(
            select(GameEntryRow).where(GameEntryRow.run_id == run_id)
        ).scalar_one()
        e.busted_at = datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc)
        e.nav_shortfall = 365_003.32
        e.trade_count = 2

    row = record_service.get_record(user_id)["run_history"][0]

    assert row["state"] == "bust"
    assert row["nav_shortfall"] == 365_003.32
    assert row["trade_count"] == 2
    assert row["busted_at"].startswith("2026-10-09")
    assert row["starts_on"] and row["ends_on"]
    assert str(field_id)
