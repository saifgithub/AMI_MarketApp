"""CR172 §11 — marking an open option leg, and what happens when it cannot be.

The whole file turns on one distinction: **no mark is not a mark of zero, and
it is not a mark at cost either.** `Portfolio.total_value` holds an unmarked
leg at `avg_premium`, which is the right *value* — the total stays continuous
and no phantom loss appears — but it is emphatically not a *current* figure, and
the NAV row that records the day has to say so. `OptionMarks.unmarked` is what
carries that, and `_blend_option_source` is what turns it into the `stale` label
`portfolio_nav_daily` already understands.

**The mock case is structurally impossible, not merely guarded.**
`get_enriched_chain` refuses a chain whose spot came from `mock_walk` or
`unavailable` before any chain object is built, so an option mark derived from a
fabricated underlying cannot exist. That is why this feed's failure mode is
*unmarked* rather than *mocked* — and why `_blend_option_source` degrades to
`unavailable`/`stale` and leaves `mock` meaning what it has always meant.

The trap worth naming: strikes arrive as provider floats and ours round-trip
through `Numeric`, so `195.0 == 195.00000000000003` is false. A mark missed on a
float comparison is indistinguishable from a strike the chain does not list —
the position silently holds at cost with no reason given. `_strike_key` is the
fence.
"""

from __future__ import annotations

import datetime
from uuid import uuid4

import pytest

from app.schemas.trade import OptionLeg
from app.services.market_data import OptionChain, OptionQuote
from app.services.option_chain import EnrichedChain, EnrichedOptionQuote
from app.services.sim_options import OptionMarks, option_marks_for

EXPIRY = datetime.date(2026, 10, 7)
NOW = datetime.datetime(2026, 8, 24, tzinfo=datetime.timezone.utc)


def _leg(right="call", strike=195.0, qty=1.0, premium=9.1, expiry=EXPIRY,
         underlying="AAPL", occ=None) -> OptionLeg:
    return OptionLeg(
        id=uuid4(),
        occ_symbol=occ or f"{underlying}-{right}-{strike}-{expiry.isoformat()}",
        underlying=underlying, right=right, strike=strike, expiry=expiry,
        quantity=qty, avg_premium=premium, multiplier=100.0,
        collateral_posted=0.0, strategy_id=uuid4(), strategy_name="long_call",
        opened_at=NOW, days_to_expiry=44,
    )


def _eq(strike: float, mid: float | None, right: str) -> EnrichedOptionQuote:
    return EnrichedOptionQuote(
        quote=OptionQuote(
            strike=strike, bid=None, ask=None, last=None, volume=None,
            open_interest=None, implied_vol=None,
        ),
        right=right, mid=mid,
        state="tradeable" if mid else "unusable", state_reason="",
        iv_used=None, iv_source=None, greeks=None, greeks_reason=None,
    )


def _chain(calls=(), puts=(), *, spot_source="yfinance",
           underlying="AAPL", expiry=EXPIRY) -> EnrichedChain:
    return EnrichedChain(
        chain=OptionChain(
            underlying=underlying, expiry=expiry, calls=(), puts=(),
            source=spot_source,
        ),
        spot=195.42, spot_source=spot_source, rate=0.04, rate_source="fred",
        dividend_yield=0.0, t_years=0.12,
        calls=tuple(calls), puts=tuple(puts),
    )


@pytest.fixture()
def chains(monkeypatch):
    """Route `get_enriched_chain` to a dict keyed by (underlying, expiry).

    Patched on `option_chain` because `option_marks_for` imports it lazily from
    there — patching a name this module bound would leave the real fetch in
    place and quietly reach the network.
    """
    served: dict[tuple[str, datetime.date], EnrichedChain | None] = {}
    calls: list[tuple[str, datetime.date]] = []

    def fake(underlying, expiry):
        calls.append((underlying, expiry))
        return served.get((underlying, expiry))

    import app.services.option_chain as oc

    monkeypatch.setattr(oc, "get_enriched_chain", fake)
    return served, calls


# ── marking ─────────────────────────────────────────────────────────────────

def test_a_leg_is_marked_at_the_chains_mid(chains):
    served, _ = chains
    leg = _leg()
    served[("AAPL", EXPIRY)] = _chain(calls=[_eq(195.0, 11.40, "call")])
    result = option_marks_for([leg])
    assert result.marks == {leg.occ_symbol: 11.40}
    assert result.unmarked == ()
    assert result.source == "yfinance"


def test_one_chain_is_fetched_per_underlying_and_expiry(chains):
    """A four-leg book on one expiry must not fetch four chains."""
    served, calls = chains
    served[("AAPL", EXPIRY)] = _chain(
        calls=[_eq(195.0, 11.4, "call"), _eq(205.0, 4.2, "call")],
        puts=[_eq(185.0, 3.1, "put"), _eq(175.0, 1.2, "put")],
    )
    legs = [
        _leg(strike=195.0), _leg(strike=205.0, qty=-1.0),
        _leg(right="put", strike=185.0), _leg(right="put", strike=175.0, qty=-1.0),
    ]
    result = option_marks_for(legs)
    assert len(result.marks) == 4
    assert calls == [("AAPL", EXPIRY)]


def test_calls_and_puts_at_the_same_strike_do_not_collide(chains):
    """A straddle. Keying on strike alone would give both legs one price."""
    served, _ = chains
    served[("AAPL", EXPIRY)] = _chain(
        calls=[_eq(195.0, 11.40, "call")], puts=[_eq(195.0, 7.25, "put")],
    )
    call, put = _leg(right="call", strike=195.0), _leg(right="put", strike=195.0)
    result = option_marks_for([call, put])
    assert result.marks[call.occ_symbol] == 11.40
    assert result.marks[put.occ_symbol] == 7.25


def test_a_float_imprecise_strike_still_matches(chains):
    """THE trap. A missed float match is indistinguishable from a strike the
    chain does not list, and the position would silently hold at cost."""
    served, _ = chains
    served[("AAPL", EXPIRY)] = _chain(
        calls=[_eq(195.00000000000003, 11.40, "call")],
    )
    leg = _leg(strike=195.0)
    result = option_marks_for([leg])
    assert result.marks == {leg.occ_symbol: 11.40}, result.unmarked


# ── refusing to mark ────────────────────────────────────────────────────────

def test_a_strike_with_no_two_sided_quote_is_unmarked_not_zero(chains):
    """`mid` is None on a strike nobody is quoting. A zero there would report
    the position as a total loss; the last trade or the intrinsic would report
    a price no market would transact at."""
    served, _ = chains
    served[("AAPL", EXPIRY)] = _chain(calls=[_eq(195.0, None, "call")])
    leg = _leg()
    result = option_marks_for([leg])
    assert result.marks == {}
    assert result.unmarked == (leg.occ_symbol,)


def test_a_zero_mid_is_not_accepted_as_a_price(chains):
    served, _ = chains
    served[("AAPL", EXPIRY)] = _chain(calls=[_eq(195.0, 0.0, "call")])
    leg = _leg()
    assert option_marks_for([leg]).unmarked == (leg.occ_symbol,)


def test_no_chain_at_all_leaves_every_leg_on_it_unmarked(chains):
    """`get_enriched_chain` returns None for an outage, a mock provider, or a
    refused synthetic spot — it has already logged which."""
    served, _ = chains
    served[("AAPL", EXPIRY)] = None
    legs = [_leg(strike=195.0), _leg(strike=205.0)]
    result = option_marks_for(legs)
    assert result.marks == {}
    assert set(result.unmarked) == {l.occ_symbol for l in legs}
    assert result.source == "unavailable"


def test_a_strike_the_chain_does_not_list_is_unmarked(chains):
    served, _ = chains
    served[("AAPL", EXPIRY)] = _chain(calls=[_eq(200.0, 8.0, "call")])
    leg = _leg(strike=195.0)
    assert option_marks_for([leg]).unmarked == (leg.occ_symbol,)


def test_a_partly_marked_book_reports_unavailable_not_the_live_source(chains):
    """The silent average this field exists to prevent: half the book priced
    live, and the day recorded as fully priced."""
    served, _ = chains
    served[("AAPL", EXPIRY)] = _chain(
        calls=[_eq(195.0, 11.4, "call"), _eq(205.0, None, "call")],
    )
    good, bad = _leg(strike=195.0), _leg(strike=205.0, qty=-1.0)
    result = option_marks_for([good, bad])
    assert result.marks == {good.occ_symbol: 11.4}
    assert result.unmarked == (bad.occ_symbol,)
    assert result.source == "unavailable"


def test_one_dark_underlying_degrades_the_whole_set(chains):
    served, _ = chains
    served[("AAPL", EXPIRY)] = _chain(calls=[_eq(195.0, 11.4, "call")])
    served[("TSLA", EXPIRY)] = None
    result = option_marks_for([_leg(), _leg(underlying="TSLA", strike=300.0)])
    assert len(result.marks) == 1
    assert result.source == "unavailable"


def test_no_legs_reaches_no_network(chains):
    _served, calls = chains
    assert option_marks_for([]) == OptionMarks({}, "", ())
    assert calls == []


# ── the blend that feeds the NAV label ──────────────────────────────────────

def test_an_unmarked_option_degrades_a_live_equity_book():
    """A portfolio whose equities marked live and whose options did not is not
    a live-priced portfolio."""
    from app.services.sim_engine import _blend_option_source

    marks = OptionMarks(marks={}, source="", unmarked=("X",))
    assert _blend_option_source("yfinance", marks) == "unavailable"


def test_a_fully_marked_option_book_keeps_the_equity_source():
    from app.services.sim_engine import _blend_option_source

    marks = OptionMarks(marks={"X": 1.0}, source="yfinance", unmarked=())
    assert _blend_option_source("yfinance", marks) == "yfinance"


def test_an_options_only_book_takes_the_chains_source():
    """No equities, so no equity source to defer to."""
    from app.services.sim_engine import _blend_option_source

    marks = OptionMarks(marks={"X": 1.0}, source="yfinance", unmarked=())
    assert _blend_option_source("", marks) == "yfinance"


def test_the_degradation_is_never_mock():
    """`mock` means fabricated, and an option mark is never fabricated — it is
    missing. Collapsing the two would make `games_scoring_pass`'s void
    condition mean two different things."""
    from app.services.sim_engine import _blend_option_source

    marks = OptionMarks(marks={}, source="", unmarked=("X",))
    assert "mock" not in _blend_option_source("yfinance", marks)
