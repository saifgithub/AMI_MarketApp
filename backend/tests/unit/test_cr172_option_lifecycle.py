"""CR172 §7 acceptance — what happens to an option when nobody touches it.

The two that matter most, in order:

  * `test_boundary_*` — **the penny.** OCC exercises by exception at $0.01 in
    the money and abandons everything under it, and that single comparison
    decides whether a user wakes up holding 100 shares they must fund or
    holding nothing at all. It is tested on both sides of the line and at the
    sub-penny case that rounds to a cent but is still abandoned.
  * `test_floor_reentry_*` — **allow and flag.** Exercise creates a
    `sim_holdings` row by RULE, not by an order. The floor cannot refuse it
    after the fact, and it must not stay silent about it either; both halves
    are asserted, because either one alone is a plausible-looking pass.

Every test drives the real engine and the real settlement, for the DEF190
reason CR171's suite states: testing the arithmetic in isolation proves the
arithmetic, and says nothing about whether the arithmetic is the one that runs.
"""

from __future__ import annotations

import datetime
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    SimHoldingRow,
    SimOptionLegRow,
    SimOptionTradeRow,
    SimPortfolioRow,
)
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.services.option_lifecycle import DividendEvent
from app.services.sim_engine import SimEngine

EXPIRY = datetime.date(2026, 1, 16)
BEFORE_EXPIRY = datetime.date(2026, 1, 9)


class _Pinned:
    name = "pinned"

    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def quote(self, ticker: str) -> Quote | None:
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source=self.source)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def _mandate(**over):
    base = {
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "max_trades_per_day": 100,
        "max_trades_per_week": 500,
        "compliance": {"long_only": False, "halal": False},
    }
    base.update(over)
    return hydrate_coach_mandate(base)


def _portfolio_row(user_id):
    with get_session() as s:
        return s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one()


def _add_leg(
    user_id,
    *,
    right: str,
    strike: float,
    quantity: float,
    premium: float = 2.0,
    collateral: float = 0.0,
    underlying: str = "AAPL",
    expiry: datetime.date = EXPIRY,
    strategy_id=None,
    strategy_name: str = "long_call",
    with_structure: bool = False,
):
    strategy_id = strategy_id or uuid4()
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one()
        leg = SimOptionLegRow(
            id=uuid4(),
            user_id=user_id,
            portfolio_id=p_row.id,
            occ_symbol=f"{underlying:<6}{expiry.strftime('%y%m%d')}"
                       f"{'C' if right == 'call' else 'P'}{round(strike * 1000):08d}",
            underlying=underlying,
            right=right,
            strike=strike,
            expiry=expiry,
            quantity=quantity,
            avg_premium=premium,
            multiplier=100,
            collateral_posted=collateral,
            strategy_id=strategy_id,
            strategy_name=strategy_name,
        )
        s.add(leg)
        if with_structure:
            s.add(SimOptionTradeRow(
                id=uuid4(),
                user_id=user_id,
                portfolio_id=p_row.id,
                strategy_id=strategy_id,
                underlying=underlying,
                strategy_name=strategy_name,
                net_cost_at_open=premium * 100 * abs(quantity),
                collateral_posted=collateral,
            ))
        s.flush()
        return leg.id, strategy_id


def _set_cash(user_id, cash: float):
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one()
        p_row.current_cash = cash
        s.flush()


def _add_shares(user_id, ticker: str, quantity: float, avg_cost: float):
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one()
        s.add(SimHoldingRow(
            portfolio_id=p_row.id,
            ticker=ticker,
            quantity=quantity,
            avg_cost=avg_cost,
            opened_at=datetime.datetime.now(datetime.timezone.utc),
        ))
        s.flush()


def _leg(leg_id) -> SimOptionLegRow:
    with get_session() as s:
        return s.execute(
            select(SimOptionLegRow).where(SimOptionLegRow.id == leg_id)
        ).scalar_one()


def _holdings(user_id) -> list[SimHoldingRow]:
    with get_session() as s:
        p_row = s.execute(
            select(SimPortfolioRow).where(
                SimPortfolioRow.user_id == user_id,
                SimPortfolioRow.kind == "training",
            )
        ).scalar_one()
        return list(p_row.holdings)


def _engine(prices=None) -> SimEngine:
    return SimEngine(provider=_Pinned(prices or {"AAPL": 100.0}))


def _ready(prices=None):
    sim = _engine(prices)
    user_id = uuid4()
    sim.ensure_portfolio(user_id)
    return sim, user_id


# ── The penny: OCC exercise by exception ─────────────────────────────────────


@pytest.mark.parametrize(
    "strike,settlement_price,expected",
    [
        (100.0, 100.01, "exercised"),   # exactly at the threshold
        (100.0, 100.00, "expired"),     # at the money — abandoned
        (100.0, 99.00, "expired"),      # out of the money
        (100.0, 100.009, "expired"),    # ITM by less than a cent, and it ROUNDS
                                        # to a cent — the case that separates a
                                        # raw comparison from `round(x, 2)`
        # $2.01 minus $2.00 is 0.009999999999999787 in IEEE-754, BELOW the 0.01
        # literal. A contract a penny in the money must not be abandoned
        # because of how the subtraction lands in binary — this is the case the
        # epsilon on the comparison exists for, and the only one that can tell
        # `>= t - eps` apart from `>= t` or `> t`.
        (2.0, 2.01, "exercised"),
        (2.0, 2.00, "expired"),
    ],
)
def test_boundary_exercise_by_exception_is_measured_on_the_raw_distance(
    strike, settlement_price, expected,
):
    sim, user_id = _ready()
    leg_id, _ = _add_leg(user_id, right="call", strike=strike, quantity=1)
    _set_cash(user_id, 50_000.0)

    events = sim.run_option_lifecycle(
        user_id,
        mandate=_mandate(),
        on_date=EXPIRY,
        settlement_prices={"AAPL": settlement_price},
    )

    assert [e.action for e in events] == [expected]
    assert _leg(leg_id).state == "closed"


def test_boundary_a_short_call_one_cent_itm_is_assigned_not_expired():
    """The same comparison, from the other side of the contract. One rule, two
    names — a threshold that only worked for longs would silently gift every
    short seller their premium."""
    sim, user_id = _ready()
    _add_shares(user_id, "AAPL", 100, 90.0)
    leg_id, _ = _add_leg(
        user_id, right="call", strike=100.0, quantity=-1, strategy_name="covered_call",
    )

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 100.01},
    )

    assert [e.action for e in events] == ["assigned"]
    assert _leg(leg_id).close_reason == "assigned"


# ── Lifecycle transitions ────────────────────────────────────────────────────


def test_expired_worthless_closes_the_leg_and_realises_the_premium_paid():
    sim, user_id = _ready()
    leg_id, _ = _add_leg(user_id, right="call", strike=120.0, quantity=2, premium=3.0)
    _set_cash(user_id, 10_000.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 100.0},
    )

    row = _leg(leg_id)
    assert row.state == "closed"
    assert row.close_reason == "expired"
    assert float(row.realised_pnl) == -600.0      # 2 contracts x 100 x $3
    assert float(row.close_price) == 0.0
    assert events[0].cash_delta == 0.0
    assert _portfolio_row(user_id).current_cash == 10_000.0
    assert "expired worthless" in events[0].message


def test_long_call_exercise_takes_delivery_at_the_strike_and_folds_in_the_premium():
    sim, user_id = _ready()
    _add_leg(user_id, right="call", strike=100.0, quantity=1, premium=4.0)
    _set_cash(user_id, 20_000.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 130.0},
    )

    assert events[0].settlement == "shares"
    assert events[0].shares_delta == 100.0
    assert float(_portfolio_row(user_id).current_cash) == 10_000.0   # 20k − 100×$100
    holding = _holdings(user_id)[0]
    assert float(holding.quantity) == 100.0
    # Basis is strike + premium: the $4 left cash at open, so charging it again
    # here would be a second bill for the same money.
    assert float(holding.avg_cost) == pytest.approx(104.0)


def test_long_call_without_the_cash_is_sold_out_at_parity_and_says_so():
    """A broker files a do-not-exercise and sells to close. Same economics,
    and the user is told which one happened."""
    sim, user_id = _ready()
    _add_leg(user_id, right="call", strike=100.0, quantity=1, premium=4.0)
    _set_cash(user_id, 500.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 130.0},
    )

    assert events[0].settlement == "cash"
    assert events[0].downgrade is not None
    assert events[0].cash_delta == 3_000.0            # $30 intrinsic x 100
    assert events[0].realised_pnl == 2_600.0          # less the $4 premium
    assert _holdings(user_id) == []


def test_long_put_exercise_delivers_the_shares_out_and_realises_the_premium():
    sim, user_id = _ready()
    _add_shares(user_id, "AAPL", 100, 95.0)
    _add_leg(
        user_id, right="put", strike=100.0, quantity=1, premium=2.0,
        strategy_name="protective_put",
    )
    _set_cash(user_id, 1_000.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 80.0},
    )

    assert events[0].shares_delta == -100.0
    assert float(_portfolio_row(user_id).current_cash) == 11_000.0   # 1k + 100×$100
    assert _holdings(user_id) == []
    # The premium is realised on the LEG because the equity lot books only
    # (strike − avg_cost); neither side owns it twice.
    assert events[0].realised_pnl == -200.0


def test_cash_secured_put_assignment_is_never_refused_for_insufficient_cash():
    """CR171 §7's rule, inherited: the collateral was posted at open precisely
    so this moment cannot fail. A user at zero cash still takes delivery."""
    sim, user_id = _ready()
    leg_id, _ = _add_leg(
        user_id, right="put", strike=100.0, quantity=-1, premium=3.0,
        collateral=10_000.0, strategy_name="cash_secured_put",
    )
    _set_cash(user_id, 0.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 90.0},
    )

    assert events[0].action == "assigned"
    assert events[0].settlement == "shares"
    assert events[0].shares_delta == 100.0
    assert float(_portfolio_row(user_id).current_cash) == 0.0   # 10k released, 10k paid
    holding = _holdings(user_id)[0]
    assert float(holding.avg_cost) == pytest.approx(97.0)       # strike − premium
    assert _leg(leg_id).close_reason == "assigned"


def test_covered_call_assignment_delivers_the_shares_and_keeps_the_premium():
    sim, user_id = _ready()
    _add_shares(user_id, "AAPL", 100, 90.0)
    _add_leg(
        user_id, right="call", strike=100.0, quantity=-1, premium=2.5,
        strategy_name="covered_call",
    )
    _set_cash(user_id, 0.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 115.0},
    )

    assert events[0].shares_delta == -100.0
    assert float(_portfolio_row(user_id).current_cash) == 10_000.0
    assert _holdings(user_id) == []
    assert events[0].realised_pnl == 250.0


def test_a_vertical_settles_the_long_leg_first_so_both_settle_in_shares():
    """Order is not cosmetic: the assignment needs the stock the exercise
    delivers. Settle the short leg first and the spread degrades to two cash
    settlements — the same total by a different route, and a user who never
    sees the shares move."""
    sim, user_id = _ready()
    strategy_id = uuid4()
    _add_leg(
        user_id, right="call", strike=100.0, quantity=1, premium=6.0,
        strategy_id=strategy_id, strategy_name="bull_call_spread",
    )
    _add_leg(
        user_id, right="call", strike=110.0, quantity=-1, premium=2.0,
        strategy_id=strategy_id, strategy_name="bull_call_spread",
    )
    _set_cash(user_id, 20_000.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 130.0},
    )

    assert [e.action for e in events] == ["exercised", "assigned"]
    assert [e.settlement for e in events] == ["shares", "shares"]
    assert _holdings(user_id) == []
    # 20k − 100×$100 (exercise) + 100×$110 (assignment) = 21,000
    assert float(_portfolio_row(user_id).current_cash) == 21_000.0


def test_the_structure_row_closes_when_its_last_leg_does():
    sim, user_id = _ready()
    _, strategy_id = _add_leg(
        user_id, right="call", strike=120.0, quantity=1, premium=1.0,
        with_structure=True,
    )

    sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 100.0},
    )

    with get_session() as s:
        row = s.execute(
            select(SimOptionTradeRow).where(
                SimOptionTradeRow.strategy_id == strategy_id
            )
        ).scalar_one()
        assert row.status == "closed"
        assert row.closed_at is not None
        assert float(row.realised_pnl) == -100.0


# ── Pin risk, and the prices we refuse to settle against ─────────────────────


def test_pin_risk_is_flagged_and_the_rule_still_decides():
    sim, user_id = _ready()
    _add_leg(user_id, right="call", strike=100.0, quantity=1, premium=1.0)
    _set_cash(user_id, 20_000.0)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=EXPIRY,
        settlement_prices={"AAPL": 100.02},
    )

    assert events[0].pin_risk is True
    assert events[0].action == "exercised"


def test_a_leg_with_no_usable_settlement_price_stays_open_and_is_reported():
    """`current_quote` never returns None — it returns a $0.01 sentinel. Settle
    against that and every put a user owns exercises at once."""
    sim = SimEngine(provider=_Pinned({"AAPL": 0.0}))
    user_id = uuid4()
    sim.ensure_portfolio(user_id)
    leg_id, _ = _add_leg(user_id, right="put", strike=100.0, quantity=1)

    events = sim.run_option_lifecycle(user_id, mandate=_mandate(), on_date=EXPIRY)

    assert [e.action for e in events] == ["not_evaluated"]
    assert "no usable settlement price" in events[0].message
    assert _leg(leg_id).state == "open"


# ── Early assignment (D9) ────────────────────────────────────────────────────


def test_early_assignment_takes_the_short_call_before_the_ex_dividend_date():
    sim, user_id = _ready()
    _add_shares(user_id, "AAPL", 100, 90.0)
    leg_id, _ = _add_leg(
        user_id, right="call", strike=100.0, quantity=-1, premium=2.0,
        strategy_name="covered_call",
    )
    _set_cash(user_id, 0.0)

    events = sim.run_option_lifecycle(
        user_id,
        mandate=_mandate(),
        on_date=BEFORE_EXPIRY,
        settlement_prices={"AAPL": 120.0},
        option_marks={_leg(leg_id).occ_symbol: 20.10},   # $0.10 extrinsic
        dividends={"AAPL": DividendEvent(
            ex_date=datetime.date(2026, 1, 12), amount_per_share=0.25,
        )},
    )

    assert [e.action for e in events] == ["early_assigned"]
    assert _leg(leg_id).close_reason == "assigned"
    assert _holdings(user_id) == []


def test_early_assignment_does_not_fire_when_the_extrinsic_beats_the_dividend():
    sim, user_id = _ready()
    _add_shares(user_id, "AAPL", 100, 90.0)
    leg_id, _ = _add_leg(
        user_id, right="call", strike=100.0, quantity=-1, premium=2.0,
        strategy_name="covered_call",
    )

    events = sim.run_option_lifecycle(
        user_id,
        mandate=_mandate(),
        on_date=BEFORE_EXPIRY,
        settlement_prices={"AAPL": 120.0},
        option_marks={_leg(leg_id).occ_symbol: 21.50},   # $1.50 extrinsic
        dividends={"AAPL": DividendEvent(
            ex_date=datetime.date(2026, 1, 12), amount_per_share=0.25,
        )},
    )

    assert events == []
    assert _leg(leg_id).state == "open"


def test_without_a_dividend_calendar_the_short_call_is_reported_unevaluated():
    """Not "safe" — unevaluated. A pass that means "we did not look" is the
    DEF169 shape, and this is the one leg where it matters most."""
    sim, user_id = _ready()
    _add_shares(user_id, "AAPL", 100, 90.0)
    _add_leg(
        user_id, right="call", strike=100.0, quantity=-1,
        strategy_name="covered_call",
    )

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(), on_date=BEFORE_EXPIRY,
        settlement_prices={"AAPL": 120.0},
    )

    assert [e.action for e in events] == ["not_evaluated"]
    assert "dividend calendar" in events[0].message


# ── §8 floor re-entry: allow and flag ────────────────────────────────────────


def test_floor_reentry_flags_the_breach_the_exercise_created_without_blocking():
    sim, user_id = _ready({"AAPL": 130.0})
    _add_leg(user_id, right="call", strike=100.0, quantity=1, premium=4.0)
    _set_cash(user_id, 20_000.0)

    events = sim.run_option_lifecycle(
        user_id,
        mandate=_mandate(single_name_cap_pct=10.0),
        on_date=EXPIRY,
        settlement_prices={"AAPL": 130.0},
    )

    assert events[0].action == "exercised"
    assert float(_holdings(user_id)[0].quantity) == 100.0, (
        "the shares must still be there — the floor cannot un-exercise a "
        "contract the exchange already exercised"
    )
    assert events[0].compliance_flags, (
        "and it must not stay silent: a mandate breached by a mechanism the "
        "user was never told about is the worse half of this failure"
    )
    assert any("single-name cap" in flag for flag in events[0].compliance_flags)


def test_floor_reentry_is_recorded_as_unevaluated_when_no_mandate_is_supplied():
    sim, user_id = _ready({"AAPL": 130.0})
    _add_leg(user_id, right="call", strike=100.0, quantity=1, premium=4.0)
    _set_cash(user_id, 20_000.0)

    events = sim.run_option_lifecycle(
        user_id, on_date=EXPIRY, settlement_prices={"AAPL": 130.0},
    )

    assert events[0].compliance_flags == []
    assert events[0].compliance_not_evaluated != []


def test_an_expiring_leg_that_adds_no_shares_is_not_flagged():
    """The re-entry exists for positions settlement CREATED. A worthless
    expiry creates nothing, and flagging it would train the user to ignore the
    flag."""
    sim, user_id = _ready()
    _add_leg(user_id, right="call", strike=200.0, quantity=1)

    events = sim.run_option_lifecycle(
        user_id, mandate=_mandate(single_name_cap_pct=1.0), on_date=EXPIRY,
        settlement_prices={"AAPL": 100.0},
    )

    assert events[0].compliance_flags == []
    assert events[0].compliance_not_evaluated == []
