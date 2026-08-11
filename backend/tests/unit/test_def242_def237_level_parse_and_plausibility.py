"""DEF242 + DEF237 — the two halves of one failure, fixed together.

They ship as one change because the first makes the second load-bearing:
widening the number group turns more prose numerals into candidate levels, and
DEF237 is the reason a regex fix alone was never sufficient.

DEF242 — `_LEVEL_PATTERNS` still carried `(\\d+(?:\\.\\d+)?)`, the exact group
DEF234 replaced in the sibling parser five weeks earlier. It stops at the comma,
so *"Entry: $1,507.00"* parsed as an entry of **1.0**. Not a silent miss: a
fabricated level flows into `_annotate_rr_against_levels`, which renders a ratio
and a downside from it and signs them *"These are the figures of record"*.

DEF237 — that annotator had no plausibility gate of any kind. Its sibling, the
DEF231 direction check, did have one, and it only ever guarded one direction:

    gap_pct = 100 × (close − level) / level

so `abs(gap_pct) > 400` resolves to `close > 5 × level` and to nothing else. A
level far ABOVE the close never tripped it — 13.8× the close evaluates to −92.8%
and passes a 400% bound.

The threshold is DERIVED, not chosen: 5.0 is 400% restated symmetrically, so the
side that was already guarded keeps exactly its behaviour. It is deliberately
not tuned — the 216-turn epoch holds 5 full level triples, which cannot validate
a threshold (P16), and a number fitted to five examples would read as
evidence-backed while being nothing of the sort.
"""

from __future__ import annotations

import pytest

from app.services.room_runner import (
    _MAX_PLAUSIBLE_LEVEL_RATIO,
    _level_is_implausible,
    _match_level,
    _verify_and_annotate_geometry,
)


# ── DEF242: the VALUE, not merely the match ──────────────────────────────────


@pytest.mark.parametrize(
    "text,kind,expected",
    [
        # RED before: each of these separated values returned the leading group.
        ("Entry: $1,507.00", "entry", 1507.00),
        ("entry around $1,073.46", "entry", 1073.46),
        ("stop at $1,189.80", "stop", 1189.80),
        ("target $2,340.55", "target", 2340.55),
        ("target of $12,500", "target", 12500.0),
        # Unseparated values must be untouched by the widening.
        ("entry at $188.62", "entry", 188.62),
        ("stop 94", "stop", 94.0),
        ("target 115.5", "target", 115.5),
    ],
)
def test_a_separated_level_parses_to_its_own_value(text, kind, expected):
    """Asserting on the VALUE is the point. A test that only asked "did something
    match?" passed throughout the defect — `1,507.00` always matched; it just
    matched as 1.0."""
    assert _match_level(text, kind) == expected


def test_the_two_level_families_now_share_one_number_group():
    """The defect was drift between two copies. `_LEVEL_NUMBER` is defined once,
    above `_LEVEL_PATTERNS`, so a future widening cannot reach one and miss the
    other — which is how DEF234 fixed one and left this one live."""
    import app.services.room_runner as rr

    source = (rr.__file__ or "").replace(".pyc", ".py")
    with open(source, encoding="utf-8") as fh:
        body = fh.read()
    assert body.count("\n_LEVEL_NUMBER = ") == 1, "a second copy is how they drifted"


# ── DEF237: symmetric, and derived ───────────────────────────────────────────


def test_the_gate_is_symmetric():
    """The whole defect in one assertion: the same distance, both ways round,
    must be judged the same. Before, only one of these was caught."""
    close = 150.0
    far_above = close * (_MAX_PLAUSIBLE_LEVEL_RATIO + 1)
    far_below = close / (_MAX_PLAUSIBLE_LEVEL_RATIO + 1)
    assert _level_is_implausible(far_above, close) is True
    assert _level_is_implausible(far_below, close) is True


def test_the_specific_ratio_the_old_gate_let_through():
    """13.8× the close — the case named in the defect. Under `abs(gap_pct) > 400`
    this evaluated to −92.8% and passed."""
    close = 150.0
    assert _level_is_implausible(13.8 * close, close) is True


def test_ordinary_levels_are_not_touched():
    """A gate that fires on real trades is worse than no gate: it would suppress
    the verification the user is told happened."""
    close = 150.0
    for level in (150.0, 142.5, 165.0, 96.0, 115.0, 300.0, 60.0):
        assert _level_is_implausible(level, close) is False, level


@pytest.mark.parametrize("level,close", [(None, 150.0), (150.0, None), (0.0, 150.0), (150.0, 0.0)])
def test_a_missing_or_zero_input_is_a_miss_not_a_refusal(level, close):
    """Silence is the designed failure mode when there is nothing to compare
    (DEF234). Returning True here would suppress every annotation on a run whose
    technicals are not LIVE."""
    assert _level_is_implausible(level, close) is False


# ── The two together, on the shape that motivated both ───────────────────────


# CR146 measured this on NVDA: `[^\n$0-9]{0,15}` reaches past "stop-loss below
# the " and takes the "50" out of "50-day". DEF242 does not fix it — the prompt
# half is CR146 Tier A — which is precisely why DEF237 has to exist.
_MISPARSED_TRIPLE = (
    "Entry at $1,205.00, stop-loss below the 50-day low of $1,189.80, "
    "target $1,340.00."
)


def test_a_misparsed_level_is_refused_rather_than_rendered():
    """RED before: this returned an annotation reading *"11.2% upside vs 95.9%
    downside"* — a downside computed from a stop of $50 that the agent never
    proposed — signed "These are the figures of record"."""
    out, signal = _verify_and_annotate_geometry(
        _MISPARSED_TRIPLE, size_pct=3.0, reference_close=1200.0
    )
    assert out == _MISPARSED_TRIPLE, "the transcript must be returned untouched"
    assert signal is None
    assert "figures of record" not in out


def test_without_a_reference_close_it_degrades_to_the_old_behaviour():
    """`_reference_close` is gated on `field_state["technicals"] == LIVE`, so a run
    with no recorded provenance supplies None. The honest degradation is the
    pre-DEF237 behaviour, NOT a comparison against a number of unknown origin
    (CR104) — this test pins that the gate is genuinely load-bearing rather than
    something that happened to hold for another reason."""
    out, _signal = _verify_and_annotate_geometry(
        _MISPARSED_TRIPLE, size_pct=3.0, reference_close=None
    )
    assert "figures of record" in out


def test_a_coherent_triple_is_still_verified_with_a_close_present():
    """The gate must not cost the feature. A well-formed setup at a plausible
    close still gets AMI's computed geometry."""
    text = "Entry at $150.00, stop at $142.50, target at $172.00."
    out, _signal = _verify_and_annotate_geometry(
        text, size_pct=3.0, reference_close=150.0
    )
    assert "figures of record" in out
    assert "R:R" in out


def test_a_refusal_still_strikes_a_narrated_ratio():
    """The gate must not trade a fabricated AMI figure for an unmarked agent one.
    AMI renders no computed geometry here — that is the point — but a ratio the
    agent asserted is still struck as unverifiable, exactly as it is for a setup
    that does not form. Silence would leave the claim standing (CR040).

    Both real corpus hits are this shape: a PM that wrote *"the upside to the
    $524.51 target is 38.6%"* had `38.6` taken as its target, and it narrated a
    risk/reward in the same sentence."""
    text = (
        "Entry at $378.27, a 20% stop loss at $302.62, and the upside to the "
        "$524.51 target is 38.6%. R:R: 2.5:1 on this setup."
    )
    out, signal = _verify_and_annotate_geometry(
        text, size_pct=3.0, reference_close=378.0
    )
    assert "[AMI: unverifiable" in out, "an asserted ratio must not survive unmarked"
    assert "could not read a price level" in out
    assert "figures of record" not in out, "no computed figure may be rendered"
    assert signal is not None and signal["implied_rr"] == -1.0


def test_the_whole_triple_is_refused_not_partially_annotated():
    """The levels are meaningful only together — `risk_reward` needs all three —
    so salvaging the two plausible ones would compute a ratio from a set AMI has
    already decided it does not believe."""
    text = "Entry at $150.00, stop at $1.00, target at $172.00."
    out, signal = _verify_and_annotate_geometry(
        text, size_pct=3.0, reference_close=150.0
    )
    assert out == text
    assert signal is None
