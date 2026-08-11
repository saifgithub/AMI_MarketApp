"""CR145 Tier A · CR150 A2/A3 · CR146 Tier B — render what is already fetched.

Six numbers the pipeline computes on every convene and then throws away:

| number | computed at | fate before AT:R68 |
|---|---|---|
| `marketCap` | `fundamentals.py` | denominator of the FCF-yield calc, never shown |
| `freeCashflow` | same | collapsed to a percentage |
| `totalDebt` | same | consumed inside `net_cash_millions` |
| `sma_short` / `sma_long` | `technicals.py` | reduced to the word "uptrend" |
| volume ratio | same | reduced to "above 20-day average" |

No new provider, no new fetch, no new field on any wire. The justification is
DEF228's, verbatim: arithmetic on numbers already on the sheet asserts nothing
new — and an agent that is handed a LABEL without the number behind it reaches
for training memory to fill the gap, which is what the grounding directive
forbids two paragraphs earlier in the same prompt.

**Market cap is the one that changes what an agent can do.** The mandate carries
*"Liquid only. Avoid microcaps (< $500M market cap)"* as a HARD constraint in
**17 of 18** prompts, **0 of 18** fact sheets stated a market cap, and the same
prompt forbids recalling one from training memory. The rule was unfollowable by
construction — not disobeyed, *unfollowable*. That is what these tests are for.

`_price_anchor` is the second half of the batch, and the reason all these lines
route through one function: the fact sheet carries TWO prices — `Reference
price` (fundamentals) and `last close` (technicals) — and DEF228 happened
because a derived figure took one half from each. Every derived line now shares
an anchor and prints its name.
"""

from __future__ import annotations

import pytest

from app.schemas import AgentId
from app.services.room_prompts import _format_profile
from app.services.technicals import Technicals, build_technicals_context_block


@pytest.fixture
def profile() -> dict:
    return {
        "base_price": 271.83,
        "last_close": 268.40,
        "market_cap": 1_234_567,
        "free_cash_flow": 45_678,
        "total_debt": 8_901,
        "net_cash": 944,
        "low": 155.4,
        "high": 402.9,
        "support": 240.11,
        "breakout": 300.55,
        "rsi": 61,
        "rsi_tone": "neutral",
        "trend": "uptrend",
        "volume_tone": "above 20-day average",
        "sma_short": 262.10,
        "sma_long": 251.40,
        "volume_ratio": 1.47,
        "field_state": {
            "base_price": "live", "technicals": "live", "week52": "live",
            "net_cash": "live", "market_cap": "live", "free_cash_flow": "live",
            "total_debt": "live",
        },
    }


# ── CR145 Tier A / CR150 A2 — company size ────────────────────────────────────


def test_market_cap_reaches_the_prompt_at_last(profile):
    """The whole point: `Avoid microcaps (< $500M market cap)` becomes checkable."""
    text = _format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "market cap $1,234,567M" in text


def test_free_cash_flow_renders_in_dollars_not_only_as_a_yield(profile):
    """A yield cannot distinguish $200M on a $5B cap from $2B on a $50B cap, and
    "FCF consistency" is in this analyst's own job description."""
    assert "FCF $45,678M (TTM)" in _format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)


def test_gross_debt_renders_beside_the_netted_figure(profile):
    """A netted number hides leverage: $40B cash against $45B debt and $1B
    against $6B both render as "net debt $5,000M", and those are not the same
    balance sheet."""
    text = _format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "gross debt $8,901M" in text
    assert "Net cash $944M" in text or "net cash $944M" in text


def test_company_size_is_gated_per_field_not_per_line(profile):
    """CR104 — a provider gap on one part must not take the other two down, and
    must not render the missing one under a `(LIVE)` label."""
    partial = dict(profile)
    partial["field_state"] = dict(profile["field_state"], free_cash_flow="unavailable")
    text = _format_profile(partial, AgentId.FUNDAMENTALS_ANALYST)
    assert "market cap $1,234,567M" in text
    assert "gross debt $8,901M" in text
    assert "FCF $" not in text


def test_no_company_size_line_at_all_when_nothing_is_live(profile):
    """DEF053's rule: no label for a number we never had. Not a line reading
    "Company size: not available"."""
    bare = dict(profile)
    bare["field_state"] = dict(
        profile["field_state"], market_cap="unavailable",
        free_cash_flow="unavailable", total_debt="unavailable",
    )
    assert "Company size" not in _format_profile(bare, AgentId.FUNDAMENTALS_ANALYST)


def test_company_size_is_in_the_fundamentals_lane_only(profile):
    """CR145 Tier C — the render lands inside the lane split shipped in Batch 5,
    not beside it."""
    assert "market cap" not in _format_profile(profile, AgentId.SOCIAL_MEDIA_ANALYST)
    assert "market cap $1,234,567M" in _format_profile(profile, AgentId.TRADER)


# ── CR150 A3 — distance from both ends of the 52-week range ───────────────────


def test_the_52_week_line_states_distance_from_both_ends(profile):
    """This is the figure the Bear reaches for and gets wrong: on SNDK it wrote
    83% for an actual −48.0% below the high, and that became the stance headline
    the comb rendered."""
    text = _format_profile(profile, AgentId.BEAR_RESEARCHER)
    assert "52-week range: $155.4–$402.9" in text
    assert "-33.4% vs the high" in text     # (268.40 - 402.9) / 402.9
    assert "+72.7% vs the low" in text      # (268.40 - 155.4) / 155.4


def test_the_52_week_line_names_the_price_it_measured_from(profile):
    assert "from the last close $268.4" in _format_profile(profile, AgentId.BEAR_RESEARCHER)


def test_the_52_week_line_survives_a_missing_anchor(profile):
    """The range itself is real even when no price is live; degrade to the bare
    range rather than dropping a live fact or printing a percentage of None."""
    no_price = dict(profile)
    no_price["field_state"] = dict(
        profile["field_state"], technicals="unavailable", base_price="unavailable"
    )
    text = _format_profile(no_price, AgentId.BEAR_RESEARCHER)
    assert "52-week range: $155.4–$402.9" in text
    assert "vs the high" not in text


# ── CR146 Tier B — the numbers behind the labels ──────────────────────────────


def test_the_moving_averages_behind_the_trend_word_are_stated(profile):
    """`trend` is derived from `price > sma_short > sma_long` and both were then
    discarded, so an agent told "uptrend" could not say whether price was 0.4%
    or 14% above the 50-day."""
    text = _format_profile(profile, AgentId.MARKET_ANALYST)
    assert "20-day SMA: $262.1, 50-day SMA: $251.4" in text
    assert "+6.8% vs the 50-day" in text    # (268.40 - 251.40) / 251.40


def test_the_volume_ratio_behind_the_volume_word_is_stated(profile):
    """"above 20-day average" is true at 1.11× and at 9×, and those are not the
    same tape."""
    text = _format_profile(profile, AgentId.MARKET_ANALYST)
    assert "1.47× the 20-day average" in text
    assert "above 20-day average" in text   # the label is kept, not replaced


def test_the_technicals_numbers_stay_inside_the_technicals_lane(profile):
    assert "20-day SMA" not in _format_profile(profile, AgentId.NEWS_ANALYST)


# ── The single price anchor ───────────────────────────────────────────────────


def test_every_derived_line_measures_from_the_same_price(profile):
    """DEF228's root cause: the sheet carries two prices and a derived figure
    took one half from each. All three derived lines must name the same one."""
    text = _format_profile(profile, AgentId.BULL_RESEARCHER)
    assert text.count("the last close $268.4") >= 2   # 52-week + asymmetry
    assert "the reference price" not in text


def test_the_anchor_falls_back_together_across_every_derived_line(profile):
    """With technicals dark, all of them must move to the reference price at
    once — a mixed anchor is the defect, not a degraded read."""
    no_tech = dict(profile)
    no_tech["field_state"] = dict(profile["field_state"], technicals="unavailable")
    text = _format_profile(no_tech, AgentId.BULL_RESEARCHER)
    assert "from the reference price $271.83" in text
    assert "the last close" not in text


# ── CR146 Tier B — the sheet's two prices ─────────────────────────────────────


def test_the_two_prices_are_reconciled_not_left_as_two_facts(profile):
    """`Reference price` (the quote) and `last close` (final candle of the 3m
    history) diverge in 7 of 16 post-fix prompts, and one turn read them as two
    separate facts: "Price at $189.31 … and the final close $189.22 firmly
    inside this wide band"."""
    text = _format_profile(profile, AgentId.MARKET_ANALYST)
    assert "$271.83 (the live quote)" in text
    assert "$268.4 (the last close" in text
    assert "not two facts" in text


def test_neither_price_is_deleted_to_make_the_problem_go_away(profile):
    """They are genuinely different measurements from different sources.
    Dropping one would hide a real provider disagreement rather than resolve
    it."""
    text = _format_profile(profile, AgentId.MARKET_ANALYST)
    assert "271.83" in text and "268.4" in text


def test_no_reconciliation_clause_when_the_two_prices_agree(profile):
    """Nothing to reconcile, so the extra words would be noise on every prompt
    where the sources happen to match."""
    same = dict(profile, last_close=271.83)
    text = _format_profile(same, AgentId.MARKET_ANALYST)
    assert "Reference price: $271.83" in text
    assert "not two facts" not in text


def test_no_reconciliation_clause_when_technicals_are_dark(profile):
    """There is only one price then, so claiming two sources would be false."""
    no_tech = dict(profile)
    no_tech["field_state"] = dict(profile["field_state"], technicals="unavailable")
    assert "not two facts" not in _format_profile(no_tech, AgentId.MARKET_ANALYST)


# ── Both surfaces agree ───────────────────────────────────────────────────────


def test_the_one_on_one_technicals_block_carries_the_same_numbers(monkeypatch):
    """`test_prompt_data_parity.py` asserts each field is rendered on BOTH
    surfaces. Rendering only in the Room would let the same agent state a
    different 50-day average about the same ticker on the same day."""
    from app.core.config import settings
    from app.services import technicals as technicals_mod

    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(
        technicals_mod, "compute_technicals",
        lambda t: Technicals(
            rsi=61, rsi_tone="neutral", trend="uptrend",
            volume_tone="above 20-day average", support=240.11, breakout=300.55,
            price=268.40, sma_short=262.10, sma_long=251.40, volume_ratio=1.47,
        ),
    )
    block = build_technicals_context_block("AAPL")
    assert block is not None
    assert "20-day SMA: $262.1, 50-day SMA: $251.4" in block
    assert "+6.8% vs the 50-day" in block
    assert "1.47× the 20-day average" in block
