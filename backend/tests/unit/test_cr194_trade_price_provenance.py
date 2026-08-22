"""CR194 — every trade row records which provider actually priced it.

DEF305 liquidated every bracketed position on Alpha at mock-walk prices and
credited $6,882.22 of invented proceeds into real cash. The post-mortem could
only separate the eight fabricated closes from the one legitimate TSLA stop by
an accident: `round(v, 2)` against a `Numeric(12,4)` column left every fake
ending `.XX00`. Nothing designed that discriminator and it dies the day the
rounding changes.

So `price_source` / `close_price_source` are not a label on bad data — they
are the audit trail that proves the DEF305 kill switch held, and they turn a
future regression into one query instead of an eyeball exercise.

Acceptance 4 says the write is asserted **at the call site, not on a helper**
(DEF190), so each test below drives the real entry point — `submit`,
`evaluate_outcomes`, `close_trade`, the game liquidation — rather than calling
`_close_lot` directly. A helper-level test would stay green if a call site
stopped passing the source, which is the only way this can actually break.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.db import get_session
from app.db.models import SimTradeRow
from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote, set_market_data_provider
from app.services.sim_engine import SimEngine

_PRICE = 100.0


class _SourcedProvider:
    """Constant price, and a source we control so the assertion is exact."""

    name = "sourced_test"

    def __init__(self, source: str = "yfinance", price: float = _PRICE) -> None:
        self.source = source
        self.price = price

    def quote(self, ticker: str):
        return Quote(price=self.price, source=self.source, change_pct=0.0)

    def get_price(self, ticker: str):
        return self.price

    def earnings(self, ticker: str):
        return None


@pytest.fixture()
def provider():
    p = _SourcedProvider()
    set_market_data_provider(p)
    yield p
    set_market_data_provider(None)


@pytest.fixture()
def engine():
    return SimEngine()


def _mandate():
    return hydrate_coach_mandate({
        "plan": "trader", "single_name_cap_pct": 100.0,
        "compliance": {"long_only": False, "halal": False},
    })


def _rows(user_id):
    with get_session() as s:
        return list(
            s.query(SimTradeRow).filter(SimTradeRow.user_id == user_id).all()
        )


def _buy(engine, user_id, **kw):
    return engine.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=10.0,
        order_type=OrderType.MARKET, mandate=_mandate(), **kw
    )


# ── Acceptance 1: a fill records the provider that served it ───────────────

def test_a_live_fill_records_the_provider(provider, engine):
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    result = _buy(engine, user_id)
    assert result.accepted

    rows = _rows(user_id)
    assert len(rows) == 1
    assert rows[0].price_source == "yfinance"


def test_a_mock_walk_fill_says_mock_walk(engine):
    """The DEF305 case. This is the value the column exists to make visible."""
    set_market_data_provider(_SourcedProvider(source="mock_walk"))
    try:
        user_id = uuid4()
        engine.ensure_portfolio(user_id)
        assert _buy(engine, user_id).accepted
        assert _rows(user_id)[0].price_source == "mock_walk"
    finally:
        set_market_data_provider(None)


# ── The close paths ────────────────────────────────────────────────────────

def test_the_bracket_sweep_records_the_close_source(provider, engine):
    """`evaluate_outcomes` — the exact path DEF305 ran down.

    Driven through the real entry point: a target sitting below the mark, so
    the sweep fires on its own rather than being hand-fed a price.
    """
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    # A target ABOVE the fill (the floor refuses one below), then the market
    # moves up to it — so the sweep fires on its own price read.
    assert _buy(engine, user_id, target=_PRICE + 5.0).accepted

    provider.price = _PRICE + 6.0
    provider.source = "mock_walk"
    engine.evaluate_outcomes(user_id)

    closed = [r for r in _rows(user_id) if r.closed_price is not None]
    assert closed, "the bracket did not fire — the test proves nothing"
    assert closed[0].close_price_source == "mock_walk"
    # The OPEN source is untouched by the close: two facts, two columns.
    assert closed[0].price_source == "yfinance"


def test_a_manual_close_records_the_close_source(provider, engine):
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    result = _buy(engine, user_id)
    assert result.accepted

    provider.source = "mock_walk"
    assert engine.manual_close(user_id, result.trade.id) is not None

    closed = [r for r in _rows(user_id) if r.closed_price is not None]
    assert closed and closed[0].close_price_source == "mock_walk"


# ── Acceptance 2: no default, ever ─────────────────────────────────────────

def test_an_unset_source_reads_null_not_a_default():
    """"We do not know" and "it was a real quote" are different facts.

    A `server_default` of 'yfinance' would manufacture exactly the reassurance
    this column exists to stop manufacturing (CR040), and would have made the
    nine fabricated DEF305 closes read as live quotes.
    """
    for name in ("price_source", "close_price_source"):
        col = SimTradeRow.__table__.c[name]
        assert col.nullable is True, name
        assert col.default is None, name
        assert col.server_default is None, name


@pytest.mark.allow_ledger_drift
def test_a_row_written_without_a_source_stays_null():
    """Acceptance 3 in the form that survives: the 111 pre-existing rows.

    A bare row, written the way a forgetful site would write one, must read
    NULL on both columns — never a value the ORM or the DDL supplied on its
    behalf. Marked `allow_ledger_drift` because it inserts a trade row with no
    matching holding on purpose: the point is the columns, and the autouse
    phantom-share invariant would otherwise fire on a fixture that is
    deliberately not a real book.
    """
    user_id = uuid4()
    with get_session() as s:
        row = SimTradeRow(
            id=uuid4(), user_id=user_id, portfolio_id=uuid4(), ticker="AAPL",
            side="buy", quantity=1, entry_price=1.0, status="open",
        )
        s.add(row)
        row_id = row.id
    with get_session() as s:
        stored = s.get(SimTradeRow, row_id)
        assert stored.price_source is None
        assert stored.close_price_source is None


def test_an_open_row_has_no_close_source_yet(provider, engine):
    """Non-vacuity: the close column must not be filled at open time.

    If it were, a still-open position would claim provenance for a close that
    has not happened — a fact about the future, which is the DEF059 shape.
    """
    user_id = uuid4()
    engine.ensure_portfolio(user_id)
    assert _buy(engine, user_id).accepted
    row = _rows(user_id)[0]
    assert row.price_source == "yfinance"
    assert row.close_price_source is None
