"""CR219 R59-F2 — `key_number`/`decisive_number` are quotations, so check them.

The audit's finding (`dev_instructions/R59_numbers_audit.md` §3-F2): the Risk
Officer is instructed to quote a figure from the evidence and "do not compute
anything new", but nothing enforced that the string actually IS a quotation —
it was a free 60-char string, rendered verbatim, and promoted into the comb
headline. That is the one hole in CR197's "the model never emits a computed
number" claim (`risk_officer.py` module docstring).

This file pins four things:

  1. **The normalization rule** (`risk_officer.py` module docstring) — every
     tolerated formatting variant parses to the same comparable figure, tested
     individually per the dev instructions' explicit list.
  2. **The check-and-demote behaviour runs UNCONDITIONALLY** — there is no
     flag that turns it off. A miss earns `[AMI: unverifiable]` in the body
     and is demoted from the headline slot to `_rung_derived_headline` — a
     headline built only from the ladder's own computed figures, which cannot
     itself fail this check.
  3. **The failure posture** — a checker that cannot run (malformed input)
     degrades to UNVERIFIED, the same outcome as a genuine miss, never a
     silent pass into the headline (CLAUDE.md's degrade-loudly rule, DEF059's
     "confident fake" shape one door over).
  4. **A verified figure renders clean and stays in the headline slot** — the
     check is not a strip-everything filter, it is a check-or-demote one.

Why on by default, not an opt-in: a default-off check is precisely the CR040
shape this whole audit is chasing — a control that is fully built and tested
and never actually runs on the path a real user reads. The registry in
`app.services.numeric_provenance` records `("risk_rung", "key_number")` and
`("risk_rung", "decisive_number")`; those rows only earn `CODE_CHECKED`
honestly if the renderer really does check them on every call, not merely
when some caller remembers to ask.
"""

from __future__ import annotations

import pytest

from app.schemas.agents import AgentId
from app.services.risk_officer import (
    _UNVERIFIABLE_MARK,
    RISK_TURN_ORDER,
    _corroborating_values,
    _extract_numerals,
    _quotation_check,
    _rung_derived_headline,
    render_officer_turns,
    render_risk_assessment,
)
from app.trading_math.option_ladder import build_option_ladder

# reference 3.0 → rungs 1.5 (trim, contribution_pts 0.09) /
# 3.0 (reference, 0.18) / 5.0 (press, 0.30) — the exact fixture CR197/CR201
# already use, so a value quoted from THIS ladder is directly comparable to
# their fixtures' own numbers.
_ROWS = build_option_ladder(
    reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
    cap_pts=30.0, current_drawdown_pct=0.0,
)


@pytest.fixture
def rows():
    return _ROWS


def _payload(sizes=(1.5, 3.0, 5.0), **kw):
    """Every `key_number` here is a genuine quotation from THIS fixture's own
    ladder (`kn-{s}` contains the rung's own size), and `decisive_number`
    defaults to the reference rung's own `contribution_pts` — real figures the
    officer is actually entitled to cite, not unquotable placeholders. Tests
    that need to exercise a MISS build their own payload explicitly."""
    p = {
        "options": [
            {
                "size_pct": s,
                "case_for": f"for-{s}",
                "case_against": f"against-{s}",
                "key_number": f"kn-{s}",
            }
            for s in sizes
        ],
        "recommended": 3.0,
        "confidence": "medium",
        "decisive_number": "0.18",
    }
    p.update(kw)
    return p


# ── Normalization rule: every tolerated form, exactly as the dev instructions
#    list them ─────────────────────────────────────────────────────────────


class TestNormalizationRule:
    """Every form named in the dev instructions: '1,234.5', '1234.50',
    '$1.2B', '4.06%', bare '4.06'."""

    def test_thousands_separated_form(self, rows):
        assert _quotation_check("1,234.5", {"pe": 1234.5}, rows) is True

    def test_plain_decimal_form(self, rows):
        assert _quotation_check("1234.50", {"pe": 1234.5}, rows) is True

    def test_thousands_and_plain_forms_are_the_same_claim(self, rows):
        """'1,234.5' and '1234.50' must corroborate against the SAME sheet
        value — they are formatting variants of one number, not two."""
        profile = {"pe": 1234.5}
        assert _quotation_check("1,234.5", profile, rows) == _quotation_check(
            "1234.50", profile, rows
        )

    def test_dollar_billion_suffix_form(self, rows):
        """'$1.2B' against a raw market_cap of 1_234_000_000: the claim's own
        precision (1 decimal, in billions) is what the sheet value is rounded
        to — round(1_234_000_000 / 1e9, 1) == 1.2."""
        assert _quotation_check("$1.2B", {"market_cap": 1_234_000_000.0}, rows) is True

    def test_dollar_billion_suffix_form_rejects_a_real_mismatch(self, rows):
        assert _quotation_check("$1.2B", {"market_cap": 3_400_000_000.0}, rows) is False

    def test_percent_suffixed_form(self, rows):
        assert _quotation_check("4.06%", {"rsi": 4.06}, rows) is True

    def test_bare_form(self, rows):
        assert _quotation_check("4.06", {"rsi": 4.06}, rows) is True

    def test_percent_and_bare_forms_are_the_same_claim(self, rows):
        profile = {"rsi": 4.06}
        assert _quotation_check("4.06%", profile, rows) == _quotation_check(
            "4.06", profile, rows
        )

    def test_lowercase_and_uppercase_magnitude_letters_both_work(self, rows):
        profile = {"market_cap": 1_200_000_000.0}
        assert _quotation_check("$1.2b", profile, rows) is True
        assert _quotation_check("$1.2B", profile, rows) is True

    def test_million_and_thousand_suffixes(self, rows):
        assert _quotation_check("$450M", {"free_cash_flow": 450_000_000.0}, rows) is True
        assert _quotation_check("12.5K shares", {"volume": 12_500.0}, rows) is True


# ── A key_number with no numerals at all is not a miss ───────────────────────


class TestNoNumeralsIsNotAMiss:
    """The dev instructions are explicit: a key_number containing NO numerals
    (pure words) is not a miss — leave it alone."""

    def test_pure_words_key_number_verifies(self, rows):
        assert _quotation_check("guidance was raised last quarter", {}, rows) is True

    def test_pure_words_with_punctuation_verifies(self, rows):
        assert _quotation_check("margins are compressing, not expanding.", {}, rows) is True

    def test_empty_string_verifies(self, rows):
        assert _quotation_check("", {}, rows) is True

    def test_none_verifies(self, rows):
        assert _quotation_check(None, {}, rows) is True

    def test_no_numerals_means_extraction_found_none(self):
        assert _extract_numerals("no digits here at all") == []


# ── Corroboration sources: the sheet, the ladder, or both ────────────────────


class TestCorroborationSources:
    def test_a_figure_only_the_ladder_carries_still_corroborates(self, rows):
        """No profile at all (None) — ladder-only verification, per the dev
        instructions' 'sheet or the ladder's own figures'."""
        assert _quotation_check("0.18", None, rows) is True  # reference contribution_pts

    def test_a_figure_only_the_sheet_carries_still_corroborates(self, rows):
        assert _quotation_check("43", {"rsi": 43.0}, rows) is True

    def test_a_figure_in_neither_is_a_genuine_miss(self, rows):
        assert _quotation_check("igned by nobody: 12345", {}, rows) is False

    def test_every_ladder_field_is_a_corroboration_source(self, rows):
        """`_corroborating_values` must walk every numeric field CR219's own
        finding says the officer is entitled to quote — size_pct,
        contribution_pts, share_of_cap_pct, headroom_after_pts, reward_risk —
        not just size_pct."""
        r = rows[1]  # the reference rung
        for value in (r.size_pct, r.contribution_pts, r.share_of_cap_pct,
                      r.headroom_after_pts, r.reward_risk):
            assert value in _corroborating_values(None, rows)

    def test_a_multi_value_sheet_corroborates_any_one_of_its_numbers(self, rows):
        profile = {"pe": 22.4, "rsi": 61.0, "rev_growth": 8.2}
        assert _quotation_check("PE of 22.4", profile, rows) is True
        assert _quotation_check("RSI at 61", profile, rows) is True
        assert _quotation_check("growth of 8.2%", profile, rows) is True


# ── Failure posture: never crashes, degrades to UNVERIFIED ───────────────────


class TestFailurePosture:
    """CLAUDE.md's degrade-loudly rule: an internal error in the checker must
    never look like a passed check. False (unverified) is the ONLY safe
    output for a checker that could not actually check."""

    def test_a_profile_that_is_not_dict_shaped_does_not_crash(self, rows):
        class NotADict:
            pass

        assert _quotation_check("42", NotADict(), rows) is False

    def test_rows_that_are_not_a_list_of_ladder_options_does_not_crash(self):
        assert _quotation_check("42", {}, "not-a-list-of-rows") is False

    def test_rows_as_none_does_not_crash(self):
        assert _quotation_check("42", {}, None) is False

    def test_a_deeply_nested_or_cyclic_profile_does_not_hang_or_crash(self, rows):
        cyclic: dict = {"a": {}}
        cyclic["a"]["self"] = cyclic  # a profile could never legitimately do
        # this, but the checker must not hang or crash if one somehow does.
        assert _quotation_check("42", cyclic, rows) is False

    def test_render_officer_turns_never_crashes_on_a_malformed_profile(self, rows):
        """The end-to-end guarantee: even when the checker degrades on a
        malformed `profile`, the RENDER still completes — a miss (checker
        error included) demotes and annotates, it never raises past render."""

        class NotADict:
            pass

        turns = render_officer_turns(
            _payload(), rows, headline_max_chars=80, profile=NotADict()
        )
        assert len(turns) == 3


# ── render_officer_turns: checks and demotes UNCONDITIONALLY ─────────────────


class TestRenderOfficerTurnsChecksByDefault:
    """There is no flag. Calling with no `profile` still runs ladder-only
    verification — omitting the fact sheet is not the same as skipping the
    check."""

    def test_a_corroborated_key_number_renders_clean(self, rows):
        payload = _payload()
        payload["options"][0]["key_number"] = "0.09"  # trim's own contribution_pts
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        trim = next(t for t in turns if t.agent_id is AgentId.CONSERVATIVE_DEBATOR)
        assert "Key figure: 0.09" in trim.text
        assert _UNVERIFIABLE_MARK not in trim.text
        assert trim.headline == "0.09"

    def test_an_uncorroborated_key_number_is_annotated_in_the_body(self, rows):
        payload = _payload()
        payload["options"][2]["key_number"] = "a made-up 987.6"  # press rung
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        press = next(t for t in turns if t.agent_id is AgentId.AGGRESSIVE_DEBATOR)
        assert f"Key figure: a made-up 987.6 {_UNVERIFIABLE_MARK}" in press.text

    def test_an_uncorroborated_key_number_is_demoted_from_the_headline(self, rows):
        """The finding's exact ask: demoted from the headline slot so the
        rung-derived fallback headline takes over."""
        payload = _payload()
        payload["options"][2]["key_number"] = "a made-up 987.6"
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        press = next(t for t in turns if t.agent_id is AgentId.AGGRESSIVE_DEBATOR)
        assert press.headline != "a made-up 987.6"
        assert press.headline == _rung_derived_headline(rows[2])
        assert "987.6" not in (press.headline or "")

    def test_a_corroborated_decisive_number_carries_the_call_clean(self, rows):
        payload = _payload(decisive_number="0.18")  # reference's own contribution_pts
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        neu = next(t for t in turns if t.agent_id is AgentId.NEUTRAL_DEBATOR)
        assert "decided by 0.18" in neu.text
        assert _UNVERIFIABLE_MARK not in neu.text
        assert neu.headline == "0.18"

    def test_an_uncorroborated_decisive_number_is_annotated_on_the_call_line(self, rows):
        payload = _payload(decisive_number="a fabricated 555.5")
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        neu = next(t for t in turns if t.agent_id is AgentId.NEUTRAL_DEBATOR)
        assert f"decided by a fabricated 555.5 {_UNVERIFIABLE_MARK}" in neu.text

    def test_an_uncorroborated_decisive_number_is_demoted_from_the_headline(self, rows):
        payload = _payload(decisive_number="a fabricated 555.5")
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        neu = next(t for t in turns if t.agent_id is AgentId.NEUTRAL_DEBATOR)
        assert neu.headline != "a fabricated 555.5"
        assert neu.headline == _rung_derived_headline(rows[1])  # the reference rung

    def test_recommended_rungs_headline_falls_back_to_key_number_when_decisive_number_absent(
        self, rows
    ):
        """Unchanged precedent (not this CR's concern, but must still hold):
        `decisive_number` empty ⇒ the recommended rung's headline is its OWN
        key_number, checked on its own merits."""
        payload = _payload(decisive_number="", sizes=(1.5, 3.0, 5.0))
        payload["options"][1]["key_number"] = "0.18"  # reference's own figure
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        neu = next(t for t in turns if t.agent_id is AgentId.NEUTRAL_DEBATOR)
        assert neu.headline == "0.18"

    def test_a_verified_string_against_the_sheet_is_not_demoted(self, rows):
        """profile carries the figure the sheet-only, non-ladder claim needs."""
        payload = _payload()
        payload["options"][2]["key_number"] = "RSI 61"
        turns = render_officer_turns(
            payload, rows, headline_max_chars=80, profile={"rsi": 61.0},
        )
        press = next(t for t in turns if t.agent_id is AgentId.AGGRESSIVE_DEBATOR)
        assert press.headline == "RSI 61"
        assert _UNVERIFIABLE_MARK not in press.text

    def test_omitting_profile_still_runs_ladder_only_verification(self, rows):
        """No `profile` argument at all — not the same as skipping the check.
        A figure only the SHEET could have corroborated must still miss."""
        payload = _payload()
        payload["options"][0]["key_number"] = "RSI 61"  # not on the ladder
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        trim = next(t for t in turns if t.agent_id is AgentId.CONSERVATIVE_DEBATOR)
        assert _UNVERIFIABLE_MARK in trim.text

    def test_a_pure_words_key_number_is_never_demoted(self, rows):
        payload = _payload()
        payload["options"][0]["key_number"] = "guidance was raised"
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        trim = next(t for t in turns if t.agent_id is AgentId.CONSERVATIVE_DEBATOR)
        assert trim.headline == "guidance was raised"
        assert _UNVERIFIABLE_MARK not in trim.text

    def test_demotion_still_respects_the_existing_character_cap(self, rows):
        """`_rung_derived_headline`'s output must still go through
        `_capped_headline` like every other candidate — this test only
        documents that the fallback string is short enough in practice, it
        does not change the capping mechanism itself."""
        payload = _payload()
        payload["options"][2]["key_number"] = "bogus 42"
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        press = next(t for t in turns if t.agent_id is AgentId.AGGRESSIVE_DEBATOR)
        assert press.headline is not None
        assert len(press.headline) <= 80

    def test_fallback_path_has_nothing_to_check(self, rows):
        """The officer-call-failed fallback path (ladder alone, [AMI …] mark)
        has no `key_number`/`decisive_number` at all — verification changes
        nothing about its shape because there is no payload to check."""
        turns = render_officer_turns(
            None, rows, headline_max_chars=80, fallback_reason="no reply within 30s"
        )
        assert len(turns) == 3
        for t in turns:
            assert "[AMI:" in t.text
            assert "no reply within 30s" in t.text

    def test_an_unassessed_rungs_absence_is_unaffected_by_verification(self, rows):
        """A skipped rung has no `opt` to read a key_number from at all, so it
        never reaches the checker — 'did not assess' still renders exactly as
        it always has, alongside a checked, corroborated other rung."""
        payload = _payload(sizes=(1.5, 3.0), decisive_number="0.18")
        payload["options"][1]["key_number"] = "0.18"  # reference's own figure
        turns = render_officer_turns(payload, rows, headline_max_chars=80)
        press = next(t for t in turns if t.agent_id is AgentId.AGGRESSIVE_DEBATOR)
        assert "did not assess this size" in press.text
        neu = next(t for t in turns if t.agent_id is AgentId.NEUTRAL_DEBATOR)
        assert _UNVERIFIABLE_MARK not in neu.text

    def test_turn_order_and_voice_count_are_unaffected(self, rows):
        turns = render_officer_turns(_payload(), rows, headline_max_chars=80)
        assert [t.agent_id for t in turns] == list(RISK_TURN_ORDER)
        assert len(turns) == 3


# ── render_risk_assessment: the same check, on the body-only renderer ────────


class TestRenderRiskAssessment:
    def test_an_uncorroborated_key_number_is_annotated(self, rows):
        payload = {
            "options": [{"size_pct": 3.0, "case_for": "f", "case_against": "a",
                          "key_number": "a made-up 987.6"}],
        }
        text = render_risk_assessment(payload, rows)
        assert f"Key figure: a made-up 987.6 {_UNVERIFIABLE_MARK}" in text

    def test_an_uncorroborated_decisive_number_is_annotated(self, rows):
        payload = {"recommended": 3.0, "confidence": "high",
                   "decisive_number": "a fabricated 555.5"}
        text = render_risk_assessment(payload, rows)
        assert f"decided by a fabricated 555.5 {_UNVERIFIABLE_MARK}" in text

    def test_a_corroborated_figure_renders_clean(self, rows):
        payload = {
            "options": [{"size_pct": 1.5, "case_for": "f", "case_against": "a",
                          "key_number": "0.09"}],  # trim's own contribution_pts
        }
        text = render_risk_assessment(payload, rows)
        assert "Key figure: 0.09" in text
        assert _UNVERIFIABLE_MARK not in text

    def test_a_sheet_only_figure_verifies_when_profile_is_supplied(self, rows):
        payload = {"recommended": 3.0, "confidence": "high", "decisive_number": "RSI 61"}
        text = render_risk_assessment(payload, rows, profile={"rsi": 61.0})
        assert "decided by RSI 61" in text
        assert _UNVERIFIABLE_MARK not in text

    def test_a_sheet_only_figure_misses_without_profile(self, rows):
        """Omitting `profile` runs ladder-only verification, it does not skip
        the check — the same figure that verified above must miss here."""
        payload = {"recommended": 3.0, "confidence": "high", "decisive_number": "RSI 61"}
        text = render_risk_assessment(payload, rows)
        assert f"decided by RSI 61 {_UNVERIFIABLE_MARK}" in text
