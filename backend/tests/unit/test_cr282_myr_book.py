"""CR282 lane C — the MYR book: routing, board lots, tick grid, price limits,
Bursa fees, per-market sweep gating, the per-exchange ticker reference.

No network. Every behaviour under test is MY-only with `MARKET_BURSA_ENABLED`
on; the flag-off class at the bottom proves nothing about the US book moves.
"""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from sqlalchemy import select, update

from app.core.config import settings
from app.db import get_session
from app.db.models import SimPortfolioRow, SimRestingOrderRow, SimTradeRow, TickerReferenceRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine
from app.services.sim_resting_orders import commitment_for, sweep_resting_orders
from app.trading_math.bursa_rules import (
    MarketRuleViolation,
    bursa_fees,
    check_price_limit,
    check_tick,
    is_on_tick,
    nearest_valid_prices,
)
from app.trading_math.markets import Market

KL = ZoneInfo("Asia/Kuala_Lumpur")
_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION = _BACKEND / "alembic" / "versions" / "cr282a0b0c0d1_sim_portfolios_market.py"


class _Pinned:
    name = "pinned"

    def __init__(self, prices: dict[str, float], change_pct: float = 0.0):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.change_pct = change_pct

    def set(self, ticker: str, price: float) -> None:
        self.prices[ticker.upper()] = price

    def quote(self, ticker: str) -> Quote | None:
        return Quote(
            price=self.prices.get(ticker.upper(), 100.0),
            source="yfinance",
            change_pct=self.change_pct if ticker.upper().endswith(".KL") else 0.0,
        )

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate():
    return hydrate_coach_mandate(
        {"plan": "trader", "single_name_cap_pct": 100.0, "max_open_risk_pct": 100.0}
    )


@pytest.fixture
def bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


def _buy(sim, uid, ticker="1155.KL", qty=100, **kw):
    return sim.submit(
        user_id=uid, ticker=ticker, side=Side.BUY, quantity=qty,
        mandate=_mandate(), **kw,
    )


def _portfolios(uid):
    with get_session() as s:
        return s.execute(
            select(SimPortfolioRow).where(SimPortfolioRow.user_id == uid)
        ).scalars().all()


# ── migration ────────────────────────────────────────────────────────────────


def test_migration_adds_market_column_backfilled_us_and_reverses(tmp_path):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location("cr282_mig", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE sim_portfolios (id VARCHAR PRIMARY KEY, kind VARCHAR)"))
        conn.execute(sa.text("INSERT INTO sim_portfolios VALUES ('a', 'training')"))
        ops = Operations(MigrationContext.configure(conn))
        with Operations.context(ops.migration_context):
            mod.upgrade()
            mod.upgrade()  # idempotent
        cols = {c["name"]: c for c in sa.inspect(conn).get_columns("sim_portfolios")}
        assert cols["market"]["nullable"] is False
        assert conn.execute(sa.text("SELECT market FROM sim_portfolios")).scalar() == "US"
        with Operations.context(ops.migration_context):
            mod.downgrade()
        assert "market" not in {c["name"] for c in sa.inspect(conn).get_columns("sim_portfolios")}


def test_single_alembic_head_includes_this_migration():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, heads
    chain = {r.revision for r in script.walk_revisions(base="base", head=heads[0])}
    assert "cr282a0b0c0d1" in chain


# ── pure rules ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("price", [0.005, 0.995, 1.00, 1.01, 9.99, 10.00, 10.02, 99.98, 100.00, 100.10])
def test_on_grid_prices(price):
    assert is_on_tick(price)


@pytest.mark.parametrize("price", [0.997, 1.005, 9.995, 10.01, 99.99, 100.05, 0])
def test_off_grid_prices(price):
    assert not is_on_tick(price)


def test_off_grid_refusal_names_nearest_prices():
    with pytest.raises(MarketRuleViolation) as e:
        check_tick(99.99)
    assert e.value.code == "tick_size"
    assert "99.98" in str(e.value) and "100" in str(e.value)
    assert nearest_valid_prices(0.997) == (Decimal("0.995"), Decimal("1.000"))


def test_fee_schedule_min_brokerage_and_both_caps():
    small = bursa_fees(1000.0)  # 0.10% = 1.00 -> RM8 minimum
    assert (small.brokerage, small.clearing, small.stamp_duty) == (8.0, 0.3, 1.0)
    assert small.total == 9.3
    mid = bursa_fees(100_000.0)
    assert (mid.brokerage, mid.clearing, mid.stamp_duty) == (100.0, 30.0, 100.0)
    big = bursa_fees(10_000_000.0)  # clearing and stamp both hit RM1,000
    assert big.clearing == 1000.0 and big.stamp_duty == 1000.0
    assert big.brokerage == 10_000.0  # brokerage is uncapped in the research schedule


def test_price_limit_band_and_sub_rm1_rule():
    check_price_limit(2.60, 2.00)
    check_price_limit(1.40, 2.00)
    with pytest.raises(MarketRuleViolation):
        check_price_limit(2.62, 2.00)
    with pytest.raises(MarketRuleViolation):
        check_price_limit(1.38, 2.00)
    # below RM1.00 the band is 30 sen absolute, not 30%
    check_price_limit(0.80, 0.50)
    check_price_limit(0.20, 0.50)
    with pytest.raises(MarketRuleViolation):
        check_price_limit(0.805, 0.50)
    with pytest.raises(MarketRuleViolation):
        check_price_limit(0.195, 0.50)


# ── routing and isolation ────────────────────────────────────────────────────


def test_first_kl_buy_creates_the_myr_book_at_rm50000_and_charges_fees(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00, "AAPL": 100.0}))
    uid = uuid4()
    r = _buy(sim, uid, qty=100)
    assert r.accepted, r.compliance.violations
    assert (r.market, r.currency) == ("MY", "MYR")
    assert r.fees == {
        "brokerage": 8.0, "clearing": 0.3, "stamp_duty": 1.0, "total": 9.3, "currency": "MYR",
    }
    assert r.toll_charged == 9.3
    books = {p.kind: p for p in _portfolios(uid)}
    assert set(books) == {"training_my"}  # no US book was created by a Bursa action
    my = books["training_my"]
    assert my.market == "MY" and float(my.starting_capital) == 50_000.0
    assert float(my.current_cash) == pytest.approx(50_000.0 - 1000.0 - 9.3)
    with get_session() as s:
        row = s.execute(select(SimTradeRow).where(SimTradeRow.user_id == uid)).scalar_one()
        assert float(row.toll_charged) == 9.3 and row.portfolio_id == my.id


def test_books_are_isolated_both_ways(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00, "AAPL": 100.0}))
    uid = uuid4()
    assert _buy(sim, uid, "1155.KL", 100).accepted
    assert _buy(sim, uid, "AAPL", 5).accepted
    us = sim.ensure_portfolio(uid)
    my = sim.ensure_portfolio(uid, market=Market.MY)
    assert us.id != my.id
    assert [h.ticker for h in us.holdings] == ["AAPL"]
    assert [h.ticker for h in my.holdings] == ["1155.KL"]
    assert us.starting_capital == 10_000.0 and my.starting_capital == 50_000.0
    assert us.current_cash == pytest.approx(10_000.0 - 500.0)  # no Bursa fee, no RM leak
    assert [t.ticker for t in sim.list_trades(uid)] == ["AAPL"]
    assert [t.ticker for t in sim.list_trades(uid, market=Market.MY)] == ["1155.KL"]
    assert sim.count_trades(uid) == 1 and sim.count_trades(uid, market=Market.MY) == 1
    # a US sell can never be satisfied from the MY book and vice versa
    r = sim.submit(user_id=uid, ticker="1155.KL", side=Side.SELL, quantity=100,
                   mandate=_mandate())
    assert r.accepted
    assert [h.ticker for h in sim.ensure_portfolio(uid).holdings] == ["AAPL"]


def test_default_portfolio_lookup_still_returns_the_us_book(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00}))
    uid = uuid4()
    _buy(sim, uid)
    sim.ensure_portfolio(uid)  # the US book now exists too
    p = sim.ensure_portfolio(uid)
    assert p.starting_capital == 10_000.0
    with get_session() as s:
        row = sim._load_portfolio_row(s, uid)
        assert row.kind == "training" and row.market == "US"


# ── board lots ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("qty,ok", [(100, True), (200, True), (150, False), (50, False), (0, False), (-100, False), (100.5, False)])
def test_board_lot(bursa_on, qty, ok):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00}))
    uid = uuid4()
    if ok:
        assert _buy(sim, uid, qty=qty).accepted
    else:
        with pytest.raises(MarketRuleViolation) as e:
            _buy(sim, uid, qty=qty)
        assert e.value.code == "board_lot" and "100" in str(e.value)
        assert _portfolios(uid) == []


def test_us_fractional_quantity_unchanged(bursa_on):
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    assert sim.submit(user_id=uuid4(), ticker="AAPL", side=Side.BUY, quantity=1.5,
                      mandate=_mandate()).accepted


# ── tick + price limits through the engine ───────────────────────────────────


def test_off_grid_limit_price_is_refused(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00}))
    with pytest.raises(MarketRuleViolation) as e:
        _buy(sim, uuid4(), order_type=OrderType.LIMIT, limit_price=9.505)
    assert e.value.code == "tick_size"


def test_limit_beyond_30pct_of_previous_close_is_refused(bursa_on):
    # price 2.20 up 10% => previous close 2.00 => band 1.40..2.60
    sim = SimEngine(provider=_Pinned({"1155.KL": 2.20}, change_pct=10.0))
    uid = uuid4()
    with pytest.raises(MarketRuleViolation) as e:
        _buy(sim, uid, order_type=OrderType.LIMIT, limit_price=2.62)
    assert e.value.code == "price_limit"
    r = _buy(sim, uid, order_type=OrderType.LIMIT, limit_price=1.42)
    assert r.accepted and r.resting


def test_sub_rm1_limit_uses_the_30_sen_rule(bursa_on):
    sim = SimEngine(provider=_Pinned({"0166.KL": 0.50}))
    with pytest.raises(MarketRuleViolation):
        _buy(sim, uuid4(), "0166.KL", order_type=OrderType.LIMIT, limit_price=0.195)
    assert _buy(sim, uuid4(), "0166.KL", order_type=OrderType.LIMIT, limit_price=0.20).resting


def test_market_order_fills_at_quote_without_price_limit_check(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 2.20}, change_pct=-50.0))
    r = _buy(sim, uuid4())
    assert r.accepted and r.trade.entry_price == 2.20


# ── unsupported on Bursa ─────────────────────────────────────────────────────


def test_shorts_refused_from_marketspec(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00}))
    with pytest.raises(MarketRuleViolation) as e:
        sim.submit(user_id=uuid4(), ticker="1155.KL", side=Side.SELL, quantity=100,
                   mandate=_mandate())
    assert e.value.code == "shorts_unsupported" and "Bursa Malaysia" in str(e.value)


def test_partial_sell_larger_than_holding_is_refused_not_shorted(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00}))
    uid = uuid4()
    _buy(sim, uid, qty=100)
    r = sim.submit(user_id=uid, ticker="1155.KL", side=Side.SELL, quantity=200,
                   mandate=_mandate())
    assert not r.accepted


def test_options_and_alpaca_unsupported_flags_on_the_spec():
    from app.trading_math.markets import spec_for

    spec = spec_for(Market.MY)
    assert not spec.options_supported and not spec.alpaca_supported and not spec.shorts_supported


# ── sell fees ────────────────────────────────────────────────────────────────


def test_sell_pays_fee_on_proceeds(bursa_on):
    prov = _Pinned({"1155.KL": 10.00})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    _buy(sim, uid, qty=100)
    prov.set("1155.KL", 11.00)
    r = sim.submit(user_id=uid, ticker="1155.KL", side=Side.SELL, quantity=100,
                   mandate=_mandate())
    assert r.accepted and r.fees["total"] == bursa_fees(1100.0).total
    cash = sim.ensure_portfolio(uid, market=Market.MY).current_cash
    expected = 50_000.0 - 1000.0 - bursa_fees(1000.0).total + 1100.0 - bursa_fees(1100.0).total
    assert cash == pytest.approx(expected)


def test_insufficient_cash_message_is_in_ringgit(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 400.00, "5099.KL": 150.00}))
    uid = uuid4()
    assert _buy(sim, uid, "1155.KL", 100).accepted  # RM40,000 + fees
    r = _buy(sim, uid, "5099.KL", 100)  # RM15,000 against ~RM9,950 left
    assert not r.accepted
    assert r.compliance.violations[0].startswith("insufficient cash: need RM")


# ── preview ──────────────────────────────────────────────────────────────────


def test_preview_reports_ringgit_and_fees(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00}))
    pv = sim.preview(user_id=uuid4(), ticker="1155.KL", side=Side.BUY, quantity=100,
                     mandate=_mandate())
    assert pv.accepted and pv.currency == "MYR" and pv.fees["total"] == 9.3
    assert pv.cash_available == 50_000.0
    with pytest.raises(MarketRuleViolation):
        sim.preview(user_id=uuid4(), ticker="1155.KL", side=Side.BUY, quantity=150,
                    mandate=_mandate())


# ── sweep: per-market sessions ───────────────────────────────────────────────


def _expiry(order_id) -> datetime:
    with get_session() as s:
        e = s.get(SimRestingOrderRow, order_id).expires_at
    return e if e.tzinfo else e.replace(tzinfo=timezone.utc)


def _rest_my_buy(sim, uid, limit=9.00, **kw):
    r = _buy(sim, uid, order_type=OrderType.LIMIT, limit_price=limit, tif="gtd_30", **kw)
    assert r.resting
    return r.resting_order.id


def test_my_resting_order_fills_in_session_only(bursa_on):
    prov = _Pinned({"1155.KL": 10.00})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    oid = _rest_my_buy(sim, uid)
    prov.set("1155.KL", 8.90)  # through the limit
    close = _expiry(oid)  # 16:50 KL on a session day
    lunch = close - timedelta(hours=4)          # 12:50 KL
    pre_open = close - timedelta(hours=7, minutes=55)  # 08:55 KL
    for closed_now in (lunch, pre_open):
        stats = sweep_resting_orders(user_id=uid, now=closed_now, engine=sim)
        assert stats["filled"] == 0 and stats["skipped_closed"] == 1
    stats = sweep_resting_orders(user_id=uid, now=close - timedelta(hours=1), engine=sim)
    assert stats["filled"] == 1 and stats["skipped_closed"] == 0
    p = sim.ensure_portfolio(uid, market=Market.MY)
    assert [h.ticker for h in p.holdings] == ["1155.KL"]


def test_my_order_does_not_fill_on_a_bursa_holiday(bursa_on):
    prov = _Pinned({"1155.KL": 10.00})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    oid = _rest_my_buy(sim, uid)
    prov.set("1155.KL", 8.90)
    with get_session() as s:
        s.execute(update(SimRestingOrderRow).where(SimRestingOrderRow.id == oid)
                  .values(expires_at=datetime(2027, 12, 31, tzinfo=timezone.utc)))
    holiday_midmorning = datetime(2026, 8, 31, 10, 0, tzinfo=KL)  # National Day, Mon
    stats = sweep_resting_orders(user_id=uid, now=holiday_midmorning, engine=sim)
    assert stats["filled"] == 0
    assert sweep_resting_orders(
        user_id=uid, now=datetime(2026, 9, 1, 10, 0, tzinfo=KL), engine=sim,
    )["filled"] == 1


def test_bursa_hours_do_not_fill_a_us_order_and_us_hours_do_not_fill_a_my_order(bursa_on):
    prov = _Pinned({"1155.KL": 10.00, "AAPL": 100.0})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    my_id = _rest_my_buy(sim, uid)
    us = sim.submit(user_id=uid, ticker="AAPL", side=Side.BUY, quantity=2,
                    mandate=_mandate(), order_type=OrderType.LIMIT, limit_price=90.0,
                    tif="gtd_30")
    assert us.resting
    prov.set("1155.KL", 8.90)
    prov.set("AAPL", 89.0)
    with get_session() as s:
        s.execute(update(SimRestingOrderRow).values(
            expires_at=datetime(2027, 12, 31, tzinfo=timezone.utc)))
    # Tue 2026-12-01 10:00 KL = 02:00Z: Bursa open, NYSE closed (21:00 ET Mon)
    bursa_open = datetime(2026, 12, 1, 10, 0, tzinfo=KL)
    stats = sweep_resting_orders(user_id=uid, now=bursa_open, engine=sim)
    assert stats["filled"] == 1
    with get_session() as s:
        states = {r.ticker: r.state for r in s.execute(select(SimRestingOrderRow)).scalars()}
    assert states == {"1155.KL": "filled", "AAPL": "working"}
    # Mon 2026-12-07 10:00 ET: NYSE open, Bursa shut (23:00 KL)
    us_open = datetime(2026, 12, 7, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    stats = sweep_resting_orders(user_id=uid, now=us_open, engine=sim)
    assert stats["filled"] == 1
    assert my_id is not None


def test_my_bracket_stop_fires_only_inside_bursa_and_pays_the_fee(bursa_on):
    prov = _Pinned({"1155.KL": 10.00})
    sim = SimEngine(provider=prov)
    uid = uuid4()
    assert _buy(sim, uid, qty=100, stop=9.00).accepted
    prov.set("1155.KL", 8.50)
    lunch = datetime(2026, 12, 1, 13, 0, tzinfo=KL)
    assert sweep_resting_orders(user_id=uid, now=lunch, engine=sim)["brackets_closed"] == 0
    held = sim.ensure_portfolio(uid, market=Market.MY).holdings
    assert [h.ticker for h in held] == ["1155.KL"]
    session = datetime(2026, 12, 1, 15, 0, tzinfo=KL)
    assert sweep_resting_orders(user_id=uid, now=session, engine=sim)["brackets_closed"] == 1
    p = sim.ensure_portfolio(uid, market=Market.MY)
    assert p.holdings == []
    expected = 50_000.0 - 1000.0 - bursa_fees(1000.0).total + 850.0 - bursa_fees(850.0).total
    assert p.current_cash == pytest.approx(expected)


def test_commitment_is_scoped_to_the_book(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00, "AAPL": 100.0}))
    uid = uuid4()
    _rest_my_buy(sim, uid, limit=9.00)
    sim.submit(user_id=uid, ticker="AAPL", side=Side.BUY, quantity=2, mandate=_mandate(),
               order_type=OrderType.LIMIT, limit_price=90.0)
    assert commitment_for(uid).cash_committed == 180.0
    assert commitment_for(uid, Market.MY).cash_committed == 900.0


# ── flag off ─────────────────────────────────────────────────────────────────


def test_flag_off_kl_is_refused_and_the_us_book_is_untouched():
    assert settings.market_bursa_enabled is False
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00, "AAPL": 100.0}))
    uid = uuid4()
    with pytest.raises(MarketRuleViolation) as e:
        _buy(sim, uid)
    assert e.value.code == "market_disabled"
    with pytest.raises(MarketRuleViolation):
        sim.ensure_portfolio(uid, market=Market.MY)
    assert _portfolios(uid) == []
    assert sim.submit(user_id=uid, ticker="AAPL", side=Side.BUY, quantity=1.5,
                      mandate=_mandate()).accepted
    us = sim.ensure_portfolio(uid)
    assert us.current_cash == pytest.approx(10_000.0 - 150.0)
    assert [p.kind for p in _portfolios(uid)] == ["training"]


def test_flag_off_sweep_gates_on_us_only():
    prov = _Pinned({"AAPL": 100.0})
    sim = SimEngine(provider=prov)
    stats = sweep_resting_orders(
        now=datetime(2026, 12, 1, 10, 0, tzinfo=KL), engine=sim,  # NYSE closed
    )
    assert stats["skipped_closed"] == 1


# ── API ──────────────────────────────────────────────────────────────────────


def _client(monkeypatch=None):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.sim import router
    from app.services.auth_service import AuthService

    app = FastAPI()
    app.include_router(router)
    user, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    return TestClient(app, raise_server_exceptions=False), user, {"Authorization": f"Bearer {token}"}


def test_api_market_param_default_us_and_my_book(bursa_on, monkeypatch):
    from app.services import sim_engine as se

    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00, "AAPL": 100.0}))
    monkeypatch.setattr(se, "_engine", sim)
    c, user, h = _client()
    from app.api.sim import get_sim_engine
    c.app.dependency_overrides[get_sim_engine] = lambda: sim

    body = {"user_id": str(user.id), "ticker": "1155.KL", "side": "buy", "quantity": 100}
    r = c.post("/v1/sim/submit", json=body, headers=h)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] and j["currency"] == "MYR" and j["fees"]["total"] == 9.3

    us = c.get(f"/v1/sim/portfolio/{user.id}", headers=h).json()
    assert us["market"] == "US" and us["currency"] == "USD" and us["holdings"] == []
    my = c.get(f"/v1/sim/portfolio/{user.id}", params={"market": "MY"}, headers=h).json()
    assert my["market"] == "MY" and my["currency"] == "MYR"
    assert my["starting_capital"] == 50_000.0
    assert [x["ticker"] for x in my["holdings"]] == ["1155.KL"]

    t_us = c.get(f"/v1/sim/trades/{user.id}", headers=h).json()
    t_my = c.get(f"/v1/sim/trades/{user.id}", params={"market": "MY"}, headers=h).json()
    assert t_us["trades"] == [] and "currency" not in t_us
    assert len(t_my["trades"]) == 1 and t_my["currency"] == "MYR"


def test_api_board_lot_is_a_422_naming_the_rule(bursa_on):
    sim = SimEngine(provider=_Pinned({"1155.KL": 10.00}))
    c, user, h = _client()
    from app.api.sim import get_sim_engine
    c.app.dependency_overrides[get_sim_engine] = lambda: sim
    body = {"user_id": str(user.id), "ticker": "1155.KL", "side": "buy", "quantity": 150}
    for path in ("/v1/sim/submit", "/v1/sim/preview"):
        r = c.post(path, json=body, headers=h)
        assert r.status_code == 422, r.text
        d = r.json()["detail"]
        assert d["code"] == "board_lot" and "100" in d["message"] and d["market"] == "MY"


def test_api_flag_off_market_my_is_422_and_kl_submit_refused():
    c, user, h = _client()
    r = c.get(f"/v1/sim/portfolio/{user.id}", params={"market": "MY"}, headers=h)
    assert r.status_code == 422
    r = c.get(f"/v1/sim/portfolio/{user.id}", headers=h)
    assert r.status_code == 200 and r.json()["market"] == "US"
    r = c.post("/v1/sim/submit", headers=h, json={
        "user_id": str(user.id), "ticker": "1155.KL", "side": "buy", "quantity": 100})
    assert r.status_code == 422


# ── ticker reference: per-exchange refresh ───────────────────────────────────


def _us(sym):
    return {"symbol": sym, "company_name": sym, "exchange": "NASDAQ", "is_etf": False}


def _bursa_csv(n):
    return "code,name\n" + "\n".join(f"{1000 + i:04d},Counter {i}" for i in range(n))


def test_bursa_load_parses_and_refuses_a_truncated_file():
    from app.services.ticker_reference import (
        TickerReferenceSourceError,
        load_bursa_reference,
        parse_bursa_csv,
    )

    recs = parse_bursa_csv("code,name\n1155,MAYBANK\nbad,x\n5099.KL,AIRASIA X\n,\n")
    assert [r["symbol"] for r in recs] == ["1155.KL", "5099.KL"]
    assert {r["exchange"] for r in recs} == {"Bursa Malaysia"}
    with pytest.raises(TickerReferenceSourceError):
        load_bursa_reference("code,name\n1155,MAYBANK\n")


def test_us_refresh_never_deactivates_bursa_rows_and_vice_versa():
    from app.services.ticker_reference import load_bursa_reference, upsert_reference

    now = datetime.now(timezone.utc)
    load_bursa_reference(_bursa_csv(600), now)
    with get_session() as s:
        upsert_reference(s, [_us("ZZZA"), _us("ZZZB")], now)
    with get_session() as s:
        bursa_active = s.execute(
            select(sa.func.count()).select_from(TickerReferenceRow).where(
                TickerReferenceRow.exchange == "Bursa Malaysia",
                TickerReferenceRow.is_active.is_(True),
            )
        ).scalar_one()
    assert bursa_active == 600

    # a later US refresh that drops ZZZB deactivates only ZZZB
    with get_session() as s:
        upsert_reference(s, [_us("ZZZA")], now)
    # a later Bursa load that drops a code deactivates only that Bursa row
    load_bursa_reference(_bursa_csv(599), now)
    with get_session() as s:
        rows = {r.symbol: r.is_active for r in s.execute(select(TickerReferenceRow)).scalars()}
    assert rows["ZZZA"] is True and rows["ZZZB"] is False
    assert rows["1000.KL"] is True and rows["1599.KL"] is False


def test_bursa_load_does_not_make_the_us_refresh_look_fresh():
    from app.services.ticker_reference import (
        _latest_refresh_at,
        load_bursa_reference,
    )

    with get_session() as s:
        s.execute(update(TickerReferenceRow).values(is_active=False))
    load_bursa_reference(_bursa_csv(600), datetime.now(timezone.utc))
    with get_session() as s:
        assert _latest_refresh_at(s) is None
