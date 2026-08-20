"""DEF240 — when a mandate permits a large single-name position, AMI says so.

Saiful's ruling, 2026-08-08, after three per-agent reviews of the CR143 audit
found the same thing independently: *"Keep it, but make AMI say the number out
loud."*

Nothing was broken. `day_trader_preset.py` really does set
`single_name_cap_pct: 100.0`; 7 of 18 epoch convenes ran under it; the floor
enforces exactly what the prompt states. The agents were behaving correctly when
the Bull argued 50% of portfolio in one name and the Aggressive argued 100% into
a book already 95.8% GME. The defect is that every rendered figure stayed neutral
about what that concentration means — CR040's question inverted.

These tests hold the disclosure to three properties: it fires on the ENFORCED
size (never the requested one), it is factual rather than advisory (AMI is
simulation-only), and it never becomes a veto (DEF059 — the safety floor is the
sole vetoer).
"""

from __future__ import annotations

import pytest

from app.services.room_runner import (
    _LOUD_CONCENTRATION_PCT,
    _concentration_note,
)


def test_below_the_threshold_says_nothing():
    """An ordinary 3% position must not carry a concentration sentence — a
    disclosure that fires on everything is read as boilerplate and stops working."""
    assert _concentration_note(3.0, 3.0) == ""
    assert _concentration_note(25.0, 100.0) == "", "the threshold is exclusive"


def test_above_the_threshold_states_the_share_and_the_cap():
    note = _concentration_note(50.0, 100.0)
    assert "50.0% of the portfolio in one name" in note
    assert "single-name cap is 100.0%" in note
    assert "this position does not exceed it" in note


def test_the_note_is_factual_not_advisory():
    """AMI is simulation-only and does not advise. The sentence states a share and
    the cap it sits under — no recommendation, no adjective, no imperative.

    **This list is a floor, not the check.** The round-1 audit MAJOR was
    "so the safety floor permits it", and no word here would have caught it:
    "permits" is not advice-shaped in isolation, only as this sentence's
    conclusion, where it reads as authorization — the same connotation as "the
    law permits it". Tone is settled by a human reading the sentence; these
    assertions only stop a known regression.
    """
    note = _concentration_note(60.0, 100.0).lower()
    advisory = (
        "should", "recommend", "advise", "consider reducing", "too much",
        "risky", "dangerous", "warning", "careful", "we suggest",
    )
    # Round-1 MAJOR: authorization verbs turn a disclosure into a sanction.
    authorising = (
        "permits", "permitted", "allows", "allowed", "approved", "sanctioned",
        "cleared", "acceptable", "is fine", "is safe", "no problem",
    )
    for banned in advisory + authorising:
        assert banned not in note, f"{banned!r} turns a disclosure into a verdict on the trade"


def test_the_note_states_what_is_true_not_what_is_sanctioned():
    """The sibling disclosures are the standard: "(sized down to 40.0% — mandate
    risk-tier ceiling.)" states what HAPPENED. The round-1 version of this note
    stated an evaluative OUTCOME (permitted vs not). Both are true; only one is a
    disclosure. The user must still learn why the trade was not blocked."""
    note = _concentration_note(50.0, 100.0)
    assert "does not exceed" in note, (
        "the user still needs to know why this was not blocked"
    )


def test_a_missing_cap_still_states_the_share():
    """Degrade loudly: an unresolvable cap must not swallow the concentration
    figure, which is the half the user actually needs."""
    note = _concentration_note(50.0, None)
    assert "50.0% of the portfolio in one name" in note
    assert "cap" not in note


def test_no_size_says_nothing():
    assert _concentration_note(None, 100.0) == ""


def test_the_threshold_is_a_disclosure_line_not_a_risk_limit():
    """25% is four equal names — the point past which one company's outcome, not a
    portfolio's, is what the book tracks. Pinned so a later edit has to argue with
    the number rather than drift it."""
    assert _LOUD_CONCENTRATION_PCT == 25.0


# ── the enforced size, not the requested one ──────────────────────────────────


def _approve(size_pct: float, cap: float) -> str:
    """Drive the real PM APPROVE assembly and return `verdict.reason`."""
    import json
    from uuid import uuid4

    from app.schemas.agents import AgentId
    from app.schemas.room import VerdictAction
    from app.services.coach_engine import hydrate_coach_mandate
    from app.services.room_runner import RoomRunner

    captured: dict[str, object] = {}

    class _Gateway:
        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            if "speak as the chief investment officer" in system_prompt.lower():
                yield json.dumps({
                    "action": "APPROVE", "size_pct": size_pct,
                    "entry": 100.0, "stop": 94.0, "target": 113.0,
                    "horizon_days": 42, "narration": "PM: take it.",
                })
            else:
                yield "[STANCE: for | CONVICTION: high | HEADLINE: x]\nA reply."

    import asyncio

    async def _drain():
        async for ev in RoomRunner(llm=_Gateway()).run(  # type: ignore[arg-type]
            user_id=uuid4(), ticker="MSFT",
            mandate=hydrate_coach_mandate({
                "plan": "trader", "risk_score": 3, "single_name_cap_pct": cap,
            }),
            char_delay_min=0.0, char_delay_max=0.0,
        ):
            if ev.kind == "verdict":
                captured["v"] = ev.verdict

    asyncio.run(_drain())
    v = captured.get("v")
    assert v is not None, "no verdict was emitted"
    return v.reason or ""


def test_def240_fires_on_a_permissive_mandate_end_to_end():
    """A 100% cap, a PM that asks for 50%: the floor permits it, and the reason
    the user reads must say what 50% in one name is."""
    reason = _approve(size_pct=50.0, cap=100.0)
    assert "Concentration: this is 50.0% of the portfolio in one name" in reason
    assert "single-name cap is 100.0%" in reason


def test_def240_states_the_CLAMPED_size_not_the_requested_one():
    """The PM asks for 90% under a 40% cap. The floor clamps to 40%, so the
    disclosure must say 40% — stating the request would describe a position the
    user never gets, which is the DEF235 failure in a new place."""
    reason = _approve(size_pct=90.0, cap=40.0)
    assert "40.0% of the portfolio in one name" in reason
    assert "90" not in reason.split("Concentration:")[1]


def test_def240_is_silent_on_an_ordinary_mandate_end_to_end():
    """The 3.0% risk-tier default: no concentration sentence anywhere."""
    reason = _approve(size_pct=3.0, cap=3.0)
    assert "Concentration:" not in reason


def test_def240_never_changes_the_verdict():
    """DEF059 — the safety floor is the sole vetoer. A concentration disclosure is
    a sentence, never a decision: the same trade must still be APPROVE."""
    import json
    from uuid import uuid4
    import asyncio

    from app.schemas.room import VerdictAction
    from app.services.coach_engine import hydrate_coach_mandate
    from app.services.room_runner import RoomRunner

    captured: dict[str, object] = {}

    class _Gateway:
        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            if "speak as the chief investment officer" in system_prompt.lower():
                yield json.dumps({
                    "action": "APPROVE", "size_pct": 80.0, "entry": 100.0,
                    "stop": 94.0, "target": 113.0, "horizon_days": 42,
                    "narration": "PM: take it.",
                })
            else:
                yield "[STANCE: for | CONVICTION: high | HEADLINE: x]\nA reply."

    async def _drain():
        async for ev in RoomRunner(llm=_Gateway()).run(  # type: ignore[arg-type]
            user_id=uuid4(), ticker="MSFT",
            mandate=hydrate_coach_mandate({
                "plan": "trader", "risk_score": 3, "single_name_cap_pct": 100.0,
            }),
            char_delay_min=0.0, char_delay_max=0.0,
        ):
            if ev.kind == "verdict":
                captured["v"] = ev.verdict

    asyncio.run(_drain())
    v = captured["v"]
    assert v.action == VerdictAction.APPROVE.value
    assert "Concentration:" in (v.reason or "")


# ── the geometry annotation, the other surface the ruling names ───────────────


def test_def240_geometry_annotation_says_it_too():
    """The ruling names both surfaces: "the drawdown annotation and the PM
    verdict". The annotation already states the cap as a percentage (DEF235);
    above the threshold it must also say what that percentage IS.

    This is the half a `verdict.reason`-only test misses — and it did: mutation
    MUT-8 (delete this clause) SURVIVED the first pass with all 10 other DEF240
    tests green.
    """
    from app.services.room_runner import _verify_and_annotate_geometry

    text = "Entry: $100\nStop: $94\nTarget: $113\nR:R: 9:1"
    annotated, _sig = _verify_and_annotate_geometry(text, size_pct=100.0)
    assert "at the mandate's 100.0% single-name cap" in annotated
    assert "that cap is 100.0% of the portfolio in one name" in annotated


def test_def240_geometry_annotation_is_silent_on_an_ordinary_cap():
    from app.services.room_runner import _verify_and_annotate_geometry

    text = "Entry: $100\nStop: $94\nTarget: $113\nR:R: 9:1"
    annotated, _sig = _verify_and_annotate_geometry(text, size_pct=3.0)
    assert "at the mandate's 3.0% single-name cap" in annotated
    assert "of the portfolio in one name" not in annotated
