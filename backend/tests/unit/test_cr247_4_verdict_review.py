"""CR247 Phase 4 — the second-pass verdict review (D11–D13, D27).

Two audits, routed and combined in deterministic code; only the audits are
LLM calls, and they run on the gateway's FALLBACK provider — a different
model than the CIO (D18's model-correlation test at +1 call on ~16% of
convenes, D12's approval base rate):

  * veto review (on APPROVE) — fail the approval when the Bear's or the
    Conservative's specific, numbered objections went unanswered with numbers
    in the CIO's narration. Combination is code: final = APPROVE only if the
    audit upholds. A veto flips to PASS (never REJECT — the veto denies the
    approval, it does not assert the opposite), narrated "Veto review
    (audit): …", journaled with the original verdict preserved. An
    UNPARSEABLE veto audit is not an approve: the approval it could not read
    flips to PASS with "audit unparseable" — pinned here.
  * resurrection review (on PASS) — show the PASS rested on evidence the
    mandate makes inadmissible (the Phase 2.3 horizon line defines
    inadmissibility). It cannot approve: reconsider re-runs the CIO ONCE
    with the audit note appended (pinned text), the re-run meets the same
    safety floor, and the re-run's verdict is final — no loops, no second
    review. An unparseable resurrection audit fails CLOSED (no re-run).

Degrades (CR040), all pinned: no fallback provider registered -> loud warn +
skip-with-journal, verdict unchanged; scripted dissent or a scripted/outage/
fail-safe verdict -> no review at all (nothing real to audit); the routed
record rides `Verdict.verdict_review` into the Decision Journal snapshot.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path as _FsPath
from uuid import uuid4

import pytest
import structlog

from app.core.config import Settings, settings
from app.schemas import AgentId
from app.schemas.agents import AgentMessage
from app.schemas.room import Verdict, VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import (
    RESURRECTION_AUDIT_NOTE_SENTINEL,
    resurrection_review_schema,
    veto_review_schema,
)
from app.services.room_runner import (
    RoomRunner,
    _apply_verdict_review,
    _RoomContext,
)
from tests.unit.test_room_runner import _collect, _FakeGateway

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

import test_config_compose_parity as _compose_parity  # noqa: E402

PM_APPROVE = json.dumps(
    {
        "action": "APPROVE",
        "size_pct": 3.0,
        "entry": 150.0,
        "stop": 141.0,
        "target": 172.0,
        "horizon_days": 42,
        "narration": "PM: APPROVE; the desk's plan is sound and the mandate clears.",
        "kill_criterion": "A close below the 200-day SMA at $141.00 would reverse this call.",
    }
)
PM_APPROVE_RERUN = json.dumps(
    {
        "action": "APPROVE",
        "size_pct": 2.0,
        "entry": 150.0,
        "stop": 141.0,
        "target": 172.0,
        "horizon_days": 42,
        "narration": "PM: APPROVE on reconsideration; the fundamental case carries it.",
        "kill_criterion": "A close below the 200-day SMA at $141.00 would reverse this call.",
    }
)
PM_PASS = json.dumps(
    {
        "action": "PASS",
        "narration": "PM: PASS; RSI is overbought and the tape is choppy here.",
        "kill_criterion": "A pullback to the 50-day SMA with margin trend intact would reopen this.",
    }
)
PM_PASS_RERUN = json.dumps(
    {
        "action": "PASS",
        "narration": "PM: PASS; even setting the technicals aside, the Bear's margin case stands.",
        "kill_criterion": "A pullback to the 50-day SMA with margin trend intact would reopen this.",
    }
)

# Distinctive dissent text the veto case must carry verbatim.
BEAR_CASE = (
    "1. Gross margin fell 220bps YoY to 41.2% with no guide recovery.\n"
    "2. OpenAI dependency: 34% of services revenue renegotiates in 18 months.\n"
    "3. Regulatory overhang: the antitrust docket names the app store billing."
)
CONSERVATIVE_CASE = (
    "1. At 3.0% size the stop implies 0.6% portfolio risk against a 20% cap — fine — "
    "but the entry chases a 12% two-week run.\n"
    "2. No position is justified without an earnings date outside the holding window."
)

VETO_JSON = json.dumps(
    {"decision": "veto", "reasons": [
        "Bear objection 1 (gross margin 220bps) is waved at, never answered with numbers",
    ]}
)
UPHOLD_JSON = json.dumps(
    {"decision": "uphold", "reasons": [
        "The narration engages each numbered objection with the fact-sheet figures",
    ]}
)
RECONSIDER_JSON = json.dumps(
    {"decision": "reconsider", "reasons": [
        "The PASS rests on 'RSI is overbought' — inadmissible under a long horizon",
    ]}
)
RESURRECTION_UPHOLD_JSON = json.dumps(
    {"decision": "uphold", "reasons": [
        "The PASS rests on the Bear's admissible margin and concentration case",
    ]}
)
GARBAGE = "I cannot comply with that format request."


def _mandate(**overrides):
    base = {"plan": "trader", "risk_score": 3, "horizon": "long"}
    base.update(overrides)
    return hydrate_coach_mandate(base)


class _ReviewGateway(_FakeGateway):
    """Full-convene fake with a review lane: programmed per-flow replies, a
    PM FIFO (so the resurrection re-run can answer differently from the
    original draw), full message recording for prompt-content assertions, and
    a `pick_review_provider` stub (None simulates the missing-Anthropic-key
    environment)."""

    def __init__(self, replies=None, *, review_provider="anthropic"):
        super().__init__(replies=replies)
        self._review_provider = review_provider
        self.review_replies: dict[str, str] = {}
        self.review_calls: list[dict] = []
        self.pm_calls: list[dict] = []
        self.pm_queue: list[str] = []

    def pick_review_provider(self):
        return self._review_provider

    async def stream_chat(
        self, *, system_prompt, messages, model_tier, locale="en",
        max_tokens=1024, **kw,
    ):
        flow = kw.get("audit_flow")
        if flow in ("room_veto_review", "room_resurrection_review"):
            self.review_calls.append({
                "flow": flow,
                "system_prompt": system_prompt,
                "messages": messages,
                "constraint": kw.get("constraint"),
                "provider_name": kw.get("provider_name"),
            })
            text = self.review_replies.get(flow, UPHOLD_JSON)
            mid = len(text) // 2
            yield text[:mid]
            yield text[mid:]
            return
        if kw.get("audit_agent_id") == AgentId.PORTFOLIO_MANAGER.value:
            self.pm_calls.append({"messages": messages, "system_prompt": system_prompt})
            if self.pm_queue:
                text = self.pm_queue.pop(0)
                mid = len(text) // 2
                yield text[:mid]
                yield text[mid:]
                return
        async for chunk in super().stream_chat(
            system_prompt=system_prompt, messages=messages,
            model_tier=model_tier, locale=locale, max_tokens=max_tokens, **kw,
        ):
            yield chunk


def _full_room_gateway(*, pm_first: str, review_provider="anthropic") -> _ReviewGateway:
    return _ReviewGateway(
        replies={
            "portfolio_manager": pm_first,
            "bear_researcher": BEAR_CASE,
            "conservative_debator": CONSERVATIVE_CASE,
        },
        review_provider=review_provider,
    )


def _run(gateway, monkeypatch, *, samples: int = 1, mandate=None):
    monkeypatch.setattr(settings, "pm_self_consistency_samples", samples)
    return _collect(
        RoomRunner(llm=gateway).run(  # type: ignore[arg-type]
            user_id=uuid4(),
            ticker="AAPL",
            mandate=mandate or _mandate(),
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
    )


def _verdict(events) -> Verdict:
    return next(e.verdict for e in events if e.kind == "verdict")


# ── 1. flags: defaults + compose parity ────────────────────────────────────


def test_both_review_flags_default_on():
    """D27 built BOTH reviews because the census could not pick. Read the
    model field, not the live singleton, so an earlier monkeypatch cannot
    mask a reverted default."""
    assert Settings.model_fields["room_veto_review_enabled"].default is True
    assert Settings.model_fields["room_resurrection_review_enabled"].default is True


def test_compose_forwards_both_review_flags():
    env = _compose_parity._api_alpha_env_block()
    assert "ROOM_VETO_REVIEW_ENABLED" in env
    assert "ROOM_RESURRECTION_REVIEW_ENABLED" in env


def test_neither_flag_is_in_the_not_forwarded_escape_hatch():
    assert "room_veto_review_enabled" not in _compose_parity._NOT_FORWARDED
    assert "room_resurrection_review_enabled" not in _compose_parity._NOT_FORWARDED


# ── 2. routing ──────────────────────────────────────────────────────────────


def test_veto_fires_on_approve_and_uphold_keeps_it(monkeypatch):
    gw = _full_room_gateway(pm_first=PM_APPROVE)
    gw.review_replies["room_veto_review"] = UPHOLD_JSON
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.APPROVE.value
    assert len(gw.review_calls) == 1
    assert gw.review_calls[0]["flow"] == "room_veto_review"
    assert gw.review_calls[0]["provider_name"] == "anthropic"
    assert v.verdict_review is not None
    assert v.verdict_review.kind == "veto"
    assert v.verdict_review.decision == "uphold"
    assert v.verdict_review.provider == "anthropic"
    assert v.verdict_review.original["action"] == "APPROVE"


def test_resurrection_fires_on_pass_and_uphold_stays_put(monkeypatch):
    gw = _full_room_gateway(pm_first=PM_PASS)
    gw.review_replies["room_resurrection_review"] = RESURRECTION_UPHOLD_JSON
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.PASS.value
    assert len(gw.review_calls) == 1
    assert v.verdict_review is not None
    assert v.verdict_review.kind == "resurrection"
    assert v.verdict_review.decision == "uphold"
    assert v.verdict_review.rerun is False
    assert len(gw.pm_calls) == 1, "uphold must not re-run the CIO"


def test_veto_flag_off_routes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "room_veto_review_enabled", False)
    gw = _full_room_gateway(pm_first=PM_APPROVE)
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.APPROVE.value
    assert gw.review_calls == []
    assert v.verdict_review is None, "not routed = absence, never a stand-in record"


def test_resurrection_flag_off_routes_nothing(monkeypatch):
    monkeypatch.setattr(settings, "room_resurrection_review_enabled", False)
    gw = _full_room_gateway(pm_first=PM_PASS)
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.PASS.value
    assert gw.review_calls == []
    assert v.verdict_review is None


def test_no_review_on_the_scripted_path(monkeypatch):
    """The structured-path guard: a convene with no real LLM provider is the
    scripted demo path — there is nothing real to audit, and the review must
    not fire (and especially must not try to reach a fallback provider)."""

    class _OfflineGateway(_FakeGateway):
        def has_real_provider(self):
            return False

        def pick_review_provider(self):  # even with a provider to name: no
            raise AssertionError("scripted path must not consult the reviewer")

    gw = _OfflineGateway()
    events = _run(gw, monkeypatch)
    v = _verdict(events)
    assert v.verdict_review is None


def test_no_review_on_the_outage_pass(monkeypatch):
    """DEF059's CIO-outage PASS is code-built, not a decision — no audit."""

    class _SilentPM(_ReviewGateway):
        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **kw):
            if kw.get("audit_agent_id") == AgentId.PORTFOLIO_MANAGER.value:
                return
            async for chunk in super().stream_chat(
                system_prompt=system_prompt, messages=messages,
                model_tier=model_tier, locale=locale, max_tokens=max_tokens, **kw,
            ):
                yield chunk

    gw = _SilentPM(
        replies={"bear_researcher": BEAR_CASE, "conservative_debator": CONSERVATIVE_CASE},
    )
    events = _run(gw, monkeypatch)
    v = _verdict(events)
    from app.services.room_runner import is_llm_outage_verdict

    assert is_llm_outage_verdict(v.model_dump())
    assert v.verdict_review is None
    assert gw.review_calls == []


def test_review_fires_once_per_convene_under_self_consistency(monkeypatch):
    """CR214's five-draw vote produces ONE verdict, so the audit fires once —
    not once per sample."""
    gw = _full_room_gateway(pm_first=PM_APPROVE)
    gw.review_replies["room_veto_review"] = UPHOLD_JSON
    events = _run(gw, monkeypatch, samples=3)
    v = _verdict(events)

    assert v.samples == 3
    assert v.approve_votes == 3
    assert len(gw.review_calls) == 1


# ── 3. the veto flip ────────────────────────────────────────────────────────


def test_a_veto_flips_approve_to_pass_with_the_original_preserved(monkeypatch):
    gw = _full_room_gateway(pm_first=PM_APPROVE)
    gw.review_replies["room_veto_review"] = VETO_JSON
    events = _run(gw, monkeypatch, samples=3)
    v = _verdict(events)

    assert v.action == VerdictAction.PASS.value, "a veto denies the approval"
    assert v.reason.startswith("Veto review (audit):")
    assert "gross margin 220bps" in v.reason
    # a PASS carries no trade levels — and no option structure either
    assert (v.size_pct, v.entry, v.stop, v.target, v.time_horizon_days) == (
        None, None, None, None, None,
    )
    assert v.structure is None
    assert v.level_provenance is None
    assert v.overridden_from_llm is True
    # CR214 — the vote travels with the flip, same as a floor override
    assert v.samples == 3
    assert v.approve_votes == 3
    # the original verdict is preserved in full on the record
    rec = v.verdict_review
    assert rec.kind == "veto"
    assert rec.decision == "veto"
    assert rec.original["action"] == "APPROVE"
    assert rec.original["size_pct"] == 3.0
    assert rec.original["entry"] == 150.0
    assert "desk's plan is sound" in rec.original["reason"]


def test_an_unparseable_veto_audit_is_not_an_approve(monkeypatch):
    """The pinned fail direction: final = APPROVE only if BOTH passes approve,
    and a pass that produced nothing readable approves nothing. The approval
    flips to PASS with 'audit unparseable' — never a silent uphold."""
    gw = _full_room_gateway(pm_first=PM_APPROVE)
    gw.review_replies["room_veto_review"] = GARBAGE
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.PASS.value
    assert "audit unparseable" in v.reason
    assert v.verdict_review.parse_failed is True
    assert v.verdict_review.decision is None
    assert v.verdict_review.original["action"] == "APPROVE"


# ── 4. the resurrection re-run ──────────────────────────────────────────────


def test_reconsider_reruns_the_cio_once_with_the_audit_note(monkeypatch):
    gw = _full_room_gateway(pm_first=PM_PASS)
    gw.review_replies["room_resurrection_review"] = RECONSIDER_JSON
    gw.pm_queue.extend([PM_PASS, PM_PASS_RERUN])
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    # exactly one re-run, carrying the audit note
    assert len(gw.pm_calls) == 2, "original draw + exactly one re-run"
    rerun_user = gw.pm_calls[1]["messages"][0].content
    assert RESURRECTION_AUDIT_NOTE_SENTINEL in rerun_user
    assert "RSI is overbought" in rerun_user, "the note carries the audit's reasons"
    assert "inadmissible" in rerun_user
    # the re-run's PASS is final: no loops, no second review
    assert v.action == VerdictAction.PASS.value
    assert len(gw.review_calls) == 1
    assert "Reconsidered once at the audit's request." in v.reason
    assert v.verdict_review.rerun is True
    assert v.verdict_review.rerun_action == "PASS"
    assert v.verdict_review.rerun_parse_failed is False
    # a single re-decision is not a vote; the original vote is on the record
    assert v.samples is None and v.approve_votes is None
    assert v.verdict_review.original["action"] == "PASS"


def test_a_reconsidered_approve_is_floor_checked_and_final(monkeypatch):
    gw = _full_room_gateway(pm_first=PM_PASS)
    gw.review_replies["room_resurrection_review"] = RECONSIDER_JSON
    # the FIFO holds BOTH draws: the original PASS, then the re-run's APPROVE
    gw.pm_queue.extend([PM_PASS, PM_APPROVE_RERUN])
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.APPROVE.value, "the re-run may approve"
    assert v.entry == 150.0 and v.size_pct == 2.0
    assert len(gw.review_calls) == 1, "the re-run's verdict is never itself reviewed"
    assert v.verdict_review.rerun_action == "APPROVE"
    # the narration the user watched is the re-run's
    assert "fundamental case carries it" in v.reason
    assert "Reconsidered once at the audit's request." in v.reason


def test_an_unparseable_resurrection_audit_fails_closed(monkeypatch):
    """Opposite fail direction from the veto: an unreadable resurrection audit
    must not send the CIO back on garbage — the verdict stands, loudly
    journaled."""
    gw = _full_room_gateway(pm_first=PM_PASS)
    gw.review_replies["room_resurrection_review"] = GARBAGE
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.PASS.value
    assert v.reason == "PM: PASS; RSI is overbought and the tape is choppy here."
    assert len(gw.pm_calls) == 1, "no re-run"
    assert v.verdict_review.parse_failed is True
    assert v.verdict_review.rerun is False


def test_an_unparseable_rerun_keeps_the_original_pass(monkeypatch):
    """A re-run that produces nothing readable never destroys the real,
    readable PASS it was meant to reconsider."""
    gw = _full_room_gateway(pm_first=PM_PASS)
    gw.review_replies["room_resurrection_review"] = RECONSIDER_JSON
    gw.pm_queue.extend([PM_PASS, "not a verdict at all"])
    events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.PASS.value
    assert "RSI is overbought" in v.reason
    # the re-run was attempted, and its garbage reply even went through the
    # DEF058 reformat retry before the original PASS was kept: draw + re-run
    # + reformat = three PM-flavoured calls, and no second review anywhere
    assert len(gw.pm_calls) == 3
    assert len(gw.review_calls) == 1
    assert v.verdict_review.rerun is True
    assert v.verdict_review.rerun_action is None
    assert v.verdict_review.rerun_parse_failed is True


# ── 5. prompt content ───────────────────────────────────────────────────────


def test_the_veto_prompt_carries_the_numbered_objections_and_the_narration(monkeypatch):
    gw = _full_room_gateway(pm_first=PM_APPROVE)
    gw.review_replies["room_veto_review"] = UPHOLD_JSON
    _run(gw, monkeypatch)

    (call,) = gw.review_calls
    case = call["messages"][0].content
    assert "Gross margin fell 220bps" in case
    assert "OpenAI dependency" in case
    assert "no position is justified" in case.lower()
    assert "desk's plan is sound" in case, "the CIO narration"
    assert "kill_criterion" in case
    assert "horizon: long" in case, "the mandate"
    # the wire carried the grammar demand
    assert call["constraint"] is not None
    assert call["constraint"].name == "veto_review"
    assert call["constraint"].json_schema == veto_review_schema()


def test_the_resurrection_prompt_carries_the_mandate_horizon(monkeypatch):
    gw = _full_room_gateway(pm_first=PM_PASS)
    gw.review_replies["room_resurrection_review"] = RESURRECTION_UPHOLD_JSON
    _run(gw, monkeypatch)

    (call,) = gw.review_calls
    case = call["messages"][0].content
    assert "horizon: long" in case
    assert "short-term technical readings inform entry timing only" in case, (
        "the Phase 2.3 line — the definition of inadmissibility"
    )
    assert "cannot validate or invalidate the thesis" in case
    assert "RSI is overbought" in case, "the PASS narration under audit"
    assert call["constraint"].name == "resurrection_review"
    assert call["constraint"].json_schema == resurrection_review_schema()


# ── 6. degrade: no fallback provider ────────────────────────────────────────


def test_no_fallback_provider_warns_skips_and_keeps_the_verdict(monkeypatch):
    """This environment has no ANTHROPIC_API_KEY; on Alpha the key exists.
    Either way the flag-ON-missing-key shape is pinned: a visible warning, a
    journal record, and the verdict UNCHANGED — never a silent skip, and the
    audit never falls back to the CIO's own model."""
    gw = _full_room_gateway(pm_first=PM_APPROVE, review_provider=None)
    with structlog.testing.capture_logs() as logs:
        events = _run(gw, monkeypatch)
    v = _verdict(events)

    assert v.action == VerdictAction.APPROVE.value
    assert gw.review_calls == [], "no call may reach the wire without a provider"
    errors = [r for r in logs if r["event"] == "room_verdict_review_no_provider"]
    assert len(errors) == 1
    assert errors[0]["kind"] == "veto"
    rec = v.verdict_review
    assert rec is not None and rec.skipped_reason == "no_fallback_provider"
    assert rec.provider is None
    assert rec.decision is None


# ── 7. input guards at the apply boundary (unit-level) ──────────────────────


def _handoff(kind_inputs: dict | None = None):
    """A minimal (ctx, run, gateway) handoff for `_apply_verdict_review`."""
    ctx = _RoomContext(
        ticker="AAPL",
        mandate=_mandate(),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
        user_id=uuid4(),
    )
    from app.schemas.room import RoomRun, RoomStatus

    transcript = []
    if kind_inputs:
        for agent_id, content in kind_inputs.items():
            transcript.append(AgentMessage(
                agent_id=agent_id, role="agent", content=content,
                timestamp=datetime.now(UTC),
            ))
    room_run = RoomRun(
        id=uuid4(), user_id=ctx.user_id, ticker="AAPL",
        triggered_at=datetime.now(UTC), mandate_version=1,
        model_tier="mid", transcript=transcript,
        verdict=None, credit_cost=0, status=RoomStatus.RUNNING,
    )
    return ctx, room_run


@pytest.mark.asyncio
async def test_scripted_dissent_skips_the_veto_with_a_record():
    """A scripted Bear/Conservative turn is canned text; auditing the CIO's
    answer to it is theater — skip loudly, verdict unchanged."""
    ctx, room_run = _handoff()
    ctx.scripted_turns = {AgentId.BEAR_RESEARCHER}
    gw = _ReviewGateway(review_provider="anthropic")

    verdict = Verdict(
        action=VerdictAction.APPROVE, size_pct=3.0, entry=150.0,
        stop=141.0, target=172.0, time_horizon_days=42,
        reason="PM: APPROVE; synthesis defended.",
        kill_criterion="A close below $141.",
    )
    final, override = await _apply_verdict_review(
        verdict=verdict, pm_outage=False, parsed=verdict, live=True,
        run_id=uuid4(), ctx=ctx, profile={}, formatter={}, mandate=ctx.mandate,
        run=room_run, gateway=gw, agent_timeout_s=30.0,
    )
    assert final.action == VerdictAction.APPROVE.value
    assert final.verdict_review.skipped_reason == "scripted_dissent"
    assert override is None
    assert gw.review_calls == []


@pytest.mark.asyncio
async def test_missing_dissent_transcript_skips_the_veto_with_a_record():
    ctx, room_run = _handoff()  # no bear/conservative turns at all
    gw = _ReviewGateway(review_provider="anthropic")
    verdict = Verdict(
        action=VerdictAction.APPROVE, size_pct=3.0, entry=150.0,
        stop=141.0, target=172.0, time_horizon_days=42,
        reason="PM: APPROVE; synthesis defended.",
        kill_criterion="A close below $141.",
    )
    final, _ = await _apply_verdict_review(
        verdict=verdict, pm_outage=False, parsed=verdict, live=True,
        run_id=uuid4(), ctx=ctx, profile={}, formatter={}, mandate=ctx.mandate,
        run=room_run, gateway=gw, agent_timeout_s=30.0,
    )
    assert final.action == VerdictAction.APPROVE.value
    assert final.verdict_review.skipped_reason == "missing_dissent_transcript"
    assert gw.review_calls == []
