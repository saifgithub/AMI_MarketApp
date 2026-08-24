"""CR206 — the dividend feed D9's early-assignment rule needs.

The rule (`option_lifecycle.early_assignment_due`) was written, correct, and
had **never run**. Its only production caller passed neither `dividends` nor
`option_marks`, so every open short call was reported `not_evaluated` every
day — honest, and completely inert.

The guard worth naming: `test_the_amount_is_never_derived_from_the_annual_rate`.
`EarningsInfo.dividend_rate` was already on hand and is the *annual* figure;
`rate / 4` is right for the quarterly payers that dominate US large caps and
wrong for monthly REITs and semi-annual ADRs. The number decides whether a
real user's short call is assigned early and their shares called away, so an
assumed value is DEF059's shape pointed at a position that can be taken away.

The second one worth naming is the None/`[]` distinction, tested end to end:
`None` means the feed could not tell you and the leg must keep saying
`not_evaluated`; `[]` means this company pays nothing, which is a measurement
and lets the rule conclude. Collapsing them turns an outage into a confident
"your short call is safe".
"""

from __future__ import annotations

import datetime
from datetime import date

import pytest

from app.services import sim_options
from app.services.market_data import (
    DIVIDEND_HISTORY_TTL_SECONDS,
    OPTION_CHAIN_TTL_SECONDS,
    CachingProvider,
    DividendPayment,
    FallbackProvider,
    MockWalkProvider,
)

_TODAY = date(2026, 8, 25)


class _Info:
    def __init__(self, ex): self.ex_dividend_date = ex


class _Provider:
    """Minimal stand-in for the provider protocol's two relevant methods."""

    name = "stub"

    def __init__(self, payments, ex_date, *, raise_on_earnings=False):
        self._payments = payments
        self._ex = ex_date
        self._raise = raise_on_earnings
        self.calls = 0

    def dividend_history(self, underlying):
        self.calls += 1
        return self._payments

    def earnings(self, ticker):
        if self._raise:
            raise RuntimeError("feed down")
        return _Info(self._ex)


def _pay(d: str, amt: float) -> DividendPayment:
    return DividendPayment(ex_date=date.fromisoformat(d), amount_per_share=amt, source="stub")


@pytest.fixture
def use(monkeypatch):
    def _use(provider):
        import app.services.market_data as md
        monkeypatch.setattr(md, "get_market_data_provider", lambda: provider)
    return _use


# ── The measured-amount rule ─────────────────────────────────────────────


def test_the_amount_is_the_most_recent_actual_payment(use):
    use(_Provider([_pay("2026-02-06", 0.24), _pay("2026-05-08", 0.25),
                   _pay("2026-08-07", 0.26)], "2026-11-06"))
    feed = sim_options.next_dividend_for(["AAPL"], today=_TODAY)
    assert feed.events["AAPL"].amount_per_share == 0.26
    assert feed.events["AAPL"].ex_date == date(2026, 11, 6)


def test_the_amount_is_never_derived_from_the_annual_rate(use):
    """A MONTHLY payer. An annual rate of 12 x 0.10 = 1.20 divided by four
    gives 0.30 — three times the real payment, and on a rule that decides
    whether a position is taken away. The measured last payment is 0.10."""
    payments = [_pay(f"2026-0{m}-15", 0.10) for m in range(1, 9)]
    use(_Provider(payments, "2026-09-15"))
    feed = sim_options.next_dividend_for(["O"], today=_TODAY)
    assert feed.events["O"].amount_per_share == 0.10
    assert feed.events["O"].amount_per_share != pytest.approx(1.20 / 4)


def test_a_semi_annual_payer_is_not_quartered_either(use):
    use(_Provider([_pay("2026-03-02", 1.40), _pay("2026-08-03", 1.45)], "2027-03-02"))
    feed = sim_options.next_dividend_for(["ADR"], today=_TODAY)
    assert feed.events["ADR"].amount_per_share == 1.45


def test_the_latest_payment_wins_regardless_of_series_order(use):
    use(_Provider([_pay("2026-08-07", 0.26), _pay("2026-02-06", 0.24)], "2026-11-06"))
    assert sim_options.next_dividend_for(["X"], today=_TODAY).events["X"].amount_per_share == 0.26


# ── Measured absence vs. unknown — the DEF059 fence ───────────────────────


def test_a_non_dividend_payer_resolves_to_no_event_not_a_zero(use):
    """`[]` is a measurement: this company pays nothing, so no trigger
    exists. It must NOT appear in `events` with amount 0 — `early_assignment
    _due` would then be deciding off a fabricated dividend."""
    use(_Provider([], "2026-11-06"))
    feed = sim_options.next_dividend_for(["GOOG"], today=_TODAY)
    assert "GOOG" not in feed.events
    assert "GOOG" not in feed.unresolved


def test_a_suspended_dividend_resolves_to_no_event(use):
    """Payments exist historically but no upcoming ex-date is published."""
    use(_Provider([_pay("2025-03-01", 0.5)], None))
    feed = sim_options.next_dividend_for(["SUSP"], today=_TODAY)
    assert "SUSP" not in feed.events
    assert "SUSP" not in feed.unresolved


def test_a_past_ex_date_does_not_trigger_a_future_assignment(use):
    """yfinance's `exDividendDate` is often the LAST one. Assigning against a
    dividend already paid would call shares away for a payment nobody is
    about to capture."""
    use(_Provider([_pay("2026-08-07", 0.26)], "2026-08-07"))
    assert "PAST" not in sim_options.next_dividend_for(["PAST"], today=_TODAY).events


def test_a_feed_that_cannot_answer_is_unresolved_not_absent(use):
    """THE distinction. None means the feed could not tell you, and the leg
    must keep reporting `not_evaluated` rather than being called safe."""
    use(_Provider(None, "2026-11-06"))
    feed = sim_options.next_dividend_for(["DOWN"], today=_TODAY)
    assert "DOWN" not in feed.events
    assert feed.unresolved == ("DOWN",)


def test_an_earnings_failure_does_not_invent_an_ex_date(use):
    use(_Provider([_pay("2026-08-07", 0.26)], "2026-11-06", raise_on_earnings=True))
    assert "ERR" not in sim_options.next_dividend_for(["ERR"], today=_TODAY).events


def test_underlyings_are_deduped_and_uppercased(use):
    prov = _Provider([_pay("2026-08-07", 0.26)], "2026-11-06")
    use(prov)
    feed = sim_options.next_dividend_for(["aapl", "AAPL", " aapl "], today=_TODAY)
    assert list(feed.events) == ["AAPL"]
    assert prov.calls == 1


# ── The provider chain ───────────────────────────────────────────────────


def test_the_mock_provider_returns_none_never_an_empty_list():
    """The mock invents prices. Inventing a dividend would let D9 decide a
    real assignment off a fabricated number; returning [] would assert a
    measurement it never made."""
    assert MockWalkProvider().dividend_history("AAPL") is None


def test_fallback_falls_through_on_none_but_not_on_empty():
    """`[]` is a real answer. Falling through it would let a secondary that
    knows nothing overwrite a primary that knows something."""
    empty = _Provider([], None)
    rich = _Provider([_pay("2026-08-07", 0.26)], None)
    assert FallbackProvider(empty, rich).dividend_history("X") == []

    down = _Provider(None, None)
    assert FallbackProvider(down, rich).dividend_history("X") == rich._payments


def test_the_cache_stores_an_empty_measurement_but_never_a_failure():
    """Caching a failure for six hours turns one bad request into six hours
    of `not_evaluated` on every short call."""
    empty = _Provider([], None)
    c = CachingProvider(empty)
    assert c.dividend_history("X") == []
    assert c.dividend_history("X") == []
    assert empty.calls == 1, "a measured empty is cacheable"

    down = _Provider(None, None)
    c2 = CachingProvider(down)
    assert c2.dividend_history("Y") is None
    assert c2.dividend_history("Y") is None
    assert down.calls == 2, "a failure must be retried, never cached"


def test_the_dividend_ttl_is_much_longer_than_the_chain_ttl():
    """Different clocks: a chain reprices per tick, a dividend is declared
    once a quarter with its ex-date known weeks ahead."""
    assert DIVIDEND_HISTORY_TTL_SECONDS > OPTION_CHAIN_TTL_SECONDS * 10
