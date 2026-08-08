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
field, and compares two numbers: a level THIS RUN HOLDS against the structured
`last_close` the fact sheet already carries.

"Retest" is NOT in the verb set and GRAB is therefore NOT caught — a retest can
be awaited from either side of a level, so the direction it implies is genuinely
ambiguous, and GRAB's incoherence lived in the *breakdown claim* beside it,
which is prose. That miss is asserted below rather than left to be discovered:
the precision bias is the design, and a test that pretends otherwise would be
the "coverage" claim this defect exists to avoid.

## The narrowing, and why the old tests all changed shape

The first build compared the close against ANY `$` figure a directional verb
governed. Every one of its four defects — three audit MAJORs plus DEF234, which
reached live Alpha — was a case where the captured figure was **not a level of
that run**: `we'd pay $52.30`, a second sentence's level, and `$1.00` truncated
out of `$1,073.46`. DEF231's own row had specified the narrow design and it was
not built that way; the generality was the whole defect surface.

So the figure must now match one of the levels the run actually holds, and every
test below has to say which levels those were. Two gates now have to agree, and
they are kept separate because they fail in **opposite** directions:

  * the **grammar** decides whether the figure is the verb's own object. It is
    the only thing that can stop *"recover to the prior high, above the recent
    low of $52.30"*, because $52.30 there is a perfectly real level.
  * the **structured-level match** decides whether the figure is a level of this
    run at all. It is the only thing that can stop *"we'd pay $52.30"* and
    DEF234's `$1.00`, because both are perfectly grammatical.

The round-1 and round-2 MAJOR reproductions below therefore now pass $52.30 in
as a genuine level of the run — the constructions must stay dead on the grammar
alone, with the second gate wide open. That is a strictly harder test than the
one they replaced.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas.room import Verdict, VerdictAction
from app.services import room_runner
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    _DIRECTIONAL_CLAIM_RES,
    RoomRunner,
    _annotate_direction_against_price,
    _direction_contradictions,
    _match_structured_level,
    _reference_close,
    _structured_levels,
)
from app.services.technicals import Technicals

# The SNDK run, verbatim.
_SNDK_CLOSE = 1212.21
_SNDK_RANGE_LOW = 998.19
_SNDK_RANGE_HIGH = 2354.39
_SNDK_REASON = (
    "PASS. SNDK is trading at the 16th percentile of its 50-day range "
    "($998.19–$2354.39) and the multiple is stretched. Wait for the price to "
    "reclaim the 50-day range low of $998.19 before revisiting the name."
)
_SNDK_LEVELS = [("support", _SNDK_RANGE_LOW), ("breakout", _SNDK_RANGE_HIGH)]


def _lv(*values: float) -> list[tuple[str, float]]:
    """Levels this run holds. The name only selects the phrase the annotation
    prints, so `support` stands in wherever the printed name is not asserted."""
    return [("support", v) for v in values]


# ── the comparison ────────────────────────────────────────────────────────────


def test_the_sndk_instruction_is_caught_with_both_numbers():
    signals = _direction_contradictions(_SNDK_REASON, _SNDK_CLOSE, _SNDK_LEVELS)
    assert len(signals) == 1
    assert signals[0]["level"] == _SNDK_RANGE_LOW
    assert signals[0]["level_name"] == "support"
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
    levels = _lv(1100.00, 1300.00)
    assert _direction_contradictions(reason, _SNDK_CLOSE, levels) == []
    assert _annotate_direction_against_price(reason, _SNDK_CLOSE, levels) == (reason, [])


def test_the_mirror_direction_is_caught_too():
    """Symmetry: a level the price is already below cannot be fallen back to."""
    signals = _direction_contradictions(
        "Only a pullback to $1300.00 interests us.", _SNDK_CLOSE, _lv(1300.00)
    )
    assert len(signals) == 1
    assert signals[0]["price_is"] == "below"


def test_retest_is_deliberately_not_a_directional_verb():
    """The GRAB shape. A retest can be awaited from either side, so the verb
    states no direction to contradict — asserted so the precision bias is a
    recorded decision, not an accident that later looks like coverage."""
    assert _direction_contradictions(
        "Await a retest of the $3.18 support level.", 3.67, _lv(3.18)
    ) == []


def test_a_price_sitting_on_the_level_is_not_a_contradiction():
    """Within the tolerance, "reclaim $X" from just under it describes the next
    move rather than one already made."""
    assert _direction_contradictions("Wait for it to reclaim $1000.00", 1005.0, _lv(1000.0)) == []
    assert _direction_contradictions("Wait for it to reclaim $1000.00", 1015.0, _lv(1000.0)) != []


def test_a_second_price_in_the_gap_is_not_attributed_to_the_verb():
    """The span between the verb and its level carries no other `$` figure, so
    a distant number further down the sentence can't be read as the level."""
    text = "Reclaim the level it lost when it broke $1500.00 on volume, versus $900.00 support."
    assert _direction_contradictions(text, _SNDK_CLOSE, _lv(1500.00, 900.00)) == []


# ── round-1 audit MAJOR: the `$` figure must be the verb's OWN object ─────────
#
# The first cut asked only that the price sit within 45 characters of the verb,
# which is proximity, not grammar. Both sentences below are ordinary PM prose
# where the verb takes a NON-price object and an unrelated figure follows; both
# annotated a level the sentence made no directional claim about. Reproduced by
# the auditor against the real function, not hand-traced — kept verbatim.
#
# $52.30 is now passed in AS A LEVEL OF THE RUN, so the structured-level gate is
# deliberately open and only the grammar can hold these. That is the harder
# version of the original assertion, not a weaker one.

@pytest.mark.parametrize("text,close", [
    ("The company must reclaim its margin story before we'd pay $52.30 for it.", 60.00),
    ("Sentiment could pull back toward caution before the print, last quoted at $52.30.", 45.00),
])
def test_a_verb_with_a_non_price_object_does_not_annotate(text, close):
    levels = _lv(52.30)
    assert _direction_contradictions(text, close, levels) == []
    assert _annotate_direction_against_price(text, close, levels) == (text, [])


@pytest.mark.parametrize("text,close,level", [
    ("Wait for the price to reclaim the 50-day range low of $998.19 first.", 1212.21, 998.19),
    ("It must recover to the $52.30 support level.", 60.00, 52.30),
    ("Needs to break above the $4.06 50-day high.", 5.00, 4.06),
    ("Expect it to fall back to the prior low of $900.00.", 800.00, 900.00),
    ("Wait for it to reclaim $1000.00 before revisiting.", 1015.00, 1000.00),
])
def test_the_tightened_grammar_still_catches_every_real_level_reference(text, close, level):
    """The other half of the fix: a whitelist that also excluded the real
    shapes would be a silent no-op, which is worse than the false positive."""
    assert len(_direction_contradictions(text, close, _lv(level))) == 1


# ── round-2 audit MAJOR: two levels in one sentence ──────────────────────────
#
# The round-1 whitelist is built out of level nouns PLUS the prepositions that
# relate two levels to each other, so a sentence naming TWO levels walked the
# vocabulary end to end and attributed the second level's price to the first
# level's verb. Nothing required the captured figure to be the verb's level.
#
# This is the class the structured-level gate CANNOT help with — the second
# level is a real level — so $52.30 is passed in as one, and the grammar is
# left to hold the line alone.
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
    assert _direction_contradictions(text, close, _lv(52.30)) == []


def test_a_preposition_adjacent_to_the_verb_is_still_part_of_the_verb_phrase():
    """The fix admits a preposition once, in the verb's own slot — `reclaim
    above $51.40` is in the corpus. It is a second preposition, deeper in the
    gap, that opens a new phrase whose level is not the verb's."""
    assert len(_direction_contradictions("it must reclaim above $51.40", 60.00, _lv(51.40))) == 1
    assert len(_direction_contradictions("a reclaim of $65 would change it", 80.00, _lv(65.0))) == 1


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
    assert _direction_contradictions(
        "we'd want it to reclaim $1,073.46 first", 1300.00, _lv(1073.46)
    ) == [
        {"claim": "reclaim $1,073.46", "level": 1073.46, "level_name": "support",
         "quoted": 1073.46, "close": 1300.00, "gap_pct": 21.1, "price_is": "above"}
    ]
    assert _direction_contradictions(
        "it must break above $1,073.46", 900.00, _lv(1073.46)
    ) == []


def test_markdown_emphasis_around_the_level_does_not_hide_it():
    """The PM writes markdown; `break above **$27.65**` appears in the corpus.
    The round-2 whitelist rejected it — a silent coverage hole in the fix for
    the round-1 finding."""
    signals = _direction_contradictions(
        "needs to break above **$27.65** first", 30.00, _lv(27.65)
    )
    assert len(signals) == 1 and signals[0]["level"] == 27.65


def test_a_parenthesised_level_is_still_read():
    signals = _direction_contradictions(
        "a drop to support ($3.81) would change this", 3.50, _lv(3.81)
    )
    assert len(signals) == 1 and signals[0]["level"] == 3.81


def test_an_implausible_gap_is_refused_and_logged_not_rendered():
    """The backstop for the NEXT parse defect in this class. A PM does not tell
    a user to wait for a level 400× away from the price, so a gap that large is
    evidence the extraction failed — and a miss is this check's designed
    failure mode, where a confident "41566.7% ABOVE" is not.

    Reaching it now needs a run whose own level is absurd against its own close,
    which is a different bug again; the backstop stays because the cost of
    keeping it is one comparison and the cost of not having it is DEF234."""
    assert _direction_contradictions("wait for it to reclaim $12.00", 5000.00, _lv(12.00)) == []
    # ...and the same shape inside the plausible band still fires.
    assert _direction_contradictions("wait for it to reclaim $12.00", 40.00, _lv(12.00)) != []


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
    levels = _lv(_SNDK_RANGE_LOW)
    assert _direction_contradictions("reclaim the momentum of $998.19", _SNDK_CLOSE, levels) == []
    assert _direction_contradictions("reclaim the low of $998.19", _SNDK_CLOSE, levels) != []


def test_two_different_closes_disagree_about_the_same_sentence():
    """Non-vacuity: the close reaches the comparison. Same sentence, one price
    on each side of the level — exactly one must fire."""
    fired_above = _direction_contradictions(_SNDK_REASON, _SNDK_CLOSE, _SNDK_LEVELS)
    fired_below = _direction_contradictions(_SNDK_REASON, 900.00, _SNDK_LEVELS)
    assert fired_above and not fired_below


# ── the narrowing: the figure must be a level THIS RUN holds ─────────────────
#
# The gate DEF231's row asked for and the first build did not have. Each case
# below is one of the four defects the general version shipped, re-run with the
# grammar removed from the picture — the sentence is impeccable, and it is the
# match that refuses.


def test_a_figure_that_is_not_a_level_of_this_run_is_never_annotated():
    """The class, in one assertion. Same sentence, same close; the only thing
    that changes is whether the run holds that level."""
    text = "Wait for the price to reclaim the 50-day range low of $998.19."
    assert _direction_contradictions(text, _SNDK_CLOSE, _SNDK_LEVELS) != []
    # A run whose 50-day low is somewhere else entirely: nothing to compare.
    assert _direction_contradictions(text, _SNDK_CLOSE, _lv(1050.00, 2354.39)) == []


def test_def234_could_not_have_shipped_through_this_gate():
    """`$1,073.46` truncated to `$1.00` reached live Alpha and rendered
    "107900.0% ABOVE $1.00". A mis-parse produces a number no run holds, so the
    match refuses before the arithmetic is ever done — the implausible-gap
    backstop is not what stops it here, and does not have to be."""
    assert _direction_contradictions(
        "we'd want it to reclaim $1,073.46 first", 1300.00, _lv(950.00)
    ) == []


def test_a_round_number_the_pm_invented_is_out_of_scope_and_that_is_the_cost():
    """The measured price of the narrowing, asserted rather than left implicit.
    A PM that writes "wait for a break above $100" when the price is $120 IS
    incoherent, and AMI now says nothing, because $100 is not a level it handed
    anyone and AMI cannot tell an invented round number from a mis-parse. A
    silent miss is this check's designed failure mode; a confident annotation
    about a number of unknown origin is the one it must never have."""
    assert _direction_contradictions(
        "wait for a break above $100 before revisiting", 120.00, _lv(104.20, 131.00)
    ) == []


def test_no_structured_level_means_no_check_at_all():
    """A run with a live close but no level — technicals live, 52-week
    placeholder, PASS verdict — has nothing to compare against, so it is not
    checked. Refusal is the default (CR104)."""
    assert _direction_contradictions(_SNDK_REASON, _SNDK_CLOSE, []) == []
    assert _annotate_direction_against_price(_SNDK_REASON, _SNDK_CLOSE, []) == (_SNDK_REASON, [])


@pytest.mark.parametrize("quoted,expected", [
    (998.19, "support"),    # exact, as the fact sheet rendered it
    (998.2, "support"),     # the PM dropped a decimal
    (998.0, "support"),     # ...and then the rest
    (1000.00, "support"),   # ...and rounded to the round number, 0.18% away
    (2354.39, "breakout"),
    (998.19 * 1.004, "support"),   # inside the band
    (998.19 * 1.006, None),        # outside it
    (1010.00, None),               # 1.2% away is a different number
])
def test_the_match_band_is_rounding_wide_and_no_wider(quoted, expected):
    matched = _match_structured_level(quoted, _SNDK_LEVELS)
    assert (matched[0] if matched else None) == expected


def test_a_match_inside_the_band_can_never_flip_the_direction():
    """Why the band is half the coherence tolerance rather than equal to it.

    It is NOT what makes the direction safe — `gap_pct` is computed from the
    close and the matched run's own level, and never reads the quoted figure,
    so the PM's rounding cannot reach the verdict by any path (round-5 auditor's
    correction to this docstring; the proof answers a narrower question than the
    original wording implied). What the ordering buys is that the level AMI
    NAMES sits on the same side of the close as the number the PM wrote, so the
    note can substitute one for the other without describing a different
    situation. Asserted on the worst case — the quoted number pushed to the far
    edge of the band, straddling the close."""
    close = 1000.00
    level = 1004.00                      # 0.4% above the close
    quoted = level * 0.995               # 998.98 — below the close, other side
    assert _match_structured_level(quoted, [("support", level)]) == ("support", level)
    # ...and the pair is inside the coherence tolerance, so nothing is said.
    assert _direction_contradictions(
        f"wait for it to reclaim ${quoted:.2f}", close, [("support", level)]
    ) == []
    # A level far enough from the close to fire is far enough that every figure
    # the band admits sits on the same side of it.
    signals = _direction_contradictions(
        "wait for it to reclaim $1000.00", 1212.21, [("support", 998.19)]
    )
    assert len(signals) == 1 and signals[0]["price_is"] == "above"


def test_a_low_priced_name_cannot_round_its_way_into_a_match():
    """The band is relative, so it does not widen on cheap tickers. GRAB's
    support is $3.18; "$3" is 5.7% away and is not a quote of it, even though
    it is what `round()` would produce."""
    assert _match_structured_level(3.0, _lv(3.18)) is None


def test_the_arithmetic_uses_the_runs_number_not_the_quoted_one():
    """Once matched, the level AMI holds is the one it reports and computes
    from — the PM's rounding never reaches the user's screen as a figure of
    record."""
    signals = _direction_contradictions(
        "wait for it to reclaim $998.2", _SNDK_CLOSE, _SNDK_LEVELS
    )
    assert len(signals) == 1
    assert signals[0]["level"] == _SNDK_RANGE_LOW   # 998.19, not 998.2
    assert signals[0]["quoted"] == 998.2


def test_the_closest_level_wins_when_two_are_within_the_band():
    assert _match_structured_level(
        100.10, [("support", 100.00), ("stop", 100.20), ("entry", 140.00)]
    ) == ("stop", 100.20)


# ── the verb families the offline LLM sweep found (AT:R66) ───────────────────
#
# The bake-off in this defect's audit lane disqualified the LLM at RUNTIME —
# regex 10/10 to its 8/10 on constructed cases, failing on exactly the two audit
# MAJORs, and mostly fabricating on real verdicts. Its one advantage was RECALL,
# so it was run offline over the 692 verdicts carrying a `$` from which the
# pattern extracted nothing, purely as a lead generator. 373 claimed leads,
# clustered by shape and hand-read; three families survived.
#
# Every case below is a real corpus sentence, trimmed. `breakout above` alone
# contributes 159 of the fixture's 365 extractions — more than the entire
# previous verb set — because it is how the PM most often states a level.

@pytest.mark.parametrize("text,close,level,fires", [
    # "breakout" as a noun. The pre-existing rule matches "break out above" but
    # a \b after `break` stops one letter short of the one-word form.
    ("wait for a confirmed breakout above $236.26 on rising volume", 250.00, 236.26, True),
    ("wait for a confirmed breakout above $236.26 on rising volume", 200.00, 236.26, False),
    ("waiting for the $94.43 support retest or a breakout to $135.16", 150.00, 135.16, True),
    # "close above" / "close below".
    ("we hold cash until a decisive close above $244.07 validates it", 260.00, 244.07, True),
    ("we hold cash until a decisive close above $244.07 validates it", 230.00, 244.07, False),
    ("I will only reconsider this trade if price closes above $25.67", 30.00, 25.67, True),
    ("a daily close below $12.10 invalidates the thesis", 11.00, 12.10, True),
    # "clears".
    ("no entry until price clears the $23.67 breakout resistance", 26.00, 23.67, True),
    ("we will re-evaluate only if price clears $236.26 with volume", 200.00, 236.26, False),
])
def test_the_families_the_offline_sweep_found(text, close, level, fires):
    signals = _direction_contradictions(text, close, _lv(level))
    assert bool(signals) is fires
    if fires:
        assert signals[0]["level"] == level


@pytest.mark.parametrize("text", [
    # Stop placements. A stop is where the trade exits, not somewhere the price
    # is being told to go — and the PM writes these constantly.
    "a hard stop at $52.30 protects the position",
    "the stop loss is widened to $52.30 to survive the print",
    "tightening the stop to $52.30 after the run",
    # Entry statements. Same reasoning: a price you would transact at is not a
    # directional claim about where the price must travel.
    "entering at $52.30 risks immediate multiple compression",
    "raise the entry trigger to $52.30",
    "a limit entry at $52.30 keeps the risk defined",
    # The GRAB shape, still deliberately out (a retest is awaited from either
    # side), and still asserted now that the verb set has grown.
    "wait for a retest of $52.30 support",
    # Past tense: a claim about history, not an unmet condition. Comparing it to
    # the LAST close would frame "it closed above $X in June" as an instruction.
    "the stock closed above $52.30 in June before fading",
])
def test_what_the_sweep_proposed_and_was_rejected_on_reading(text):
    """The leads the LLM produced that did NOT become verbs, pinned so a later
    pass cannot quietly adopt them. An unread lead list would have encoded every
    one of these — which is the whole reason the LLM is a lead generator here
    and not an answer."""
    assert _direction_contradictions(text, 60.00, _lv(52.30)) == []
    assert _direction_contradictions(text, 45.00, _lv(52.30)) == []


def test_a_pm_can_name_the_verdicts_own_levels_in_its_own_words():
    """Round-5 MINOR. `_structured_levels` made entry/stop/target candidate
    levels, but `_LEVEL_NOUN` had no words for them, so a plain sentence naming
    one never matched at all — a gap this change's own predecessor created.
    Adding the three nouns moves the extraction set over all 811 corpus rows by
    exactly zero, so it costs none of the precision the whitelist buys."""
    assert len(_direction_contradictions(
        "Reclaim the entry of $52.30 before we add.", 60.00, [("entry", 52.30)]
    )) == 1
    assert len(_direction_contradictions(
        "A break below the stop of $52.30 ends it.", 45.00, [("stop", 52.30)]
    )) == 1
    assert len(_direction_contradictions(
        "Wait for a pullback to the target of $52.30.", 45.00, [("target", 52.30)]
    )) == 1
    # Still refused, and deliberately: `break below` already carries its
    # preposition, so round 4's fix withholds the gap's own preposition slot and
    # `at` ends the match. That rule exists because the two never legitimately
    # compose (`break above near the recent low of $X`), and it is not worth
    # reopening for a phrasing with zero corpus support — the designed failure
    # mode is a miss.
    assert _direction_contradictions(
        "A break below the stop at $52.30 ends it.", 45.00, [("stop", 52.30)]
    ) == []


def test_a_comma_chain_of_level_nouns_is_apposition_not_a_second_referent():
    """The property the round-5 auditor established with four constructions, and
    the reason it is a design property rather than luck.

    English builds a genuine second referent with a conjunction ("the range low
    AND the range high of $X") or a preposition ("the range low, ABOVE the range
    high of $X"). `and`/`or` were never in `_LEVEL_NOUN`, and round 2's fix
    blocks a second preposition — so the only chains the vocabulary can walk are
    bare comma-appositions, where the trailing clauses re-describe the SAME
    thing the figure names. Both mechanisms are asserted, so adding a conjunction
    to the vocabulary later fails here rather than silently reopening round 2."""
    levels = [("support", 900.00), ("breakout", 52.30)]
    # Apposition: fires, and correctly — one referent, redundantly worded.
    assert len(_direction_contradictions(
        "Reclaim the range low, the key level of $52.30.", 60.00, levels
    )) == 1
    # A conjunction asserts two referents; the vocabulary cannot cross it.
    assert _direction_contradictions(
        "Reclaim the range low and the range high of $52.30.", 60.00, levels
    ) == []
    # A second preposition opens a new phrase; round 2's fix ends the match.
    assert _direction_contradictions(
        "Reclaim the range low, above the range high of $52.30.", 60.00, levels
    ) == []


def test_bare_clear_is_an_adjective_and_is_not_a_verb_here():
    assert _direction_contradictions(
        "a clear $52.30 discount to peers", 60.00, _lv(52.30)
    ) == []
    assert _direction_contradictions(
        "until price clears $52.30", 60.00, _lv(52.30)
    ) != []


# Round-6 audit MAJOR. `clear` is the only verb in the family that is ambiguous
# about WHETHER a price claim is being made at all — "the company clears $X in
# FCF" is about profit, not direction. The gap grammar cannot separate the two
# senses (both run straight from verb to `$`), so the discriminator is the
# subject. Each case below fired before the fix and rendered a confident
# directional note on the Verdict Board about a number that was never a price.
@pytest.mark.parametrize("text", [
    # The auditor's five, verbatim.
    "The company clears $52.30 million in annual free cash flow, well above peers.",
    "Management clears $52.30 per share in normalized earnings this year.",
    "The fund manager clears $52.30 billion in assets under management.",
    "The position clears $52.30 in unrealized profit at current levels.",
    "Net of fees the trader clears $52.30 on this position.",
    # Mine, to show the class is closed by the subject and not by a suffix gate:
    # none of these carries `million`/`per share`/`in <noun>` after the figure.
    "The trader's position clears $52.30 net of fees.",
    "Free cash flow clears $52.30 per share.",
])
def test_clear_does_not_fire_on_the_earnings_sense_of_the_verb(text):
    assert _direction_contradictions(text, 60.00, _lv(52.30)) == []


@pytest.mark.parametrize("text", [
    # Every price-sense subject the 811-row corpus actually attests.
    "no entry until price clears the $52.30 breakout resistance",
    "we hold until price action clears the $52.30 level",
    "capital preserved until the stock clears the $52.30 breakout level",
    "we wait for a confirmed breakout clears the $52.30 level",
])
def test_clear_still_fires_on_the_price_sense(text):
    assert _direction_contradictions(text, 60.00, _lv(52.30)) != []


def test_clear_with_an_elided_subject_is_a_deliberate_miss():
    """The one extraction the round-6 fix gives up, recorded so it cannot be
    "fixed" by accident. The subject is `price`, six words back across a
    coordinating conjunction. Admitting a bare `or clears` to recover it would
    re-open the entire agent-subject class ("the company earns X and clears
    $52.30 million"), which is the defect this test file's parametrized case
    above exists to hold closed. A miss costs nothing here."""
    assert _direction_contradictions(
        "We adhere to WAIT until price corrects toward the $50.00 support level "
        "or clears the $52.30 breakout.",
        60.00, _lv(52.30),
    ) == []


# ── which levels a run holds ──────────────────────────────────────────────────


def _pass() -> Verdict:
    return Verdict(action=VerdictAction.PASS, reason="x")


def _approve(**kw) -> Verdict:
    return Verdict(action=VerdictAction.APPROVE, reason="x", **kw)


def test_technicals_supply_the_range_only_when_their_provenance_is_live():
    profile = {"support": 998.19, "breakout": 2354.39, "last_close": 1212.21}
    assert _structured_levels(
        {**profile, "field_state": {"technicals": "live"}}, _pass()
    ) == _SNDK_LEVELS
    assert _structured_levels({**profile, "field_state": {"technicals": "unavailable"}}, _pass()) == []
    assert _structured_levels({**profile, "field_state": {}}, _pass()) == []


def test_the_52_week_range_needs_its_own_state_because_of_the_placeholder():
    """`fetch_live_fundamentals` substitutes a ±5% band off price when the real
    `fiftyTwoWeek*` fields are missing. That placeholder is a derived guess, not
    a level anyone was shown, and `field_state["week52"]` is the only thing that
    tells them apart."""
    profile = {"low": 900.00, "high": 2400.00}
    assert _structured_levels({**profile, "field_state": {"week52": "live"}}, _pass()) == [
        ("low", 900.00), ("high", 2400.00),
    ]
    assert _structured_levels({**profile, "field_state": {"week52": "unavailable"}}, _pass()) == []


def test_the_last_close_is_the_reference_not_a_candidate_level():
    levels = _structured_levels(
        {"support": 998.19, "breakout": 2354.39, "last_close": 1212.21,
         "field_state": {"technicals": "live"}}, _pass(),
    )
    assert "last_close" not in dict(levels)


def test_verdict_prices_count_only_on_an_approve():
    profile = {"field_state": {}}
    assert _structured_levels(profile, _pass()) == []
    assert dict(_structured_levels(
        profile, _approve(entry=100.0, stop=94.0, target=113.0)
    )) == {"entry": 100.0, "stop": 94.0, "target": 113.0}


def test_a_level_ami_minted_after_the_pm_finished_writing_is_not_a_candidate():
    """CR106 B1's provenance, used as a gate. The PM cannot have been quoting a
    stop AMI derived from its entry after the fact, so letting `ami_default`
    stand as a candidate would only ever admit a coincidence."""
    verdict = _approve(
        entry=100.0, stop=94.0, target=113.0,
        level_provenance={"entry": "pm", "stop": "ami_default", "target": "ami_default"},
    )
    assert dict(_structured_levels({"field_state": {}}, verdict)) == {"entry": 100.0}


def test_a_run_predating_the_provenance_field_keeps_its_prices():
    """`level_provenance` is None on older runs and that means "unknown", not
    "all minted" (CR106 T-BACKFILL). Dropping every price on those runs would
    silently disable the check for them."""
    assert dict(_structured_levels(
        {"field_state": {}}, _approve(entry=100.0, stop=94.0)
    )) == {"entry": 100.0, "stop": 94.0}


def test_a_non_positive_or_unparseable_level_is_not_a_candidate():
    assert _structured_levels(
        {"support": 0.0, "breakout": None, "field_state": {"technicals": "live"}}, _pass()
    ) == []


# ── the reference price ───────────────────────────────────────────────────────


def test_no_reference_close_means_no_check_at_all():
    assert _direction_contradictions(_SNDK_REASON, None, _SNDK_LEVELS) == []
    assert _annotate_direction_against_price(_SNDK_REASON, None, _SNDK_LEVELS) == (_SNDK_REASON, [])


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
    annotated, signals = _annotate_direction_against_price(
        _SNDK_REASON, _SNDK_CLOSE, _SNDK_LEVELS
    )
    assert signals
    # The PM's own sentence survives verbatim — AMI does not know what it meant
    # to say, only that the numbers don't support what it said.
    assert _SNDK_REASON in annotated
    assert "[AMI checked this instruction against the price:" in annotated
    assert "$1212.21" in annotated and "$998.19" in annotated
    assert "21.4% ABOVE" in annotated


def test_the_annotation_names_the_level_it_matched():
    """Knowing WHICH level was quoted is the dividend of matching against the
    run's own numbers: the note stops saying "some price you wrote" and starts
    saying "the range low we handed you"."""
    annotated, _ = _annotate_direction_against_price(_SNDK_REASON, _SNDK_CLOSE, _SNDK_LEVELS)
    assert "the 50-day range low ($998.19)" in annotated

    annotated, _ = _annotate_direction_against_price(
        "wait for it to reclaim $94.00", 120.00,
        [("stop", 94.00)],
    )
    assert "this verdict's stop ($94.00)" in annotated


def test_one_note_however_many_contradictions():
    text = (
        "Wait for it to reclaim $998.19, and only then for a pullback to $1300.00."
    )
    annotated, signals = _annotate_direction_against_price(
        text, _SNDK_CLOSE, _lv(998.19, 1300.00)
    )
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
        support=_SNDK_RANGE_LOW, breakout=_SNDK_RANGE_HIGH, price=_SNDK_CLOSE,
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
    assert "the 50-day range low ($998.19)" in verdict.reason
    assert "$1212.21" in verdict.reason


def test_a_coherent_pass_verdict_is_untouched_end_to_end(live_technicals):
    coherent = "PASS. The multiple is stretched; a pullback to $1100.00 would change that."
    verdict = _run_pm_pass(coherent)
    assert verdict.action == VerdictAction.PASS.value
    assert "[AMI" not in verdict.reason


def test_an_instruction_about_a_level_this_run_does_not_hold_is_left_alone(live_technicals):
    """End-to-end proof that the narrowing reaches the wired path, using the
    exact number DEF234 shipped. $1,073.46 sits between SNDK's range low and
    high and 13% below its close, so the old build would have annotated it; this
    run holds $998.19 and $2354.39 and nothing else, so AMI says nothing."""
    reason = "PASS. We'd want it to reclaim $1,073.46 before revisiting the name."
    verdict = _run_pm_pass(reason)
    assert verdict.action == VerdictAction.PASS.value
    assert "[AMI" not in verdict.reason
