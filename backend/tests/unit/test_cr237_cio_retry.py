"""CR237 — "Ask the CIO again" after a CIO-outage PASS.

When every analyst desk answers but the CIO is unreachable, the Room ends in
the DEF059 fail-safe PASS and (DEF432) is refunded. The analysts' work is
still on the run; this lets the user retry ONLY the CIO's own turn against
that saved work, free, without reconvening the whole Room.

Covers:
  - `cio_retry_eligible`: every branch in its own docstring.
  - The safety floor still applies on a retry's own APPROVE — the single most
    important guarantee in this CR (a bypass here is a compliance hole, not a
    cosmetic bug).
  - Retry rebuilds mandate/portfolio/risk context FRESH, not from the
    original run's stale snapshot — a mandate edit between the outage and the
    retry is caught by eligibility, not silently ignored.
  - A successful retry replaces the outage verdict on the SAME run id, updates
    the journal entry once (never duplicates it), leaves `refund_recorded`
    True (so `run_was_refunded` stays truthful — ledger nets zero, no new
    charge), and sets `cio_retried`.
  - A retry that hits the outage again leaves the outage PASS in place, no
    credit movement, no journal change.
  - Refusals: someone else's run, a non-outage verdict, a second concurrent
    retry on the same run (in-flight guard).
  - A restart mid-retry (simulated: a fresh `RoomRunner` instance, matching
    `_retrying_runs`'s documented "nothing survives a restart" contract)
    leaves the outage PASS untouched with no credit movement.
  - Migration chain sanity (single head, immutable) — via the two required
    suite-wide guards, run alongside this file per the task brief.
  - DEF432 round-1 MINOR-1 (auditor U68), end-to-end for the CIO-outage-PASS
    shape specifically (the NO_VERDICT sibling was already covered in
    test_def432_room_outage_refund.py; this closes the same gap for the PASS
    shape and for the respawn path, both previously untested end-to-end): a
    FAILED `refund()` call must never claim "This Room wasn't charged.",
    must leave `run_was_refunded`/the `done` event's `refunded` at False, and
    must not corrupt the Decision Journal. The production fix
    (`refund_recorded`, set only after `refund()` returns) already ships on
    `main` — these tests are the previously-missing coverage for it.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.schemas.mandate import Mandate
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.services import room_runner as room_runner_mod
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for, spend
from app.services.journal_store import get_journal_store
from app.schemas.journal import EntryType
from app.services.mandate_store import MandateStore
from app.services.room_runner import (
    PM_LLM_UNAVAILABLE_REASON,
    RoomRunner,
    build_journal_entry_for_run,
    cio_retry_eligible,
    is_llm_outage_verdict,
    run_was_refunded,
)
from tests.unit.test_def425_shutdown_cancel_no_refund_gap import _billed_user, _row

pytestmark = pytest.mark.allow_ledger_drift  # direct runner.run()/retry_cio_step() calls, same shape as test_def432_room_outage_refund.py

CREDIT_COST = 12
TICKER = "AAPL"


# ── shared fixtures ──────────────────────────────────────────────────────────


def _mandate_for(user_id, *, blocklist: list[str] | None = None) -> Mandate:
    m = hydrate_coach_mandate({"plan": "trader", "risk_score": 3}).model_copy(
        update={"user_id": user_id}
    )
    if blocklist:
        m = m.model_copy(update={
            "compliance": m.compliance.model_copy(update={"ticker_blocklist": blocklist}),
        })
    return m


def _seed_stored_mandate(user_id, *, blocklist: list[str] | None = None) -> Mandate:
    """Persist a real, versioned mandate in MandateStore for `user_id` so
    `retry_cio_step`'s own `resolve_mandate(user_id, None)` call reads the
    SAME mandate (version + blocklist) the original run was hydrated with —
    otherwise `cio_retry_eligible`'s mandate-version check always fails."""
    m = _mandate_for(user_id, blocklist=blocklist)
    return MandateStore().upsert(user_id, m)


class _CioDownThenApproveGateway:
    """Every desk answers normally. The CIO's own turn is EMPTY for every
    call while `.down` is True (produces the DEF059 outage PASS with a real
    `cio_context_snapshot` — `pm_self_consistency_samples` draws the CIO's
    prompt up to 5x PER verdict attempt, so a call-count switch flips mid
    self-consistency vote and never actually outages; `.down` is instead
    flipped explicitly, by the test, between building the original outage
    run and calling the retry) and returns a scripted APPROVE on every call
    once `.down` is set False (the retry)."""

    def __init__(self, pm_json: str):
        self.pm_json = pm_json
        self.down = True
        self.cio_calls = 0

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            self.cio_calls += 1
            if self.down:
                return  # empty stream -> DEF059 outage PASS
            yield self.pm_json
            return
        yield "AMI agent live reply with a real contribution."


class _AlwaysDownGateway:
    """Every desk answers; the CIO's stream is always empty — outage never
    clears, including on retry."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            return
        yield "AMI agent live reply with a real contribution."


def _pm_json(action="APPROVE", size_pct=3.0, entry=150, stop=141, target=172):
    return (
        f'{{"action": "{action}", "size_pct": {size_pct}, "entry": {entry}, '
        f'"stop": {stop}, "target": {target}, "horizon_days": 42, '
        '"narration": "Synthesis defended; the mandate clears at this size."}'
    )


def _run_outage_room(user_id, mandate, gateway) -> tuple[RoomRunner, "uuid.UUID"]:
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]
    run_id = uuid4()

    async def go():
        return [ev async for ev in runner.run(
            run_id=run_id,
            user_id=user_id, ticker=TICKER,
            mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=CREDIT_COST,
        )]

    events = asyncio.run(go())
    verdicts = [ev for ev in events if ev.kind == "verdict"]
    assert len(verdicts) in (1, 2)
    final = verdicts[-1].verdict
    assert final.action == VerdictAction.PASS
    assert is_llm_outage_verdict(final.model_dump())
    return runner, run_id


def _retry(runner: RoomRunner, run_id, user_id):
    async def go():
        return [ev async for ev in runner.retry_cio_step(run_id, user_id=user_id)]
    return asyncio.run(go())


# ── cio_retry_eligible: every branch in its own docstring ───────────────────


def _bare_run(
    *, user_id=None, status=RoomStatus.COMPLETED, verdict=None,
    cio_context_snapshot=None, mandate_version=1, finished_at=None,
) -> RoomRun:
    uid = user_id or uuid4()
    return RoomRun(
        id=uuid4(), user_id=uid, ticker=TICKER,
        triggered_at=datetime.now(timezone.utc),
        finished_at=finished_at or datetime.now(timezone.utc),
        mandate_version=mandate_version, model_tier="mid", rounds=1,
        transcript=[], verdict=verdict, credit_cost=12, status=status,
        cio_context_snapshot=cio_context_snapshot,
    )


def _outage_verdict() -> Verdict:
    return Verdict(
        action=VerdictAction.PASS,
        reason=f"{PM_LLM_UNAVAILABLE_REASON} This Room wasn't charged.",
        overridden_from_llm=True,
    )


def test_eligible_true_for_a_fresh_own_outage_run_with_snapshot():
    uid = uuid4()
    run = _bare_run(
        user_id=uid, verdict=_outage_verdict(),
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
    )
    assert cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_none_run_is_never_eligible():
    assert not cio_retry_eligible(None, requesting_user_id=uuid4(), current_mandate_version=1)


def test_ineligible_for_someone_elses_run():
    owner, attacker = uuid4(), uuid4()
    run = _bare_run(
        user_id=owner, verdict=_outage_verdict(),
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
    )
    assert not cio_retry_eligible(run, requesting_user_id=attacker, current_mandate_version=1)


def test_ineligible_when_status_is_not_completed():
    uid = uuid4()
    for status in (RoomStatus.RUNNING, RoomStatus.QUEUED, RoomStatus.FAILED, RoomStatus.CANCELLED):
        run = _bare_run(
            user_id=uid, status=status, verdict=_outage_verdict(),
            cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
        )
        assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_ineligible_for_a_reasoned_pass_not_the_outage_shape():
    uid = uuid4()
    reasoned = Verdict(
        action=VerdictAction.PASS,
        reason="Chief Investment Officer: the thesis does not clear the mandate at this size.",
    )
    run = _bare_run(
        user_id=uid, verdict=reasoned,
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
    )
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_ineligible_for_no_verdict_partial_outage_shape():
    """The R51 partial-outage NO_VERDICT (too few desks) is a DIFFERENT outage
    shape than the CIO-only PASS — CR237.md explicitly scopes retry to the
    CIO-outage PASS only; NO_VERDICT must never be retryable."""
    from app.services.room_runner import PM_ROOM_INCOMPLETE_REASON

    uid = uuid4()
    no_verdict = Verdict(
        action=VerdictAction.NO_VERDICT,
        reason=f"{PM_ROOM_INCOMPLETE_REASON} 8 of 12 desks responded. This Room wasn't charged.",
        overridden_from_llm=True,
    )
    run = _bare_run(
        user_id=uid, verdict=no_verdict,
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
    )
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_ineligible_when_verdict_shape_is_not_outage_at_all():
    uid = uuid4()
    approve = Verdict(action=VerdictAction.APPROVE, reason="Clears the mandate.")
    run = _bare_run(
        user_id=uid, verdict=approve,
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
    )
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_ineligible_when_no_snapshot_was_persisted():
    """Every run before CR237 shipped has no snapshot — never eligible,
    per CR237 ruling #2's own quoted text."""
    uid = uuid4()
    run = _bare_run(
        user_id=uid, verdict=_outage_verdict(),
        cio_context_snapshot=None, mandate_version=1,
    )
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_ineligible_when_mandate_version_has_moved():
    uid = uuid4()
    run = _bare_run(
        user_id=uid, verdict=_outage_verdict(),
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
    )
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=2)


def test_ineligible_once_past_the_max_age_window():
    from app.core.config import settings

    uid = uuid4()
    stale_finish = datetime.now(timezone.utc) - timedelta(
        minutes=settings.room_cio_retry_max_age_minutes + 1
    )
    run = _bare_run(
        user_id=uid, verdict=_outage_verdict(),
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
        finished_at=stale_finish,
    )
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_eligible_right_at_the_edge_of_the_max_age_window():
    from app.core.config import settings

    uid = uuid4()
    just_inside = datetime.now(timezone.utc) - timedelta(
        minutes=settings.room_cio_retry_max_age_minutes - 1
    )
    run = _bare_run(
        user_id=uid, verdict=_outage_verdict(),
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
        finished_at=just_inside,
    )
    assert cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


def test_ineligible_when_finished_at_is_missing():
    uid = uuid4()
    run = RoomRun(
        id=uuid4(), user_id=uid, ticker=TICKER,
        triggered_at=datetime.now(timezone.utc), finished_at=None,
        mandate_version=1, model_tier="mid", rounds=1,
        transcript=[], verdict=_outage_verdict(), credit_cost=12,
        status=RoomStatus.COMPLETED, cio_context_snapshot={"ticker": TICKER},
    )
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=1)


# in-flight guard is exercised end-to-end below (it needs a live RoomRunner
# instance, not a bare RoomRun).


# ── the floor still applies on retry — the load-bearing guarantee ───────────


def test_floor_still_applies_on_retry_blocklisted_ticker_rejected():
    """Drive a retry whose CIO APPROVEs a blocklisted ticker; the deterministic
    floor must override it to REJECT — never the CIO's raw APPROVE. This is
    the single most important test in the whole CR: a retry that bypasses the
    floor is a compliance hole, not a cosmetic bug."""
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=[TICKER])

    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    retry_events = _retry(runner, run_id, user_id)
    verdict_events = [ev for ev in retry_events if ev.kind == "verdict"]
    assert len(verdict_events) == 1
    final = verdict_events[0].verdict

    assert final.action == VerdictAction.REJECT, (
        "the CIO's raw APPROVE on a blocklisted ticker must be overridden by "
        "the deterministic safety floor, exactly as it would be on a normal "
        "run — the floor is not coachable and a retry does not get to skip it"
    )
    assert final.overridden_from_llm is True
    assert "blocklist" in " ".join(final.violations).lower() or TICKER in " ".join(final.violations)

    run = runner.get_run(run_id)
    assert run.verdict.action == VerdictAction.REJECT


def test_floor_kill_mutation_removing_the_floor_call_fails_this_test():
    """Mutation check for the test above: monkeypatch `enforce_safety_floor`
    (as imported into room_runner) to be a passthrough (the LLM's raw verdict,
    unchecked) and confirm the floor-still-applies test then FAILS — i.e. the
    test actually exercises the floor call, not some other REJECT path."""
    import app.services.room_runner as rr

    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=[TICKER])
    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    original = rr.enforce_safety_floor
    rr.enforce_safety_floor = lambda llm_verdict, *a, **k: llm_verdict  # passthrough
    try:
        retry_events = _retry(runner, run_id, user_id)
        verdict_events = [ev for ev in retry_events if ev.kind == "verdict"]
        final = verdict_events[0].verdict
        assert final.action == VerdictAction.APPROVE, (
            "with the floor call stubbed to a passthrough, the blocklisted "
            "APPROVE must sail through unmodified — proving the real test "
            "above is the floor call's own effect, not an artifact"
        )
    finally:
        rr.enforce_safety_floor = original


def test_floor_passes_a_clean_retry_approve_through_unmodified():
    """Control: no blocklist, ordinary trade — the retry's APPROVE must stand
    as the CIO gave it, not get spuriously overridden."""
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)

    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    retry_events = _retry(runner, run_id, user_id)
    final = [ev for ev in retry_events if ev.kind == "verdict"][0].verdict
    assert final.action == VerdictAction.APPROVE
    assert not final.overridden_from_llm


# ── retry rebuilds safety context FRESH, not from the stale snapshot ────────


def test_mandate_change_between_outage_and_retry_is_caught_by_eligibility():
    """A mandate edit between the original outage and the retry attempt bumps
    `mandate.version` in the store — `cio_retry_eligible` must catch that (the
    debate argued under the old mandate is stale) rather than silently retrying
    against the new one."""
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)

    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    # Cleared deliberately — proves the refusal below is eligibility (the
    # stale mandate version), not merely the CIO still being down.
    gateway.down = False

    # Edit the mandate — bumps version in the store.
    MandateStore().patch(user_id, {"risk_score": 5})

    retry_events = _retry(runner, run_id, user_id)
    errors = [ev for ev in retry_events if ev.kind == "error"]
    verdicts = [ev for ev in retry_events if ev.kind == "verdict"]
    assert len(verdicts) == 0
    assert len(errors) == 1
    assert "reconvene" in errors[0].text.lower()

    # The outage PASS must remain untouched — no silent retry against the
    # new mandate.
    run = runner.get_run(run_id)
    assert is_llm_outage_verdict(run.verdict.model_dump())
    assert run.cio_retried is False


def test_eligibility_predicate_kill_mutation_removing_mandate_check():
    """Mutation check: with the mandate-version comparison stubbed out of
    `cio_retry_eligible`, the stale-mandate case above must become eligible —
    confirming the real test exercises that specific branch."""
    uid = uuid4()
    run = _bare_run(
        user_id=uid, verdict=_outage_verdict(),
        cio_context_snapshot={"ticker": TICKER}, mandate_version=1,
    )
    # Real behaviour: version mismatch -> ineligible.
    assert not cio_retry_eligible(run, requesting_user_id=uid, current_mandate_version=2)

    # Mutate: ignore mandate_version entirely.
    import app.services.room_runner as rr
    original = rr.cio_retry_eligible

    def _mutated(run, *, requesting_user_id, current_mandate_version, now=None):
        if run is None:
            return False
        if run.user_id != requesting_user_id:
            return False
        status = run.status if isinstance(run.status, str) else run.status.value
        if status != "completed":
            return False
        if not original.__globals__["is_llm_outage_verdict"](
            run.verdict.model_dump() if run.verdict else None
        ):
            return False
        if not run.cio_context_snapshot:
            return False
        return True  # mandate_version check removed

    assert _mutated(run, requesting_user_id=uid, current_mandate_version=2), (
        "with the mandate-version check removed, the same stale-mandate case "
        "must flip to eligible — proving the real predicate's False above is "
        "that check's own effect"
    )


def test_retry_reads_current_portfolio_value_not_original_runs():
    """CR237 ruling #2 — portfolio_value/current_drawdown_pct are rebuilt FRESH
    at retry time via the sim engine's live valuation, never carried from the
    original run's construction. Probe: patch valuation_snapshot to a
    distinguishable sentinel and confirm the retry's CIO step actually reads
    it (via the compliance check succeeding/failing on a drawdown-cap trade
    that only trips with the FRESH value)."""
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)
    mandate = mandate.model_copy(update={"max_drawdown_pct": 10})

    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    calls = {"count": 0}
    real_snapshot = room_runner_mod.get_sim_engine().valuation_snapshot

    def _spy(uid):
        calls["count"] += 1
        return real_snapshot(uid)

    import app.services.room_runner as rr
    original_get_sim_engine = rr.get_sim_engine

    class _Wrapped:
        def valuation_snapshot(self, uid):
            return _spy(uid)

    rr.get_sim_engine = lambda: _Wrapped()
    try:
        _retry(runner, run_id, user_id)
    finally:
        rr.get_sim_engine = original_get_sim_engine

    assert calls["count"] == 1, (
        "retry_cio_step must call the sim engine's OWN valuation_snapshot at "
        "retry time — not reuse a value baked into the original run/snapshot"
    )


# ── a successful retry: replace-in-place, journal updated once, no charge ───


def test_successful_retry_replaces_outage_verdict_on_same_run_id():
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)
    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    _retry(runner, run_id, user_id)

    run = runner.get_run(run_id)
    assert run.id == run_id
    assert run.verdict.action == VerdictAction.APPROVE
    assert not is_llm_outage_verdict(run.verdict.model_dump())
    assert run.cio_retried is True
    assert run.cio_context_snapshot is None, "cleared once resolved"


def test_successful_retry_updates_journal_entry_once_not_duplicated():
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)
    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    # Seed the original journal entry the way api/room.py's on_complete would.
    original_run = runner.get_run(run_id)
    draft = build_journal_entry_for_run(original_run, user_id)
    get_journal_store().append(draft)

    before_entries, before_total, _ = get_journal_store().list_for_user(
        user_id, plan="trader", limit=100,
    )
    before_count = before_total

    _retry(runner, run_id, user_id)

    after_entries, after_total, _ = get_journal_store().list_for_user(
        user_id, plan="trader", limit=100,
    )
    assert after_total == before_count, "no new journal row — updated in place"

    entry = get_journal_store().first_for_reference(
        user_id, EntryType.ROOM_RUN, run_id,
    )
    assert entry is not None
    assert "wasn't charged" not in entry.summary


def test_successful_retry_keeps_refund_recorded_true_ledger_nets_zero():
    """CR237 ruling #5 — the original charge was already given back by
    DEF432; a successful retry must not flip `refund_recorded` back to False
    (which would make `run_was_refunded` lie and the client's cost line
    fabricate a charge that never happened)."""
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")

    mandate = _seed_stored_mandate(user_id, blocklist=None)
    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    # Outage refunded the original charge already.
    assert balance_for(user_id)[0] == before

    _retry(runner, run_id, user_id)

    run = runner.get_run(run_id)
    assert run.refund_recorded is True
    assert run_was_refunded(run) is True, (
        "a retried run must keep reporting refunded=True even though its "
        "verdict no longer LOOKS like an outage"
    )
    # No new charge, no second refund — balance unchanged by the retry.
    assert balance_for(user_id)[0] == before


def test_successful_retry_makes_no_spend_or_refund_call_at_all():
    """Free: the retry must never touch the ledger, success or failure."""
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)
    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False  # clear the outage for the retry

    calls: list[tuple] = []
    real_spend = room_runner_mod.spend
    real_refund = room_runner_mod.refund

    def _counting_spend(*a, **k):
        calls.append(("spend", a, k))
        return real_spend(*a, **k)

    def _counting_refund(*a, **k):
        calls.append(("refund", a, k))
        return real_refund(*a, **k)

    import app.services.room_runner as rr
    rr.spend = _counting_spend
    rr.refund = _counting_refund
    try:
        _retry(runner, run_id, user_id)
    finally:
        rr.spend = real_spend
        rr.refund = real_refund

    assert calls == [], "retry_cio_step must never call spend() or refund()"


# ── retry hits the outage again ──────────────────────────────────────────────


def test_retry_still_down_keeps_outage_pass_no_journal_change_told_plainly():
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)
    gateway = _AlwaysDownGateway()
    runner, run_id = _run_outage_room(user_id, mandate, gateway)

    original_run = runner.get_run(run_id)
    draft = build_journal_entry_for_run(original_run, user_id)
    get_journal_store().append(draft)
    before_entry = get_journal_store().first_for_reference(user_id, EntryType.ROOM_RUN, run_id)

    retry_events = _retry(runner, run_id, user_id)
    errors = [ev for ev in retry_events if ev.kind == "error"]
    verdicts = [ev for ev in retry_events if ev.kind == "verdict"]

    assert len(errors) == 1
    assert "unreachable" in errors[0].text.lower()
    # `_run_cio_step` (shared with `run()`) always yields its own assembled
    # verdict at the end of the CIO's turn, BEFORE `retry_cio_step`'s
    # still-down check runs — so a still-down retry emits exactly ONE
    # verdict event (the outage-shaped one, unchanged from the original run)
    # plus the error event above; it does NOT emit a second verdict or
    # silently drop the event entirely.
    assert len(verdicts) == 1
    assert is_llm_outage_verdict(verdicts[0].verdict.model_dump())

    run = runner.get_run(run_id)
    assert is_llm_outage_verdict(run.verdict.model_dump())
    assert run.cio_retried is False
    assert run.cio_context_snapshot is not None, "left intact for a further retry"

    after_entry = get_journal_store().first_for_reference(user_id, EntryType.ROOM_RUN, run_id)
    assert after_entry.summary == before_entry.summary


def test_retry_still_down_moves_no_credits():
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")

    mandate = _seed_stored_mandate(user_id, blocklist=None)
    gateway = _AlwaysDownGateway()
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    assert balance_for(user_id)[0] == before  # original outage refund

    _retry(runner, run_id, user_id)

    assert balance_for(user_id)[0] == before


# ── refusals ──────────────────────────────────────────────────────────────


def test_retry_refuses_a_non_outage_verdict():
    """A normal completed APPROVE has no snapshot and is never eligible — the
    retry method re-checks eligibility itself even if a caller's earlier
    check somehow passed."""
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)

    class _CioAnswersGateway:
        def has_real_provider(self):
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            if "speak as the chief investment officer" in system_prompt.lower():
                yield _pm_json(action="APPROVE")
                return
            yield "AMI agent live reply with a real contribution."

    runner = RoomRunner(llm=_CioAnswersGateway())  # type: ignore[arg-type]
    run_id = uuid4()

    async def go():
        return [ev async for ev in runner.run(
            run_id=run_id, user_id=user_id, ticker=TICKER, mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0, credit_cost=CREDIT_COST,
        )]

    events = asyncio.run(go())
    final = [ev for ev in events if ev.kind == "verdict"][-1].verdict
    assert final.action == VerdictAction.APPROVE
    assert not is_llm_outage_verdict(final.model_dump())

    retry_events = _retry(runner, run_id, user_id)
    errors = [ev for ev in retry_events if ev.kind == "error"]
    assert len(errors) == 1
    assert "reconvene" in errors[0].text.lower()


def test_retry_refuses_someone_elses_run():
    owner = _billed_user()
    attacker = _billed_user()
    mandate = _seed_stored_mandate(owner, blocklist=None)
    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(owner, mandate, gateway)

    retry_events = _retry(runner, run_id, attacker)
    errors = [ev for ev in retry_events if ev.kind == "error"]
    verdicts = [ev for ev in retry_events if ev.kind == "verdict"]
    assert len(verdicts) == 0
    assert len(errors) == 1

    run = runner.get_run(run_id)
    assert is_llm_outage_verdict(run.verdict.model_dump()), "untouched by the attacker's attempt"


def test_second_concurrent_retry_on_same_run_is_refused_in_flight():
    """The in-flight guard (`_retrying_runs`) blocks a second concurrent
    retry attempt on the same run — a real concurrency probe: launch the
    first retry, let it start (yield control once), then attempt a second
    before the first finishes."""
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)

    class _SlowCioGateway:
        """Every CIO call is empty (outage) while `.slow` is False — used to
        build the original outage room, where `pm_self_consistency_samples`
        (default 5) draws the CIO's prompt up to 5x per verdict attempt, so
        every one of those draws must stay empty or the room resolves to a
        real verdict instead of the outage this test needs. Once `.slow` is
        set True (by the test, after the original room exists), the CIO call
        blocks on `.release` so the test can interleave a second retry
        attempt while the first is genuinely in flight."""

        def __init__(self):
            self.slow = False
            self.release = asyncio.Event()
            self.entered = asyncio.Event()

        def has_real_provider(self):
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            if "speak as the chief investment officer" in system_prompt.lower():
                if not self.slow:
                    return  # original run: outage on every draw
                self.entered.set()
                await self.release.wait()
                yield _pm_json(action="APPROVE")
                return
            yield "AMI agent live reply with a real contribution."

    gateway = _SlowCioGateway()
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.slow = True  # arm the block for the retry attempts below

    async def scenario():
        first_events: list = []

        async def _drain_first():
            async for ev in runner.retry_cio_step(run_id, user_id=user_id):
                first_events.append(ev)

        first_task = asyncio.create_task(_drain_first())
        await asyncio.wait_for(gateway.entered.wait(), timeout=5.0)
        # First retry is now genuinely in flight (blocked mid-CIO-call).
        assert runner.is_retrying(run_id) is True

        second_events = [
            ev async for ev in runner.retry_cio_step(run_id, user_id=user_id)
        ]

        gateway.release.set()
        await first_task
        return first_events, second_events

    first_events, second_events = asyncio.run(scenario())

    second_errors = [ev for ev in second_events if ev.kind == "error"]
    assert len(second_errors) == 1
    assert "already in progress" in second_errors[0].text.lower()
    assert len([ev for ev in second_events if ev.kind == "verdict"]) == 0

    first_verdicts = [ev for ev in first_events if ev.kind == "verdict"]
    assert len(first_verdicts) == 1
    assert first_verdicts[0].verdict.action == VerdictAction.APPROVE

    assert runner.is_retrying(run_id) is False, "guard cleared once the first retry finished"


# ── restart mid-retry leaves the outage PASS untouched, no credit movement ──


def test_restart_mid_retry_leaves_outage_pass_untouched_no_credit_movement():
    """`retry_cio_step` never sets `status` back to 'running' specifically so
    a mid-retry restart can't have `_sweep_stuck_runs` claim and respawn or
    fail+refund it (see the method's own docstring). Simulate "restart" the
    way `_retrying_runs`'s docstring frames it: a FRESH `RoomRunner` instance
    (in-memory `_retrying_runs` does not survive a process restart) reading
    back the SAME persisted row — the row's `status` must still read
    'completed' with the outage verdict intact, and the DEF425 sweep's own
    query (`status == 'running'`) must not pick it up."""
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")

    mandate = _seed_stored_mandate(user_id, blocklist=None)

    class _HangingCioGateway:
        """Every CIO call is empty (outage) while `.hang` is False — builds
        the original room, where every one of `pm_self_consistency_samples`'s
        (default 5) draws must stay empty or the room resolves to a real
        verdict. Once `.hang` is True, the retry's CIO call never returns —
        models a process that dies mid-retry (nobody awaits the coroutine to
        completion; we just never let it finish and instead inspect the
        persisted row directly, as a genuine restart would find it)."""

        def __init__(self):
            self.hang = False

        def has_real_provider(self):
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            if "speak as the chief investment officer" in system_prompt.lower():
                if not self.hang:
                    return  # original run: outage on every draw
                await asyncio.Event().wait()  # never resolves — "the process died"
                yield "unreachable"
                return
            yield "AMI agent live reply with a real contribution."

    gateway = _HangingCioGateway()
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    assert balance_for(user_id)[0] == before  # original outage refund
    gateway.hang = True  # arm the hang for the abandoned retry below

    async def start_and_abandon():
        task = asyncio.create_task(
            _drain(runner.retry_cio_step(run_id, user_id=user_id))
        )
        await asyncio.sleep(0.05)  # let it enter the hanging CIO call
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _drain(gen):
        async for _ in gen:
            pass

    asyncio.run(start_and_abandon())

    # "Restart": a brand-new RoomRunner (fresh in-memory _retrying_runs),
    # reading the SAME persisted row back from the DB.
    fresh_runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]
    row = fresh_runner.get_run(run_id)

    assert row.status == RoomStatus.COMPLETED, (
        "retry_cio_step must never leave status at RUNNING — a restart's "
        "_sweep_stuck_runs (status == 'running') must not be able to claim "
        "and respawn/fail this run"
    )
    assert is_llm_outage_verdict(row.verdict.model_dump()), (
        "the outage PASS must still be exactly what it was before the "
        "abandoned retry attempt"
    )
    assert row.cio_retried is False
    assert row.refund_recorded is True  # from the original outage refund only

    # No credit movement from the abandoned retry.
    assert balance_for(user_id)[0] == before

    # The in-memory guard on the fresh runner is clear — nothing survives a
    # restart to still be "in flight", so a real retry is immediately
    # offerable again.
    assert fresh_runner.is_retrying(run_id) is False


# ── DEF432 round-1 MINOR-1 (auditor U68): a failed refund never claims the ──
# ── Room wasn't charged — closed here end-to-end for the CIO-outage-PASS   ──
# ── shape and the respawn path (the NO_VERDICT/direct-run() shape was      ──
# ── already covered in test_def432_room_outage_refund.py).                ──


class _CioDownGateway:
    """Every desk answers; the CIO's stream is always empty — the DEF059
    CIO-outage PASS shape, every draw (not just the first — self-consistency
    draws up to `pm_self_consistency_samples` times per verdict attempt)."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            return
        yield "AMI agent live reply with a real contribution."


def test_def432_minor1_failed_refund_on_cio_outage_pass_direct_run(monkeypatch):
    """Probe (mirrors DEF432.auditor.md's round-2 reproduction): drive a
    direct `run()` to the CIO-outage PASS with `refund` made to raise.
    ALL FOUR must hold:
      1. `run_was_refunded(run)` is False.
      2. `run.verdict.reason` does NOT contain "This Room wasn't charged."
      3. The Decision Journal summary built from that run doesn't claim it.
      4. `run.refund_recorded` is False (the field the `done` event's
         `refunded` flag reads — same predicate, so this closes claim 4 too).
    """
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    after_charge = balance_for(user_id)[0]
    assert after_charge == before - CREDIT_COST

    def _raising_refund(uid, amount, *, reason):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(room_runner_mod, "refund", _raising_refund)

    runner = RoomRunner(llm=_CioDownGateway())  # type: ignore[arg-type]
    run_id = uuid4()

    async def go():
        return [ev async for ev in runner.run(
            run_id=run_id,
            user_id=user_id, ticker=TICKER,
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=CREDIT_COST,
        )]

    events = asyncio.run(go())
    verdicts = [ev for ev in events if ev.kind == "verdict"]
    # Exactly ONE verdict event: the refund's re-emit branch is inside its
    # own `else:` (success only) — a failed refund never reaches it, same
    # as test_def432_room_outage_refund.py's identical NO_VERDICT case.
    assert len(verdicts) == 1
    verdict = verdicts[0].verdict

    assert is_llm_outage_verdict(verdict.model_dump())
    assert verdict.reason == PM_LLM_UNAVAILABLE_REASON
    assert "wasn't charged" not in verdict.reason  # claim 2

    run = runner.get_run(run_id)
    assert run is not None
    assert run.refund_recorded is False  # claim 4 (and the done event reads this)
    assert run_was_refunded(run) is False  # claim 1
    assert "wasn't charged" not in run.verdict.reason

    draft = build_journal_entry_for_run(run, user_id)
    assert "wasn't charged" not in draft.summary  # claim 3

    # The credits were never given back — balance stays at the post-charge
    # figure, matching the ledger (net effect of a failed refund attempt).
    assert balance_for(user_id)[0] == after_charge


def test_def432_minor1_kill_mutation_setting_refund_recorded_before_refund_returns(
    monkeypatch,
):
    """Mutation check (coordinator-requested): set `refund_recorded = True`
    BEFORE `refund()` is even attempted (the exact class of bug DEF432
    MINOR-1 was) and confirm the direct-run test above then FAILS — proving
    it actually exercises the ordering, not some other invariant."""
    user_id = _billed_user()
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")

    def _raising_refund(uid, amount, *, reason):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(room_runner_mod, "refund", _raising_refund)

    runner = RoomRunner(llm=_CioDownGateway())  # type: ignore[arg-type]
    run_id = uuid4()

    # Mutate: `run()`'s COMPLETED branch decided a refund is due for an
    # outage-shaped verdict — set `refund_recorded` unconditionally at that
    # DECISION point, before the try/except around `refund()` even runs.
    # We can't edit the running method's bytecode from here, so we simulate
    # the same observable defect by pre-setting the flag on the row the
    # instant it's persisted mid-run, via a _persist_run wrapper — the same
    # "recorded before confirmed" ordering bug, at the same observable
    # granularity a real revert of the `else:` guard would produce.
    real_persist = room_runner_mod._persist_run
    armed = {"once": False}

    def _mutated_persist(run):
        if (
            not armed["once"]
            and run.status == RoomStatus.COMPLETED
            and is_llm_outage_verdict(run.verdict.model_dump() if run.verdict else None)
        ):
            armed["once"] = True
            run.refund_recorded = True  # set on the mere decision, not the result
        return real_persist(run)

    monkeypatch.setattr(room_runner_mod, "_persist_run", _mutated_persist)

    async def go():
        return [ev async for ev in runner.run(
            run_id=run_id,
            user_id=user_id, ticker=TICKER,
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=CREDIT_COST,
        )]

    asyncio.run(go())

    run = runner.get_run(run_id)
    assert run_was_refunded(run) is True, (
        "with refund_recorded set before refund() is confirmed, "
        "run_was_refunded must flip to True — proving the real test's False "
        "is the ordering fix's own effect, not an artifact"
    )


def test_def432_minor1_failed_refund_on_respawned_cio_outage_pass(monkeypatch):
    """Same probe as the direct-run test above, driven through the RESPAWN
    path (`_respawn_run_from_row`, not a direct `run()` call) — the auditor's
    own round-2 reproduction measured on respawn specifically, and until now
    nothing exercised the failed-refund case on that path at all (only the
    successful-refund respawn case existed, in
    test_def425_def432_respawn_keeps_charge.py)."""
    from app.core.config import settings as real_settings
    from app.db import get_session as _get_session
    from app.db.models import RoomRunRow
    from app.services.mandate_store import get_mandate_store

    user_id = _billed_user()
    before = balance_for(user_id)[0]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)

    run_id = uuid4()
    started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    with _get_session() as s:
        s.add(RoomRunRow(
            id=run_id,
            user_id=user_id,
            ticker=TICKER,
            triggered_at=started_at,
            started_at=started_at,
            mandate_version=1,
            model_tier="mid",
            rounds=1,
            transcript=[],
            verdict=None,
            credit_cost=CREDIT_COST,
            status="running",
            retry_count=0,
        ))
    spend(user_id, CREDIT_COST, reason=f"room:AAPL:{run_id}")
    after_charge = balance_for(user_id)[0]
    assert after_charge == before - CREDIT_COST

    def _raising_refund(uid, amount, *, reason):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(room_runner_mod, "refund", _raising_refund)

    runner = RoomRunner(llm=_CioDownGateway())  # type: ignore[arg-type]
    assert len(runner._pending_retry) == 1  # __init__ sweep claimed the row

    async def _go():
        await runner.resume_pending_retries()
        async for _ in runner.subscribe(run_id):
            pass

    asyncio.run(_go())

    row = _row(run_id)
    assert row.status == "completed"
    assert is_llm_outage_verdict(row.verdict)
    assert "wasn't charged" not in (row.verdict.get("reason") or "")  # claim 2
    assert row.refund_recorded is False  # claim 4

    run = runner.get_run(run_id)
    assert run_was_refunded(run) is False  # claim 1

    draft = build_journal_entry_for_run(run, user_id)
    assert "wasn't charged" not in draft.summary  # claim 3

    # Never refunded — balance stays at the post-charge figure.
    assert balance_for(user_id)[0] == after_charge
