"""CR172 acceptance criterion 1 — the user who never asked for options.

> *A user with `derivatives_allowed=False` — the default — sees no behaviour
> change anywhere, and `total_value`, drawdown, TWR and both NAV series return
> byte-identical numbers. **Proven by test, not asserted.***

Every other CR172 test asks what happens once the gate is open. This file is
the only one that asks what happens to the ~100% of users for whom it never
opens, and it is the criterion the CR states in the strongest terms because it
is the one whose failure would be invisible: an options subsystem that shifts a
non-options book by a cent moves `total_value`, and `total_value` is read by
`total_drawdown_pct`, by `portfolio_nav_daily` (the equity curve), by
`portfolio_value_snapshots` (CR136's series), by the TWR chain those two feed,
and by every risk limit measured as a percentage of the book. Nobody would see
it as an options bug. They would see a portfolio that quietly disagrees with
its own arithmetic.

**The oracle is the point.** `_pre_cr172_total_value` below is not a second
implementation of today's rule — that would be exactly the two-renderers shape
DEF098 forbids, and it would drift into agreement with whatever today's code
does. It is the body of `Portfolio.total_value` copied verbatim from
`git show 4c072f09^:backend/app/schemas/trade.py`, the commit immediately
before CR172 slice 3 added the option term. It is frozen historical code, and
a differential against frozen code is the only thing that can honestly answer
"byte-identical to before". If a future change makes the oracle wrong, the
correct response is a CR that says so — never an edit that re-syncs it.

**The criterion's other half lives next door.** "No behaviour change anywhere"
also covers what the twelve agents are told, and that is
`test_cr172_room_structure.py::test_a_mandate_without_derivatives_never_reads_the_option_board`
— which asserts the option board is never READ, not merely never rendered, so
the PM prompt stays byte-identical to pre-CR172 rather than merely equivalent.
This file owns the numbers; that one owns the prompt.

**Byte-identical, not approximately equal.** `_identical` compares `repr`,
not `==`: CPython's float repr is the shortest string that round-trips, so two
floats share a repr exactly when they share every bit. `==` is wrong in both
directions for this question — it calls `0.0` and `-0.0` the same number when
they are different bit patterns, and it calls a NaN different from itself.
`pytest.approx` would be wronger still; "within a tolerance" is the claim this
criterion exists to refuse.
"""

from __future__ import annotations

import datetime
from uuid import UUID, uuid4

import pytest

from app.db import get_session
from app.db.models import (
    PortfolioValueSnapshotRow,
    SimOptionLegRow,
    SimOptionTradeRow,
)
from app.schemas.trade import Holding, OrderType, Portfolio, ShortLeg, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote, set_market_data_provider
from app.services.portfolio_nav_daily import (
    nav_history,
    run_portfolio_nav_snapshot_tick,
    twr_pct_for_window,
)
from app.services.portfolio_snapshot import run_portfolio_snapshot_tick
from app.services.sim_engine import get_sim_engine
from app.trading_math.option_strategy import StrategyLeg
from app.trading_math.portfolio import drawdown_pct as _drawdown_pct
from app.trading_math.portfolio import total_value as _total_value
from app.trading_math.shorts import short_legs_value as _short_legs_value

_DAY_1 = datetime.date(2026, 8, 3)
_DAY_2 = datetime.date(2026, 8, 4)
_EXPIRY = datetime.date(2027, 3, 19)

# A fixed board, so a mark is a constant rather than a walk. `MockWalkProvider`
# (the conftest default) advances one step per elapsed WHOLE SECOND, so two
# reads either side of a second boundary return different prices — which would
# turn "the NAV row equals the oracle" into a coin flip on test duration rather
# than a statement about options.
_PRICES = {"AAPL": 190.0, "MSFT": 410.25, "NVDA": 103.33}


class _FixedProvider:
    """Constant quotes, live-sourced. `source="yfinance"` matters: CR136 M03's
    tick REFUSES to snapshot a book priced off `mock_walk`, so a mock-sourced
    provider would make the second NAV series test pass by writing nothing."""

    name = "fixed_test"

    def quote(self, ticker: str):
        price = _PRICES.get(ticker.upper().strip())
        if price is None:
            return None
        return Quote(price=price, source="yfinance", change_pct=0.0)

    def get_price(self, ticker: str):
        q = self.quote(ticker)
        return q.price if q is not None else None

    def earnings(self, ticker: str):
        return None


@pytest.fixture(autouse=True)
def _fixed_prices():
    set_market_data_provider(_FixedProvider())
    yield
    set_market_data_provider(None)


# ── the oracle: frozen pre-CR172 code, never re-derived ─────────────────────


def _pre_cr172_total_value(p: Portfolio, marks: dict[str, float] | None = None) -> float:
    """`Portfolio.total_value`, verbatim from `4c072f09^` — do not update."""
    marks = marks or {}
    long_side = _total_value(
        p.current_cash,
        ((h.quantity, marks.get(h.ticker, h.avg_cost)) for h in p.holdings),
    )
    return long_side + _short_legs_value(
        (s.cash_posted, s.quantity, s.entry_price, marks.get(s.ticker, s.entry_price))
        for s in p.shorts
    )


def _pre_cr172_drawdown_pct(
    p: Portfolio, marks: dict[str, float] | None = None,
) -> float:
    """`Portfolio.total_drawdown_pct`, verbatim from `4c072f09^`."""
    return _drawdown_pct(p.starting_capital, _pre_cr172_total_value(p, marks))


def _identical(actual: float, expected: float) -> bool:
    return repr(actual) == repr(expected)


def _diff(label: str, actual: float, expected: float) -> str:
    return (
        f"{label} moved for a user who has no options: "
        f"got {actual!r}, pre-CR172 arithmetic gives {expected!r}"
    )


# ── the books ───────────────────────────────────────────────────────────────


def _holding(ticker: str, quantity: float, avg_cost: float) -> Holding:
    return Holding(
        ticker=ticker, quantity=quantity, avg_cost=avg_cost,
        opened_at=datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
    )


def _short(ticker: str, quantity: float, entry: float, posted: float) -> ShortLeg:
    return ShortLeg(
        id=uuid4(), ticker=ticker, quantity=quantity, entry_price=entry,
        cash_posted=posted,
        opened_at=datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
    )


def _book(**over) -> Portfolio:
    body = {
        "id": uuid4(), "user_id": uuid4(), "name": "Main",
        "starting_capital": 10_000.0, "current_cash": 10_000.0,
        "holdings": [], "shorts": [], "options": [],
        "created_at": datetime.datetime(2026, 8, 1, tzinfo=datetime.UTC),
    }
    body.update(over)
    return Portfolio(**body)


# Deliberately awkward arithmetic in places: a cash figure that is not
# representable in binary, a fractional share count, a price whose product
# needs more than two decimals. A term that is "0.0" in the wrong way — an
# added `-0.0`, a sum that promotes to a different accumulation order — shows
# up here and nowhere in a book made of round hundreds.
_BOOKS = {
    "all cash": _book(),
    "cash with an unrepresentable fraction": _book(current_cash=10_000.1),
    "one holding": _book(
        current_cash=5_000.0, holdings=[_holding("AAPL", 26.0, 190.0)],
    ),
    "fractional shares at an awkward price": _book(
        current_cash=1_234.56,
        holdings=[_holding("AAPL", 3.7, 190.03), _holding("NVDA", 0.1, 103.33)],
    ),
    "a training short": _book(
        current_cash=8_000.0,
        holdings=[_holding("AAPL", 10.0, 190.0)],
        shorts=[_short("MSFT", 4.0, 410.25, 2_461.5)],
    ),
    "a book underwater": _book(
        current_cash=100.0, holdings=[_holding("NVDA", 50.0, 200.0)],
    ),
}

_MARK_SETS = {
    "no marks at all": {},
    "every ticker marked": dict(_PRICES),
    "a mark for a ticker the book does not hold": {"TSLA": 250.0},
}


@pytest.mark.parametrize("book_name", sorted(_BOOKS))
@pytest.mark.parametrize("marks_name", sorted(_MARK_SETS))
def test_the_total_is_bit_for_bit_the_pre_cr172_figure(book_name, marks_name):
    book = _BOOKS[book_name]
    marks = _MARK_SETS[marks_name]

    actual = book.total_value(marks)
    expected = _pre_cr172_total_value(book, marks)

    assert _identical(actual, expected), _diff("total_value", actual, expected)


@pytest.mark.parametrize("book_name", sorted(_BOOKS))
@pytest.mark.parametrize("marks_name", sorted(_MARK_SETS))
def test_the_drawdown_is_bit_for_bit_the_pre_cr172_figure(book_name, marks_name):
    book = _BOOKS[book_name]
    marks = _MARK_SETS[marks_name]

    actual = book.total_drawdown_pct(marks)
    expected = _pre_cr172_drawdown_pct(book, marks)

    assert _identical(actual, expected), _diff("drawdown_pct", actual, expected)


def test_option_marks_cannot_move_a_book_that_has_no_legs():
    """The second parameter CR172 added to both signatures.

    A caller that starts passing `option_marks` — the §11 tail will — must not
    be able to move a book with nothing to mark, however rich the dict is.
    """
    book = _BOOKS["a training short"]
    marks = dict(_PRICES)
    noisy = {
        "AAPL270319C00190000": 12.5,
        "MSFT270319P00400000": 8.25,
        "": 999_999.0,
    }

    assert _identical(
        book.total_value(marks, noisy), _pre_cr172_total_value(book, marks),
    )
    assert _identical(
        book.total_drawdown_pct(marks, noisy), _pre_cr172_drawdown_pct(book, marks),
    )


# ── the gate, measured at the book rather than at the refusal ──────────────


def _mandate(*, derivatives_allowed: bool = False):
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "compliance": {
            "long_only": False, "halal": False,
            "derivatives_allowed": derivatives_allowed,
        },
    })


_LONG_CALL = (
    StrategyLeg(
        right="call", strike=190.0, quantity=1.0, premium=5.0,
        multiplier=100.0, expiry=_EXPIRY.isoformat(),
    ),
)


def _seeded_user(sim, *, shares: float = 26.0) -> UUID:
    user_id = uuid4()
    sim.ensure_portfolio(user_id)
    if shares:
        result = sim.submit(
            user_id=user_id,
            ticker="AAPL", side=Side.BUY, quantity=shares,
            order_type=OrderType.MARKET, mandate=_mandate(),
        )
        assert result.accepted, result.compliance.violations
    return user_id


def test_a_refused_open_leaves_the_book_and_every_figure_where_it_found_them():
    """The end-to-end shape of criterion 1: the user tries, is refused, and
    nothing about their portfolio is different afterwards.

    Asserted on the BOOK, not on the refusal. `test_cr172_option_floor.py`
    already proves `check_option_open` says no; the question here is whether
    saying no is enough — whether a leg row, a trade row, a cash movement or a
    changed valuation survives the refusal. A floor that refuses correctly and
    half-writes is the failure this criterion is worded to catch.
    """
    sim = get_sim_engine()
    user_id = _seeded_user(sim)

    before, marks_before, value_before, drawdown_before, _src = (
        sim.portfolio_marks_snapshot(user_id)
    )

    result = sim.open_option_structure(
        user_id, underlying="AAPL", strategy_name="long_call",
        legs=_LONG_CALL, expiry=_EXPIRY, mandate=_mandate(),
    )
    assert result.accepted is False

    after, marks_after, value_after, drawdown_after, _src2 = (
        sim.portfolio_marks_snapshot(user_id)
    )

    assert after.options == [], "a refused open put a leg on the book"
    assert marks_after == marks_before
    assert _identical(after.current_cash, before.current_cash), _diff(
        "current_cash", after.current_cash, before.current_cash,
    )
    assert _identical(value_after, value_before), _diff(
        "total_value", value_after, value_before,
    )
    assert _identical(drawdown_after, drawdown_before), _diff(
        "drawdown_pct", drawdown_after, drawdown_before,
    )
    assert _identical(value_after, _pre_cr172_total_value(after, marks_after)), _diff(
        "total_value", value_after, _pre_cr172_total_value(after, marks_after),
    )

    with get_session() as s:
        assert s.query(SimOptionLegRow).count() == 0
        assert s.query(SimOptionTradeRow).count() == 0


def test_the_snapshot_a_non_derivatives_user_reads_is_the_pre_cr172_one():
    """`portfolio_marks_snapshot` is the single fan-out both NAV series, the
    Room's pre-trade check and `valuation_snapshot` all read. Pinning it here
    is what makes the two series tests below about the SERIES rather than about
    the arithmetic a third time."""
    sim = get_sim_engine()
    user_id = _seeded_user(sim)

    p, marks, total_value, drawdown_pct, _source = sim.portfolio_marks_snapshot(user_id)

    assert p.options == []
    assert _identical(total_value, _pre_cr172_total_value(p, marks)), _diff(
        "total_value", total_value, _pre_cr172_total_value(p, marks),
    )
    assert _identical(drawdown_pct, _pre_cr172_drawdown_pct(p, marks)), _diff(
        "drawdown_pct", drawdown_pct, _pre_cr172_drawdown_pct(p, marks),
    )


# ── NAV series 1 of 2 — `portfolio_nav_daily`, the equity curve ────────────


def test_the_equity_curve_row_is_the_pre_cr172_figure():
    sim = get_sim_engine()
    user_id = _seeded_user(sim)

    run_portfolio_nav_snapshot_tick(trading_day=lambda: _DAY_1)

    p, marks, _tv, _dd, _src = sim.portfolio_marks_snapshot(user_id)
    rows = nav_history(user_id)
    assert len(rows) == 1
    assert _identical(
        float(rows[0].nav), round(_pre_cr172_total_value(p, marks), 2),
    ), _diff("portfolio_nav_daily.nav", float(rows[0].nav),
             round(_pre_cr172_total_value(p, marks), 2))


def test_a_refused_open_between_two_ticks_does_not_bend_the_curve_or_the_twr():
    """TWR is chain-linked off the NAV series, so it inherits criterion 1 —
    but only if the refusal writes nothing that a later tick would read. Two
    trading days with an attempted option open in between is the smallest
    series that can show a bend."""
    sim = get_sim_engine()
    user_id = _seeded_user(sim)

    run_portfolio_nav_snapshot_tick(trading_day=lambda: _DAY_1)
    day_1_nav = float(nav_history(user_id)[0].nav)

    refused = sim.open_option_structure(
        user_id, underlying="AAPL", strategy_name="long_call",
        legs=_LONG_CALL, expiry=_EXPIRY, mandate=_mandate(),
    )
    assert refused.accepted is False

    run_portfolio_nav_snapshot_tick(trading_day=lambda: _DAY_2)

    rows = nav_history(user_id)
    assert [r.as_of_date for r in rows] == [_DAY_1, _DAY_2]
    assert _identical(float(rows[1].nav), day_1_nav), _diff(
        "the second day's NAV", float(rows[1].nav), day_1_nav,
    )
    # Nothing happened between the two days, so the chain must report exactly
    # nothing happened — not a rounding-sized return.
    assert _identical(twr_pct_for_window(rows), 0.0), (
        f"TWR reported {twr_pct_for_window(rows)!r} across two days in which "
        "the only event was an option open that was refused"
    )
    assert [r.capital_event for r in rows] == ["open", None]


# ── NAV series 2 of 2 — `portfolio_value_snapshots`, CR136's series ────────


def test_the_health_snapshot_row_is_the_pre_cr172_figure():
    sim = get_sim_engine()
    user_id = _seeded_user(sim)

    run_portfolio_snapshot_tick(
        trading_day=lambda: _DAY_1, vol_provider=lambda _uid: None,
    )

    p, marks, _tv, drawdown_pct, _src = sim.portfolio_marks_snapshot(user_id)
    with get_session() as s:
        rows = s.query(PortfolioValueSnapshotRow).filter(
            PortfolioValueSnapshotRow.user_id == user_id
        ).all()
        assert len(rows) == 1
        stored_total = float(rows[0].total_value)
        stored_invested = float(rows[0].invested_value)
        stored_drawdown = float(rows[0].drawdown_pct)

    expected_total = round(_pre_cr172_total_value(p, marks), 2)
    assert _identical(stored_total, expected_total), _diff(
        "portfolio_value_snapshots.total_value", stored_total, expected_total,
    )
    assert _identical(
        stored_invested, round(expected_total - float(p.current_cash), 2),
    ), _diff(
        "invested_value", stored_invested,
        round(expected_total - float(p.current_cash), 2),
    )
    assert _identical(stored_drawdown, _pre_cr172_drawdown_pct(p, marks)), _diff(
        "snapshot drawdown_pct", stored_drawdown, _pre_cr172_drawdown_pct(p, marks),
    )


# ── the game lane — §3's "provably untouched" ──────────────────────────────


def test_a_game_portfolio_never_carries_a_leg_even_if_the_table_holds_one():
    """CR172 §3 scopes the option book to the TRAINING lane in
    `_portfolio_from_row`, and §11 requires `games_scoring_pass` to be
    *provably* untouched by options. The cheap proof is that a game portfolio
    cannot surface a leg — so this writes one straight into `sim_option_legs`
    against a game portfolio's id, bypassing every check that would normally
    stop it, and asserts the portfolio still comes back empty.

    Reaching past the write path is deliberate. Asserting that the write path
    refuses is a different claim, and it is the weaker one: it would still pass
    if the read path folded a leg into a game NAV the moment any future code
    put one there.
    """
    sim = get_sim_engine()
    user_id = uuid4()
    run_id = uuid4()
    game = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)

    with get_session() as s:
        s.add(SimOptionLegRow(
            id=uuid4(), user_id=user_id, portfolio_id=game.id,
            occ_symbol="AAPL270319C00190000", underlying="AAPL",
            right="call", strike=190.0, expiry=_EXPIRY,
            quantity=1.0, avg_premium=5.0, multiplier=100.0,
            collateral_posted=0.0,
            strategy_id=uuid4(), strategy_name="long_call",
            state="open",
        ))

    reread = sim.ensure_portfolio(user_id, kind="game", run_id=run_id)
    assert reread.options == [], (
        "a game portfolio surfaced an option leg — §11's proof that "
        "games_scoring_pass is untouched by options rests on this being "
        "structurally impossible, not merely unwritten"
    )
    _p, marks, total_value, _dd, _src = sim.portfolio_marks_snapshot(
        user_id, kind="game", run_id=run_id,
    )
    assert _identical(total_value, _pre_cr172_total_value(reread, marks))


# ── the wire ───────────────────────────────────────────────────────────────


def test_the_payload_gains_exactly_one_key_and_it_is_empty():
    """What a shipped client sees. `0.1.0+100` is on TestFlight and Play
    against this backend, and its Dart models read keys by name — so an added
    key is inert and a CHANGED or REMOVED one is a broken screen. The set is
    pinned rather than described.
    """
    sim = get_sim_engine()
    user_id = _seeded_user(sim)
    payload = sim.ensure_portfolio(user_id).model_dump()

    pre_cr172_keys = {
        "id", "user_id", "name", "starting_capital", "current_cash",
        "holdings", "shorts", "created_at",
    }
    assert set(payload) == pre_cr172_keys | {"options"}
    assert payload["options"] == []
