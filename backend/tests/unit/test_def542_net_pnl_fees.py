"""DEF542 (AT:B1) — a closed journal entry's Realised P&L is NET of fees.

Android build 134: buy 100 6888.KL @ RM1.61 (fees RM8.21), sell 100 @ RM1.61
(fees RM8.21) read "Closed 6888.KL (MANUAL) — +RM0.00" although the book lost
RM16.42. The entry now carries net = price P&L - buy-leg fees (pro-rated by the
shares sold) - exit fee, with the round trip's fees beside it. Covers the ticket
sell, the manual close, a bracket close, a partial sell, and the zero-fee US book
(payload unchanged). Fees are read from the stored `sim_trades.toll_charged`,
never recomputed in the journal.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.journal import EntryType, Outcome
from app.schemas.trade import Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.journal_store import get_journal_store
from app.services.market_data import Quote
from app.services.sim_engine import SimEngine, prorated_fee
from app.services.sim_trade_effects import (
    apply_post_fill_effects,
    journal_bracket_closes,
    journal_manual_close,
)
from app.trading_math.markets import Market


class _Pinned:
    name = "pinned"

    def __init__(self, prices: dict[str, float]):
        self.prices = {k.upper(): v for k, v in prices.items()}

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source="yfinance", change_pct=0.0)

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


@pytest.fixture(autouse=True)
def _bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


def _fill(sim, uid, ticker, side, qty, **kw):
    r = sim.submit(
        user_id=uid, ticker=ticker, side=side, quantity=qty, mandate=_mandate(), **kw
    )
    assert r.accepted, r.compliance.violations
    apply_post_fill_effects(user_id=uid, trade=r.trade)
    return r


def _closed_entries(uid):
    entries, _, _ = get_journal_store().list_for_user(uid, entry_type=EntryType.SIM_TRADE)
    return [e for e in sorted(entries, key=lambda e: e.created_at) if "closed" in e.tags]


def test_bursa_break_even_round_trip_is_net_of_both_legs_fees():
    sim = SimEngine(provider=_Pinned({"6888.KL": 1.61}))
    uid = uuid4()
    _fill(sim, uid, "6888.KL", Side.BUY, 100)
    _fill(sim, uid, "6888.KL", Side.SELL, 100)
    (closed,) = _closed_entries(uid)
    assert closed.title == "Closed 6888.KL (MANUAL) — -RM16.42"
    t = closed.payload["trade"]
    assert t["realised_pnl"] == -16.42
    assert t["fees"] == 16.42
    assert closed.payload["outcome"]["realised_pnl"] == -16.42
    assert closed.payload["outcome"]["gross_realised_pnl"] == 0.0
    assert closed.outcome == Outcome.LOSS


def test_partial_sell_prorates_the_buy_leg_fee_by_quantity_sold():
    sim = SimEngine(provider=_Pinned({"6888.KL": 1.61}))
    uid = uuid4()
    _fill(sim, uid, "6888.KL", Side.BUY, 200)  # fee on RM322: 8.00 + 0.10 + 0.32 = 8.42
    _fill(sim, uid, "6888.KL", Side.SELL, 100)  # fee on RM161: 8.21
    (closed,) = _closed_entries(uid)
    # half of 8.42 (= 4.21) + the sell's own 8.21
    assert closed.payload["trade"]["fees"] == 12.42
    assert closed.payload["trade"]["realised_pnl"] == -12.42
    assert closed.title.endswith("— -RM12.42")
    # the second half of the buy fee lands on the next sell, nothing is lost
    _fill(sim, uid, "6888.KL", Side.SELL, 100)
    _, second = _closed_entries(uid)
    assert second.payload["trade"]["fees"] == 12.42


def test_prorated_fee_rule():
    assert prorated_fee(8.42, 200, 100) == pytest.approx(4.21)
    assert prorated_fee(None, 200, 100) == 0.0
    assert prorated_fee(8.42, 200, 0) == 0.0
    assert prorated_fee(8.42, 100, 300) == pytest.approx(8.42)  # never more than the fill paid


def test_price_gain_is_reduced_by_fees():
    prov = _Pinned({"6888.KL": 1.61})
    prices = prov.prices
    sim = SimEngine(provider=prov)
    uid = uuid4()
    _fill(sim, uid, "6888.KL", Side.BUY, 1000)  # notional 1,610: fee 8.00+0.48+1.61 = 10.09
    prices["6888.KL"] = 1.71
    _fill(sim, uid, "6888.KL", Side.SELL, 1000)  # notional 1,710: 8.00+0.51+1.71 = 10.22
    (closed,) = _closed_entries(uid)
    t = closed.payload["trade"]
    assert closed.payload["outcome"]["gross_realised_pnl"] == 100.0
    assert t["fees"] == 20.31
    assert t["realised_pnl"] == 79.69
    assert closed.outcome == Outcome.WIN


def test_manual_close_of_a_bursa_lot_is_net_of_both_legs_fees():
    sim = SimEngine(provider=_Pinned({"6888.KL": 1.61}))
    uid = uuid4()
    buy = _fill(sim, uid, "6888.KL", Side.BUY, 100)
    closed_trade = sim.manual_close(uid, buy.trade.id)
    assert closed_trade is not None
    assert closed_trade.realised_pnl == 0.0  # the trade row stays GROSS (outcome scoring reads it)
    assert closed_trade.round_trip_fees == 16.42
    journal_manual_close(uid, closed_trade)
    (entry,) = _closed_entries(uid)
    assert entry.title == "Closed 6888.KL (MANUAL) — -RM16.42"
    assert entry.payload["trade"]["realised_pnl"] == -16.42
    assert entry.payload["trade"]["fees"] == 16.42
    assert entry.outcome == Outcome.LOSS


def test_bracket_close_of_a_bursa_lot_is_net_of_both_legs_fees():
    prov = _Pinned({"6888.KL": 1.61})
    prices = prov.prices
    sim = SimEngine(provider=prov)
    uid = uuid4()
    _fill(sim, uid, "6888.KL", Side.BUY, 100, stop=1.50, target=1.90)
    prices["6888.KL"] = 1.50
    updates = sim.evaluate_outcomes(uid, Market.MY)
    assert len(updates) == 1
    u = updates[0]
    assert u.realised_pnl == -11.0  # gross stays price-only
    # buy leg 8.21 + exit on RM150: 8.00 + 0.05 + 0.15 = 8.20
    assert u.fees == 16.41
    journal_bracket_closes(uid, updates, Market.MY)
    (entry,) = _closed_entries(uid)
    assert entry.payload["trade"]["realised_pnl"] == -27.41
    assert entry.payload["trade"]["fees"] == 16.41
    assert entry.title == "Closed 6888.KL (LOST) — -RM27.41"


def test_us_book_with_no_fees_is_unchanged():
    sim = SimEngine(provider=_Pinned({"AAPL": 100.0}))
    uid = uuid4()
    _fill(sim, uid, "AAPL", Side.BUY, 10)
    _fill(sim, uid, "AAPL", Side.SELL, 10)
    (closed,) = _closed_entries(uid)
    assert closed.title == "Closed AAPL (MANUAL) — +$0.00"
    assert "fees" not in closed.payload["trade"]
    assert "fees" not in closed.payload["outcome"]
    assert "gross_realised_pnl" not in closed.payload["outcome"]
    assert closed.payload["trade"]["realised_pnl"] == 0.0


def test_us_manual_close_with_no_fees_is_unchanged():
    prov = _Pinned({"AAPL": 100.0})
    prices = prov.prices
    sim = SimEngine(provider=prov)
    uid = uuid4()
    buy = _fill(sim, uid, "AAPL", Side.BUY, 10)
    prices["AAPL"] = 110.0
    closed_trade = sim.manual_close(uid, buy.trade.id)
    assert closed_trade.round_trip_fees == 0.0
    journal_manual_close(uid, closed_trade)
    (entry,) = _closed_entries(uid)
    assert entry.payload["trade"]["realised_pnl"] == 100.0
    assert "fees" not in entry.payload["trade"]
