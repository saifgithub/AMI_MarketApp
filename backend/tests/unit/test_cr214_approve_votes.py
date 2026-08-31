"""CR214 / DEF383 — the graded verdict score, and the crash that guarded it.

CR214 raises `pm_self_consistency_samples` to 5 so the Room's verdict stops being a
coin flip on roughly one call in five. Two things fall out of that, and both are
pinned here.

**DEF383 — the branch had never run.** `Verdict` sets `use_enum_values=True`, so
`verdict.action` is a plain `str` once validated. `room_runner` logged
`action=verdict.action.value` immediately after a successful vote, which raises
`AttributeError` on a str. It never fired because the vote branch is gated on
`pm_self_consistency_samples > 1` and the default was 1 from CR197 until CR214 —
i.e. the first production convene after the default changed would have taken the
AttributeError instead of a verdict. A test that only exercises `_vote_pm_samples`
misses it entirely, because the crash is at the call site, not in the vote.

**CR214 — `approve_votes` is not the agreement string.** The agreement string counts
the winner, so a 2-approve/3-pass draw and a 0-approve/5-pass draw both read as a
PASS and the first is invisible. `approve_votes` separates them. That distinction is
the entire reason the field exists: it turns a binary verdict, which parks ~90% of
convenes in a bucket that carries no signal, into a 0..N score every convene
contributes to.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.schemas.room import Verdict, VerdictAction
from app.services import room_runner
from app.services.room_runner import _vote_pm_samples

_RUNNER_SRC = Path(room_runner.__file__).read_text()


def _v(action: VerdictAction, size: float | None = None) -> Verdict:
    return Verdict(action=action, size_pct=size, reason="r")


# ── DEF383 ───────────────────────────────────────────────────────────────────


def test_verdict_action_is_a_str_not_an_enum_after_validation():
    """The premise of DEF383. If this ever flips back to an enum the guard below
    stops guarding anything, so pin the premise rather than only the symptom."""
    v = _v(VerdictAction.APPROVE)
    assert isinstance(v.action, str)
    assert not hasattr(v.action, "value")
    assert v.action == VerdictAction.APPROVE  # str-enum compare still works


def test_the_voted_verdict_carries_a_str_action():
    _n, v, _a = _vote_pm_samples([("n", _v(VerdictAction.PASS))] * 3)
    assert not hasattr(v.action, "value")


def test_the_self_consistency_log_never_calls_dot_value_on_an_action():
    """DEF383 regression, read off the source: the crash is a call-site expression,
    so there is no unit-level seam to exercise it without standing up a whole run.
    Parse instead — any `.action.value` in the runner is the same bug returning."""
    tree = ast.parse(_RUNNER_SRC)
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "value"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "action"
    ]
    assert not offenders, (
        f"`.action.value` on a use_enum_values field at line(s) {offenders} — "
        "DEF383. Verdict.action is already a str; use str(verdict.action)."
    )


# ── CR214: the graded score ──────────────────────────────────────────────────


def test_the_field_defaults_to_absent_not_zero():
    """Absence is absence (the `level_provenance` convention). A run with the knob
    off must not look like a run where nobody voted to approve — that would read as
    a real 0/N score in any downstream rank statistic."""
    v = _v(VerdictAction.PASS)
    assert v.approve_votes is None
    assert v.samples is None


def test_approve_votes_survives_the_jsonb_round_trip():
    """`room_runs.verdict` is JSONB, which is why CR214 needs no migration — but
    only if the field actually serialises."""
    v = _v(VerdictAction.PASS).model_copy(
        update={"approve_votes": 2, "samples": 5}
    )
    assert Verdict(**v.model_dump()).approve_votes == 2


def test_a_split_pass_is_distinguishable_from_a_unanimous_one():
    """The whole point. Both of these are a PASS and both report agreement over the
    WINNER, so the agreement string cannot tell them apart."""
    split = [("n", _v(VerdictAction.APPROVE, 3.0))] * 2 + [
        ("n", _v(VerdictAction.PASS))
    ] * 3
    unanimous = [("n", _v(VerdictAction.PASS))] * 5

    _n1, v1, agree1 = _vote_pm_samples(split)
    _n2, v2, agree2 = _vote_pm_samples(unanimous)

    assert v1.action == VerdictAction.PASS
    assert v2.action == VerdictAction.PASS
    assert agree1 == "3/5" and agree2 == "5/5"

    # The call site computes this; recomputing it here pins the definition.
    def approve_votes(parsed):
        return sum(
            1
            for _n, _v_ in parsed
            if _v_.action in (VerdictAction.APPROVE, VerdictAction.MODIFY)
        )

    assert approve_votes(split) == 2
    assert approve_votes(unanimous) == 0


def test_the_call_site_records_votes_over_parsed_samples_not_requested_ones():
    """An unparseable draw is dropped before the vote, so the denominator must be
    the parsed count. Recording the requested count instead would silently deflate
    the score whenever the model emitted something malformed."""
    block = _RUNNER_SRC[_RUNNER_SRC.index("_approve_votes = sum("):]
    block = block[: block.index("logger.info(")]
    assert '"samples": len(_cands)' in block, (
        "denominator must be the parsed sample count (_cands), not _pm_samples"
    )


def test_a_safety_floor_override_keeps_the_vote():
    """`enforce_safety_floor`'s override branch builds a FRESH Verdict rather than
    copying, so any field not named there is silently dropped. Dropping the vote
    here would lose it on exactly the rows that carry the most information — a
    floor-overridden REJECT is a run the Room wanted in on. The floor's decision is
    not under test; only that provenance survives it."""
    import ast

    src = Path(
        Path(room_runner.__file__).parent.parent / "agents" / "safety_floor.py"
    ).read_text()
    tree = ast.parse(src)
    overrides = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Verdict"
        and any(
            kw.arg == "overridden_from_llm" for kw in node.keywords
        )
    ]
    assert overrides, "no safety-floor override Verdict construction found"
    for node in overrides:
        named = {kw.arg for kw in node.keywords}
        assert {"approve_votes", "samples"} <= named, (
            "safety-floor override drops the CR214 vote fields; a fresh Verdict "
            "keeps only what it names"
        )
