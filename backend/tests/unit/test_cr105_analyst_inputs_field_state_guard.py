"""GUARD (CR105 item 5) — an analyst's `## Inputs` claim of real/live data
must map to a field the Room renderer can actually source, so a new
capability claim can't drift in silently the way the Concierge's did (DEF129,
CR023 class: `overlay_generator.py` claimed scheduling/mute capabilities that
were never wired). Same shape as `test_def084_halal_flag_copy_guard.py` /
`test_def084_overlay_narration_copy_guard.py` — an explicit, authored
phrase<->mechanism mapping checked for presence, not NLP claim-extraction.

`profile["field_state"]`'s populated keys (`room_runner.py::_profile_for_ticker`,
building on `_FUNDAMENTALS_NUMERIC_FIELDS`/`_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS`
plus the "week52"/"technicals"/"next_earnings"/"news"/"social" domain keys) are
the ONLY thing `_format_profile` (room_prompts.py) treats as sourced — CR104
made that the single per-field provenance mechanism. This guard binds each of
the four analysts' declared `content/agents/*.md` Inputs to that same key set,
checked in both directions:

  1. every claimed-real field in the mapping below resolves to a field_state
     key that still exists — imported live from room_runner.py's own
     fundamentals-field tuples, so a rename/removal there breaks THIS test
     rather than leaving a claim silently unbacked;
  2. the mapping's keyword phrase is still literally present in the agent's
     .md file — so if the prose drifts (reworded, or a new claim added), the
     mapping goes stale and red rather than silently checking nothing, the
     exact "allowlist blind spot" `test_cr104_...` warns about;
  3. the two already-guarded negative claims (no MACD/Bollinger/crossover; no
     Twitter/X/StockTwits/Discord) remain present verbatim.

Acceptance #4 (CR105): the checker is demonstrated red against a fabricated
claim, then green against the real mapping — see the last two tests.
"""

from __future__ import annotations

from pathlib import Path

from app.services.room_runner import (
    _EARNINGS_DIVIDEND_FIELDS,
    _FUNDAMENTALS_NUMERIC_FIELDS,
    _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_AGENTS_DIR = _REPO_ROOT / "content" / "agents"

# The ONLY provenance keys `_format_profile` ever reads off `profile["field_state"]`
# (CR104) — the "week52"/"technicals"/"next_earnings"/"news"/"social" domain
# keys are set directly by string literal in room_runner.py (not drawn from a
# tuple), so they're listed here rather than imported; the fundamentals tuples
# ARE imported so a rename there breaks this test, not silently no-ops.
#
# CR166 Tier B — `_EARNINGS_DIVIDEND_FIELDS` is imported for the same reason.
# It is a THIRD source: those two fields arrive on `EarningsInfo` (CR030), not
# from `fetch_live_fundamentals`, so they live in their own tuple rather than
# being smuggled into a roster that is iterated against the fundamentals fetch.
_FIELD_STATE_KEY_UNIVERSE = (
    set(_FUNDAMENTALS_NUMERIC_FIELDS)
    | set(_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS)
    | set(_EARNINGS_DIVIDEND_FIELDS)
    | {"week52", "technicals", "next_earnings", "news", "social"}
)

# Authored mapping: (agent stem, keyword phrase as it appears verbatim in the
# .md's Inputs section, the field_state key that phrase's "real"/"live"/
# "computed from real" claim rests on).
_CLAIMED_REAL_INPUTS = [
    ("fundamentals_analyst", "P/E, P/S, EV/EBITDA, PEG, FCF yield", "pe"),
    ("fundamentals_analyst", "P/E, P/S, EV/EBITDA, PEG, FCF yield", "price_to_sales"),
    ("fundamentals_analyst", "P/E, P/S, EV/EBITDA, PEG, FCF yield", "ev_to_ebitda"),
    ("fundamentals_analyst", "P/E, P/S, EV/EBITDA, PEG, FCF yield", "peg_ratio"),
    ("fundamentals_analyst", "P/E, P/S, EV/EBITDA, PEG, FCF yield", "fcf_yield"),
    # DEF233: the sheet carries forward P/E beside trailing, and the PEG's
    # denominator when the provider declares one. Both are claimed in the .md,
    # so both must resolve to a field_state key `_format_profile` can source.
    ("fundamentals_analyst", "P/E arrives on **two bases**", "forward_pe"),
    ("fundamentals_analyst", "is built on the trailing multiple and carries that label", "peg_basis"),
    # CR145 Tier A (AT:R68) split this one bullet in two and corrected two
    # claims inside it, so the mapping follows the wording — the guard did its
    # job by refusing to let the .md drift away from it silently.
    #
    # The margin claim was WRONG before, not merely reworded: the .md said
    # "profit margin" while the output-style bullet asked for "gross margins …
    # and the direction it is moving", and `fundamentals.py` renders
    # `profitMargins` (NET) with no trend of any kind. It now says "net profit"
    # and states that no direction is available.
    #
    # CR166 Tier B — the claim changed AGAIN, and again because the underlying
    # data did: `grossMargins` and `operatingMargins` were in the same `.info`
    # dict all along, so the .md now claims the full gross → operating → net
    # STRUCTURE. Note what did NOT change: no margin *trend* is available, the
    # .md still says so, and the output-style bullet still forbids a direction.
    ("fundamentals_analyst", "the **margin structure** (gross → operating → net)", "rev_growth"),
    ("fundamentals_analyst", "the **margin structure** (gross → operating → net)", "profit_margin"),
    ("fundamentals_analyst", "the **margin structure** (gross → operating → net)", "week52"),
    ("fundamentals_analyst", "the **margin structure** (gross → operating → net)", "gross_margin"),
    ("fundamentals_analyst", "the **margin structure** (gross → operating → net)", "operating_margin"),
    ("fundamentals_analyst", "**Earnings power**", "trailing_eps"),
    ("fundamentals_analyst", "**Earnings power**", "revenue_ttm"),
    ("fundamentals_analyst", "**Earnings power**", "revenue_per_share"),
    ("fundamentals_analyst", "**Returns and balance sheet**", "return_on_equity"),
    ("fundamentals_analyst", "**Returns and balance sheet**", "return_on_assets"),
    ("fundamentals_analyst", "**Returns and balance sheet**", "current_ratio"),
    ("fundamentals_analyst", "**Returns and balance sheet**", "quick_ratio"),
    ("fundamentals_analyst", "**Returns and balance sheet**", "debt_to_equity"),
    # CR219 R33 — the #1 arm request (21 mentions, 9/12 agents); both keys the
    # claim rests on, ratio and the quarter it is stated against.
    ("fundamentals_analyst", "**Interest coverage**", "interest_coverage"),
    ("fundamentals_analyst", "**Interest coverage**", "interest_coverage_quarter"),
    # CR219 R34 — explicit capex, so the claim never has to be inferred from
    # a change in the free-cash-flow figure R20 forbids doing arithmetic on.
    ("fundamentals_analyst", "**Capital expenditure**", "capex_ttm"),
    # CR219 R35 — all three keys the pacing claim rests on: the series, its
    # dates, and the precomputed pace label.
    ("fundamentals_analyst", "**Buyback pacing**", "buyback_quarterly"),
    ("fundamentals_analyst", "**Buyback pacing**", "buyback_quarterly_basis"),
    ("fundamentals_analyst", "**Buyback pacing**", "buyback_pace"),
    ("fundamentals_analyst", "**Ownership**", "held_pct_institutions"),
    ("fundamentals_analyst", "**Ownership**", "held_pct_insiders"),
    ("fundamentals_analyst", "**Ownership**", "shares_outstanding"),
    ("fundamentals_analyst", "**Ownership**", "float_shares"),
    # "net cash" alone was also wrong: `_net_position_line` emits net cash OR
    # net debt from the sign, and the analyst was told only one of the two.
    ("fundamentals_analyst", "Net cash **or net debt**", "net_cash"),
    # CR145 Tier A — fetched since DEF053, rendered from AT:R68. Claimed in the
    # .md, so each must resolve to a field_state key `_format_profile` sources.
    ("fundamentals_analyst", "Gross\n  debt, market cap and TTM free cash flow in dollars", "market_cap"),
    ("fundamentals_analyst", "Gross\n  debt, market cap and TTM free cash flow in dollars", "free_cash_flow"),
    ("fundamentals_analyst", "Gross\n  debt, market cap and TTM free cash flow in dollars", "total_debt"),
    ("fundamentals_analyst", "Sector/industry classification", "sector"),
    ("fundamentals_analyst", "Sector/industry classification", "industry"),
    # CR219 R37 — both halves of the own-history claim, each independently
    # gated (a filer can carry one series without the other).
    ("fundamentals_analyst", "**Multiples vs. own history**", "historical_pe_median"),
    ("fundamentals_analyst", "**Multiples vs. own history**", "historical_ev_ebitda_median"),
    # CR219 R21-DATA — unblocks WP04-R21's overlay rewrite.
    ("fundamentals_analyst", "**Earnings revisions**", "eps_revisions_direction"),
    ("fundamentals_analyst", "**Surprise history**", "surprise_quarters"),
    # CR166 Tier B — the dividend claim grew the half that makes a yield mean
    # something (cover + ex-date), and the consensus claim grew its dispersion.
    ("fundamentals_analyst", "**Dividend** — yield (trailing)", "dividend_yield"),
    ("fundamentals_analyst", "**Dividend** — yield (trailing)", "payout_ratio"),
    ("fundamentals_analyst", "**Dividend** — yield (trailing)", "dividend_rate"),
    ("fundamentals_analyst", "**Dividend** — yield (trailing)", "ex_dividend_date"),
    ("fundamentals_analyst", "Analyst consensus — the rating", "analyst_rating"),
    ("fundamentals_analyst", "Analyst consensus — the rating", "analyst_target_price"),
    ("fundamentals_analyst", "Analyst consensus — the rating", "analyst_opinion_count"),
    ("fundamentals_analyst", "Analyst consensus — the rating", "analyst_rating_score"),
    ("fundamentals_analyst", "Analyst consensus — the rating", "analyst_target_high"),
    ("fundamentals_analyst", "Analyst consensus — the rating", "analyst_target_low"),
    ("fundamentals_analyst", "Analyst consensus — the rating", "analyst_target_median"),
    ("fundamentals_analyst", "Consensus EPS estimate for the next reporting date", "next_earnings"),
    (
        "market_analyst",
        "RSI(14), a 20/50-day moving-average trend read, and volume vs. a 20-day",
        "technicals",
    ),
    # DEF229(b): the .md no longer calls the 50-day high a "breakout level" —
    # naming a level as a trade trigger is what made the only long entry
    # unreachable. The underlying claim (a real recent range, from real price
    # history) is unchanged, so the mapping follows the wording.
    ("market_analyst", "The 50-day range (low and high) and where the last close sits", "technicals"),
    ("news_analyst", "Recent headlines for the ticker in question, pulled live", "news"),
    ("news_analyst", "Next earnings date, when within a 90-day window, sourced live.", "next_earnings"),
    ("social_media_analyst", "Reddit-only aggregate sentiment", "social"),
    # CR219 R36 — not one of the four analysts this guard's docstring names,
    # but the same mechanism applies: a new live-data claim, checked against
    # the same field_state key market_analyst's technicals claim above rests
    # on (ATR rides the same all-or-nothing OHLCV fetch).
    ("trader", "**ATR(14)** — average true range", "technicals"),
]

# The negative claims — each must remain present verbatim, or the prompt has
# silently reopened the exact capability-drift class DEF129 was.
_NEGATIVE_CLAIMS = [
    ("market_analyst", "No MACD, moving-average crossover signal, or Bollinger Bands are"),
    ("social_media_analyst", "No Twitter/X, StockTwits, Google Trends, or Discord access exists"),
]


def _inputs_section(agent_stem: str) -> str:
    text = (_AGENTS_DIR / f"{agent_stem}.md").read_text(encoding="utf-8")
    start = text.index("## Inputs")
    end = text.index("## Output", start)
    return text[start:end]


def test_every_claimed_real_field_maps_to_a_field_state_key_that_still_exists():
    bad_keys = sorted(
        {key for _, _, key in _CLAIMED_REAL_INPUTS if key not in _FIELD_STATE_KEY_UNIVERSE}
    )
    assert not bad_keys, (
        "CR105 guard: these claimed fields no longer map to a field_state key "
        "_format_profile can source — either room_runner.py renamed/removed "
        f"the field (update this mapping) or an analyst's .md claim is now "
        f"unbacked: {bad_keys}"
    )


def test_every_claimed_real_field_keyword_is_still_present_in_its_md_file():
    missing = [
        (agent, phrase)
        for agent, phrase, _ in _CLAIMED_REAL_INPUTS
        if phrase not in _inputs_section(agent)
    ]
    assert not missing, (
        "CR105 guard: this mapping's keyword phrase is no longer found in the "
        "agent's Inputs section — the .md wording drifted; update the mapping "
        f"(or the .md, if the underlying claim itself changed): {missing}"
    )


def test_negative_claims_still_present():
    missing = [
        (agent, phrase) for agent, phrase in _NEGATIVE_CLAIMS if phrase not in _inputs_section(agent)
    ]
    assert not missing, f"CR105 guard: a negative-capability claim was removed or reworded: {missing}"


def _unbacked_claims(claims: list[tuple[str, str, str]]) -> list[str]:
    """The checking logic under test — pulled out as a function so the
    red/green demonstration below can call it directly against synthetic
    input, the same pattern test_cr104_...'s `_offenders_for_synthetic_source`
    uses to prove the checker generalises rather than just matching today's
    files by luck."""
    return sorted({key for _, _, key in claims if key not in _FIELD_STATE_KEY_UNIVERSE})


def test_the_checker_is_demonstrated_red_against_a_fabricated_claim():
    """CR105 acceptance #4. `insider_flow_pct` is not a field_state key
    anywhere in room_runner.py — a claim resting on it is exactly the DEF129
    shape: a capability claim with no data path behind it."""
    fabricated = _CLAIMED_REAL_INPUTS + [
        ("fundamentals_analyst", "Insider buy/sell flow — real, pulled live", "insider_flow_pct"),
    ]
    assert _unbacked_claims(fabricated) == ["insider_flow_pct"]


def test_the_checker_is_green_against_the_real_mapping():
    assert _unbacked_claims(_CLAIMED_REAL_INPUTS) == []
