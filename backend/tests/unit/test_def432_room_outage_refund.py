"""DEF432 — a Room with unreachable desks charges full credits for no verdict.

Found by auditor U68 auditing DEF424 (recorded, not scored there): a Room
convened while the LLM is down ends `completed | NO_VERDICT` with the copy
"Too much of your analyst room was unreachable ... reconvene when the desks
are back" and keeps its credits (`room:MSFT 150->142`, no refund). Brief and
1-on-1 already refund an outage turn (DEF424); the Room did not.

Saiful's ruling, 2026-09-25, verbatim: **"Refund it."** — "Same rule as Brief
and 1-on-1: an outage never costs the user. The user sees 'desks unreachable
— not charged'."

Fix: `run()`'s single `COMPLETED` persistence point now refunds the run's
full `credit_cost`, exactly once, when (and only when) the final verdict is
the CR219 R51 outage NO_VERDICT — keyed on `room_verdict_is_incomplete`
(the `PM_ROOM_INCOMPLETE_REASON` sentinel), never on `action == NO_VERDICT`
alone. `_assemble_no_verdict` (CR098 Amendment 2, Market withheld) also
produces NO_VERDICT from a FULL fundamentals case argued by a live roster —
a deliberate professional-discipline refusal, not an outage — and stays
charged. A normal APPROVE/PASS/REJECT verdict is untouched.

The user-visible copy also changes: `PM_ROOM_INCOMPLETE_REASON` now carries
an appended "This Room wasn't charged." sentence at its one construction
site, so both the SSE `reason` the client renders and the Decision Journal
summary (`build_journal_entry_for_run` reads `verdict.reason` verbatim, no
separate credit field) say so with one insertion point to keep in sync.

This refund path is structurally disjoint from DEF425's shutdown/sweep
refund path: DEF425 fires from the `except (asyncio.CancelledError,
GeneratorExit)` branch (row left RUNNING or later claimed by
`_sweep_stuck_runs`) — a run that reaches THIS test's COMPLETED branch never
takes that branch, and vice versa, for a single run_id. No double-refund
risk between the two.

CR236's `done` SSE event (`api/room.py`) reported `refunded` as
`status == "failed"` only, which would have read `false` for this outage's
COMPLETED run — the app would then say "used 8 credits" for a Room that
actually cost nothing. Fixed by introducing `run_was_refunded(run)`
(`room_runner.py`), the ONE predicate both the refund decision here and
`done`'s report now call, so they cannot drift apart. Covered directly below
and in `test_cr236_room_done_credit_cost.py`.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings as real_settings
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.services import room_runner as room_runner_mod
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for, spend
from app.services.room_runner import (
    PM_LLM_UNAVAILABLE_REASON,
    PM_ROOM_INCOMPLETE_REASON,
    RoomRunner,
    build_journal_entry_for_run,
    is_llm_outage_verdict,
    room_verdict_is_incomplete,
    run_was_refunded,
)
from tests.unit.test_def425_shutdown_cancel_no_refund_gap import _billed_user

pytestmark = pytest.mark.allow_ledger_drift

PM_JSON = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
    '"target": 172, "horizon_days": 42, '
    '"narration": "Synthesis defended; the mandate clears at this size."}'
)

CREDIT_COST = 12


class _PartialOutageGateway:
    """Same fixture `test_cr219_r51_partial_outage_honesty.py` uses: answers
    the CIO properly, starves the first `fail_n` other desks by yielding
    nothing (the empty-stream shape that becomes a scripted fallback turn)."""

    def __init__(self, fail_n: int):
        self.fail_n = fail_n
        self.failed = 0

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            yield PM_JSON
            return
        if self.failed < self.fail_n:
            self.failed += 1
            return  # empty stream -> scripted fallback
        yield "AMI agent live reply with a real contribution."


def _run_room(user_id, fail_n, monkeypatch, cap=4, credit_cost=CREDIT_COST):
    monkeypatch.setattr(real_settings, "room_max_scripted_turns", cap)
    monkeypatch.setattr(room_runner_mod.settings, "room_max_scripted_turns", cap)
    gateway = _PartialOutageGateway(fail_n)
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]

    async def go():
        return [ev async for ev in runner.run(
            user_id=user_id, ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=credit_cost,
        )]

    events = asyncio.run(go())
    verdicts = [ev for ev in events if ev.kind == "verdict"]
    # DEF432 MINOR-1 — a run whose refund SUCCEEDS re-emits a second
    # `verdict` event carrying the "wasn't charged" text (see `run()`'s
    # COMPLETED branch): the first event streams from inside the phase loop,
    # necessarily before completion/refund can happen at all. A run whose
    # verdict never needed a refund (or whose refund failed) still emits
    # exactly one. Callers that want the FINAL, accurate verdict — what a
    # client ends up displaying and what gets persisted — read the last one.
    assert len(verdicts) in (1, 2)
    return verdicts[-1].verdict


# ── the outage NO_VERDICT is refunded ────────────────────────────────────────


def test_llm_down_room_no_verdict_is_refunded_net_zero(monkeypatch):
    """`_run_room` drives `RoomRunner.run()` directly, which — per DEF425's
    own note — never spends on its own; only `start_run()` does. So the test
    stands in for `start_run`'s charge with an explicit `spend()` BEFORE
    calling `run()`, and the pre-charge balance (captured before that spend)
    is the number the refund inside `run()` must land back on."""
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    assert balance_for(user_id)[0] == before - CREDIT_COST

    verdict = _run_room(user_id, fail_n=4, monkeypatch=monkeypatch, cap=4)

    assert verdict.action == VerdictAction.NO_VERDICT
    assert room_verdict_is_incomplete(verdict.model_dump())
    assert balance_for(user_id)[0] == before, (
        "an outage NO_VERDICT must net the user back to their pre-charge "
        "balance — DEF432's whole point"
    )


def test_the_user_is_told_the_room_was_not_charged(monkeypatch):
    user_id = _billed_user()
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")

    verdict = _run_room(user_id, fail_n=4, monkeypatch=monkeypatch, cap=4)

    assert verdict.reason.startswith(PM_ROOM_INCOMPLETE_REASON)
    assert "wasn't charged" in verdict.reason
    assert "AMI" in verdict.reason
    for banned in ("the LLM", "the AI", "the model", "LLM"):
        assert banned not in verdict.reason


def test_refund_fires_exactly_once_even_if_swept_or_retried_later(monkeypatch):
    """DEF425's shutdown/sweep refund and DEF432's outage refund must never
    both fire for the same run: this run reaches RoomStatus.COMPLETED via the
    normal path (never CancelledError/GeneratorExit), so the sweep never sees
    it — a completed row is never selected by `_sweep_stuck_runs`'s own
    `status == "running"` query. One credit_service.refund call, one ledger
    delta."""
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")

    calls: list[tuple] = []
    real_refund = room_runner_mod.refund

    def _counting_refund(uid, amount, *, reason):
        calls.append((uid, amount, reason))
        return real_refund(uid, amount, reason=reason)

    monkeypatch.setattr(room_runner_mod, "refund", _counting_refund)

    verdict = _run_room(user_id, fail_n=4, monkeypatch=monkeypatch, cap=4)

    assert room_verdict_is_incomplete(verdict.model_dump())
    assert len(calls) == 1
    assert calls[0][0] == user_id
    assert calls[0][1] == CREDIT_COST


def test_a_failed_refund_never_claims_the_room_was_not_charged(monkeypatch):
    """DEF432 MINOR-1 (auditor U68, round 1) — the exact bug: `refund()` is
    best-effort (a failure must not turn a delivered verdict into a hard
    error), but the OLD code baked "This Room wasn't charged." into the
    verdict's reason at CONSTRUCTION time, unconditionally — before whether
    a refund would even be attempted (let alone succeed) was known. A
    `refund()` failure therefore left a run that was still fully charged
    telling the user, in the verdict text AND the Decision Journal summary
    (which reads `verdict.reason` verbatim) AND the `done` SSE event's
    `refunded` field, that it was free.

    Probe: `refund` raises for this run's user_id. Assert, ALL of:
      - the user's balance nets to the POST-CHARGE figure (not refunded);
      - the verdict's `reason` does NOT contain "wasn't charged";
      - the Decision Journal summary built from that run (verbatim from
        `verdict.reason`) does not contain it either;
      - `run_was_refunded(run)` reads False for the persisted row;
      - `run.refund_recorded` is False.
    """
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    after_charge = balance_for(user_id)[0]
    assert after_charge == before - CREDIT_COST

    def _raising_refund(uid, amount, *, reason):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(room_runner_mod, "refund", _raising_refund)
    monkeypatch.setattr(real_settings, "room_max_scripted_turns", 4)
    monkeypatch.setattr(room_runner_mod.settings, "room_max_scripted_turns", 4)

    gateway = _PartialOutageGateway(fail_n=4)
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]
    run_id = uuid4()

    async def go():
        return [ev async for ev in runner.run(
            run_id=run_id,
            user_id=user_id, ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=CREDIT_COST,
        )]

    events = asyncio.run(go())
    verdicts = [ev for ev in events if ev.kind == "verdict"]
    # Exactly ONE verdict event: the refund failed, so `run()` never reaches
    # the re-emit branch (that branch is inside the refund's own `else:`,
    # reached only on success).
    assert len(verdicts) == 1
    verdict = verdicts[0].verdict

    assert room_verdict_is_incomplete(verdict.model_dump())
    assert "wasn't charged" not in verdict.reason

    run = runner.get_run(run_id)
    assert run is not None
    assert run.refund_recorded is False
    assert run_was_refunded(run) is False
    assert "wasn't charged" not in run.verdict.reason

    draft = build_journal_entry_for_run(run, user_id)
    assert "wasn't charged" not in draft.summary

    # The credits were never given back — balance stays at the post-charge
    # figure, not the pre-charge one.
    assert balance_for(user_id)[0] == after_charge


# ── the refund is scoped to the outage cause, never a normal verdict ────────


def test_a_normal_completed_room_is_charged_no_refund(monkeypatch):
    """Control: 0 scripted turns -> a real APPROVE. Must stay charged."""
    user_id = _billed_user()
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    after_charge = balance_for(user_id)[0]

    verdict = _run_room(user_id, fail_n=0, monkeypatch=monkeypatch, cap=4)

    assert verdict.action == VerdictAction.APPROVE
    assert not room_verdict_is_incomplete(verdict.model_dump())
    assert balance_for(user_id)[0] == after_charge, (
        "a normal verdict must not be refunded by this fix"
    )


def test_a_partial_outage_that_still_reaches_a_verdict_is_charged(monkeypatch):
    """Below the scripted-turns cap the call still stands (disclosed, not
    discarded) — this is not an outage abstain and must stay charged."""
    user_id = _billed_user()
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    after_charge = balance_for(user_id)[0]

    verdict = _run_room(user_id, fail_n=2, monkeypatch=monkeypatch, cap=4)

    assert verdict.action == VerdictAction.APPROVE
    assert not room_verdict_is_incomplete(verdict.model_dump())
    assert "wasn't charged" not in verdict.reason
    assert balance_for(user_id)[0] == after_charge


def test_cr098_market_withheld_no_verdict_is_not_refunded(monkeypatch):
    """The OTHER NO_VERDICT cause: `_assemble_no_verdict` (CR098 Amendment 2)
    fires when Market is withheld — a deliberate professional-discipline
    refusal argued from a full fundamentals case, not a provider outage. Must
    stay charged and must not carry the outage "not charged" sentence."""
    from app.services.entitlements import AnalystRoster
    from app.services.room_runner import AgentId

    user_id = _billed_user()
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    after_charge = balance_for(user_id)[0]

    gateway = _PartialOutageGateway(fail_n=0)
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]
    roster = AnalystRoster(
        present=(
            AgentId.FUNDAMENTALS_ANALYST, AgentId.NEWS_ANALYST,
            AgentId.SOCIAL_MEDIA_ANALYST,
        ),
        withheld=(AgentId.MARKET_ANALYST,),
        next_step=None,
    )

    async def go():
        return [ev async for ev in runner.run(
            user_id=user_id, ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=CREDIT_COST, roster=roster,
        )]

    events = asyncio.run(go())
    verdict = [ev for ev in events if ev.kind == "verdict"][0].verdict

    assert verdict.action == VerdictAction.NO_VERDICT
    assert not room_verdict_is_incomplete(verdict.model_dump()), (
        "CR098's withheld-analyst NO_VERDICT must stay distinguishable from "
        "DEF432's outage NO_VERDICT"
    )
    assert "wasn't charged" not in (verdict.reason or "")
    assert balance_for(user_id)[0] == after_charge, (
        "a deliberate professional-discipline refusal is not an outage and "
        "must not be refunded"
    )


def test_a_zero_threshold_room_is_never_refunded_even_with_all_scripted(monkeypatch):
    """cap=0 disables the degrade-to-NO_VERDICT path entirely (pre-existing
    CR219 R51 behaviour) — so there is no outage NO_VERDICT to refund even
    when every non-CIO desk was scripted."""
    user_id = _billed_user()
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    after_charge = balance_for(user_id)[0]

    verdict = _run_room(user_id, fail_n=4, monkeypatch=monkeypatch, cap=0)

    assert verdict.action == VerdictAction.APPROVE
    assert not room_verdict_is_incomplete(verdict.model_dump())
    assert balance_for(user_id)[0] == after_charge


# ── run_was_refunded: the ONE predicate the refund decision and CR236's
#    `done` event both call, so they cannot report a different answer than
#    the one that was actually decided ────────────────────────────────────


def _bare_run(
    *, status: RoomStatus, verdict: Verdict | None, refund_recorded: bool = False,
) -> RoomRun:
    from datetime import datetime, timezone

    return RoomRun(
        id=uuid4(), user_id=uuid4(), ticker="AAPL",
        triggered_at=datetime.now(timezone.utc),
        mandate_version=1, model_tier="mid", rounds=1,
        transcript=[], verdict=verdict, credit_cost=12, status=status,
        refund_recorded=refund_recorded,
    )


def test_run_was_refunded_true_for_failed_status_regardless_of_verdict():
    assert run_was_refunded(_bare_run(status=RoomStatus.FAILED, verdict=None))


def test_run_was_refunded_true_for_completed_outage_no_verdict():
    # DEF432 MINOR-1 — `run_was_refunded` no longer infers "refunded" from
    # verdict SHAPE alone for a `completed` run; it reads the ground-truth
    # `refund_recorded` flag, set only once `refund()` has actually
    # succeeded (see `run()`'s COMPLETED branch and `run_was_refunded`'s own
    # docstring). This test asserts the "genuinely refunded" case.
    outage = Verdict(
        action=VerdictAction.NO_VERDICT,
        reason=f"{PM_ROOM_INCOMPLETE_REASON} 8 of 12 desks responded. "
               "This Room wasn't charged.",
        overridden_from_llm=True,
    )
    assert run_was_refunded(
        _bare_run(status=RoomStatus.COMPLETED, verdict=outage, refund_recorded=True)
    )


def test_run_was_refunded_false_for_completed_outage_shaped_verdict_when_refund_failed():
    """DEF432 MINOR-1 — the whole point of the fix: an outage-SHAPED verdict
    whose `refund()` call actually failed must report `refunded: False`, not
    `True` inferred from the verdict's shape. `refund_recorded` defaults to
    False (the real column default) when the caller never sets it."""
    outage = Verdict(
        action=VerdictAction.NO_VERDICT,
        reason=f"{PM_ROOM_INCOMPLETE_REASON} 8 of 12 desks responded.",
        overridden_from_llm=True,
    )
    assert not run_was_refunded(
        _bare_run(status=RoomStatus.COMPLETED, verdict=outage)
    )


def test_run_was_refunded_false_for_completed_normal_approve():
    approve = Verdict(action=VerdictAction.APPROVE, reason="Clears the mandate.")
    assert not run_was_refunded(_bare_run(status=RoomStatus.COMPLETED, verdict=approve))


def test_run_was_refunded_false_for_completed_cr098_withheld_no_verdict():
    withheld = Verdict(
        action=VerdictAction.NO_VERDICT,
        reason="Market analyst withheld this run; no position without a "
               "market read.",
    )
    assert not run_was_refunded(_bare_run(status=RoomStatus.COMPLETED, verdict=withheld))


def test_run_was_refunded_false_for_cancelled_and_running_and_queued():
    for status in (RoomStatus.CANCELLED, RoomStatus.RUNNING, RoomStatus.QUEUED):
        assert not run_was_refunded(_bare_run(status=status, verdict=None))


def test_run_was_refunded_false_for_none_row():
    assert not run_was_refunded(None)


# ── the CIO-only outage PASS is refunded too ────────────────────────────────
# Saiful, 2026-09-25, asked whether a Room whose desks all answered but whose
# CIO was unreachable (the DEF059 fail-safe PASS) should be refunded:
# "Refund it". Same outage rule; the user never got the CIO's ruling.


class _CioDownGateway:
    """Every desk answers; the CIO's stream is empty (the DEF059 shape)."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            return
        yield "AMI agent live reply with a real contribution."


def _run_room_cio_down(user_id):
    runner = RoomRunner(llm=_CioDownGateway())  # type: ignore[arg-type]

    async def go():
        return [ev async for ev in runner.run(
            user_id=user_id, ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=CREDIT_COST,
        )]

    events = asyncio.run(go())
    verdicts = [ev for ev in events if ev.kind == "verdict"]
    # DEF432 MINOR-1 — see `_run_room`'s identical comment above.
    assert len(verdicts) in (1, 2)
    return verdicts[-1].verdict


def test_cio_outage_pass_is_refunded_and_says_so():
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")

    verdict = _run_room_cio_down(user_id)

    assert verdict.action == VerdictAction.PASS
    assert verdict.reason.startswith(PM_LLM_UNAVAILABLE_REASON)
    assert "wasn't charged" in verdict.reason
    assert is_llm_outage_verdict(verdict.model_dump()), (
        "the appended sentence must not stop the outage PASS being "
        "recognised as an outage (batch analysis excludes it by this check)"
    )
    assert balance_for(user_id)[0] == before


def test_run_was_refunded_true_for_completed_cio_outage_pass():
    # DEF432 MINOR-1 — see the sibling NO_VERDICT test's comment above.
    outage = Verdict(
        action=VerdictAction.PASS,
        reason=f"{PM_LLM_UNAVAILABLE_REASON} This Room wasn't charged.",
        overridden_from_llm=True,
    )
    assert run_was_refunded(
        _bare_run(status=RoomStatus.COMPLETED, verdict=outage, refund_recorded=True)
    )


def test_run_was_refunded_false_for_completed_cio_outage_pass_when_refund_failed():
    """DEF432 MINOR-1 — the DEF059 CIO-outage PASS shape, same failed-refund
    case the NO_VERDICT sibling test covers above."""
    outage = Verdict(
        action=VerdictAction.PASS,
        reason=PM_LLM_UNAVAILABLE_REASON,
        overridden_from_llm=True,
    )
    assert not run_was_refunded(
        _bare_run(status=RoomStatus.COMPLETED, verdict=outage)
    )


def test_run_was_refunded_false_for_a_reasoned_pass():
    reasoned = Verdict(
        action=VerdictAction.PASS,
        reason="Chief Investment Officer: the thesis does not clear the "
               "mandate at this size.",
    )
    assert not run_was_refunded(_bare_run(status=RoomStatus.COMPLETED, verdict=reasoned))


def test_outage_text_without_the_override_flag_is_not_refunded():
    """The check is the sentinel AND `overridden_from_llm`, so a CIO reply
    that happened to quote the outage wording is still charged."""
    quoted = Verdict(
        action=VerdictAction.PASS,
        reason=f"{PM_LLM_UNAVAILABLE_REASON} (quoted)",
        overridden_from_llm=False,
    )
    assert not run_was_refunded(_bare_run(status=RoomStatus.COMPLETED, verdict=quoted))
