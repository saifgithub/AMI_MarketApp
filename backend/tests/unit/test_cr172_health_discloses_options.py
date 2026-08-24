"""CR172 §11 — Portfolio Health must say what it did not look at.

An option has no per-ticker daily close series, so it cannot enter the EWMA
vol/beta/correlation machinery this report is built on, and its risk is delta
and gamma rather than σ. **Excluding it is correct. Excluding it silently is
not**: a risk report that omits a position without saying so reads as a risk
report that covered it, and the position it omits is the one most capable of
surprising its holder.

This is the same disclosure shape the report already uses for `contains_etfs`
("what AMI did not look through") and for `dropped_holdings`, and the same rule
CR136's own audit produced — a consumer needs the uncertainty, not just the
point estimate.

The case worth naming is `test_an_options_only_book_does_not_read_as_empty`.
A portfolio holding nothing but structures takes the `no_holdings` early
return, and *"you hold nothing"* told to someone holding something is not a
degraded answer, it is a wrong one.
"""

from __future__ import annotations

from app.services.portfolio_health import compute_health

AS_OF = "2026-08-24"


def _health(holdings, marks, *, options_excluded=0, cash=5_000.0):
    return compute_health(
        holdings=holdings,
        marks=marks,
        cash=cash,
        series={},
        sector_of=lambda t: "Technology",
        etf_tickers=frozenset(),
        as_of=AS_OF,
        options_excluded=options_excluded,
    )


def test_a_book_with_no_options_discloses_zero_not_nothing():
    """The field is always present, so a client never has to distinguish
    "no options" from "an older backend that did not say"."""
    r = _health([("AAPL", 10.0)], {"AAPL": 195.0})
    assert r["options_not_evaluated"] == 0


def test_open_option_legs_are_counted_in_the_disclosure():
    r = _health([("AAPL", 10.0)], {"AAPL": 195.0}, options_excluded=2)
    assert r["options_not_evaluated"] == 2


def test_an_options_only_book_does_not_read_as_empty():
    """THE case. No equity holdings, so the report takes its `no_holdings`
    early return — which without this field says "you hold nothing" to a user
    holding two option legs."""
    r = _health([], {}, options_excluded=2)
    assert r["status"] == "no_holdings"
    assert r["options_not_evaluated"] == 2


def test_a_genuinely_empty_book_still_says_zero():
    r = _health([], {})
    assert r["status"] == "no_holdings"
    assert r["options_not_evaluated"] == 0


def test_the_disclosure_is_never_a_silent_omission():
    """Restated as the property that matters: for any book with options, the
    report carries a non-zero count somewhere the client can read — whether it
    reached the full evaluation or the early return."""
    for holdings, marks in (([("AAPL", 10.0)], {"AAPL": 195.0}), ([], {})):
        r = _health(holdings, marks, options_excluded=3)
        assert r.get("options_not_evaluated") == 3, r.get("status")
