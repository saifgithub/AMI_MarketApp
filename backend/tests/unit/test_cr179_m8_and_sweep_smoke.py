"""CR179 Leg 0 — M8's vocabulary, and the smoke test DEF271 asked for and never got.

TWO THINGS LIVE HERE.

**The sweep runs at all.** DEF271: `prompt_quality_sweep.py` crashed on import
with `KeyError: 'size'` from 2026-08-08 to 2026-08-12 — DEF235 had deleted the
production pattern it imported — and the whole instrument, all six metrics, was
unrunnable across the entire CR143 Batch 1–9 programme. Nobody noticed, because
nobody ran it, because nothing in CI did. That row names the fix in its own
words: *"the honest fix is a smoke test that runs the sweep against the
committed epoch in CI, and it is not built here."* This is that, built.

It deliberately runs the WHOLE sweep against a REAL committed corpus rather than
importing the module and asserting it imports. The failure it exists to catch was
a production-pattern drift reaching an interior metric — an import check would
have passed on the day DEF271 broke.

**M8's vocabulary is pinned by its own false positives.** Every case below is one
the metric actually got wrong on the 2026-08-13 corpus before it was hand-read.
That is the point: a cross-lane metric's failure mode is arguing for tightening a
firewall that is already working, so its regression tests are the sentences that
fooled it, kept verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.prompt_quality_sweep import _m8_domains_cited, run

#  tests/unit/<this> -> tests -> backend -> repo root
_CORPUS = (
    Path(__file__).resolve().parents[3]
    / "docs" / "forward_planning" / "CR143_agent_prompt_audit" / "corpus"
)


# ── M8 vocabulary ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,domain,phrase", [
    ("the stock trades at a 122.6x trailing P/E", "fundamentals", "P/E"),
    ("gross margin of 63% and operating margin of 52%", "fundamentals", "gross margin"),
    ("RSI of 40 with price below the 50-day SMA", "technicals", "RSI"),
    ("a clear support level at $424.03", "technicals", "support level"),
    ("r/wallstreetbets shows 1,455 mentions", "social", "r/wallstreetbets"),
    ("the FOMC decision lands in 34 days", "news", "FOMC"),
    ("an analyst upgrade from Morgan Stanley", "news", "analyst upgrade"),
])
def test_the_vocabulary_still_detects_a_real_citation(text, domain, phrase):
    """The positive control. A metric tightened four times against its own false
    positives can end up detecting nothing, which reads as perfect lane
    discipline — the precision-is-actually-blindness failure P16 names and an
    earlier M7 draft shipped (scored population cut 29 -> 3)."""
    hits = _m8_domains_cited(text)
    assert domain in hits, f"{text!r} should register as {domain}, got {hits}"
    assert any(phrase.lower() in h.lower() for h in hits[domain])


@pytest.mark.parametrize("text,must_not", [
    # `support` was the VERB in 100% of its hits on the real corpus.
    ("a 122.6x P/E supported by a 16% profit margin", "technicals"),
    ("generates ample cash to support the 0.62% dividend yield", "technicals"),
    ("consensus target and a buy rating indicate analyst support", "technicals"),
    # `momentum`: revenue momentum is fundamentals, sector momentum is news.
    ("Top-line momentum is the key input: TTM revenue growth", "technicals"),
    ("the headline cluster highlights broad sector momentum", "technicals"),
    # The News Analyst COMPLYING with the firewall, scored as violating it.
    ("No trade ideas or chart analysis are provided", "technicals"),
    # A statistics word, not a profit margin.
    ("the sample places sentiment inside the sampling error margin", "fundamentals"),
    # An EARNINGS upgrade is a fundamentals revision, not an analyst action.
    ("implies significant earnings upgrades via consensus EPS est.", "news"),
    # The Social Analyst's own input, which CR145's filing miscounted as
    # technicals for 6 of 18 turns.
    ("mention volume spiked 3x week over week", "technicals"),
    ("sentiment trend is deteriorating", "technicals"),
])
def test_the_hand_read_false_positives_stay_dead(text, must_not):
    """Each of these was scored as trespass by an earlier form of M8 and proved
    wrong by reading the sentence. Pinned so a future widening cannot quietly
    reintroduce them."""
    assert must_not not in _m8_domains_cited(text), (
        f"{text!r} must not register as {must_not} — it is the homonym, not the domain"
    )


def test_a_shared_lane_phrase_belongs_to_nobodys_trespass_count():
    """`next_earnings` renders into the fundamentals lane AND the news lane, so
    naming an earnings date is not trespass for either desk."""
    assert _m8_domains_cited("the next earnings date is 2026-11-03") == {}


# ── the sweep smoke test (DEF271) ────────────────────────────────────────────

@pytest.fixture(scope="module")
def swept(tmp_path_factory):
    """Run the REAL sweep over the REAL committed epoch. ~1s, no network."""
    d = tmp_path_factory.mktemp("epoch")
    (d / "corpus.json").write_bytes((_CORPUS / "llm_audit_2026-08-13-epoch.json").read_bytes())
    (d / "runs.json").write_bytes((_CORPUS / "room_runs_2026-08-13-epoch.json").read_bytes())
    return run(d)


def test_the_sweep_runs_end_to_end_on_the_committed_epoch(swept):
    """DEF271's own prescribed fix. The sweep sat crashing on import for four
    days because its acceptance was 'someone runs it', and the one person who
    would have was measuring something else."""
    assert swept["epoch_turns"] > 0
    assert swept["epoch_convenes"] > 0


@pytest.mark.parametrize("metric", [
    "m1_identifiability", "m2_role_vs_ticker", "m3_number_provenance",
    "m4_risk_spread", "m5_pm_groundedness", "m6_stance_entropy",
    "m7_date_accuracy", "m8_cross_lane_citation",
])
def test_every_metric_produces_a_non_empty_result(swept, metric):
    """A metric returning `{}` is the DEF271 shape one layer in: reachable,
    running, and silently answering nothing. M5 spent two epochs being reported
    as empty on the strength of a transcription error, and the only reason that
    was caught is that someone re-read the JSON."""
    assert swept[metric], f"{metric} produced an empty result"


def test_m8_scores_only_the_laned_analysts(swept):
    """The eight full-sheet agents hold every domain by design; scoring them
    would inflate the denominator and make the rate look precise while
    measuring nothing."""
    m8 = swept["m8_cross_lane_citation"]
    assert set(m8["scored_agents"]) == {
        "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst"
    }
    assert m8["turns_scored"] == sum(v["turns"] for v in m8["per_agent"].values())


def test_m8_reports_its_exclusions_rather_than_applying_them_silently(swept):
    """The dual-lane drops (`52-week` to the Fundamentals Analyst) are the
    difference between a 40.6% rate and a 2.5% one. An exclusion that large has
    to be auditable, or the metric is unfalsifiable."""
    m8 = swept["m8_cross_lane_citation"]
    assert "supplied_not_trespass" in m8
    assert m8["supplied_not_trespass"], (
        "no exclusions were recorded — either the fact-sheet check stopped "
        "firing, or the lane matrix changed and this baseline is stale"
    )


def test_m7_stays_at_zero_on_the_committed_epoch(swept):
    """CR169's disposition rests on this, and DEF279 is why it is pinned: M7
    reported 13.4% on this exact corpus, all eleven hand-read, none a model
    error. If this moves, read the sentences before believing the number."""
    assert swept["m7_date_accuracy"]["pairs_mismatched"] == 0
