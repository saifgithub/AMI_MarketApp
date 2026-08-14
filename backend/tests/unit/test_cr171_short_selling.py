"""CR171 acceptance — short selling in the training lane.

The two that matter most, in order:

  * `test_a3_*` / `test_a5_*` — **the cash and the ledger**. Short proceeds must
    never enter `current_cash`, and a short must write no `sim_trades` row. Get
    either wrong and the damage is silent and permanent: a credit that is not
    spendable is indistinguishable from a PROFIT in the NAV series that
    `total_value`, `total_drawdown_pct`, `portfolio_nav_daily` and the TWR chain
    are all computed from, and a SELL trade row makes every genuine phantom
    share look accounted for on `def110_backfill`, the one detector we have for
    that class.
  * `test_a7_*` — **the forced buy-in succeeds at zero cash.** The collateral is
    posted at open precisely so the margin call cannot fail; a cover that could
    be refused for a low balance is a containment mechanism that breaks exactly
    when it is needed.

Every test drives the real engine and the real sweep. `sim_shorts` is a pure
enough module to test in isolation, and testing it that way would prove the
arithmetic while saying nothing about whether the arithmetic is the one that
runs — the failure this lineage keeps shipping (DEF190).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import SimShortPositionRow, SimTradeRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import sweep_resting_orders
from app.trading_math.market_hours import session_close_on_or_after


def _live_session_time() -> datetime:
    """A 16:00 ET close minus an hour is 15:00 ET on a weekday — inside the
    session by construction, whatever day the suite runs."""
    return session_close_on_or_after(datetime.now(timezone.utc)) - timedelta(hours=1)


def _closed_time() -> datetime:
    """20:00 ET is after every close."""
    return session_close_on_or_after(datetime.now(timezone.utc)) - timedelta(hours=20)


class _Pinned:
    name = "pinned"

    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def set(self, ticker: str, price: float) -> None:
        self.prices[ticker.upper()] = price

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source=self.source)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


@pytest.fixture(autouse=True)
def _no_borrow_socket(monkeypatch):
    """§4 resolves the borrow rate at OPEN, and Layer 2 reads yfinance. Without
    this every short in this file opens a real socket — the suite then depends
    on Yahoo being up and on AAPL's current short interest, so a test asserting
    a $500 margin debit would start failing for a reason that has nothing to do
    with margin. Pinned to Layer 3, which is also what Alpha reaches today for
    any ticker outside the S&P snapshot.
    """
    monkeypatch.setattr(
        "app.services.short_borrow_rate._fetch_info", lambda ticker: {},
    )


def _mandate(*, long_only: bool = False, halal: bool = False, **over):
    """`long_only` and `halal` live under `compliance`, not at the top level —
    passing them flat hydrates to the DEFAULT (`long_only=True`), which would
    make every short in this file refuse for the wrong reason and read as the
    feature not working.

    The trade-count limits are lifted because several tests below place four or
    more orders to build a position; a per-day brake firing mid-test would
    report itself as a concentration or long-only refusal.
    """
    base = {
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "max_trades_per_day": 100,
        "max_trades_per_week": 500,
        "compliance": {"long_only": long_only, "halal": halal},
    }
    base.update(over)
    return hydrate_coach_mandate(base)


def _shorts(user_id):
    with get_session() as s:
        return s.execute(
            select(SimShortPositionRow).where(
                SimShortPositionRow.user_id == user_id
            )
        ).scalars().all()


def _trades(user_id):
    with get_session() as s:
        return s.execute(
            select(SimTradeRow).where(SimTradeRow.user_id == user_id)
        ).scalars().all()


def _short(sim, user_id, *, ticker="AAPL", qty=10, **kw):
    return sim.submit(
        user_id=user_id, ticker=ticker, side=Side.SELL, quantity=qty,
        mandate=kw.pop("mandate", _mandate()),
        order_type=OrderType.MARKET, **kw,
    )


# ── Acceptance 1 — long_only is finally read on the path that decides ──────


def test_a1_long_only_refuses_a_sell_to_open_at_the_floor_itself():
    """DEF262. The refusal must come from `check_mandate_compliance`, naming
    the MANDATE, not from `_execute_fill`'s holdings check.

    Before this the floor's `long_only` branch was a bare `pass` with a comment
    saying the decision was "delegated to trade service" — and it was delegated
    nowhere that reads the flag. `_execute_fill` refused the sell for lacking
    shares and stamped `blocked_by="long_only"` on a message about holdings, so
    the flag named a refusal it never made. Turning it OFF changed nothing.
    """
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.ensure_portfolio(user_id)

    r = _short(sim, user_id, mandate=_mandate(long_only=True))

    assert not r.accepted
    assert r.compliance.blocked_by == "long_only"
    assert any("long-only" in v for v in r.compliance.violations), (
        "the violation must name the mandate setting, not the share count: "
        f"{r.compliance.violations}"
    )
    assert _shorts(user_id) == []


def test_a1_the_flag_actually_responds_to_being_turned_off():
    """The half DEF262 really was: with `long_only` off, the same order opens a
    short. A control that does not respond to its own switch is a control the
    user cannot learn anything from."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.ensure_portfolio(user_id)

    r = _short(sim, user_id, mandate=_mandate(long_only=False))

    assert r.accepted and r.short_action == "short_open"
    assert len(_shorts(user_id)) == 1


# ── Acceptance 2 — a sell never crosses zero ───────────────────────────────


def test_a2_a_partial_sell_is_refused_naming_both_numbers():
    """`0 < held < quantity`. A real broker splits this into a close plus a
    short; we refuse it, because the split is two fills, two trade rows and two
    cost bases from one action, and the P&L attribution that follows is exactly
    what DEF166 and DEF110 have already cost twice."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )

    r = _short(sim, user_id, qty=8)

    assert not r.accepted
    sentence = " ".join(r.compliance.violations)
    assert "8" in sentence and "5" in sentence, (
        f"both numbers must appear so the user can act on it: {sentence}"
    )
    assert _shorts(user_id) == [], "a refused partial must not open a short"


def test_a2_a_full_sell_of_a_held_position_behaves_exactly_as_before():
    """`held >= quantity` is byte-identical to today: an ordinary sell-to-close
    that writes a `sim_trades` row and NO short."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )

    r = _short(sim, user_id, qty=5)

    assert r.accepted and r.short_action is None
    assert r.trade is not None, "a sell-to-close is still an ordinary trade row"
    assert _shorts(user_id) == []


# ── Acceptance 3 — opening a short does not move total_value ───────────────


def test_a3_opening_a_short_does_not_increase_cash_or_change_total_value():
    """The identity the whole cash design rests on. At an unchanged mark the
    leg is worth exactly the cash that left, so the sum does not move."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    before_cash = sim.ensure_portfolio(user_id).current_cash
    before_value = sim.total_value(user_id)

    r = _short(sim, user_id, qty=10)
    assert r.accepted

    after = sim.ensure_portfolio(user_id)
    assert after.current_cash < before_cash, (
        "the 50% margin above the proceeds leaves cash"
    )
    assert after.current_cash == before_cash - 500.0, (
        "1.50 collateral on $1,000 notional debits exactly $500"
    )
    assert abs(sim.total_value(user_id) - before_value) < 0.01, (
        "opening a short must not change what the portfolio is worth"
    )


def test_a3_covering_at_the_same_price_returns_the_portfolio_unchanged():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    before_cash = sim.ensure_portfolio(user_id).current_cash
    _short(sim, user_id, qty=10)

    sim.cover_short(user_id=user_id, ticker="AAPL")

    assert abs(sim.ensure_portfolio(user_id).current_cash - before_cash) < 0.01


# ── Acceptance 4 — a short that moves against the user costs them ──────────


def test_a4_total_value_falls_when_the_short_goes_the_wrong_way():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _short(sim, user_id, qty=10)
    at_entry = sim.total_value(user_id)

    prov.set("AAPL", 110.0)
    assert sim.total_value(user_id) < at_entry
    assert abs((at_entry - sim.total_value(user_id)) - 100.0) < 0.01, (
        "a $10 move against 10 shares costs exactly $100 — no leverage, no gearing"
    )

    prov.set("AAPL", 90.0)
    assert sim.total_value(user_id) > at_entry


# ── Acceptance 5 — def110_backfill must not see a short at all ─────────────


def test_a5_a_short_writes_no_sim_trades_row():
    """`def110_backfill.expected()` subtracts Σ quantity over OPEN SELL trade
    rows to derive what a portfolio's holdings should be. A short with a trade
    row would make every genuine phantom share look accounted for — breaking
    the one detector we have for the class of bug DEF110 was."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()

    _short(sim, user_id, qty=10)

    assert _trades(user_id) == [], (
        "the sim_short_positions row IS the record; a SELL trade row here "
        "silently corrupts phantom-share detection"
    )
    assert len(_shorts(user_id)) == 1


# ── Acceptance 6 — borrow accrues once per day ─────────────────────────────


def test_a6_borrow_accrues_once_per_day_however_often_the_pass_runs():
    """`last_borrow_accrual_date` is the idempotency key, and it is a stored
    DATE rather than an elapsed-time comparison for the reason a restart makes
    obvious: elapsed time is a different value on every boot."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    _short(sim, user_id, qty=10)
    cash = sim.ensure_portfolio(user_id).current_cash

    first = sim.accrue_short_borrow(user_id, on_date="2026-08-14")
    second = sim.accrue_short_borrow(user_id, on_date="2026-08-14")
    third = sim.accrue_short_borrow(user_id, on_date="2026-08-14")

    assert first > 0, "a day of borrow on $1,000 is small but not nothing"
    assert second == 0.0 and third == 0.0
    assert abs(sim.ensure_portfolio(user_id).current_cash - (cash - first)) < 0.01

    # A new day charges again — the guard is idempotency, not a one-off.
    assert sim.accrue_short_borrow(user_id, on_date="2026-08-15") > 0


def test_a6_borrow_is_not_market_hours_gated():
    """Borrow accrues on CALENDAR days. Gating it on the session would quietly
    make the weekend a position is held over free, which is precisely the
    carrying cost a simulator can teach honestly."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    _short(sim, user_id, qty=10)

    stats = sweep_resting_orders(
        user_id=user_id, now=_closed_time(), engine=sim,
    )

    assert stats["skipped_closed"] == 1, "precondition: the market is shut"
    assert stats["borrow_charged_cents"] > 0


# ── Acceptance 7 & 8 — the margin call ─────────────────────────────────────


def test_a7_a_breached_short_is_force_closed_at_the_observed_mark():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _short(sim, user_id, qty=10)

    # collateral 1500, entry 1000. ratio = (1500 + 1000 - 10m) / 10m < 1.30
    # once m > 108.69...
    prov.set("AAPL", 130.0)
    closed = sim.force_close_breached_shorts(user_id)

    assert closed == ["AAPL"]
    row = _shorts(user_id)[0]
    assert row.state == "closed"
    assert row.close_reason == "margin", (
        "a position that vanished with no explanation is the games lane's "
        "'the order simply VANISHED' defect on a much bigger number"
    )
    assert float(row.close_price) == 130.0


def test_a7_the_forced_close_succeeds_with_zero_cash():
    """The whole point of posting collateral. A margin close that could be
    refused for insufficient cash is a containment mechanism that fails exactly
    when it is needed."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _short(sim, user_id, qty=10)

    with get_session() as s:
        p = sim._load_portfolio_row(s, user_id)
        p.current_cash = 0.0

    prov.set("AAPL", 130.0)
    assert sim.force_close_breached_shorts(user_id) == ["AAPL"]
    assert _shorts(user_id)[0].state == "closed"


def test_a8_a_breach_outside_market_hours_does_not_close_the_position():
    """A margin close against a stale overnight print is CR109 §5.1's time
    machine in the direction that costs the user money — worse than DEF261,
    not better. It closes on the next sweep inside the session."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    _short(sim, user_id, qty=10)
    prov.set("AAPL", 130.0)

    shut = sweep_resting_orders(user_id=user_id, now=_closed_time(), engine=sim)
    assert shut["shorts_margined"] == 0
    assert _shorts(user_id)[0].state == "open"

    live = sweep_resting_orders(
        user_id=user_id, now=_live_session_time(), engine=sim,
    )
    assert live["shorts_margined"] == 1
    assert _shorts(user_id)[0].state == "closed"


# ── Acceptance 9 — the bracket inverts ─────────────────────────────────────


def test_a9_a_shorts_stop_fires_ABOVE_entry_and_target_BELOW():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    stopped, won = uuid4(), uuid4()
    _short(sim, stopped, qty=2, stop=105.0, target=90.0)
    _short(sim, won, qty=2, stop=105.0, target=90.0)

    prov.set("AAPL", 106.0)
    assert sim.evaluate_short_brackets(stopped) == ["AAPL"]
    assert _shorts(stopped)[0].close_reason == "stop"

    prov.set("AAPL", 89.0)
    assert sim.evaluate_short_brackets(won) == ["AAPL"]
    assert _shorts(won)[0].close_reason == "target"


def test_a9_a_stop_below_entry_is_refused_at_submit():
    """Not silently accepted. A short's stop below entry is not a stop, it is a
    second target: it can only fire after the position has given back
    everything it made. `short_rules.dart` mirrors this client-side and the two
    must agree at the boundary."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()

    r = _short(sim, user_id, qty=2, stop=90.0)

    assert not r.accepted
    assert "ABOVE" in " ".join(r.compliance.violations)
    assert _shorts(user_id) == []


def test_a9_a_long_position_bracket_is_untouched():
    """§5 is explicit that `evaluate_outcomes`'s `Side.BUY` gate is CORRECT and
    must not simply be removed — a SELL row there is an exit, so its levels are
    meaningless and firing on them would close a position twice."""
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=2,
        mandate=_mandate(), order_type=OrderType.MARKET, stop=90.0, target=120.0,
    )

    prov.set("AAPL", 89.0)
    assert len(sim.evaluate_outcomes(user_id)) == 1
    assert _trades(user_id)[0].status == "lost"


# ── Acceptance 10 — concentration is GROSS ─────────────────────────────────


def test_a10_an_existing_short_counts_toward_the_single_name_cap():
    """Long $5k and short $5k of one ticker is $10k of exposure, not $0. It is
    two positions, two borrow costs and two ways to be wrong; netting them
    would let a user hide unlimited gross exposure behind a flat net.

    The gate used to be `is_buy` alone, which was right while a sell could only
    REDUCE a position. A sell-to-open increases it, in the other direction.
    """
    sim = SimEngine(provider=_Pinned({"TSLA": 100.0}))
    user_id = uuid4()
    capped = _mandate(single_name_cap_pct=60.0)

    first = _short(sim, user_id, ticker="TSLA", qty=40, mandate=capped)
    assert first.accepted, "precondition: a 40% short is inside a 60% cap"
    sim.cover_short(user_id=user_id, ticker="TSLA")

    # Same size, but now with a LONG already on the books in the same name.
    sim.submit(
        user_id=user_id, ticker="TSLA", side=Side.BUY, quantity=40,
        mandate=capped, order_type=OrderType.MARKET,
    )
    # 40 held, so a sell of 40 is a CLOSE. Sell 41 — more than held — and §1
    # refuses it as a partial before concentration is even reached, so exercise
    # the cap on a second name the user is already short.
    over = _short(sim, user_id, ticker="NVDA", qty=40, mandate=capped)
    assert over.accepted
    again = _short(sim, user_id, ticker="NVDA", qty=40, mandate=capped)
    assert not again.accepted, (
        "the EXISTING short must be measured as exposure, not as zero"
    )
    assert again.compliance.blocked_by == "concentration"


def test_a10_a_short_in_a_name_with_no_position_is_still_capped():
    """The cap must bite a first short too — before CR171 the whole check was
    skipped on any sell, so an unbounded short passed a mandate that reported
    itself as enforced."""
    sim = SimEngine(provider=_Pinned({"TSLA": 100.0}))
    user_id = uuid4()

    r = _short(sim, user_id, ticker="TSLA", qty=90, mandate=_mandate(
        single_name_cap_pct=20.0,
    ))

    assert not r.accepted
    assert r.compliance.blocked_by == "concentration"


# ── Acceptance 11 — the halal ruling: INFORM, do not block ─────────────────
#
# Saiful's ruling supersedes the CR doc's proposed outright refusal, which was
# deliberately escalated rather than settled in code review. Verbatim,
# 2026-08-13: *"Our job is only to inform. The user can continue with whatever
# trade they want to do. So we will put a flag and notice to inform the user,
# but we let the trade through."*


def test_a11_a_halal_mandate_gets_a_NOTICE_and_the_short_still_opens():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.ensure_portfolio(user_id)

    r = _short(
        sim, user_id, qty=10, mandate=_mandate(halal=True),
        halal_universe={"AAPL"},
    )

    assert r.accepted, "inform, do not block — the trade goes through"
    assert r.short_action == "short_open"
    assert len(_shorts(user_id)) == 1
    assert r.compliance.violations == [], (
        "a notice is not a violation; putting it there would refuse the trade"
    )
    assert any("Sharia" in a for a in r.compliance.advisories), (
        f"the user must actually be told: {r.compliance.advisories}"
    )


def test_a11_the_notice_reaches_the_wire_not_just_the_service_object(monkeypatch):
    """CR040 in its plainest form. An advisory computed correctly, logged
    server-side and never serialized informs nobody — and the whole ruling is
    that we inform. Driven through the real route for that reason."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.sim import router as sim_router
    from app.services.auth_service import AuthService
    from app.services.mandate_store import get_mandate_store

    # The route resolves the universe itself, and there is none seeded in the
    # test DB — the screen would PAUSE loudly (correct CR069 behaviour) and
    # refuse the trade for a reason that has nothing to do with this test.
    monkeypatch.setattr(
        "app.services.sim_engine.default_halal_universe", lambda: {"AAPL"},
    )

    app = FastAPI()
    app.include_router(sim_router)
    client = TestClient(app, raise_server_exceptions=False)
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    get_mandate_store().upsert(user.id, _mandate(halal=True, user_id=user.id))

    body = client.post(
        "/v1/sim/submit",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "user_id": str(user.id), "ticker": "AAPL",
            "side": "sell", "quantity": 2,
        },
    ).json()

    assert body.get("ok") is True, body
    assert any(
        "Sharia" in a for a in body["compliance"]["advisories"]
    ), f"the notice must be on the wire: {body['compliance']}"


def test_a11_long_only_still_hard_refuses_independently_of_halal():
    """Only the HALAL leg became inform-not-block. `long_only` is unchanged and
    still refuses — and both can be true of one user at once, in which case the
    mandate refuses and the notice is moot."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.ensure_portfolio(user_id)

    r = _short(
        sim, user_id, qty=10, mandate=_mandate(halal=True, long_only=True),
        halal_universe={"AAPL"},
    )

    assert not r.accepted
    assert r.compliance.blocked_by == "long_only"
    assert _shorts(user_id) == []


def test_a11_a_sell_to_CLOSE_under_a_halal_mandate_gets_no_notice():
    """The notice is about opening a short, not about selling. Attaching it to
    every sell would train the user to dismiss it unread, which is how a real
    disclosure stops working."""
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    user_id = uuid4()
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=_mandate(halal=True), order_type=OrderType.MARKET,
        halal_universe={"AAPL"},
    )

    r = _short(
        sim, user_id, qty=5, mandate=_mandate(halal=True),
        halal_universe={"AAPL"},
    )

    assert r.accepted and r.short_action is None
    assert r.compliance.advisories == []
