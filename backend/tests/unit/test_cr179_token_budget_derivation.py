"""DEF289 — the decode budgets, re-derived against the data instead of an assumption.

`_AGENT_MAX_TOKENS` was sized from an unmeasured constant: the comment
`~1,900 chars ≈ 400 tokens` is 4.75 chars/token, and every one of the twelve
budgets is that arithmetic applied to a length. Measured against the committed
2026-08-13 epoch, the real worst case is **3.14** — a token buys ~34% fewer
characters than assumed — and four agents were being amputated mid-word.

**Why this file can measure a tokenizer's ratio without a tokenizer.** A
truncated turn is one that hit `max_tokens` exactly, so its character length
divided by that agent's cap IS the ratio, in production, on the model actually
serving. That makes the derivation reproducible from a committed artefact
rather than from a host that has to be up — which matters, because the vLLM
box was unreachable the day this was written.

What this guards, and what it deliberately does not:

  - It re-runs the whole derivation and fails if any cap no longer clears its
    agent's measured worst case. Editing a number in that dict without
    re-measuring is the failure this exists to catch; that is the entire
    reason CR179's binding rule says the re-derivation ships in the SAME
    commit as any sheet growth.
  - It does NOT assert truncation is zero. The corpus is the PRE-fix epoch —
    the caps in the dict are the fix. Asserting a post-fix rate against a
    pre-fix corpus would be a test that lies. The real acceptance is the Leg 5
    re-measure on a fresh corpus (CR105 Amendment 1).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.room_prompts import (
    _AGENT_MAX_TOKENS,
    _CHARS_PER_TOKEN_WORST_CASE,
    _DEFAULT_AGENT_MAX_TOKENS,
    max_tokens_for,
)
from app.schemas.agents import AgentId

# backend/tests/unit/<this> → parents[3] is the repo root. parents[2] is
# `backend/` and silently resolves to a path that does not exist, which reads
# as "corpus missing" rather than as a bug in the test.
_CORPUS_DIR = (
    Path(__file__).resolve().parents[3]
    / "docs/forward_planning/CR143_agent_prompt_audit/corpus"
)
_CORPUS = _CORPUS_DIR / "llm_audit_2026-08-13-epoch.json"

# DEF303 — the newest epoch, and the first with `output_tokens` populated.
#
# This file re-ran the whole derivation and still missed a cap that binds,
# because it re-ran it against ONE epoch and that epoch is the pre-fix one.
# Measured: 482/482 of the 08-13 rows carry a NULL `output_tokens`, 0/468 of
# the 08-14 rows do. So the character proxy above was not a preference, it was
# the only instrument available — and on the newer corpus it is no longer the
# best one.
#
# `_LATEST_CORPUS` is checked with MEASURED tokens where the column is
# populated, which is a strictly better observation than dividing characters by
# a global worst-case ratio. Both are kept: the proxy still governs any epoch
# whose tokens are NULL, and deleting it would strand the 08-13 corpus.
_LATEST_CORPUS = _CORPUS_DIR / "llm_audit_2026-08-14-epoch.json"

# The caps in force when `_LATEST_CORPUS` was recorded — DEF289's raised set,
# which is what was live on Alpha for that run. Pinned for the same reason as
# `_CAPS_AT_CORPUS_TIME`: an at-cap turn is only evidence if you know which
# ceiling it hit, and reading the live dict would make the test agree with
# whatever the dict currently says.
_CAPS_AT_LATEST_CORPUS_TIME = {
    "fundamentals_analyst": 800,
    "market_analyst": 800,
    "news_analyst": 800,
    "social_media_analyst": 800,
    "bull_researcher": 1600,
    "bear_researcher": 1400,
    "research_manager": 1600,
    "trader": 800,
    "aggressive_debator": 800,
    "conservative_debator": 800,
    "neutral_debator": 1100,
    "portfolio_manager": 1700,
}

# The caps in force when the corpus was recorded. A truncated turn is only a
# ratio measurement if we know which ceiling it hit, so these are pinned here
# rather than read from the (now corrected) live dict.
_CAPS_AT_CORPUS_TIME = {
    "fundamentals_analyst": 600,
    "market_analyst": 600,
    "news_analyst": 600,
    "social_media_analyst": 600,
    "bull_researcher": 800,
    "bear_researcher": 800,
    "research_manager": 900,
    "trader": 600,
    "aggressive_debator": 600,
    "conservative_debator": 600,
    "neutral_debator": 600,
    "portfolio_manager": 1100,
}

# Censored observations get more headroom than real ones — see the derivation
# comment in `room_prompts.py`.
_FACTOR_TRUNCATED = 1.5
_FACTOR_CLEAN = 1.25


def _was_cut(text: str) -> bool:
    """DEF125's own truncation test, unchanged: a turn that ends on an
    alphanumeric ended mid-word, because every intended ending carries
    terminal punctuation. Reused rather than reinvented so this file's rates
    are comparable with the 30-day measurement `room_prompts.py` cites."""
    return bool(text) and text[-1].isalnum()


def _corpus_by_agent() -> dict[str, list[str]]:
    rows = json.loads(_CORPUS.read_text())
    out: dict[str, list[str]] = {}
    for row in rows:
        text = (row.get("response_text") or "").strip()
        if text:
            out.setdefault(row["agent_id"], []).append(text)
    return out


def _required_cap(texts: list[str]) -> int:
    """The derivation, in code: worst observed length ÷ the worst measured
    ratio × the censoring factor, rounded up to the nearest 100."""
    longest = max(len(t) for t in texts)
    factor = _FACTOR_TRUNCATED if any(_was_cut(t) for t in texts) else _FACTOR_CLEAN
    needed = longest / _CHARS_PER_TOKEN_WORST_CASE * factor
    return int(math.ceil(needed / 100.0) * 100)


@pytest.fixture(scope="module")
def corpus() -> dict[str, list[str]]:
    if not _CORPUS.exists():
        pytest.skip(f"committed corpus not present: {_CORPUS}")
    return _corpus_by_agent()


def test_the_measured_ratio_comes_from_turns_that_actually_hit_their_ceiling(corpus):
    """The constant is not a guess — this recomputes it from the corpus.

    Every truncated turn yields one ratio. `_CHARS_PER_TOKEN_WORST_CASE` must
    be no larger than the smallest of them, or some agent is sized on a ratio
    its own output shape beats.
    """
    ratios = [
        len(text) / _CAPS_AT_CORPUS_TIME[agent]
        for agent, texts in corpus.items()
        for text in texts
        if _was_cut(text) and agent in _CAPS_AT_CORPUS_TIME
    ]
    assert ratios, "no truncated turns in the corpus — the ratio is unmeasurable from it"
    assert _CHARS_PER_TOKEN_WORST_CASE <= min(ratios) + 1e-9, (
        f"the constant {_CHARS_PER_TOKEN_WORST_CASE} is more generous than the worst "
        f"measured turn ({min(ratios):.2f} chars/token). Every cap derived from it is "
        f"short by that margin."
    )
    # And it must not be so pessimistic that it has stopped describing the
    # data — a constant nobody can justify is the 4.75 problem again.
    assert _CHARS_PER_TOKEN_WORST_CASE >= min(ratios) - 0.5


def test_the_assumption_this_defect_replaced_would_still_be_wrong(corpus):
    """The 4.75 chars/token the old comment asserted, checked against reality.

    Kept as a live assertion rather than prose: if a model change ever made
    4.75 true, this fails and the whole derivation should be revisited.
    """
    ratios = [
        len(text) / _CAPS_AT_CORPUS_TIME[agent]
        for agent, texts in corpus.items()
        for text in texts
        if _was_cut(text) and agent in _CAPS_AT_CORPUS_TIME
    ]
    assert max(ratios) < 4.75, (
        "the retired 4.75 chars/token assumption is no longer refuted by the corpus"
    )


@pytest.mark.parametrize("agent_id", list(AgentId))
def test_every_agent_cap_clears_its_measured_worst_case(agent_id, corpus):
    texts = corpus.get(agent_id.value)
    if not texts:
        pytest.skip(f"{agent_id.value} does not appear in the room corpus")
    required = _required_cap(texts)
    actual = max_tokens_for(agent_id)
    assert actual >= required, (
        f"{agent_id.value}: cap {actual} is below the {required} its measured worst "
        f"case needs ({max(len(t) for t in texts)} chars at "
        f"{_CHARS_PER_TOKEN_WORST_CASE} chars/token, "
        f"{'censored' if any(_was_cut(t) for t in texts) else 'clean'} observation). "
        f"If a sheet grew, re-derive in the same commit — that is CR179's binding rule."
    )


def test_the_four_agents_that_truncated_all_gained_headroom(corpus):
    """Named directly, because they are the defect.

    A derivation that produced no change for bull/bear/neutral/PM would mean
    the arithmetic was rewritten without fixing what it was rewritten for.
    """
    cut = {
        agent for agent, texts in corpus.items() if any(_was_cut(t) for t in texts)
    }
    assert cut == {
        "bull_researcher",
        "bear_researcher",
        "neutral_debator",
        "portfolio_manager",
    }, f"the truncating set moved: {sorted(cut)}"
    for agent in cut:
        aid = AgentId(agent)
        assert max_tokens_for(aid) > _CAPS_AT_CORPUS_TIME[agent], (
            f"{agent} truncated on this corpus and its cap did not rise"
        )


def test_the_two_researchers_are_budgeted_by_the_same_rule_not_the_same_number(corpus):
    """DEF125 required symmetry so the Bear case is never invisibly shorter.

    DEF289 keeps the requirement and changes how it is met: the Bull's censored
    maximum is larger, so an equal integer would bind the Bull first — which is
    the asymmetry the rule forbids, pointed the other way.

    So the enforced property is NOT "the integers differ" — 1600/1600 would be
    perfectly fine, since it clears both needs. It is that neither case can be
    cut while the other runs on, which requires each to clear its own measured
    need AND the one with the larger need to hold the larger budget.
    """
    bull, bear = corpus["bull_researcher"], corpus["bear_researcher"]
    need_bull, need_bear = _required_cap(bull), _required_cap(bear)
    cap_bull = max_tokens_for(AgentId.BULL_RESEARCHER)
    cap_bear = max_tokens_for(AgentId.BEAR_RESEARCHER)
    assert cap_bull >= need_bull and cap_bear >= need_bear
    assert (cap_bull >= cap_bear) == (need_bull >= need_bear), (
        f"the researcher with the larger measured need ({need_bull} vs {need_bear}) "
        f"does not hold the larger budget ({cap_bull} vs {cap_bear}) — one case will "
        f"be cut while the other runs on, for a reason the reader cannot see"
    )


def _latest_by_agent() -> dict[str, list[dict]]:
    rows = json.loads(_LATEST_CORPUS.read_text())
    out: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("agent_id"):
            out.setdefault(row["agent_id"], []).append(row)
    return out


@pytest.fixture(scope="module")
def latest() -> dict[str, list[dict]]:
    if not _LATEST_CORPUS.exists():
        pytest.skip(f"committed corpus not present: {_LATEST_CORPUS}")
    return _latest_by_agent()


def test_the_newest_corpus_is_the_one_that_carries_token_counts(latest):
    """DEF303's premise, asserted rather than described.

    If a future epoch is committed with the column NULL again, the
    token-derived checks below would silently degrade to vacuous — every
    `max(output_tokens)` would be 0 and every cap would clear it comfortably.
    That is the shape of a guard that keeps passing through the change it
    exists to catch, so it fails loudly instead.
    """
    measured = [
        r for rows in latest.values() for r in rows if r.get("output_tokens")
    ]
    total = sum(len(rows) for rows in latest.values())
    assert len(measured) == total, (
        f"{total - len(measured)} of {total} turns carry no output_tokens — the "
        f"token-derived derivation below cannot see them, and would pass vacuously"
    )


@pytest.mark.parametrize("agent_id", list(AgentId))
def test_every_cap_clears_its_measured_token_worst_case(agent_id, latest):
    """The derivation again, on measured tokens instead of the char proxy.

    Same rule, better instrument: worst observed decode × the censoring factor,
    rounded up to the nearest 100. A turn that finished AT its ceiling is
    censored — the true maximum is unknown and larger — so it earns 1.5, and a
    turn that finished under it is a real observation and earns 1.25.
    """
    rows = latest.get(agent_id.value)
    if not rows:
        pytest.skip(f"{agent_id.value} does not appear in the latest corpus")
    cap_then = _CAPS_AT_LATEST_CORPUS_TIME[agent_id.value]
    worst = max(int(r["output_tokens"]) for r in rows)
    censored = worst >= cap_then
    factor = _FACTOR_TRUNCATED if censored else _FACTOR_CLEAN
    required = int(math.ceil(worst * factor / 100.0) * 100)
    actual = max_tokens_for(agent_id)
    assert actual >= required, (
        f"{agent_id.value}: cap {actual} is below the {required} its measured worst "
        f"case needs ({worst} tokens against the {cap_then} in force when the corpus "
        f"was recorded, {'censored' if censored else 'clean'} observation). If a "
        f"sheet grew, re-derive in the same commit — that is CR179's binding rule."
    )


def test_the_conservative_debator_is_the_one_agent_whose_cap_was_binding(latest):
    """DEF303, named directly, because it is the defect.

    Two properties, and the second is the one that keeps this honest. First:
    the Conservative did reach its ceiling on this corpus, so the raise has a
    measurement behind it. Second: it was the ONLY one — a fix that quietly
    raised every debator would make the first property untestable, and the
    Aggressive is specifically the agent the character proxy would have had us
    raise for no reason (599 tokens of 800, a clean observation).
    """
    at_cap = {
        agent
        for agent, rows in latest.items()
        if max(int(r["output_tokens"]) for r in rows)
        >= _CAPS_AT_LATEST_CORPUS_TIME[agent]
    }
    assert at_cap == {"conservative_debator"}, (
        f"the binding set moved: {sorted(at_cap)} — re-derive before changing a cap"
    )
    assert max_tokens_for(AgentId.CONSERVATIVE_DEBATOR) > _CAPS_AT_LATEST_CORPUS_TIME[
        "conservative_debator"
    ], "the Conservative hit its ceiling on this corpus and its cap did not rise"
    assert (
        max_tokens_for(AgentId.AGGRESSIVE_DEBATOR)
        == _CAPS_AT_LATEST_CORPUS_TIME["aggressive_debator"]
    ), (
        "the Aggressive did not reach its ceiling — raising it would be sizing a "
        "prose agent on the PM's JSON chars-per-token ratio, which is DEF289's own "
        "retired 4.75 assumption pointed the other way"
    )


def test_the_char_proxy_and_the_token_measurement_disagree_and_the_tokens_win(latest):
    """The disagreement, pinned so nobody silently 'fixes' it later.

    Applying the character rule to this corpus demands 1000 for the Aggressive;
    the tokens say 800 is right. The proxy is not broken — it is a worst-case
    bound built from the Portfolio Manager's JSON, and prose is denser per
    token. This asserts that the gap is real and in the direction claimed, so
    that a future reader who re-runs the char rule, sees 1000, and 'corrects'
    the dict has a test telling them why not.
    """
    rows = latest["aggressive_debator"]
    chars = max(len((r.get("response_text") or "").strip()) for r in rows)
    tokens = max(int(r["output_tokens"]) for r in rows)
    proxy_required = int(
        math.ceil(chars / _CHARS_PER_TOKEN_WORST_CASE * _FACTOR_CLEAN / 100.0) * 100
    )
    token_required = int(math.ceil(tokens * _FACTOR_CLEAN / 100.0) * 100)
    assert proxy_required > token_required, (
        "the character proxy no longer over-states this agent — if the model's "
        "output shape changed, the 3.14 constant needs re-measuring, not this test "
        "deleting"
    )
    assert max_tokens_for(AgentId.AGGRESSIVE_DEBATOR) >= token_required


def test_the_aggressive_cap_was_not_raised_on_the_proxys_authority(latest):
    """DEF303's most contestable judgement, given a guard of its own.

    The auditor's MINOR-1 (round 1): the claim that three guards covered this
    was wrong — the Aggressive mutation killed one of the same two guards the
    Conservative mutation killed, so deselecting that single shared guard left
    this decision **entirely uncaught**. The judgement the submission itself
    nominated as its weakest rested on one assertion shared with a different
    decision. This is that assertion, standing alone.

    Two-sided on purpose, because only the pair says what was decided:

      - at or above what its OWN measured decode needs (749 → 800), so the
        agent is not under-capped; and
      - strictly BELOW what the character proxy demands (942 → 1000), which is
        what makes "we did not follow the proxy here" a checkable fact rather
        than a comment.

    Equality to the token requirement is deliberately NOT asserted. Caps are
    allowed to exceed their derivation — the Bull sits at 1600 against a need
    near 1000 — so pinning this one to the integer would encode a rule the
    dict does not follow. The bracket encodes the actual decision.
    """
    rows = latest["aggressive_debator"]
    chars = max(len((r.get("response_text") or "").strip()) for r in rows)
    tokens = max(int(r["output_tokens"]) for r in rows)
    proxy_required = int(
        math.ceil(chars / _CHARS_PER_TOKEN_WORST_CASE * _FACTOR_CLEAN / 100.0) * 100
    )
    token_required = int(math.ceil(tokens * _FACTOR_CLEAN / 100.0) * 100)
    cap = max_tokens_for(AgentId.AGGRESSIVE_DEBATOR)

    assert cap >= token_required, (
        f"aggressive_debator cap {cap} is below the {token_required} its own "
        f"measured decode needs ({tokens} tokens observed, clean)"
    )
    assert cap < proxy_required, (
        f"aggressive_debator cap {cap} has been raised to the character proxy's "
        f"{proxy_required}. That proxy divides by 3.14 chars/token, the GLOBAL "
        f"worst measured off the Portfolio Manager's JSON envelope, while this "
        f"agent's own prose runs at {chars / tokens:.2f} — so it over-states this "
        f"agent's need by ~{proxy_required / token_required:.2f}x. Sizing a prose "
        f"agent on the JSON agent's ratio is DEF289's retired 4.75 assumption "
        f"pointed the other way. If the model's output shape actually changed, "
        f"re-measure _CHARS_PER_TOKEN_WORST_CASE; do not raise this cap to match "
        f"a bound that is loose for a knowable reason."
    )


def test_no_cap_falls_back_to_the_default(corpus):
    """`max_tokens_for` falls back rather than raising, deliberately. This is
    what stops the fallback becoming permanent for an agent that speaks in the
    Room — DEF125's stated intent, asserted rather than assumed."""
    for agent in corpus:
        aid = AgentId(agent)
        assert aid in _AGENT_MAX_TOKENS, (
            f"{agent} speaks in the Room but has no explicit budget — it is streaming "
            f"at the {_DEFAULT_AGENT_MAX_TOKENS} fallback"
        )
