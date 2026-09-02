"""CR219 R52 — "what would change this call" survives the parser into the Verdict.

The schema and the ask are pinned in `test_cr210_schemas.py`, alongside the rest
of the CIO's grammar, because that is where a divergence between the two would
show up. This file pins the other half: that the field the grammar requires and
the prompt asks for actually REACHES `Verdict.kill_criterion` on every path,
rather than being emitted and dropped.

That distinction is not pedantry — it is DEF238's exact failure (a PM-only
feature that never worked once in production because everything tested the
builder and nothing tested the caller), and DEF264's (the CIO writing real prose
under a key nothing read, published as "it wrote no rationale" 6 times in 28
verdicts).

The sharpest test here is `test_the_criterion_is_never_published_as_the
_rationale`. `_pm_narration` falls back to the longest prose-shaped value under
an unrecognised key (DEF264, deliberately), and a kill criterion is prose, is
long enough, and reads convincingly — so on a verdict with a misspelled
`narration` key the criterion would become the decision's entire published
justification. It gets MORE convincing the better the criterion is.
"""

from __future__ import annotations

import json

import pytest

from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import (
    PM_KILL_CRITERION_MAX_CHARS,
    PM_KILL_CRITERION_MIN_CHARS,
)
from app.services.room_runner import _parse_pm_verdict, _RoomContext

CRITERION = "A daily close below the 200-day SMA at $769.48 on above-average volume."


def _ctx():
    return _RoomContext(
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        halal_universe=set(),
        classification_universe=None,
        locale_allowed_universe=None,
    )


def _parse(**payload):
    body = {"narration": "The synthesis holds and the mandate clears.", **payload}
    return _parse_pm_verdict(json.dumps(body), _ctx())


# ── it reaches the Verdict on both actions ───────────────────────────────────


def test_an_approve_carries_the_criterion():
    _, verdict = _parse(
        action="APPROVE", size_pct=3.0, entry=150, stop=141, target=172,
        horizon_days=42, kill_criterion=CRITERION,
    )
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.kill_criterion == CRITERION


def test_a_pass_carries_the_criterion_too():
    """The question a PASS leaves open is "what would have to change for you to
    buy this?" — so a refusal without one is a refusal the user can never
    revisit."""
    _, verdict = _parse(action="PASS", kill_criterion=CRITERION)
    assert verdict.action == VerdictAction.PASS
    assert verdict.kill_criterion == CRITERION


def test_a_pass_with_no_rationale_still_carries_the_criterion():
    """DEF232's absent-rationale path is a separate branch and would be an easy
    one to forget — it constructs its own Verdict."""
    _, verdict = _parse_pm_verdict(
        json.dumps({"action": "PASS", "kill_criterion": CRITERION}), _ctx()
    )
    assert verdict.kill_criterion == CRITERION


# ── absence is absence, never a stand-in ─────────────────────────────────────


def test_a_missing_criterion_is_none_and_not_fabricated():
    _, verdict = _parse(action="PASS")
    assert verdict.kill_criterion is None


def test_a_too_short_value_is_read_as_absent():
    """"No", "None", "N/A" clear a minLength of 1 while removing the field."""
    for stub in ("No", "None", "N/A", "TBD", "n/a."):
        _, verdict = _parse(action="PASS", kill_criterion=stub)
        assert verdict.kill_criterion is None, stub


def test_an_over_long_criterion_is_nulled_never_truncated():
    """The `STANCE_HEADLINE_MAX_CHARS` rule: a cut sentence is an assertion with
    its qualifier removed. "Close below the 200-day SMA unless earnings beat"
    inverts when the tail is dropped."""
    long = "x" * (PM_KILL_CRITERION_MAX_CHARS + 1)
    _, verdict = _parse(action="PASS", kill_criterion=long)
    assert verdict.kill_criterion is None


def test_a_criterion_exactly_at_each_bound_is_kept():
    """Anti-vacuity for the two tests above — the bounds are inclusive, so a
    valid criterion at the edge is not silently discarded."""
    for n in (PM_KILL_CRITERION_MIN_CHARS, PM_KILL_CRITERION_MAX_CHARS):
        _, verdict = _parse(action="PASS", kill_criterion="y" * n)
        assert verdict.kill_criterion == "y" * n, n


def test_a_non_string_value_is_read_as_absent():
    for junk in (42, None, ["a criterion in a list"], {"k": "v"}, True):
        _, verdict = _parse(action="PASS", kill_criterion=junk)
        assert verdict.kill_criterion is None, junk


# ── synonyms, by allowlist and precedence (DEF239 / DEF264) ──────────────────


@pytest.mark.parametrize("key", [
    "kill_criterion", "killCriterion", "kill_criteria", "what_would_change_this",
])
def test_the_contracted_key_and_its_synonyms_are_read(key):
    """DEF239's lesson: the model emits a key that is not always the contracted
    one, and reading one key alone published a falsehood over real content."""
    _, verdict = _parse(action="PASS", **{key: CRITERION})
    assert verdict.kill_criterion == CRITERION


def test_the_contracted_key_wins_when_several_are_present():
    _, verdict = _parse(
        action="PASS", kill_criterion=CRITERION,
        kill_criteria="A different, lower-precedence criterion sentence here.",
    )
    assert verdict.kill_criterion == CRITERION


def test_an_unrecognised_key_is_not_scraped_by_shape():
    """No shape fallback here, deliberately, and this is the anti-vacuity for
    that choice. DEF264 added one for the NARRATION because publishing "it wrote
    no rationale" over real prose was actively harmful; a missing criterion
    renders as absent, and absent is the truth. Scraping for the longest
    unclaimed string would find the narration itself."""
    _, verdict = _parse(action="PASS", exit_thesis=CRITERION)
    assert verdict.kill_criterion is None


# ── THE test: the criterion must never become the rationale ──────────────────


def test_the_criterion_is_never_published_as_the_rationale():
    """`_pm_narration` falls back to the longest prose-shaped value under an
    unrecognised key (DEF264). A kill criterion is prose, clears
    `_PM_MIN_PROSE_CHARS`, and reads convincingly — so on a verdict whose
    `narration` key is misspelled, the criterion would become the decision's
    entire published justification, on the one field CR106 renders as the
    defence of the call.

    That is DEF239's `{"ticker": "AAPL"}` failure with a far more plausible
    string, and it gets worse the better the criterion is.
    """
    narration, verdict = _parse_pm_verdict(
        json.dumps({
            "action": "PASS",
            "kill_criterion": CRITERION,
            # not in `_PM_NARRATION_KEYS`, and short enough to fail the shape
            # test, so nothing else can supply the rationale
            "nrtn": "too short",
        }),
        _ctx(),
    )
    assert CRITERION not in narration
    assert CRITERION not in verdict.reason
    assert verdict.kill_criterion == CRITERION


def test_a_real_narration_is_still_recovered_by_shape_beside_a_criterion():
    """Anti-vacuity for the exclusion above: excluding the criterion keys must
    not have broken DEF264's recovery, which is a live, load-bearing path."""
    long_prose = (
        "The synthesis holds: margins expanded two quarters running and the "
        "balance sheet carries the cycle, so the entry stands at this size."
    )
    narration, verdict = _parse_pm_verdict(
        json.dumps({
            "action": "PASS", "narr": long_prose, "kill_criterion": CRITERION,
        }),
        _ctx(),
    )
    assert narration == long_prose
    assert verdict.kill_criterion == CRITERION
