"""CR166 — the fields we already held, and the census that stops the next one hiding.

Three things are pinned here, in the order they have to hold:

  1. **The census is clean and OFFLINE.** A guard that needs the network fails
     for reasons nobody can reproduce and gets disabled; this one reads a
     checked-in manifest. It fails in both directions — a provider key we
     neither take nor exempt, and a computed field no roster can render.
  2. **The new fields survive the shapes that broke their neighbours.** A
     non-payer (payout 0.0 with no dividend), a half-populated identity (NBIS:
     `longName: null` with a live exchange), an unmapped venue code, and
     yfinance's percent-scaled `debtToEquity`.
  3. **The ablation still strips the whole consensus.** CR035's arm C removes
     the target; an arm that left the high/low/median standing would leak the
     figure it exists to remove.

`test_prompt_data_parity.py` already proves each new field reaches both
surfaces, and `test_cr145_lane_firewall.py` proves it reaches only its lane —
neither is repeated here.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services.fundamentals import (
    analyst_consensus_line,
    dividend_line,
    fetch_live_fundamentals,
    identity_line,
)
from app.services.room_prompts import _format_profile
from scripts.fact_sheet_census import (
    INTENTIONALLY_NOT_TAKEN,
    _consumed_provider_keys,
    run_census,
)


def _fake_yf(info: dict):
    class _Ticker:
        def __init__(self, _sym):
            self.info = dict(info)

    return types.SimpleNamespace(__version__="1.2.3", Ticker=_Ticker)


# ── 1. The census ────────────────────────────────────────────────────────────


def test_census_is_clean_offline():
    """The CI gate. Runs from the checked-in manifest — no network."""
    result = run_census(refresh=False)
    assert result["unreachable_provider_keys"] == [], (
        "provider keys are fetched and reach no agent. Render them, delete the "
        "fetch, or add an INTENTIONALLY_NOT_TAKEN entry with a reason: "
        f"{result['unreachable_provider_keys']}"
    )
    assert result["unreachable_computed_fields"] == [], (
        "fields computed onto Technicals/Quote/EarningsInfo that no roster can "
        f"render: {result['unreachable_computed_fields']}"
    )


def test_census_has_no_stale_exemptions():
    """An exemption for a field we now consume is a lie about the code, and it
    reads as a decision. It fails in its own right rather than sitting there."""
    result = run_census(refresh=False)
    assert result["stale_exemptions"] == [], (
        f"these are consumed now — remove them: {result['stale_exemptions']}"
    )


def test_every_exemption_carries_a_reason():
    blank = sorted(k for k, why in INTENTIONALLY_NOT_TAKEN.items() if not why.strip())
    assert not blank, f"exemptions with no reason are indistinguishable from oversights: {blank}"


def test_census_scans_market_data_too_not_just_the_fetcher():
    """Guard-on-the-guard. `_dividend_fields_from_info` in market_data.py reads
    two `.info` keys for CR030; a census that scanned only `fundamentals.py`
    reported both as discarded when they render on the dividend line. A false
    finding trains the reader to skim the list, which is how the census dies."""
    consumed = _consumed_provider_keys()
    assert {"exDividendDate", "dividendRate"} <= consumed


def test_census_goes_red_on_an_unexempted_key(monkeypatch):
    """Guard-on-the-guard: prove the clean result above can actually fail."""
    import scripts.fact_sheet_census as census

    monkeypatch.setattr(
        census, "_provider_keys", lambda refresh: (["phantomProviderKey"], "stub")
    )
    assert census.run_census()["unreachable_provider_keys"] == ["phantomProviderKey"]


# ── 2. The shapes that break neighbouring fields ─────────────────────────────


def test_identity_renders_ticker_alone_when_the_name_is_absent():
    """NBIS is the live fixture: it resolves with `exchange: NMS` and
    `longName: null` — a genuine half-populated identity, which is a better
    acceptance case than an unrecognised ticker because both halves are real."""
    assert identity_line(None, "NBIS", "NASDAQ") == "Instrument: NBIS — NASDAQ"
    assert identity_line("Apple Inc.", "AAPL", "NASDAQ") == "Instrument: Apple Inc. (AAPL) — NASDAQ"
    assert identity_line(None, "NBIS", None) == "Instrument: NBIS"


def test_an_unmapped_exchange_code_is_dropped_not_rendered_as_jargon(monkeypatch):
    """`exchange` returns a CODE. `Exchange: XKRX` is jargon to the model, so an
    unmapped venue is absent rather than guessed — the same "absent beats
    meaningless" rule DEF053 applies to numerics."""
    monkeypatch.setitem(
        sys.modules, "yfinance",
        _fake_yf({"currentPrice": 10.0, "trailingPE": 5.0,
                  "longName": "Somewhere Ltd", "exchange": "XKRX"}),
    )
    out = fetch_live_fundamentals("XXXX")
    assert "exchange_name" not in out
    assert out["long_name"] == "Somewhere Ltd"


def test_a_known_exchange_code_maps_to_a_name(monkeypatch):
    monkeypatch.setitem(
        sys.modules, "yfinance",
        _fake_yf({"currentPrice": 10.0, "trailingPE": 5.0, "exchange": "NYQ"}),
    )
    assert fetch_live_fundamentals("XXXX")["exchange_name"] == "NYSE"


def test_debt_to_equity_is_rescaled_from_yfinance_percent(monkeypatch):
    """yfinance reports `debtToEquity` as a PERCENT (AAPL: 78.445), not the
    ratio the name implies. Rendering the raw figure as "78x debt/equity" would
    describe a solvency crisis at a company with $84B of debt against $107B of
    equity."""
    monkeypatch.setitem(
        sys.modules, "yfinance",
        _fake_yf({"currentPrice": 10.0, "trailingPE": 5.0, "debtToEquity": 78.445}),
    )
    assert fetch_live_fundamentals("XXXX")["debt_to_equity"] == 0.78


def test_no_dividend_line_for_a_non_payer_with_a_zero_payout():
    """`payoutRatio` is 0.0 for a company that pays nothing, so gating the line
    on "any part present" rendered `Dividend: payout 0% of earnings` for NBIS
    and RIVN — a header over an absence (DEF053). The yield or the rate is what
    makes this a dividend; the payout ratio only qualifies one."""
    assert dividend_line(None, None, 0, None) is None
    assert dividend_line(0.35, None, 0, None) is not None


def test_a_past_ex_date_says_it_is_past():
    """yfinance's `exDividendDate` is the most recently DECLARED ex-date, which
    is routinely in the past. A bare date reads as upcoming, so the interval is
    computed here rather than left for the model to subtract (DEF124)."""
    from datetime import date

    line = dividend_line(0.35, 1.08, 12, "2026-08-10", today=date(2026, 8, 13))
    assert "ex-date 2026-08-10 (3 days ago)" in line


def test_margin_structure_survives_a_loss_maker():
    """RIVN renders operating -50% and a negative EPS. A loss-maker's figures
    are real and must not be dropped or coerced — the sheet states what the
    provider reports, with its provenance, and the agent reasons about it."""
    from app.services.fundamentals import earnings_power_line, margin_structure_line

    assert "operating -50%" in margin_structure_line(8, -50, -46)
    assert "EPS $-2.52" in earnings_power_line(-2.52, 5883, 4.68)


# ── 3. The ablation ──────────────────────────────────────────────────────────


def test_ablation_strips_the_dispersion_with_the_target(monkeypatch):
    """CR035 arm C. The dispersion rides the same flag as the mean because it is
    the same consensus: an arm that stripped the target but left $215–$400
    standing would leak the figure it exists to remove."""
    info = {
        "currentPrice": 10.0, "trailingPE": 5.0,
        "targetMeanPrice": 322.82, "recommendationKey": "buy",
        "numberOfAnalystOpinions": 41, "targetHighPrice": 400.0,
        "targetLowPrice": 215.0, "targetMedianPrice": 335.0,
        "recommendationMean": 2.13,
    }
    monkeypatch.setitem(sys.modules, "yfinance", _fake_yf(info))

    monkeypatch.setattr(settings, "suppress_analyst_consensus", False)
    full = fetch_live_fundamentals("XXXX")
    assert full["analyst_opinion_count"] == 41
    assert full["analyst_target_high"] == 400.0

    monkeypatch.setattr(settings, "suppress_analyst_consensus", True)
    ablated = fetch_live_fundamentals("XXXX")
    for key in (
        "analyst_target_price", "analyst_rating", "analyst_opinion_count",
        "analyst_target_high", "analyst_target_low", "analyst_target_median",
        "analyst_rating_score",
    ):
        assert key not in ablated, f"{key} survived the CR035 ablation"


def test_consensus_line_names_the_scale_the_score_is_on():
    """`recommendationKey` is a bucketing of `recommendationMean`: a 2.1 and a
    2.9 both render as "buy". The score is carried with its scale named rather
    than left to be inferred from a word."""
    line = analyst_consensus_line("buy", 322.82, 41, 400.0, 215.0, 335.0, 2.1)
    assert "mean score 2.1 on 1=strong buy … 5=sell" in line
    assert "41 analysts" in line
    assert "$215.00–$400.00 range" in line


def test_consensus_line_is_absent_when_the_street_said_nothing():
    assert analyst_consensus_line(None, None, None, None, None, None, None) is None


# ── Identity is deliberately ungated ─────────────────────────────────────────


@pytest.mark.parametrize("agent", list(AgentId))
def test_identity_reaches_every_agent(agent):
    """Identity is the SUBJECT of the run, not one desk's data. An agent that
    cannot name the company it is analysing is not firewalled, it is lost — so
    this line is exempt from the CR145 lane split, and that exemption is
    asserted for every agent rather than assumed for the four analysts."""
    profile = {
        "ticker": "AAPL", "long_name": "Apple Inc.", "exchange_name": "NASDAQ",
        "field_state": {"long_name": "live", "exchange_name": "live"},
    }
    assert "Instrument: Apple Inc. (AAPL) — NASDAQ" in _format_profile(profile, agent)
