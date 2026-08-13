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
_CORPUS = (
    Path(__file__).resolve().parents[3]
    / "docs/forward_planning/CR143_agent_prompt_audit/corpus"
    / "llm_audit_2026-08-13-epoch.json"
)

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
