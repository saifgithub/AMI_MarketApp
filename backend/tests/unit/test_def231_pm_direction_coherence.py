"""DEF231 — the PM's verdict reason told the user to wait for a move the price
had already made.

Two live instances on Alpha in one afternoon, both PASS, both in
`verdict.reason` — the string CR106 renders as the decision's justification:

  * SNDK, run `ebb34135`: *"wait for the price to reclaim the 50-day range low
    of $998.19"* with the last close at $1212.21, 21% ABOVE that level. The
    Market Analyst's own turn was correct to the decimal ("the 16th percentile
    of its 50-day range") — the analyst inputs were already fixed by
    DEF227/228/229. What survived was the PM composing a *directional
    instruction* inconsistent with numbers in its own paragraph.
  * GRAB, run `8da2d287`: *"await a retest of the $3.18 support level"* while
    passing on a claimed breakdown below it.

Scope, deliberately narrow. The general form — cross-check every agent's prose
against its inputs — was rejected when this was carved out of DEF228, because
a regex that silently passes reads as coverage. This checks ONE agent, ONE
field, and compares two numbers: the level the sentence names (the only thing
parsed) against the structured `last_close` the fact sheet already carries.

"Retest" is NOT in the verb set and GRAB is therefore NOT caught — a retest can
be awaited from either side of a level, so the direction it implies is genuinely
ambiguous, and GRAB's incoherence lived in the *breakdown claim* beside it,
which is prose. That miss is asserted below rather than left to be discovered:
the precision bias is the design, and a test that pretends otherwise would be
the "coverage" claim this defect exists to avoid.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.room import VerdictAction
from app.services import room_runner
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    _DIRECTIONAL_CLAIM_RES,
    RoomRunner,
    _annotate_direction_against_price,
    _direction_contradictions,
    _reference_close,
)
from app.services.technicals import Technicals

# The SNDK run, verbatim.
_SNDK_CLOSE = 1212.21
_SNDK_RANGE_LOW = 998.19
_SNDK_REASON = (
    "PASS. SNDK is trading at the 16th percentile of its 50-day range "
    "($998.19–$2354.39) and the multiple is stretched. Wait for the price to "
    "reclaim the 50-day range low of $998.19 before revisiting the name."
)


# ── the comparison ────────────────────────────────────────────────────────────


def test_the_sndk_instruction_is_caught_with_both_numbers():
    signals = _direction_contradictions(_SNDK_REASON, _SNDK_CLOSE)
    assert len(signals) == 1
    assert signals[0]["level"] == _SNDK_RANGE_LOW
    assert signals[0]["close"] == _SNDK_CLOSE
    assert signals[0]["price_is"] == "above"
    assert signals[0]["gap_pct"] == 21.4


@pytest.mark.parametrize("reason", [
    "Wait for a pullback to $1100.00 before entry.",
    "It needs to reclaim $1300.00 to confirm the trend.",
    "A break below $1100.00 invalidates the thesis.",
    "Hold above $1100.00 and the setup stays intact.",
    "No trade — the debate did not support entry.",
])
def test_a_coherent_instruction_is_left_alone(reason):
    assert _direction_contradictions(reason, _SNDK_CLOSE) == []
    assert _annotate_direction_against_price(reason, _SNDK_CLOSE) == (reason, [])


def test_the_mirror_direction_is_caught_too():
    """Symmetry: a level the price is already below cannot be fallen back to."""
    signals = _direction_contradictions("Only a pullback to $1300.00 interests us.", _SNDK_CLOSE)
    assert len(signals) == 1
    assert signals[0]["price_is"] == "below"


def test_retest_is_deliberately_not_a_directional_verb():
    """The GRAB shape. A retest can be awaited from either side, so the verb
    states no direction to contradict — asserted so the precision bias is a
    recorded decision, not an accident that later looks like coverage."""
    assert _direction_contradictions("Await a retest of the $3.18 support level.", 3.67) == []


def test_a_price_sitting_on_the_level_is_not_a_contradiction():
    """Within the tolerance, "reclaim $X" from just under it describes the next
    move rather than one already made."""
    assert _direction_contradictions("Wait for it to reclaim $1000.00", 1005.0) == []
    assert _direction_contradictions("Wait for it to reclaim $1000.00", 1015.0) != []


def test_a_second_price_in_the_gap_is_not_attributed_to_the_verb():
    """The span between the verb and its level carries no other `$` figure, so
    a distant number further down the sentence can't be read as the level."""
    text = "Reclaim the level it lost when it broke $1500.00 on volume, versus $900.00 support."
    assert _direction_contradictions(text, _SNDK_CLOSE) == []


# ── round-1 audit MAJOR: the `$` figure must be the verb's OWN object ─────────
#
# The first cut asked only that the price sit within 45 characters of the verb,
# which is proximity, not grammar. Both sentences below are ordinary PM prose
# where the verb takes a NON-price object and an unrelated figure follows; both
# annotated a level the sentence made no directional claim about. Reproduced by
# the auditor against the real function, not hand-traced — kept verbatim.

@pytest.mark.parametrize("text,close", [
    ("The company must reclaim its margin story before we'd pay $52.30 for it.", 60.00),
    ("Sentiment could pull back toward caution before the print, last quoted at $52.30.", 45.00),
])
def test_a_verb_with_a_non_price_object_does_not_annotate(text, close):
    assert _direction_contradictions(text, close) == []
    assert _annotate_direction_against_price(text, close) == (text, [])


@pytest.mark.parametrize("text,close", [
    ("Wait for the price to reclaim the 50-day range low of $998.19 first.", 1212.21),
    ("It must recover to the $52.30 support level.", 60.00),
    ("Needs to break above the $4.06 50-day high.", 5.00),
    ("Expect it to fall back to the prior low of $900.00.", 800.00),
    ("Wait for it to reclaim $1000.00 before revisiting.", 1015.00),
])
def test_the_tightened_grammar_still_catches_every_real_level_reference(text, close):
    """The other half of the fix: a whitelist that also excluded the real
    shapes would be a silent no-op, which is worse than the false positive."""
    assert len(_direction_contradictions(text, close)) == 1


# ── round-2 audit MAJOR: two levels in one sentence ──────────────────────────
#
# The round-1 whitelist is built out of level nouns PLUS the prepositions that
# relate two levels to each other, so a sentence naming TWO levels walked the
# vocabulary end to end and attributed the second level's price to the first
# level's verb. Nothing required the captured figure to be the verb's level.
#
# Note for anyone reading this later: NONE of these three shapes appears in the
# 949-verdict Alpha corpus. A corpus sweep cannot find a false-positive class
# the corpus has not happened to produce yet — it finds coverage bugs (DEF234).
# These came from adversarial construction. The two methods catch different
# classes and neither substitutes for the other; see failure pattern P16.

@pytest.mark.parametrize("text,close", [
    ("It needs to recover to the prior high, above the recent low of $52.30.", 60.00),
    ("It needs to recover to the prior high above the recent low of $52.30.", 60.00),
    ("Reclaim the 200-day, under the recent high of $52.30.", 60.00),
])
def test_a_second_level_in_the_sentence_is_not_read_as_the_verbs_level(text, close):
    assert _direction_contradictions(text, close) == []


def test_a_preposition_adjacent_to_the_verb_is_still_part_of_the_verb_phrase():
    """The fix admits a preposition once, in the verb's own slot — `reclaim
    above $51.40` is in the corpus. It is a second preposition, deeper in the
    gap, that opens a new phrase whose level is not the verb's."""
    assert len(_direction_contradictions("it must reclaim above $51.40", 60.00)) == 1
    assert len(_direction_contradictions("a reclaim of $65 would change it", 80.00)) == 1


def test_the_real_corpus_extraction_set_is_unchanged_by_the_two_level_fix():
    """Guard on the fix: a whitelist tightened until nothing matches would pass
    every negative test above and be a silent no-op. These are the shapes the
    949-verdict Alpha corpus actually produces — sampled across all seven verb
    families — and every one must still extract its own level."""
    corpus_shapes = [
        ("break above $109.49", 100.0, 109.49),
        ("break above the $533.67", 500.0, 533.67),
        ("break below the $139.18", 150.0, 139.18),
        ("breaks above the $19.62", 18.0, 19.62),
        ("drop to the $28.98", 40.0, 28.98),
        ("drop below $22.13", 30.0, 22.13),
        ("move above $15.15", 14.0, 15.15),
        ("pullback to the $146.03", 200.0, 146.03),
        ("pullback toward the $238.82", 300.0, 238.82),
        ("pulls back to the $107.75", 150.0, 107.75),
        ("reclaim the $105.38", 90.0, 105.38),
        ("reclaiming the $534.0", 500.0, 534.0),
        ("reclaims $5.46", 4.0, 5.46),
        ("reclaim the 50-day range low of $998.19", 900.0, 998.19),
    ]
    for text, close, expected in corpus_shapes:
        # `close` is placed on the coherent side, so extraction is proven by the
        # regex finding the level at all — asserted directly, not via a fire.
        found = [
            float(m.group(1).replace(",", ""))
            for pattern, _ in _DIRECTIONAL_CLAIM_RES
            for m in pattern.finditer(text)
        ]
        assert expected in found, f"corpus shape no longer extracts its level: {text!r}"


# ── DEF234: shapes drawn from the real corpus, not from imagination ──────────
#
# Every case below came from sweeping the pattern over all 946 real PM verdict
# reasons stored on Alpha — the check that should have preceded the original
# fix rather than following it. Two holes it found, one of them severe.

def test_a_thousands_separator_no_longer_truncates_the_level():
    """`break above $1,073.46` parsed as a level of $1.00 and the check then
    announced the close was "107900.0% ABOVE $1.00". One real verdict in the
    corpus carries this shape; every four-figure price does."""
    assert _direction_contradictions("we'd want it to reclaim $1,073.46 first", 1300.00) == [
        {"claim": "reclaim $1,073.46", "level": 1073.46, "close": 1300.00,
         "gap_pct": 21.1, "price_is": "above"}
    ]
    assert _direction_contradictions("it must break above $1,073.46", 900.00) == []


def test_markdown_emphasis_around_the_level_does_not_hide_it():
    """The PM writes markdown; `break above **$27.65**` appears in the corpus.
    The round-2 whitelist rejected it — a silent coverage hole in the fix for
    the round-1 finding."""
    signals = _direction_contradictions("needs to break above **$27.65** first", 30.00)
    assert len(signals) == 1 and signals[0]["level"] == 27.65


def test_a_parenthesised_level_is_still_read():
    signals = _direction_contradictions("a drop to support ($3.81) would change this", 3.50)
    assert len(signals) == 1 and signals[0]["level"] == 3.81


def test_an_implausible_gap_is_refused_and_logged_not_rendered():
    """The backstop for the NEXT parse defect in this class. A PM does not tell
    a user to wait for a level 400× away from the price, so a gap that large is
    evidence the extraction failed — and a miss is this check's designed
    failure mode, where a confident "41566.7% ABOVE" is not."""
    assert _direction_contradictions("wait for it to reclaim $12.00", 5000.00) == []
    # ...and the same shape inside the plausible band still fires.
    assert _direction_contradictions("wait for it to reclaim $12.00", 40.00) != []


def test_the_whole_corpus_extracts_a_level_that_is_actually_a_price():
    """Guard on the guard: no extraction may yield a level whose text form was
    cut short of the digits the sentence actually wrote."""
    import re
    from app.services.room_runner import _DIRECTIONAL_CLAIM_RES
    for text, close in [
        ("break above $1,073.46 on volume", 1200.0),
        ("reclaim the $12,340.00 level", 20000.0),
    ]:
        for pattern, _ in _DIRECTIONAL_CLAIM_RES:
            for m in pattern.finditer(text):
                # the captured level must run to the end of the written number
                after = text[m.end():m.end() + 1]
                assert not re.match(r"[\d,]", after), (
                    f"level capture stopped mid-number in {text!r}: {m.group(1)!r}"
                )


def test_an_unknown_noun_between_verb_and_price_ends_the_match():
    """The mechanism, stated: the gap is a vocabulary, not a distance. One
    unrecognised word is enough to stop the match — which is why a miss is the
    failure mode and a false annotation is not."""
    assert _direction_contradictions("reclaim the momentum of $998.19", _SNDK_CLOSE) == []
    assert _direction_contradictions("reclaim the low of $998.19", _SNDK_CLOSE) != []


def test_two_different_closes_disagree_about_the_same_sentence():
    """Non-vacuity: the close reaches the comparison. Same sentence, one price
    on each side of the level — exactly one must fire."""
    fired_above = _direction_contradictions(_SNDK_REASON, _SNDK_CLOSE)
    fired_below = _direction_contradictions(_SNDK_REASON, 900.00)
    assert fired_above and not fired_below


# ── the reference price ───────────────────────────────────────────────────────


def test_no_reference_close_means_no_check_at_all():
    assert _direction_contradictions(_SNDK_REASON, None) == []
    assert _annotate_direction_against_price(_SNDK_REASON, None) == (_SNDK_REASON, [])


def test_a_last_close_with_no_recorded_provenance_is_refused():
    """CR104's gate: a profile carrying `last_close` with no live technicals
    state yields no reference price, so nothing is compared against a number of
    unknown origin — refusal is the default."""
    assert _reference_close({"last_close": 1212.21, "field_state": {}}) is None
    assert _reference_close({"last_close": 1212.21, "field_state": {"technicals": "unavailable"}}) is None
    assert _reference_close(
        {"last_close": 1212.21, "field_state": {"technicals": "live"}}
    ) == 1212.21


# ── the annotation ────────────────────────────────────────────────────────────


def test_the_annotation_states_both_numbers_and_leaves_the_sentence_standing():
    annotated, signals = _annotate_direction_against_price(_SNDK_REASON, _SNDK_CLOSE)
    assert signals
    # The PM's own sentence survives verbatim — AMI does not know what it meant
    # to say, only that the numbers don't support what it said.
    assert _SNDK_REASON in annotated
    assert "[AMI checked this instruction against the price:" in annotated
    assert "$1212.21" in annotated and "$998.19" in annotated
    assert "21.4% ABOVE" in annotated


def test_one_note_however_many_contradictions():
    text = (
        "Wait for it to reclaim $998.19, and only then for a pullback to $1300.00."
    )
    annotated, signals = _annotate_direction_against_price(text, _SNDK_CLOSE)
    assert len(signals) == 2
    assert annotated.count("[AMI checked this instruction") == 1


# ── the wiring ────────────────────────────────────────────────────────────────


class _FakeGateway:
    """Programmed per-agent replies, matched off the turn's own "Speak as the X"
    instruction (same shape as test_room_runner.py's)."""

    def __init__(self, replies: dict[str, str] | None = None):
        self._replies = replies or {}

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        agent_key = "default"
        lower = system_prompt.lower()
        for k in self._replies:
            if f"speak as the {k.replace('_', ' ')}" in lower:
                agent_key = k
                break
        yield self._replies.get(agent_key, "AMI agent live reply.")


def _collect(gen) -> list:
    async def run():
        return [ev async for ev in gen]
    return asyncio.run(run())


@pytest.fixture
def live_technicals(monkeypatch):
    """A live SNDK-shaped profile: real technicals provenance, last close above
    the 50-day range low."""
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner, "fetch_live_fundamentals", lambda t: {"base_price": 1212.21})
    monkeypatch.setattr(room_runner, "compute_technicals", lambda t: Technicals(
        rsi=44, rsi_tone="neutral", trend="consolidating", volume_tone="average",
        support=_SNDK_RANGE_LOW, breakout=2354.39, price=_SNDK_CLOSE,
    ))
    monkeypatch.setattr(room_runner, "fetch_live_news", lambda t: [])
    monkeypatch.setattr(room_runner, "fetch_live_sentiment", lambda t: None)


def _run_pm_pass(reason: str):
    # `_parse_pm_verdict` carries the PM's narration into `verdict.reason` —
    # for a PASS that IS the whole verdict, which is why both live instances
    # landed there.
    fake = _FakeGateway(replies={
        "portfolio_manager": '{"action": "PASS", "narration": %s}' % _json_str(reason),
    })
    runner = RoomRunner(llm=fake)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(), ticker="SNDK", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    return next(e.verdict for e in events if e.kind == "verdict")


def _json_str(s: str) -> str:
    import json
    return json.dumps(s)


def test_a_pass_verdict_is_annotated_end_to_end(live_technicals):
    """The check has to live on the shared verdict path: BOTH live instances
    were PASS, so hanging it off the APPROVE branch — where the R:R coherence
    check lives — would have caught neither."""
    verdict = _run_pm_pass(_SNDK_REASON)
    assert verdict.action == VerdictAction.PASS.value
    assert "[AMI checked this instruction against the price:" in verdict.reason
    assert "$1212.21" in verdict.reason


def test_a_coherent_pass_verdict_is_untouched_end_to_end(live_technicals):
    coherent = "PASS. The multiple is stretched; a pullback to $1100.00 would change that."
    verdict = _run_pm_pass(coherent)
    assert verdict.action == VerdictAction.PASS.value
    assert "[AMI" not in verdict.reason
