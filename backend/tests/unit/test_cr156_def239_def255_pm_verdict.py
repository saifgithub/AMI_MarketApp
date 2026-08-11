"""DEF239 · CR156 B · DEF255 · CR156 D — the Portfolio Manager.

Four findings against the one agent whose output is parsed back into a
structured `Verdict` and rendered on the Verdict Board as the decision's
justification.

**DEF239 (≡ CR156 A2)** — `_parse_pm_verdict` read `narration` and nothing else,
so a verdict whose prose arrived under any other key published *"it wrote no
rationale"* over real sentences. `narrational` is not a hypothetical: it is what
the model emitted on live Alpha, SLB, 2026-08-11 11:27:36Z, in the same verdict
that exposed DEF258.

**CR156 B** — `_PM_VERDICT_FORMAT` says *"There are exactly two action values:
APPROVE and PASS"* while the Decision sequence three lines above it said REJECT,
in two separate layers. The parser survived (`_normalize_pm_action` maps
REJECT→PASS); the USER did not — the wire action colours the card and the prose
is what they read, so a card marked PASS carried a narration opening "REJECT:".
Measured 4 of 14 on the 2026-08-11 post-promotion batch.

**DEF255** — `horizon_days` is the THESIS horizon, not the mandate's investment
horizon. The PM emitted `1095` (the `Horizon.LONG` label restated as a number)
in 4 of 13 approvals while the code's own fallback for the same field is 42
days: a 26× disagreement inside one field, and the number the stop is judged
against.

**CR156 D** — `safety_floor.md` claimed the floor is last and therefore
dominant. True on the 1-on-1 path; false in the Room, where
`system_prompt = base + room_addition` renders the entire CONVENE block after
it. Documented, not reordered — ordering was never the control.
"""

from __future__ import annotations

import pytest

from app.schemas.mandate import Mandate
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    _MAX_EVIDENCED_HORIZON_DAYS,
    _PM_NO_RATIONALE,
    _RoomContext,
    _horizon_coherence_note,
    _parse_pm_verdict,
    _pm_narration,
)


def _ctx(mandate: Mandate | None = None) -> _RoomContext:
    return _RoomContext(
        ticker="AAPL",
        mandate=mandate or hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


# ── DEF239 — the rationale is read from whichever contracted key carries it ───


@pytest.mark.parametrize(
    "key", ["narration", "narrational", "rationale", "reasoning", "reason", "explanation"]
)
def test_the_rationale_is_found_under_any_contracted_key(key):
    assert _pm_narration({key: "The synthesis holds at reduced size."}) == (
        "The synthesis holds at reduced size."
    )


def test_narration_wins_when_more_than_one_key_carries_prose():
    """`narration` is what the contract asks for, so it takes precedence rather
    than whichever key happens to be first in the dict."""
    assert _pm_narration({"reason": "second", "narration": "first"}) == "first"


def test_the_live_narrational_typo_no_longer_loses_the_rationale():
    """The SLB regression: real prose published as "it wrote no rationale"."""
    raw = '{"action": "PASS", "narrational": "REJECT: the stop sits above the 50-day."}'
    display, verdict = _parse_pm_verdict(raw, _ctx())
    assert verdict is not None
    assert "the stop sits above the 50-day" in display
    assert _PM_NO_RATIONALE not in display


def test_the_no_rationale_disclosure_still_fires_when_nothing_carries_prose():
    """DEF232's disclosure must survive. This is why the fix is an explicit
    allowlist and NOT a scrape of any string field — scraping would render
    `{"ticker": "AAPL"}` as a defence, destroying the one signal that tells a
    user the decision was never explained."""
    raw = '{"action": "PASS", "ticker": "AAPL", "size_pct": null}'
    display, verdict = _parse_pm_verdict(raw, _ctx())
    assert verdict is not None
    assert display == _PM_NO_RATIONALE


def test_a_non_string_value_under_a_narration_key_is_not_prose():
    assert _pm_narration({"narration": 42}) == ""
    assert _pm_narration({"narration": {"text": "nested"}}) == ""
    assert _pm_narration({"narration": "   "}) == ""


# ── DEF255 — the horizon and the stop must be the same trade ─────────────────


def test_a_horizon_beyond_every_input_is_flagged():
    """1095 days against 3 months of history, TTM fundamentals and a 52-week
    range — the widest window on the sheet is 365 days."""
    note = _horizon_coherence_note(1095, entry=100.0, stop=94.0)
    assert "1095 days reaches beyond every input" in note
    assert "3 months of price history, TTM fundamentals and a 52-week range" in note
    assert "6.0% below entry" in note
    # The two clauses join cleanly — the stop clause replaces the first
    # sentence's terminator rather than following it.
    assert "long., and" not in note
    assert "that long, and the exit" in note


def test_the_stop_clause_states_the_pairing_and_predicts_nothing():
    """DEF267 — it used to assert the OUTCOME: "a weeks-to-months instrument —
    over that horizon ordinary volatility would take the position out". That
    fired on any stop below entry with no bound on the distance, so the same
    prediction was made for a 1.9% stop and a 90% one, and the stack renders no
    volatility at all (CR146 Tier A deleted the ATR/stdev demands because
    nothing supplies them). The repo's standard for this class is the sibling
    annotator's, recorded after DEF240's round-1 audit: state what happened,
    never an evaluative outcome."""
    note = _horizon_coherence_note(900, entry=46.13, stop=45.26)
    for banned in (
        "weeks-to-months instrument",
        "ordinary volatility",
        "would take the position out",
        "long before the thesis could be judged",
    ):
        assert banned not in note, f"still predicting an outcome: {banned!r}"
    assert "1.9% below entry" in note
    assert "closes on a 1.9% move against it" in note


@pytest.mark.parametrize(
    "entry,stop,expected",
    [
        (46.13, 45.26, "1.9%"),   # the live minimum the auditor measured
        (100.0, 94.0, "6.0%"),
        (100.0, 84.2, "15.8%"),   # the live maximum
        (100.0, 10.0, "90.0%"),
    ],
)
def test_the_printed_distance_is_the_real_one(entry, stop, expected):
    """MUT-5 survived the first cut: hardcoding the distance to 6.0 left 142
    tests green, because nothing tied the printed figure to the actual stop.
    The live spread was 1.9%–15.8% across 7 of 25 approvals, so a single fixture
    could never have caught it."""
    note = _horizon_coherence_note(900, entry=entry, stop=stop)
    assert f"{expected} below entry" in note
    assert f"closes on a {expected} move against it" in note


def test_a_horizon_inside_the_evidence_is_not_flagged():
    assert _horizon_coherence_note(42, entry=100.0, stop=94.0) == ""
    assert _horizon_coherence_note(_MAX_EVIDENCED_HORIZON_DAYS, 100.0, 94.0) == ""


def test_the_boundary_is_derived_from_the_widest_window_on_the_sheet():
    """365 = the 52-week range, the longest-dated evidence the PM is given.
    Stated as a boundary the EVIDENCE supports — never as a rule about how long
    anyone should hold, which would be advice."""
    assert _MAX_EVIDENCED_HORIZON_DAYS == 365


def test_the_stop_clause_is_omitted_when_there_is_no_stop_to_reason_about():
    """No minted stop, no claim about it."""
    note = _horizon_coherence_note(1095, entry=None, stop=None)
    assert "reaches beyond every input" in note
    assert "below-entry stop" not in note


def test_an_incoherent_horizon_flags_but_never_vetoes():
    """The safety floor is the sole vetoer (DEF059). An incoherent horizon is a
    reasoning flaw to disclose, not a mandate violation to block on — turning it
    into a veto would discard a real verdict over its arithmetic."""
    raw = (
        '{"action": "APPROVE", "size_pct": 2.0, "entry": 100.0, "stop": 94.0, '
        '"target": 113.0, "horizon_days": 1095, "narration": "Long thesis."}'
    )
    _display, verdict = _parse_pm_verdict(raw, _ctx())
    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE
    assert "reaches beyond every input" in verdict.reason


# ── CR156 B — the two-action vocabulary, reconciled across every layer ───────


def _pm_prompt():
    from app.schemas import AgentId
    from app.services.room_prompts import build_room_messages

    sp, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=None, ticker="AAPL", profile={"field_state": {}}, transcript=[],
    )
    return sp


def test_no_layer_tells_the_pm_to_issue_a_reject():
    """Three layers carried REJECT against a format stating two action values.
    The parser mapped it to PASS and the user read the contradiction."""
    sp = _pm_prompt()
    for banned in (
        "If compliance fails → REJECT",
        "If any compliance violation: REJECT",
        "**APPROVE**, **REJECT**, or **MODIFY-AND-APPROVE**",
        "Issue: APPROVE / REJECT / MODIFY-AND-APPROVE",
    ):
        assert banned not in sp, f"a layer still instructs REJECT: {banned!r}"


def test_the_replaces_sentence_now_names_the_decision_sequence():
    """It covered the output BLOCK only, which is why the decision sequence
    three lines above kept contradicting it."""
    sp = _pm_prompt()
    assert "'Decision sequence'" in sp
    assert "the action you emit here is PASS" in sp


def test_the_modify_vocabulary_survives():
    """`test_room_prompt_parity.py:68` is a deliberate canary — "if this ever
    disappears, revisit the profile too". MODIFY-AND-APPROVE maps to APPROVE and
    was never the problem, so it is kept and the canary stays green WITHOUT
    being edited. Only REJECT moved."""
    assert "MODIFY" in _pm_prompt()


def test_the_one_on_one_output_format_block_is_not_deleted():
    """`agent_runner.py` builds the PM's 1-on-1 prompt with NO
    `_PM_VERDICT_FORMAT`, so that block is the only format instruction it has
    there. Delete it and the 1-on-1 PM is un-formatted — keep or replace, never
    delete (CR156 Tier B constraint 2)."""
    from pathlib import Path

    profile = Path(__file__).resolve().parents[3] / "content/agents/portfolio_manager.md"
    assert "## Output format" in profile.read_text()


# ── CR156 D — the ordering claim, corrected ─────────────────────────────────


def test_the_docs_no_longer_claim_the_floor_is_last_in_the_room():
    """It is last on the 1-on-1 path and NOT last in the Room, where
    `system_prompt = base + room_addition` renders the whole CONVENE block after
    it — on the one surface where a verdict is parsed and acted on."""
    from pathlib import Path

    doc = (
        Path(__file__).resolve().parents[3]
        / "docs/initial_specs/02_agents/safety_floor.md"
    ).read_text()
    assert "By placing the safety floor *last*, we make it the dominant instruction" not in doc
    assert "**The Room: false.**" in doc
    assert "the floor is in the middle of the prompt, not at the end" in doc


# ── DEF264 — the allowlist was the wrong shape, measured ────────────────────
#
# DEF239 replaced a single `parsed["narration"]` read with an allowlist after
# the model emitted `narrational` once. The 26-convene post-promotion sweep
# (`r68-postbatch9`, 2026-08-11) found it emitting **`narr`** in 6 of 28
# verdicts — 21%, not an edge case, and not a synonym but an ABBREVIATION that
# no amount of enumerating rationale/reasoning/explanation would have reached.
# All six published "it wrote no rationale for the call" over three or four
# paragraphs of real analysis.
#
# Measured cause, not assumed: max PM output that sweep was 466 tokens against
# an 1100 ceiling and 0 of 30 turns hit the cap, so truncation (DEF258/DEF261)
# is ruled out — the responses were complete, well-formed JSON under a key we
# did not read.

_REAL_NARR = (
    "Verdict: PASS — No position is warranted because the fundamental "
    "asymmetry violates the long-term wealth mandate. The -1% net profit "
    "margin and $11,430M net debt confirm structural impairment."
)


def test_the_live_narr_abbreviation_is_read():
    """The 6-of-28 key, verbatim from the sweep."""
    assert _pm_narration({"action": "PASS", "narr": _REAL_NARR}) == _REAL_NARR


def test_a_contracted_key_still_outranks_an_unrecognised_one():
    """The allowlist keeps its job — precedence. `narration` is what the
    contract asks for, so it wins when several keys carry prose."""
    assert _pm_narration(
        {"narr": "abbreviated", "narration": _REAL_NARR, "commentary": "x" * 90}
    ) == _REAL_NARR


def test_an_unknown_key_carrying_real_prose_is_recovered():
    """The point of the shape test: the next unknown key costs nothing."""
    assert _pm_narration({"action": "PASS", "commentary": _REAL_NARR}) == _REAL_NARR


def test_def239s_objection_still_holds_and_is_the_reason_this_is_not_a_scrape():
    """`{"ticker": "AAPL"}` must never render as a defence — that would destroy
    the one signal telling a user the decision was never explained (DEF232).
    Asserted with a LONG value too, so the guard is by key name and not merely
    an accident of length."""
    assert _pm_narration({"action": "PASS", "ticker": "AAPL"}) == ""
    assert _pm_narration({"action": "PASS", "ticker": _REAL_NARR}) == ""
    assert _pm_narration({"action": "PASS", "decision": _REAL_NARR}) == ""


def test_a_short_string_under_an_unknown_key_is_metadata_not_a_rationale():
    """The stated trade. DEF232 characterised a non-explanation at this same
    boundary — 'exactly 1 verdict carries a reason under 40 characters' across
    1,016 stored verdicts — so the number is borrowed, not invented. A short
    CONTRACTED key is unaffected, which is where a genuinely terse rationale
    would arrive."""
    from app.services.room_runner import _PM_MIN_PROSE_CHARS

    assert _PM_MIN_PROSE_CHARS == 40
    assert _pm_narration({"action": "PASS", "note": "no"}) == ""
    assert _pm_narration({"action": "PASS", "reason": "no"}) == "no"


def test_the_longest_candidate_wins_when_several_unknown_keys_carry_prose():
    short_prose = "A shorter but still perfectly valid explanation here."
    got = _pm_narration({"action": "PASS", "note": short_prose, "commentary": _REAL_NARR})
    assert got == _REAL_NARR


def test_the_fallback_announces_itself(monkeypatch):
    """CR040 — the ONLY reason this took a 26-convene sweep to surface is that
    nothing said the PM was using an unknown key. Now it does, by name, so the
    next one is a log line rather than an hour of forensics."""
    from app.services import room_runner as rr

    seen: list[tuple[str, dict]] = []
    monkeypatch.setattr(
        rr.logger, "warning", lambda event, **kw: seen.append((event, kw))
    )
    _pm_narration({"action": "PASS", "narr": _REAL_NARR})
    assert [e for e, _ in seen] == ["room_pm_narration_from_unknown_key"]
    assert seen[0][1]["key"] == "narr"


def test_a_contracted_key_does_not_trip_the_warning(monkeypatch):
    """It must stay quiet on the contracted path, or it is noise nobody reads
    and the signal is gone again."""
    from app.services import room_runner as rr

    seen: list[str] = []
    monkeypatch.setattr(rr.logger, "warning", lambda event, **kw: seen.append(event))
    _pm_narration({"action": "PASS", "narration": _REAL_NARR})
    assert seen == []


def test_no_code_docstring_still_claims_the_floor_dominates_by_position():
    """DEF267 — CR156 D retracted this in `safety_floor.md` and left the same
    sentence in `agent_prompts.py`'s docstring: in the function that appends the
    floor, citing the doc that now contradicts it. The Batch 8 lane claimed
    "both the doc and the code now say so" while the pin only read the doc."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[2] / "app/services/agent_prompts.py"
    ).read_text()
    assert "appended LAST so it always dominates" not in src
    assert "does NOT follow that it dominates" in src
