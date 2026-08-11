"""CR109 slice 3c — the house strategy desks, and the one fence that matters.

Design §11.2 lets a desk's result feed a real user's career points. That single
fact is what makes this slice different from every other "fill the board with
bots" feature: a fabricated desk return does not stay in the game, it lands in
a real person's permanent Record. So the tests below are weighted almost
entirely toward one property —

    > A desk's P&L is never generated, sampled, or tuned to look plausible.

— and specifically toward the case that would produce a fabricated one by
accident rather than by intent. `market_data` falls through to
`MockWalkProvider` whenever the live feed 429s or errors, and that provider
invents a plausible price from `hash(ticker)`. Nothing about a mock price looks
wrong; it is a number in the right range with the right shape. A desk that
selected its basket from those bars would produce a return that reads as a real
result forever after. This is the DEF059 shape (LLM down → confident fake
APPROVE) transplanted into scoring, and the honest answer is the same one CR040
gives everywhere else: **degrade loudly — abstain, do not substitute.**

The remainder covers disclosure (a desk must be visibly a desk on every
entrant-rendering surface, §11.2's engineering fence), the taper (fill TO a
target, never a fixed count), the kill switch, and the one widened rule this
slice adds to `enter_field` — which is verified against `users.is_desk` rather
than trusted, because a bare bypass flag is exactly what the §7.1 fence forbids
one function over.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import GameEntryRow, GameFieldRow, GameQueuedOrderRow, User
from app.services import games_desks as desks
from app.services import games_service as games
from app.services.market_data import Candle, EarningsInfo, Quote, set_market_data_provider

# Sunday 23:00 ET — the Monday field is `entry_open`, the US market is shut.
_ENTRY_OPEN = datetime(2026, 8, 10, 3, 0, tzinfo=timezone.utc)
# Monday 09:10 ET — 20 minutes before the open, so the field is `locked`.
# This is the window desks actually fill in.
_LOCKED = datetime(2026, 8, 10, 13, 10, tzinfo=timezone.utc)
# Monday 11:00 ET — the regular session is open.
_MARKET_OPEN = datetime(2026, 8, 10, 15, 0, tzinfo=timezone.utc)


# ── A provider that serves REAL-looking data under a real source name ────────


class _RealisticProvider:
    """Bars and quotes under a `yfinance` source, so provenance checks pass.

    Deliberately NOT random: each ticker gets a deterministic ramp keyed off
    its position in the universe, which gives the momentum/contrarian/
    concentrated rankings a stable, hand-checkable order.
    """

    name = "yfinance"

    def __init__(self, *, source: str = "yfinance", dividends: bool = True) -> None:
        self.source = source
        self._dividends = dividends

    def _slope(self, ticker: str) -> float:
        try:
            return 1.0 + desks.DESK_UNIVERSE.index(ticker) * 0.01
        except ValueError:
            return 1.0

    def quote(self, ticker: str) -> Quote:
        return Quote(price=100.0 * self._slope(ticker), source=self.source)

    def get_price(self, ticker: str) -> float:
        return self.quote(ticker).price

    def history(self, ticker: str, period: str) -> list[Candle]:
        slope = self._slope(ticker)
        out = []
        for i in range(260):
            px = 100.0 + i * (slope - 1.0) * 10.0
            out.append(Candle(t=1_700_000_000 + i * 86_400, o=px, h=px, low=px, c=px, v=1000))
        return out

    def history_with_source(self, ticker: str, period: str):
        return self.history(ticker, period), self.source

    def news(self, ticker: str, limit: int = 5):
        return []

    def earnings(self, ticker: str):
        if not self._dividends:
            return None
        rate = 1.0 + desks.DESK_UNIVERSE.index(ticker) * 0.1 if ticker in desks.DESK_UNIVERSE else 0.0
        return EarningsInfo(
            earnings_date=None, quarter=None, eps_estimate=None,
            ex_dividend_date="2026-09-01", dividend_rate=rate,
        )


def _use_real_data(**kw) -> _RealisticProvider:
    from app.services import sim_engine as _sim

    provider = _RealisticProvider(**kw)
    set_market_data_provider(provider)
    _sim._engine = None  # rebuild so SimEngine picks the new provider up
    return provider


# ══ The integrity line: real data or no play ════════════════════════════════


def test_mock_walk_bars_are_rejected_outright():
    """The conftest pins every test to `MockWalkProvider`, which is exactly
    what production falls through to when Yahoo 429s. A desk must not see it."""
    view = desks._MarketView()
    assert view.bars("AAPL", "1y") is None
    assert view.price("AAPL") is None


@pytest.mark.parametrize(
    "build",
    [desks._momentum_basket, desks._contrarian_basket,
     desks._concentrated_basket, desks._dividend_basket,
     desks._equal_weight_basket, desks._index_basket],
    ids=["momentum", "contrarian", "concentrated", "dividend", "equal_weight", "index"],
)
def test_every_desk_abstains_rather_than_inventing_a_basket(build):
    """No strategy has a fallback. Each raises rather than returning
    *something* — because "something" here becomes a scored result that pays
    a real player's career points."""
    with pytest.raises(desks.DeskDataUnavailable):
        build(desks._MarketView())


def test_a_desk_that_cannot_price_does_not_enter_the_field():
    """End to end: mock data in, zero entries out. The field is short its
    opponents, which is the honest outcome — a short field is a small field,
    a desk trading on invented bars is a corrupted score."""
    with get_session() as s:
        field = games.ensure_weekly_field(s, now=_LOCKED)
        field_id = field.id

    stats = desks.fill_field_with_desks(field_id, now=_LOCKED)

    assert stats["entered"] == 0
    assert stats["skipped"] == len(desks.DESK_ROSTER)
    with get_session() as s:
        assert s.execute(select(GameEntryRow.id)).first() is None


def test_a_stale_or_unknown_source_counts_as_fabricated():
    """`mock_walk` is not the only way to get a number nobody observed. The
    check is a prefix allowlist-by-exclusion so a future leaf is rejected by
    default rather than silently admitted."""
    assert desks._is_real_source("yfinance")
    assert desks._is_real_source("yahoo")
    for bad in ("mock_walk", "mock", "MOCK_WALK", "stale", "unavailable", "", None):
        assert not desks._is_real_source(bad), bad


def test_no_desk_return_is_ever_written_directly():
    """The module places ORDERS. It never writes a NAV row, a TWR, or a rank —
    those come from the same snapshot tick and scoring pass a human's do. A
    write path here would be the fabrication route, so its absence is asserted
    rather than assumed."""
    src = inspect.getsource(desks)
    for forbidden in ("final_twr_pct", "PortfolioNavDailyRow", "career_points_delta",
                      "final_rank", "random.", "uniform("):
        assert forbidden not in src, (
            f"games_desks.py must not touch {forbidden!r} — a desk's result is "
            f"produced by the market through the shared path, never written here"
        )


# ══ Execution parity: same path, same fee, same queue ═══════════════════════


def test_desk_orders_queue_like_a_human_weekend_order():
    _use_real_data()
    with get_session() as s:
        field_id = games.ensure_weekly_field(s, now=_LOCKED).id

    stats = desks.fill_field_with_desks(field_id, now=_LOCKED)
    assert stats["entered"] > 0

    with get_session() as s:
        queued = s.execute(
            select(GameQueuedOrderRow).where(GameQueuedOrderRow.state == "queued")
        ).scalars().all()
    assert queued, "desks act while the market is shut, so every leg must QUEUE"
    assert all(q.side == "buy" for q in queued)


def test_a_desk_pays_the_same_fee_a_human_pays():
    """No fee exemption. §11.2: a fee-exempt desk is a tuned result by the back
    door — it would beat an identically-traded human by the cost of trading."""
    from app.services.games_scoring import trade_fee

    _use_real_data()
    with get_session() as s:
        field_id = games.ensure_weekly_field(s, now=_LOCKED).id
    desks.fill_field_with_desks(field_id, now=_LOCKED)

    drained = games.process_queued_orders(now=_MARKET_OPEN)
    assert drained["filled"] > 0

    with get_session() as s:
        rows = s.execute(
            select(GameEntryRow.fees_paid, GameEntryRow.trade_count)
            .join(User, User.id == GameEntryRow.user_id)
            .where(User.is_desk.is_(True))
        ).all()
    traded = [(float(f), int(c)) for f, c in rows if c > 0]
    assert traded, "at least one desk should have filled"
    for fees, count in traded:
        assert fees >= trade_fee(0.0) * count > 0


def test_desk_fills_produce_real_holdings_not_a_written_number():
    _use_real_data()
    with get_session() as s:
        field_id = games.ensure_weekly_field(s, now=_LOCKED).id
    desks.fill_field_with_desks(field_id, now=_LOCKED)
    games.process_queued_orders(now=_MARKET_OPEN)

    from app.services.sim_engine import get_sim_engine

    with get_session() as s:
        entries = s.execute(
            select(GameEntryRow.user_id, GameEntryRow.run_id)
            .join(User, User.id == GameEntryRow.user_id)
            .where(User.is_desk.is_(True))
        ).all()
    total_holdings = 0
    for user_id, run_id in entries:
        p, _m, _tv, _dd, _s = get_sim_engine().portfolio_marks_snapshot(
            user_id, kind="game", run_id=run_id,
        )
        total_holdings += len(p.holdings)
    assert total_holdings > 0, "a desk's book must contain real positions"


# ══ Disclosure ══════════════════════════════════════════════════════════════


def test_every_desk_is_disclosed_by_the_one_entrant_renderer():
    """§11.2's engineering fence: a desk is visibly a desk on every surface
    that renders an entrant. One renderer, so a surface added later cannot
    forget to disclose."""
    ids = desks.ensure_desk_users()
    assert len(ids) == len(desks.DESK_ROSTER)
    for desk in desks.DESK_ROSTER:
        identity = desks.entrant_identity(ids[desk.key])
        assert identity["is_desk"] is True
        assert identity["desk_key"] == desk.key
        assert identity["handle"] == desk.name
        assert identity["desk_rule"], "a desk without a published rule is an undisclosed bot"


def test_a_human_entrant_is_not_marked_as_a_desk():
    user_id = uuid4()
    games.enter_field(user_id, now=_ENTRY_OPEN)
    with get_session() as s:
        s.add(User(id=user_id, handle="curious-vector", is_anonymous=True))
    identity = desks.entrant_identity(user_id)
    assert identity["is_desk"] is False
    assert identity["desk_rule"] is None


def test_the_published_roster_carries_the_rule_and_the_universe():
    """Disclosure is the feature, so the rules surface gets a first-class
    payload — a player must be able to reproduce any desk's basket by hand."""
    roster = desks.published_roster()
    assert len(roster) == len(desks.DESK_ROSTER)
    for row in roster:
        assert row["rule"].strip()
        assert row["universe"] == list(desks.DESK_UNIVERSE)


def test_desks_are_enumerable_for_the_real_user_metric_filter():
    desks.ensure_desk_users()
    ids = desks.desk_user_ids()
    assert len(ids) == len(desks.DESK_ROSTER)
    assert all(desks.is_desk_user(i) for i in ids)
    assert not desks.is_desk_user(uuid4())


# ══ Scaling and control ═════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "humans,present,expected",
    [
        (0, 0, 6),   # empty field — every desk plays
        (1, 0, 6),   # Saiful alone — capped by the roster, not by the target
        (3, 0, 5),
        (7, 0, 1),
        (8, 0, 0),   # the field stands on its own; desks stop appearing
        (20, 0, 0),
        (1, 6, 1),   # already-present desks count against the target
        (9, 6, 0),   # never negative — a live entrant is not retracted mid-week
    ],
)
def test_desks_fill_to_a_target_never_a_fixed_count(humans, present, expected):
    assert desks.desks_needed(humans, present, 8) == expected


def test_the_kill_switch_stops_future_fills(monkeypatch):
    _use_real_data()
    monkeypatch.setattr(settings, "games_desks_enabled", False)
    with get_session() as s:
        field_id = games.ensure_weekly_field(s, now=_LOCKED).id

    stats = desks.fill_field_with_desks(field_id, now=_LOCKED)

    assert stats["entered"] == 0
    with get_session() as s:
        assert s.execute(select(GameEntryRow.id)).first() is None


def test_filling_twice_does_not_double_enter():
    """Idempotent: the guard is which desks are already in THIS field, so a
    container restart mid-fill resumes rather than fielding two Momentum
    Desks."""
    _use_real_data()
    with get_session() as s:
        field_id = games.ensure_weekly_field(s, now=_LOCKED).id

    first = desks.fill_field_with_desks(field_id, now=_LOCKED)
    second = desks.fill_field_with_desks(field_id, now=_LOCKED)

    assert first["entered"] > 0
    assert second["entered"] == 0
    with get_session() as s:
        keys = s.execute(
            select(User.desk_key)
            .join(GameEntryRow, GameEntryRow.user_id == User.id)
            .where(GameEntryRow.field_id == field_id)
        ).scalars().all()
    assert len(keys) == len(set(keys))


def test_ensure_desk_users_is_idempotent():
    first = desks.ensure_desk_users()
    second = desks.ensure_desk_users()
    assert first == second
    with get_session() as s:
        count = len(s.execute(select(User.id).where(User.is_desk.is_(True))).scalars().all())
    assert count == len(desks.DESK_ROSTER)


# ══ The one widened rule ════════════════════════════════════════════════════


def test_a_human_cannot_use_the_desk_entry_window():
    """`as_desk=True` widens the accepted field states by one (`locked`). It is
    checked against `users.is_desk`, not trusted — so it is a widened rule
    rather than a bypass, which is the distinction §7.1's fence turns on one
    module over."""
    human = uuid4()
    with get_session() as s:
        s.add(User(id=human, is_anonymous=True))
    with pytest.raises(games.FieldNotOpenError):
        games.enter_field(human, now=_LOCKED, as_desk=True)


def test_a_human_cannot_enter_a_locked_field_the_ordinary_way():
    """A human at 09:10 ET on a Monday is rolled forward to NEXT week's field —
    which is correct, and is exactly why the desk path must name its field
    explicitly. Asking for THIS week's locked field by id is refused."""
    human = uuid4()
    with get_session() as s:
        s.add(User(id=human, is_anonymous=True))
        locked_field_id = games.ensure_weekly_field(s, now=_ENTRY_OPEN).id

    rolled = games.enter_field(human, now=_LOCKED)
    with get_session() as s:
        assert rolled.field_id != locked_field_id, (
            "past locks_at the roll must move a human to next week's field"
        )

    other_human = uuid4()
    with get_session() as s:
        s.add(User(id=other_human, is_anonymous=True))
    with pytest.raises(games.FieldNotOpenError):
        games.enter_field(other_human, now=_LOCKED, field_id=locked_field_id)


def test_desks_enter_the_field_being_filled_not_the_one_the_roll_returns():
    """The bug this pins: past `locks_at`, `ensure_weekly_field` rolls to NEXT
    Monday. A desk filling THIS Monday's locked field would have entered the
    wrong field entirely — taper computed for one field, entries landing in
    another, and the human's actual field left empty."""
    _use_real_data()
    with get_session() as s:
        locked_field_id = games.ensure_weekly_field(s, now=_ENTRY_OPEN).id

    desks.fill_field_with_desks(locked_field_id, now=_LOCKED)

    with get_session() as s:
        field_ids = set(s.execute(
            select(GameEntryRow.field_id)
            .join(User, User.id == GameEntryRow.user_id)
            .where(User.is_desk.is_(True))
        ).scalars().all())
    assert field_ids == {locked_field_id}


def test_the_lock_window_is_derived_from_timestamps_not_the_state_column():
    """`state` is only refreshed on the field the roll is currently targeting,
    which in this window is next week's — so a state-column filter would have
    found nothing, every week, silently."""
    with get_session() as s:
        locked_field_id = games.ensure_weekly_field(s, now=_ENTRY_OPEN).id
        stale_state = s.execute(
            select(GameFieldRow.state).where(GameFieldRow.id == locked_field_id)
        ).scalar_one()

    assert stale_state == "entry_open", "precondition: the column is stale here"
    assert desks.fields_in_lock_window(_LOCKED) == [locked_field_id]
    assert desks.fields_in_lock_window(_ENTRY_OPEN) == []
    assert desks.fields_in_lock_window(_MARKET_OPEN) == []


def test_desk_entry_does_not_pollute_the_gate_1_reentry_metric():
    """A desk re-enters every week by construction. Counting it would make
    `close -> re-entry` — one of the two numbers Gate 1 runs on — a measure of
    the cron rather than of players."""
    src = inspect.getsource(games.enter_field)
    assert "if not as_desk:" in src
    assert "_log_close_to_reentry_if_any" in src


# ══ Determinism ═════════════════════════════════════════════════════════════


def test_basket_selection_is_deterministic_given_the_same_data():
    """Same market view, same basket. A desk whose picks moved between two
    reads of identical data would be unreproducible, which defeats the
    disclosure: a published rule you cannot re-run is not disclosed."""
    _use_real_data()
    for desk in desks.DESK_ROSTER:
        a = desk.build(desks._MarketView())
        b = desk.build(desks._MarketView())
        assert a == b, desk.key


def test_baskets_are_fully_invested_and_normalised():
    _use_real_data()
    for desk in desks.DESK_ROSTER:
        basket = desk.build(desks._MarketView())
        assert basket
        assert abs(sum(w for _t, w in basket) - 1.0) < 1e-9, desk.key
        assert len({t for t, _w in basket}) == len(basket), desk.key


def test_the_concentrated_desk_supplies_the_tail():
    """A roster of only diversified strategies produces a suspiciously narrow
    spread. Real fields have blowups and moonshots (§11.2)."""
    _use_real_data()
    widths = {d.key: len(d.build(desks._MarketView())) for d in desks.DESK_ROSTER}
    assert widths["concentrated"] == 2
    assert widths["equal_weight"] >= 8
    assert widths["concentrated"] < widths["momentum"] < widths["equal_weight"]
