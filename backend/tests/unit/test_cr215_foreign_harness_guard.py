"""CR215 — structural guards on the foreign (non-Claude) harness tier.

The foreign auditor is ADVISORY. Its findings live in a file the dispatch board does not read, on a
branch that never reaches main, carrying a token no watcher parses. Those are three independent
reasons its opinion cannot move the gate — and all three are load-bearing, because the thing writing
that file is a model we do not control and did not train.

"Prompt instructions are not controls" (CLAUDE.md, CR038: agents ignore even emphatic instructions
~70% of the time). So the rule that the foreign tier never emits a board-parseable verdict is pinned
here rather than merely requested in a prompt.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FOREIGN_DIR = REPO / "orchestration" / "audit" / "foreign"
AUDIT_LAUNCHER = REPO / "orchestration" / "audit" / "dispatch_foreign_audit.sh"
DISPATCH_LAUNCH = REPO / "orchestration" / "dispatch" / "dispatch_launch.sh"
AGENT_FILE = FOREIGN_DIR / "AUDITOR_AGENT.md"

# Byte-identical to what the board itself parses — dispatch.sh:62 TOK plus the verdict keywords.
BOARD_VERDICT = re.compile(r"^(#{1,6} )?\*{0,2}VERDICT: *(COMPLETE|AWAITING_FIXES)", re.M)


def test_foreign_findings_never_emit_a_board_parseable_verdict() -> None:
    """A foreign finding file must not contain a line the board would read as a verdict.

    `dispatch.sh` and `watcher.sh` both derive lane state from the LAST line emitting
    `VERDICT: COMPLETE|AWAITING_FIXES`. A foreign model that wrote one unfenced would be voting in
    a gate it is not part of.
    """
    for path in sorted(FOREIGN_DIR.glob("*.foreign.md")):
        text = path.read_text(encoding="utf-8")
        assert not BOARD_VERDICT.search(text), (
            f"{path.relative_to(REPO)} emits a board-parseable VERDICT: token. "
            "Foreign output is advisory and must use FOREIGN-VERDICT:."
        )


def test_agent_file_states_the_verdict_prohibition() -> None:
    text = AGENT_FILE.read_text(encoding="utf-8")
    assert "FOREIGN-VERDICT:" in text
    assert "Never begin a line with `VERDICT:`" in text, (
        "the foreign auditor's role file must state the prohibition explicitly"
    )


def test_launcher_structurally_rejects_a_verdict_token() -> None:
    """The prohibition is checked after the run, not merely asked for before it."""
    text = AUDIT_LAUNCHER.read_text(encoding="utf-8")
    assert "grep -qE '^(#{1,6} )?\\*{0,2}VERDICT: *(COMPLETE|AWAITING_FIXES)'" in text, (
        "dispatch_foreign_audit.sh must grep the produced file for a board-parseable verdict"
    )
    assert "QUARANTINED" in text


def test_launcher_guard_regex_matches_the_board_token_verbatim() -> None:
    """Parity pin, in the spirit of test_config_compose_parity.

    The launcher's quarantine only works while it recognises exactly what the board recognises. If
    `dispatch.sh`'s TOK is ever widened, this fails until the foreign guard is widened with it —
    otherwise the guard silently stops covering the token it exists to catch.
    """
    board = (REPO / "orchestration" / "dispatch" / "dispatch.sh").read_text(encoding="utf-8")
    match = re.search(r"^TOK='([^']+)'", board, re.M)
    assert match, "dispatch.sh no longer defines TOK — the foreign guard's parity anchor is gone"
    tok = match.group(1)
    assert tok == r"^(#{1,6} )?\*{0,2}", f"dispatch.sh TOK changed to {tok!r}"
    launcher = AUDIT_LAUNCHER.read_text(encoding="utf-8")
    assert tok + "VERDICT: *(COMPLETE|AWAITING_FIXES)" in launcher, (
        "the foreign launcher's quarantine regex has drifted from the board's TOK"
    )


def test_launcher_records_unavailability_rather_than_failing_silently() -> None:
    """DEF059: absence of foreign findings must never read as the foreign tier being satisfied."""
    text = AUDIT_LAUNCHER.read_text(encoding="utf-8")
    assert "unavailable()" in text
    assert "UNAVAILABLE" in text
    # every early-exit on a missing precondition routes through unavailable(), never a bare exit 0
    assert "|| unavailable" in text or "unavailable \"" in text


def test_foreign_audit_never_writes_the_lane_file_the_board_reads() -> None:
    """The advisory output path must not be the gated one (`audit/cr/<ITEM>.auditor.md`)."""
    # Comments may legitimately name the gated path to explain why it is off limits; only the
    # executable lines matter.
    code = "\n".join(
        line for line in AUDIT_LAUNCHER.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "audit/cr/" not in code, (
        "the foreign launcher must never write into orchestration/audit/cr/, which the board reads"
    )
    assert 'REL_OUT="orchestration/audit/foreign/' in code


def test_local_tier_is_refused_for_an_auditor() -> None:
    """BINDINGS.md:73 'Never economy tier for an auditor'; `local` is cheaper still.

    DEF059 is the precedent: a gate that can fail open manufactures a confident fake APPROVE.
    """
    text = DISPATCH_LAUNCH.read_text(encoding="utf-8")
    assert "refusing TIER=local for auditor-shaped instance" in text
    assert "*auditor*|*audit*)" in text


def test_local_tier_fails_loud_when_the_coder_home_is_unregistered() -> None:
    """CLAUDE.md degrade-loudly: a missing provider must not silently fall back to a Claude model."""
    text = DISPATCH_LAUNCH.read_text(encoding="utf-8")
    assert "TIER=local UNAVAILABLE" in text
    assert "register_ami_vllm.sh" in text


def test_claude_tiers_are_untouched_by_the_local_tier() -> None:
    """The foreign tier is additive. The three Claude tiers keep their exact model/effort/budget."""
    text = DISPATCH_LAUNCH.read_text(encoding="utf-8")
    for expected in (
        'economy)  MODEL="claude-haiku-4-5-20251001"; EFFORT="low";    BUDGET=2',
        'standard) MODEL="claude-sonnet-5";           EFFORT="medium"; BUDGET=5',
        'premium)  MODEL="claude-opus-4-8";           EFFORT="high";   BUDGET=10',
    ):
        assert expected in text, f"CR057 tier row changed: {expected}"
