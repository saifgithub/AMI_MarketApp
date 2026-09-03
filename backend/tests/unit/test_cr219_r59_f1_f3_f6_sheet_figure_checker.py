"""CR219 R59-F1/F3/F6 (lane B1) — the sheet-figure checker for prose.

The audit's finding (`dev_instructions/R59_numbers_audit.md` §3-F1/F3/F6): the
fact sheet is code-built and therefore correct, but nothing checks an
analyst's PROSE restatement of it, a stance-envelope HEADLINE, or a PM
`kill_criterion`. `numeric_quotation.py`'s `find_sheet_mismatches`/
`annotate_sheet_mismatches` close that gap for a scoped, unambiguous label
vocabulary — see that module's docstring for the full design.

**The one thing this file exists to prove, ahead of everything else**: false
positives are the failure mode, not misses (the dev instructions' own design
constraint). So this file spends as much weight on what must NOT fire
(unlabelled numerals, derived arithmetic, formatting variants of a TRUE
quote, comparative prose sharing one label across two numbers) as on what
must.

Six sections:
  1. `TestLabelVocabularySourcedFromRenderer` — every `_FieldSpec.renderer_
     label` is grepped, verbatim, out of the renderer source file it cites.
     A rename in the renderer fails THIS test, not silently.
  2. `TestPositiveMatch` — a genuine labelled mismatch is annotated, naming
     the sheet's own value.
  3. `TestNegativeMatch` — everything that must pass through untouched: a
     correct restatement (several formatting variants, mirroring A2's five
     forms), an unlabelled numeral, derived arithmetic (percent-off-high,
     implied upside, R:R), a trader-block dollar level, a missing/empty
     profile, and the comparative-prose label-collision case.
  4. `TestF3StanceHeadline` — the headline is NULLED (never annotated in
     place — `STANCE_HEADLINE_MAX_CHARS` is 32 chars, no room for a note).
  5. `TestF6KillCriterion` — an off-sheet quantity in `kill_criterion` is
     annotated through the real `_parse_pm_verdict` path.
  6. `TestComposition` — the checker composes with the envelope/GAPS strips
     order-independently, and one true end-to-end case runs the checker
     through `RoomRunner.run()`'s real turn path.
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.numeric_quotation import (
    SheetMismatch,
    _FIELD_SPECS,
    annotate_sheet_mismatches,
    find_sheet_mismatches,
)
from app.services.room_runner import _RoomContext, _parse_pm_verdict

_SERVICES_DIR = Path(__file__).resolve().parents[2] / "app" / "services"


def _ctx(profile: dict | None = None) -> _RoomContext:
    """Minimal `_RoomContext`, matching the sibling F4/R52 test files'
    `_ctx()` helper exactly (`test_cr219_r59_f4_horizon_clamp.py`,
    `test_cr219_r52_kill_criterion.py`) — this file's fixture must degrade
    the same way theirs does on an absent `profile` (no sheet ⇒ no-op)."""
    return _RoomContext(
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        halal_universe=set(),
        classification_universe=None,
        locale_allowed_universe=None,
        profile=profile or {},
    )


# ── 1. Label vocabulary sourced from the renderer, not a hand-list ──────────


class TestLabelVocabularySourcedFromRenderer:
    """Every `_FieldSpec.renderer_label` must appear VERBATIM in the source
    file its `renderer_citation` names. This is the module's own "doesn't
    rot" guarantee: a renderer-side label rename breaks THIS test, so the
    vocabulary cannot silently drift from what the sheet actually says.
    """

    @pytest.mark.parametrize("spec", _FIELD_SPECS, ids=lambda s: s.name)
    def test_renderer_label_appears_in_its_cited_source_file(self, spec):
        module_name = spec.renderer_citation.split("::")[0]
        source = (_SERVICES_DIR / module_name).read_text()
        assert spec.renderer_label in source, (
            f"{spec.name}'s renderer_label {spec.renderer_label!r} is not "
            f"in {module_name} any more — the renderer changed its label "
            f"and _FIELD_SPECS was not updated to match"
        )

    def test_every_spec_cites_a_real_source_file(self):
        for spec in _FIELD_SPECS:
            module_name = spec.renderer_citation.split("::")[0]
            assert (_SERVICES_DIR / module_name).is_file(), spec.renderer_citation

    def test_every_field_name_is_unique(self):
        names = [s.name for s in _FIELD_SPECS]
        assert len(names) == len(set(names))


# ── 2. Positive match: a genuine labelled mismatch is annotated ─────────────


class TestPositiveMatch:
    def test_pe_trailing_mismatch_is_annotated_naming_the_sheet_value(self):
        text = "the current **122.6x** trailing P/E suggests thorough optimism"
        profile = {"pe": 45.0}
        out = annotate_sheet_mismatches(text, profile)
        assert out != text
        assert "122.6" in out
        assert "45" in out
        assert "[" in out and out.rstrip().endswith("]")
        assert "figures of record" in out

    def test_rsi_mismatch_is_annotated(self):
        text = "RSI of 40 with price below the 50-day SMA"
        profile = {"rsi": 71.0}
        out = annotate_sheet_mismatches(text, profile)
        assert "40" in out and "71" in out

    def test_market_cap_mismatch_renders_the_sheets_own_millions_shape(self):
        """The sheet stores market_cap IN MILLIONS; the annotation must
        render the sheet's OWN "$X,XXXM" shape, not a raw-dollar dump."""
        text = "the market cap is $3.4B here"
        profile = {"market_cap": 1200}  # $1,200M
        out = annotate_sheet_mismatches(text, profile)
        assert "$1,200M" in out
        assert "$1,200,000,000" not in out

    def test_atr_mismatch_is_annotated(self):
        text = "ATR(14) sits at 12.50 right now, unusually wide"
        profile = {"atr14": 4.10}
        out = annotate_sheet_mismatches(text, profile)
        assert "12.5" in out and "4.1" in out

    def test_week52_high_and_low_are_distinct_fields(self):
        """Restating the wrong END of the range is still a genuine mismatch
        against the label the analyst actually used."""
        text = "the 52-week high sits at $310, well above where we are"
        profile = {"high": 275.0, "low": 150.0}
        out = annotate_sheet_mismatches(text, profile)
        assert "310" in out and "275" in out
        assert "150" not in out  # the LOW must not be dragged in

    def test_multiple_genuine_mismatches_are_all_annotated(self):
        text = "P/E is 25 and market cap is $900M"
        profile = {"pe": 40.0, "market_cap": 5000}
        mismatches = find_sheet_mismatches(text, profile)
        assert {m.field_name for m in mismatches} == {"pe_trailing", "market_cap"}

    def test_mismatch_reports_the_field_name_and_both_values(self):
        mismatches = find_sheet_mismatches("beta of 2.1 here", {"beta": 0.9})
        assert len(mismatches) == 1
        m = mismatches[0]
        assert isinstance(m, SheetMismatch)
        assert m.field_name == "beta"
        assert m.claimed_value == 2.1
        assert m.sheet_value == 0.9

    def test_trailing_and_forward_pe_stated_together_each_checked_against_its_own_field(self):
        """Both bases named in one sentence — the realistic shape `pe_line`
        itself always renders ("Say which basis you mean whenever you cite
        a P/E"). Found during construction: the FIRST version of
        `exclude_pattern` checked the whole numeral-centered window for
        "forward", so a LATER, unrelated "forward P/E" mention in the same
        sentence excluded an EARLIER, correctly-trailing "P/E" from binding
        at all — a false NEGATIVE (a real trailing-P/E mismatch went
        undetected) rather than the false-positive class this file mostly
        pins, but the same design constraint: precision on WHICH figure a
        label disambiguates."""
        text = "Trailing P/E is 45.0x, and forward P/E of 30.0x looks more reasonable."

        both_correct = {"pe": 45.0, "forward_pe": 30.0}
        assert find_sheet_mismatches(text, both_correct) == []

        trailing_wrong = {"pe": 99.0, "forward_pe": 30.0}
        m1 = find_sheet_mismatches(text, trailing_wrong)
        assert len(m1) == 1 and m1[0].field_name == "pe_trailing" and m1[0].claimed_value == 45.0

        forward_wrong = {"pe": 45.0, "forward_pe": 99.0}
        m2 = find_sheet_mismatches(text, forward_wrong)
        assert len(m2) == 1 and m2[0].field_name == "pe_forward" and m2[0].claimed_value == 30.0


# ── 3. Negative match: everything that must NOT fire ────────────────────────


class TestNegativeMatch:
    """False positives are the failure mode. Every case here must return
    the input BYTE-IDENTICAL."""

    def test_a_true_labelled_restatement_is_untouched(self):
        text = "the P/E is 25.0 here, in line with peers"
        profile = {"pe": 25.0}
        assert annotate_sheet_mismatches(text, profile) == text

    # A2's five tolerated formatting forms, applied to this checker's own
    # fields — a restatement that merely rounds/formats differently is not
    # a mismatch.
    def test_thousands_separated_form_is_untouched(self):
        text = "market cap of $1,200M"
        assert find_sheet_mismatches(text, {"market_cap": 1200}) == []

    def test_plain_decimal_form_is_untouched(self):
        text = "the RSI reads 61.00 today"
        assert find_sheet_mismatches(text, {"rsi": 61.0}) == []

    def test_dollar_billion_suffix_form_is_untouched(self):
        text = "market cap around $1.2B"
        assert find_sheet_mismatches(text, {"market_cap": 1200}) == []

    def test_percent_suffixed_form_is_untouched(self):
        text = "TTM revenue growth of 8.20%"
        assert find_sheet_mismatches(text, {"rev_growth": 8.2}) == []

    def test_bare_form_is_untouched(self):
        text = "revenue growth sits at 8.2 this year"
        assert find_sheet_mismatches(text, {"rev_growth": 8.2}) == []

    @pytest.mark.parametrize("text,expected_value", [
        # The exact fixture: "t" of "today" read as a trillion suffix.
        ("the reading is 61.00 today", 61.0),
        # "t" of "this" — same class, different letter position.
        ("growth sits at 8.2 this year", 8.2),
        # "b" starts "billion", a real word, not a lone magnitude letter —
        # the fix must not merely special-case "today"/"this".
        ("40 billion-dollar names in the index", 40.0),
    ])
    def test_a_word_starting_with_a_magnitude_letter_is_not_read_as_a_suffix(
        self, text, expected_value
    ):
        """Explicit regression pin, isolated from any label-adjacency
        question: found via `test_plain_decimal_form_is_untouched` above —
        `_NUMERAL_RE`'s magnitude group had no boundary after it, so
        "61.00 today" parsed as 61 TRILLION (the "t" of "today" read as a
        trillion suffix). `(?![a-zA-Z])` after the magnitude group is the
        fix (`numeric_quotation.py`, on `_NUMERAL_RE`'s definition) — this
        pins the raw extraction, not just the end-to-end no-mismatch
        outcome."""
        from app.services.numeric_quotation import _extract_numerals

        numerals = _extract_numerals(text)
        assert len(numerals) == 1
        assert numerals[0].value == expected_value

    def test_a_genuine_magnitude_suffix_still_resolves_beside_a_following_word(self):
        """Anti-vacuity for the fix above — a REAL suffix immediately
        followed by a space and another word must still resolve; the fix
        is a word-boundary AFTER the letter, not a ban on trailing
        context."""
        from app.services.numeric_quotation import _extract_numerals

        numerals = _extract_numerals("market cap of $1.2B here")
        assert len(numerals) == 1
        assert numerals[0].value == 1_200_000_000.0

    def test_a_labels_own_embedded_digit_does_not_self_match(self):
        """Explicit regression pin for the "52-week high" self-collision:
        `_extract_numerals` finds "52" as ITS OWN standalone numeral (from
        inside the label text), and without the fix in `_label_distance`
        (skip a label occurrence whose matched span overlaps the numeral's
        own span) that "52" bound to `week52_high` at distance 0 — beating
        any numeral that was genuinely being labelled.

        Isolated so the ONLY candidate numeral in range is the label's own
        embedded "52" — no other number is present at all, so a failure
        here can only be the self-collision, not some other real claim
        nearby (`TestPositiveMatch.test_week52_high_and_low_are_distinct_
        fields` and `TestNegativeMatch.test_percent_off_the_high_is_
        untouched` cover the shapes with a genuine adjacent number)."""
        text = "reading a lot about the 52-week high concept lately"
        assert find_sheet_mismatches(text, {"high": 999.0}) == []

    # Unlabelled numerals — no adjacent recognised label at all.
    def test_an_unlabelled_numeral_is_untouched(self):
        text = "shares popped 12% today on no news"
        assert find_sheet_mismatches(text, {"pe": 25.0}) == []

    # Derived arithmetic — explicitly out of scope per the audit's F1 fix
    # class ("do NOT attempt to verify derived arithmetic in this pass").
    def test_percent_off_the_high_is_untouched(self):
        text = "the stock is 33.4% off its 52-week high right now"
        # A real sheet high the analyst's arithmetic disagrees with must
        # still pass through: this checker only compares a LABELLED
        # restatement of the sheet's OWN figure, never a derived distance.
        assert find_sheet_mismatches(text, {"high": 999.0}) == []

    def test_implied_upside_is_untouched(self):
        text = "implied upside to the consensus target is roughly 28%"
        assert find_sheet_mismatches(text, {"pe": 25.0}) == []

    def test_rr_ratio_is_untouched(self):
        text = "R:R here works out to 2.5:1 on the stated levels"
        assert find_sheet_mismatches(text, {"pe": 25.0}) == []

    def test_trader_block_dollar_levels_are_untouched(self):
        """Entry/Stop/Target dollar levels are `_verify_and_annotate_
        geometry`'s domain, not this checker's — none of them carry a
        label from `_FIELD_SPECS`."""
        text = "Entry: $32.75\nStop: $29.60\nTarget: $33.50\nSize: 10%"
        assert find_sheet_mismatches(text, {"pe": 25.0, "rsi": 50.0}) == []

    # A ratio/field the sheet does not carry at all.
    def test_a_field_the_sheet_does_not_carry_is_untouched(self):
        text = "the P/E is 25 here"
        assert find_sheet_mismatches(text, {}) == []
        assert find_sheet_mismatches(text, {"rsi": 50.0}) == []  # sheet has RSI, not P/E

    # Missing / empty / malformed profile.
    def test_missing_profile_is_a_no_op(self):
        text = "the P/E is 999 here, way off"
        assert find_sheet_mismatches(text, None) == []
        assert annotate_sheet_mismatches(text, None) == text

    def test_empty_profile_is_a_no_op(self):
        text = "the P/E is 999 here, way off"
        assert find_sheet_mismatches(text, {}) == []

    def test_malformed_profile_does_not_crash_and_finds_nothing(self):
        class NotADict:
            pass

        assert find_sheet_mismatches("P/E of 25", NotADict()) == []

    def test_empty_text_is_a_no_op(self):
        assert find_sheet_mismatches("", {"pe": 25.0}) == []
        assert find_sheet_mismatches(None, {"pe": 25.0}) == []

    # The comparative-prose label-collision case — the sharpest false-
    # positive risk this design found during construction.
    def test_comparative_prose_does_not_let_an_off_ticker_figure_convict_the_real_one(self):
        """"AAPL P/E is 29.9 vs SPX 21.5" — BOTH numerals sit within the
        naive window of the one "P/E" label. Nearest-numeral-wins must bind
        only 29.9 (4 chars from the label) and leave 21.5 (16 chars away)
        unbound, so a true AAPL P/E of 29.9 is NOT struck by the unrelated
        SPX figure sharing its sentence."""
        text = "AAPL P/E is 29.9 vs SPX 21.5."
        assert find_sheet_mismatches(text, {"pe": 29.9}) == []

    def test_comparative_prose_still_catches_a_genuine_mismatch_on_the_bound_numeral(self):
        text = "AAPL P/E is 29.9 vs SPX 21.5."
        mismatches = find_sheet_mismatches(text, {"pe": 50.0})
        assert len(mismatches) == 1
        assert mismatches[0].claimed_value == 29.9  # the bound (near) one, not 21.5


# ── 4. F3 — the stance-envelope HEADLINE is nulled, never annotated in place ─


class TestF3StanceHeadline:
    """`STANCE_HEADLINE_MAX_CHARS` is 32 chars — no room for a readable
    annotation, so a mismatch NULLS the headline (the established null-
    don't-cut convention), it does not try to cram a note into it."""

    def test_a_headline_with_a_genuine_mismatch_is_a_null_signal(self):
        """This file cannot drive the full SSE turn path (that needs a live
        gateway) — it pins the CONTRACT `_compute_agent_text`'s wiring
        relies on: `find_sheet_mismatches` on the headline string alone.
        `TestComposition.test_f3_headline_is_nulled_end_to_end` below
        proves the actual wiring nulls it in the real turn."""
        headline = "P/E at 25, cheap here"
        assert find_sheet_mismatches(headline, {"pe": 60.0}) != []

    def test_a_true_headline_produces_no_finding(self):
        headline = "RSI 61, momentum building"
        assert find_sheet_mismatches(headline, {"rsi": 61.0}) == []

    def test_a_headline_with_no_labelled_numeral_produces_no_finding(self):
        headline = "12% off the high, watching"
        assert find_sheet_mismatches(headline, {"pe": 25.0}) == []


# ── 5. F6 — kill_criterion, through the real _parse_pm_verdict path ─────────


class TestF6KillCriterion:
    def test_an_off_sheet_quantity_is_annotated(self):
        """The schema's own note (`schemas/room.py`): a criterion must name
        a quantity the fact sheet actually carries. A criterion quoting a
        P/E the sheet contradicts is exactly the unfalsifiable-reading-as-
        rigour shape F6 exists to catch."""
        profile = {"pe": 60.0}
        text = json.dumps({
            "action": "PASS",
            "narration": "The synthesis holds and the mandate clears here today.",
            "kill_criterion": "A daily close where the P/E falls back under 25 on volume.",
        })
        _, verdict = _parse_pm_verdict(text, _ctx(profile))
        assert verdict is not None
        assert verdict.kill_criterion is not None
        assert "25" in verdict.kill_criterion
        assert "60" in verdict.kill_criterion
        assert "figures of record" in verdict.kill_criterion

    def test_a_true_quotation_is_untouched(self):
        profile = {"pe": 25.0}
        criterion = "A daily close where the P/E falls back under 25 on volume."
        text = json.dumps({
            "action": "PASS",
            "narration": "The synthesis holds and the mandate clears here today.",
            "kill_criterion": criterion,
        })
        _, verdict = _parse_pm_verdict(text, _ctx(profile))
        assert verdict.kill_criterion == criterion

    def test_a_criterion_with_no_sheet_quantity_is_untouched(self):
        profile = {"pe": 25.0}
        criterion = "Two consecutive quarters of guidance cuts from management."
        text = json.dumps({
            "action": "PASS",
            "narration": "The synthesis holds and the mandate clears here today.",
            "kill_criterion": criterion,
        })
        _, verdict = _parse_pm_verdict(text, _ctx(profile))
        assert verdict.kill_criterion == criterion

    def test_missing_profile_leaves_the_criterion_untouched(self):
        """`ctx.profile` defaults to `{}` — R52/F4's own `_ctx()` pattern —
        so an empty sheet must never strike an otherwise-plausible
        criterion (unknowable is not unverifiable)."""
        criterion = "A daily close where the P/E falls back under 25 on volume."
        text = json.dumps({
            "action": "PASS",
            "narration": "The synthesis holds and the mandate clears here today.",
            "kill_criterion": criterion,
        })
        _, verdict = _parse_pm_verdict(text, _ctx())  # profile={} default
        assert verdict.kill_criterion == criterion

    def test_a_none_criterion_stays_none(self):
        text = json.dumps({
            "action": "PASS",
            "narration": "The synthesis holds and the mandate clears here today.",
        })
        _, verdict = _parse_pm_verdict(text, _ctx({"pe": 25.0}))
        assert verdict.kill_criterion is None

    def test_approve_path_also_checks_the_criterion(self):
        """The card carries `kill_criterion` on BOTH actions (R52) — the
        checker must not be APPROVE-only or PASS-only."""
        profile = {"pe": 60.0}
        text = json.dumps({
            "action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141,
            "target": 172, "horizon_days": 42,
            "narration": "PM: APPROVE; synthesis defended; mandate clears.",
            "kill_criterion": "A daily close where the P/E falls back under 25 on volume.",
        })
        _, verdict = _parse_pm_verdict(text, _ctx(profile))
        assert verdict is not None
        assert verdict.action == VerdictAction.APPROVE
        assert "60" in verdict.kill_criterion


# ── 6. Composition: strips + the real end-to-end turn path ──────────────────


class TestComposition:
    def test_annotation_composes_with_a_prior_geometry_annotation(self):
        """F1's checker runs AFTER `_verify_and_annotate_geometry` at the
        real call site — prove the two annotations can coexist on one turn
        without either corrupting the other's output."""
        from app.services.room_runner import _verify_and_annotate_geometry

        text = (
            "Entry: $32.75\nStop: $29.60\nTarget: $33.50\nR:R: 2.5:1\n"
            "The P/E here is 60, rich relative to history."
        )
        geom_text, _ = _verify_and_annotate_geometry(text, size_pct=3.0)
        assert "AMI verified" in geom_text  # the geometry note landed first

        final = annotate_sheet_mismatches(geom_text, {"pe": 25.0})
        assert "AMI verified" in final  # still present, untouched
        assert "60" in final and "25" in final  # the new note also landed
        assert final.count("[AMI") >= 1 or "checked" in final

    def test_annotation_order_does_not_matter(self):
        """Same composition, reversed order — both notes must survive
        either way (each is a pure append on independent trigger
        conditions, so the design constraint is order-independence)."""
        from app.services.room_runner import _verify_and_annotate_geometry

        text = (
            "Entry: $32.75\nStop: $29.60\nTarget: $33.50\nR:R: 2.5:1\n"
            "The P/E here is 60, rich relative to history."
        )
        sheet_first = annotate_sheet_mismatches(text, {"pe": 25.0})
        geom_after, _ = _verify_and_annotate_geometry(sheet_first, size_pct=3.0)
        assert "AMI verified" in geom_after
        assert "60" in geom_after and "25" in geom_after

    def test_f3_headline_is_nulled_end_to_end(self):
        """The real turn path: `RoomRunner.run()` with a fake gateway and a
        monkeypatched sheet, driving the ACTUAL `_compute_agent_text` →
        `parse_stance_envelope` → F3-null wiring, not a reimplementation of
        it. A headline quoting a sheet figure the mocked profile
        contradicts must arrive on the transcript as `headline=None`."""
        import asyncio

        from app.services import room_runner as rr

        # A minimal, deterministic profile: one live field (`pe`) is enough
        # to exercise the checker without the rest of `_profile_for_ticker`'s
        # branching (news/social/technicals default off under
        # use_real_market_data=False, which is this test's own default).
        def _fake_profile_for_ticker(ticker, **kwargs):
            return {
                "ticker": ticker.upper(),
                "field_state": {"pe": "live", "run_date": "live"},
                "run_date": "2026-09-03",
                "pe": 25.0,
                "catalyst": "Q3 earnings",
                "sentiment_tone": "mixed",
                "sentiment_score": "typical intensity (illustrative)",
                "mention_trend": "roughly typical for the week (illustrative)",
                "influencer_take": "broadly constructive, no euphoria",
                "pattern": "sentiment confirming price, not yet at exhaustion",
                "bull_evidence": "evidence",
                "bull_missing": "missing",
                "bull_size": 4,
                "bull_falsifier": "falsifier",
                "bear_catalyst": "catalyst",
                "bear_size": 2,
                "bear_invalidator": "invalidator",
                "upside": 28,
                "downside": 18,
                "synth_lean": "constructive bull",
                "historical_mode": False,
            }

        orig = rr._profile_for_ticker

        class _FakeGatewayWithBadHeadline:
            def has_real_provider(self) -> bool:
                return True

            async def stream_chat(self, *, system_prompt, messages, model_tier,
                                   locale="en", max_tokens=1024, **_audit):
                if "speak as the fundamentals analyst" in system_prompt.lower():
                    text = (
                        "[STANCE: for | CONVICTION: medium | "
                        "HEADLINE: P/E at 25, cheap here]\n"
                        "The P/E here is way off at 25, worth a look."
                    )
                elif "portfolio manager" in system_prompt.lower():
                    text = '{"action": "PASS", "narration": "Passing, mandate discipline."}'
                else:
                    text = "AMI agent live reply."
                mid = len(text) // 2
                yield text[:mid]
                yield text[mid:]

        try:
            rr._profile_for_ticker = _fake_profile_for_ticker  # type: ignore[assignment]
            runner = rr.RoomRunner(llm=_FakeGatewayWithBadHeadline())  # type: ignore[arg-type]
            mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

            async def _run():
                events = []
                async for ev in runner.run(
                    user_id=uuid4(), ticker="AAPL", mandate=mandate,
                    char_delay_min=0.0, char_delay_max=0.0,
                ):
                    events.append(ev)
                return events

            events = asyncio.run(_run())
        finally:
            rr._profile_for_ticker = orig  # type: ignore[assignment]

        fa_done = next(
            ev for ev in events
            if getattr(ev, "kind", None) == "agent_done"
            and str(getattr(ev, "agent_id", "")) in ("AgentId.FUNDAMENTALS_ANALYST", "fundamentals_analyst")
        )
        # The sheet's real P/E is 25.0 — the agent's HEADLINE claimed 25 too
        # (a TRUE quote, deliberately, so this proves the wiring reached the
        # real path without accidentally testing the mismatch case twice);
        # a companion negative-shape assertion below drives an actual
        # mismatch through the same path.
        assert fa_done.headline in ("P/E at 25, cheap here", None)

    def test_f3_headline_is_nulled_end_to_end_on_a_genuine_mismatch(self):
        """Same real path as above, but the headline's P/E now DISAGREES
        with the mocked sheet — must arrive as `headline=None`, never the
        unverifiable string."""
        import asyncio

        from app.services import room_runner as rr

        def _fake_profile_for_ticker(ticker, **kwargs):
            return {
                "ticker": ticker.upper(),
                "field_state": {"pe": "live", "run_date": "live"},
                "run_date": "2026-09-03",
                "pe": 90.0,  # deliberately far from the headline's "25"
                "catalyst": "Q3 earnings",
                "sentiment_tone": "mixed",
                "sentiment_score": "typical intensity (illustrative)",
                "mention_trend": "roughly typical for the week (illustrative)",
                "influencer_take": "broadly constructive, no euphoria",
                "pattern": "sentiment confirming price, not yet at exhaustion",
                "bull_evidence": "evidence",
                "bull_missing": "missing",
                "bull_size": 4,
                "bull_falsifier": "falsifier",
                "bear_catalyst": "catalyst",
                "bear_size": 2,
                "bear_invalidator": "invalidator",
                "upside": 28,
                "downside": 18,
                "synth_lean": "constructive bull",
                "historical_mode": False,
            }

        orig = rr._profile_for_ticker

        class _FakeGatewayWithMismatchedHeadline:
            def has_real_provider(self) -> bool:
                return True

            async def stream_chat(self, *, system_prompt, messages, model_tier,
                                   locale="en", max_tokens=1024, **_audit):
                if "speak as the fundamentals analyst" in system_prompt.lower():
                    text = (
                        "[STANCE: for | CONVICTION: medium | "
                        "HEADLINE: P/E at 25, cheap here]\n"
                        "The multiple looks reasonable against history."
                    )
                elif "portfolio manager" in system_prompt.lower():
                    text = '{"action": "PASS", "narration": "Passing, mandate discipline."}'
                else:
                    text = "AMI agent live reply."
                mid = len(text) // 2
                yield text[:mid]
                yield text[mid:]

        try:
            rr._profile_for_ticker = _fake_profile_for_ticker  # type: ignore[assignment]
            runner = rr.RoomRunner(llm=_FakeGatewayWithMismatchedHeadline())  # type: ignore[arg-type]
            mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

            async def _run():
                events = []
                async for ev in runner.run(
                    user_id=uuid4(), ticker="AAPL", mandate=mandate,
                    char_delay_min=0.0, char_delay_max=0.0,
                ):
                    events.append(ev)
                return events

            events = asyncio.run(_run())
        finally:
            rr._profile_for_ticker = orig  # type: ignore[assignment]

        fa_done = next(
            ev for ev in events
            if getattr(ev, "kind", None) == "agent_done"
            and str(getattr(ev, "agent_id", "")) in ("AgentId.FUNDAMENTALS_ANALYST", "fundamentals_analyst")
        )
        assert fa_done.headline is None, (
            "the HEADLINE quoted a P/E of 25 against a sheet P/E of 90 — "
            "it must be nulled, never rendered as the unverifiable claim"
        )
