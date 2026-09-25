"""DEF425 (E5-D3) — a `docker restart` of `ami_api_alpha` mid-Room-run charges
the full Room price with no verdict and no refund.

Drill 3 (`docs/forward_planning/CR004_release_readiness/
build_verification_execution.md` §A3): a live `docker restart ami_api_alpha`
mid-convene left the row `status=cancelled`, `verdict=null`,
`error_message="client disconnected mid-run"`, 12 credits charged, no refund.

Root cause: `start_run()`'s own docstring is explicit that "the run executes
in a background asyncio.Task independent of the SSE connection — a client
disconnect does not cancel the run", and nothing in this codebase ever calls
`.cancel()` on that task. So the ONLY realistic source of the
`asyncio.CancelledError`/`GeneratorExit` `run()`'s
`except (asyncio.CancelledError, GeneratorExit)` handler ever sees is the
server's own shutdown cascading cancellation into every outstanding task —
never a "client disconnected" in the sense the handler's old comment claimed.
That handler unconditionally marked the row CANCELLED with no refund, so the
row was never left RUNNING for `_sweep_stuck_runs` to claim on the next boot
— neither of the two designed safety nets (retry, or fail-with-refund) ever
fired.

Fix: `RoomRunner.mark_shutting_down()`, called from `main.py`'s lifespan
SHUTDOWN phase before it cancels its own tracked tasks (which is what
cascades into the Room's background `_pump` task), flips
`self._shutting_down`. `run()`'s cancellation handler reads it: shutdown ⇒
leave the row RUNNING (no status flip, no error_message, no refund here —
`_sweep_stuck_runs` claims it next boot, exactly as that method's own
docstring already promised); anything else ⇒ today's CANCELLED/no-refund
behaviour, kept as a defensive fallback since no live path reaches it.

Client-disconnect decision (documented, per this CR's own instruction to
read CR039 + decide): CR039's `start_run()` explicitly decouples the SSE
connection from the run — a client disconnect never reaches `run()`'s
cancellation handler at all (the docstring: "independent of the SSE
connection"). So there is no live "genuine client disconnect" case left to
decide a refund policy for; the non-shutdown branch of the handler is inert
today and kept only so the `except` clause still means something if a
future caller ever DOES cancel this task directly.

Second gap closed in the same pass: `_sweep_stuck_runs`'s own
retry-exhausted branch (`retry_count >= MAX_AUTO_RETRIES`) marked the row
`failed` with no refund either — the same user-facing wrong, one hop later,
for a run that dies twice. Now refunded, mirroring
`_respawn_run_from_row`'s abandoned-snapshot refund.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import RoomRunRow, SubscriptionEventRow, User
from app.schemas.room import RoomStatus
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for
from app.services.room_runner import MAX_AUTO_RETRIES, RoomRunner

pytestmark = pytest.mark.allow_ledger_drift


def _billed_user(plan: str = "trader") -> "UUID":
    auth = AuthService()
    u, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, u.id).plan = plan
    return u.id


def _row(run_id) -> RoomRunRow:
    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one_or_none()
        assert row is not None
        s.expunge(row)
        return row


async def _run_until_two_agents_then_gen_exit(runner: RoomRunner, **run_kwargs) -> "UUID":
    """Drive `runner.run(...)` to a deterministic mid-flight point (two
    agents spoken), then tear the generator down via `gen.aclose()` — the
    same mechanism `test_room_cancelled_mid_run_persists_partial_transcript`
    (the pre-existing DEF-adjacent regression test for this exact except
    clause) already uses, and the same mechanism a REAL cancellation
    delivers: `aclose()` throws `GeneratorExit` into the generator at
    whatever `await` it is currently suspended on — indistinguishable, from
    inside `run()`'s own `except` clause, from asyncio's shutdown cascade
    throwing `CancelledError` into the same suspension point. Deterministic
    (breaks on an event count, not a wall-clock sleep window) — a
    `create_task` + `task.cancel()` + fixed-sleep version of this raced on
    which `await` point the cancellation landed on and was observed flaky
    across repeated runs.
    """
    gen = runner.run(char_delay_min=0.0, char_delay_max=0.0, **run_kwargs)
    run_id: "UUID | None" = None
    agents_done = 0
    try:
        async for ev in gen:
            if ev.run_id is not None:
                run_id = ev.run_id
            if ev.kind == "agent_done":
                agents_done += 1
                if agents_done >= 2:
                    break
    finally:
        await gen.aclose()
    assert agents_done == 2  # sanity: consumed past two agents before closing
    assert run_id is not None
    return run_id


# ── the shutdown-cancel path leaves the row RUNNING, untouched ───────────


def test_shutdown_cancel_leaves_row_running_not_cancelled():
    from app.services.credit_service import spend

    runner = RoomRunner()
    runner.mark_shutting_down()
    mandate = hydrate_coach_mandate({"plan": "trader"})
    user_id = _billed_user()
    # `run()` called directly (not through `start_run()`) never spends — only
    # `start_run()` charges. Charge explicitly here so "no refund fires on
    # this branch" is a real, checkable claim against the balance rather
    # than a no-op assertion.
    credit_cost = 12
    spend(user_id, credit_cost, reason="room:AAPL:test-charge")
    before = balance_for(user_id)[0]

    run_id = asyncio.run(_run_until_two_agents_then_gen_exit(
        runner, user_id=user_id, ticker="AAPL", mandate=mandate,
        credit_cost=credit_cost,
    ))

    row = _row(run_id)
    assert row.status == "running", (
        "a shutdown-triggered cancellation must leave the row RUNNING for "
        "_sweep_stuck_runs to claim on the next boot — marking it "
        "CANCELLED here is exactly DEF425's bug"
    )
    assert row.error_message is None, (
        "must not persist the (now provably false, for this path) 'client "
        "disconnected mid-run' label"
    )
    assert row.verdict is None
    # `_checkpoint_run` persists the transcript after each agent turn
    # regardless of which branch eventually handles the run's end — that is
    # pre-existing, unrelated behaviour (the incremental-snapshot narrowing
    # of the data-loss window to "last one agent") this fix does not touch.
    # `_sweep_stuck_runs` clears `transcript`/`verdict` itself when it claims
    # the row for retry, so this stale snapshot never reaches a client.
    assert len(row.transcript) == 2

    # No refund fires HERE — the row is still RUNNING, i.e. still "in
    # progress" from the ledger's point of view. The sweep decides
    # retry-vs-refund on the next boot.
    assert balance_for(user_id)[0] == before


def test_shutdown_cancel_marks_interrupted_at():
    """Round 2 (auditor U68, MAJOR-1): plain RUNNING isn't enough —
    `_sweep_stuck_runs` only claims rows older than
    `room_dedup_running_minutes` (30 min), and a real restart comes back in
    seconds. The shutdown branch must stamp `interrupted_at` on the row so
    the NEXT boot's sweep can tell "just started" apart from "was
    interrupted" and claim it immediately regardless of age."""
    runner = RoomRunner()
    runner.mark_shutting_down()
    mandate = hydrate_coach_mandate({"plan": "trader"})
    user_id = _billed_user()

    run_id = asyncio.run(_run_until_two_agents_then_gen_exit(
        runner, user_id=user_id, ticker="AAPL", mandate=mandate,
    ))

    row = _row(run_id)
    assert row.status == "running"
    assert row.interrupted_at is not None


def test_shutdown_cancelled_row_is_claimed_by_the_sweep_on_next_boot_with_fresh_started_at():
    """End-to-end, round 2: NO backdating — `started_at` is left exactly as
    the run set it (seconds old, the way a real restart actually happens).
    The `interrupted_at` mark (not row age) is what lets the very next
    `RoomRunner()` (simulating the reboot right after the restart) claim the
    row immediately. Round 1's version of this test backdated `started_at`
    by an hour, which is exactly what let the MAJOR-1 gap (30-minute-old
    sweep window vs. a restart that returns in seconds) pass unnoticed."""
    runner = RoomRunner()
    runner.mark_shutting_down()
    mandate = hydrate_coach_mandate({"plan": "trader"})
    user_id = _billed_user()

    run_id = asyncio.run(_run_until_two_agents_then_gen_exit(
        runner, user_id=user_id, ticker="AAPL", mandate=mandate,
    ))

    row = _row(run_id)
    assert row.started_at is not None
    started_at = row.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - started_at
    assert age < timedelta(minutes=1), (
        "sanity: started_at must still be fresh — this test's whole point "
        "is that a fresh row is still claimed"
    )

    next_boot_runner = RoomRunner()
    pending_ids = [p.run_id for p in next_boot_runner._pending_retry]
    assert run_id in pending_ids, (
        "a shutdown-interrupted row must be claimed on the very next boot "
        "regardless of how young started_at still is — that is the whole "
        "point of the interrupted_at mark"
    )

    row = _row(run_id)
    assert row.status == "running"
    assert row.retry_count == 1
    assert row.interrupted_at is None, (
        "the sweep must clear the mark on claim — this is now a fresh "
        "retry, not still the interrupted run; leaving it set would make "
        "the very next boot re-claim it again immediately"
    )


def test_find_active_run_does_not_attach_to_an_interrupted_row():
    """Round 2 (auditor U68, MAJOR-1): before the sweep claims it,
    `_find_active_run` must not treat a shutdown-interrupted row as live —
    otherwise a re-convene of the same ticker right after boot attaches to
    the dead run and streams nothing but replayed events with no verdict,
    for the whole `room_dedup_running_minutes` window."""
    runner = RoomRunner()
    runner.mark_shutting_down()
    mandate = hydrate_coach_mandate({"plan": "trader"})
    user_id = _billed_user()

    run_id = asyncio.run(_run_until_two_agents_then_gen_exit(
        runner, user_id=user_id, ticker="AAPL", mandate=mandate,
    ))

    row = _row(run_id)
    assert row.interrupted_at is not None  # sanity

    assert runner._find_active_run(user_id, "AAPL") is None, (
        "an interrupted row is not active — a re-convene must start a new "
        "run (or attach to a subsequent retry), never attach to the dead row"
    )


# ── non-shutdown cancellation: unchanged defensive fallback ──────────────


def test_non_shutdown_cancel_keeps_the_old_cancelled_no_refund_behaviour():
    """Control — a `RoomRunner` that was NEVER told the server is shutting
    down (today's only reachable case, since nothing else cancels this task)
    keeps the pre-DEF425 behaviour: CANCELLED, "client disconnected
    mid-run", no refund. This is the branch's documented defensive
    fallback, not a live path — pinned so a future edit can't silently
    delete it."""
    from app.services.credit_service import spend

    runner = RoomRunner()
    assert runner._shutting_down is False
    mandate = hydrate_coach_mandate({"plan": "trader"})
    user_id = _billed_user()
    credit_cost = 12
    spend(user_id, credit_cost, reason="room:AAPL:test-charge")
    before = balance_for(user_id)[0]

    run_id = asyncio.run(_run_until_two_agents_then_gen_exit(
        runner, user_id=user_id, ticker="AAPL", mandate=mandate,
        credit_cost=credit_cost,
    ))

    row = _row(run_id)
    assert row.status == "cancelled"
    assert row.error_message == "client disconnected mid-run"
    # Unchanged pre-existing behaviour: no refund on this branch.
    assert balance_for(user_id)[0] == before


# ── _sweep_stuck_runs: retry-exhausted rows now refund ───────────────────


def test_sweep_refunds_a_retry_exhausted_row():
    """The second gap: a row that has already been auto-retried
    MAX_AUTO_RETRIES times is marked `failed` by the sweep and — before this
    fix — NEVER refunded, leaving the user's credits gone for a convene that
    produced no verdict at all."""
    user_id = _billed_user()
    credit_cost = 12
    run_id = uuid4()
    started_at = datetime.now(timezone.utc) - timedelta(hours=1)

    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id,
            user_id=user_id,
            ticker="AAPL",
            triggered_at=started_at,
            started_at=started_at,
            mandate_version=1,
            model_tier="cheap",
            rounds=1,
            transcript=[],
            verdict=None,
            credit_cost=credit_cost,
            status="running",
            retry_count=MAX_AUTO_RETRIES,  # already exhausted
        ))

    # Charge the user first so there's something real to refund — mirrors
    # what start_run() would have done before this row's first attempt.
    from app.services.credit_service import spend
    spend(user_id, credit_cost, reason=f"room:AAPL:{run_id}")
    before = balance_for(user_id)[0]

    RoomRunner()  # __init__ runs _sweep_stuck_runs synchronously

    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one()
        assert row.status == "failed"
        assert "abandoned" in row.error_message

    assert balance_for(user_id)[0] == before + credit_cost, (
        "a retry-exhausted, permanently-failed row must refund the credits "
        "it charged — same DEF425 user-facing wrong, one hop later"
    )
    kinds = [
        e.event_type for e in _ledger(user_id)
        if e.note and str(run_id) in e.note
    ]
    assert "credits_refunded" in kinds


def test_sweep_still_queues_retry_for_a_fresh_row_with_no_refund():
    """Control — a row still within its retry budget must be queued for
    respawn, not failed/refunded (the pre-existing retry path, unchanged)."""
    user_id = _billed_user()
    credit_cost = 12
    run_id = uuid4()
    started_at = datetime.now(timezone.utc) - timedelta(hours=1)

    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id,
            user_id=user_id,
            ticker="AAPL",
            triggered_at=started_at,
            started_at=started_at,
            mandate_version=1,
            model_tier="cheap",
            rounds=1,
            transcript=[],
            verdict=None,
            credit_cost=credit_cost,
            status="running",
            retry_count=0,
        ))

    from app.services.credit_service import spend
    spend(user_id, credit_cost, reason=f"room:AAPL:{run_id}")
    before = balance_for(user_id)[0]

    runner = RoomRunner()

    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one()
        assert row.status == "running"
        assert row.retry_count == 1

    pending_ids = [p.run_id for p in runner._pending_retry]
    assert run_id in pending_ids
    assert balance_for(user_id)[0] == before, "a queued retry must not refund"


# ── MINOR-1: on_complete must not fire on the shutdown path ──────────────


def test_shutdown_cancel_skips_on_complete_no_running_journal_entry():
    """Round 2 (auditor U68, MINOR-1): `run()` re-raises
    CancelledError/GeneratorExit on shutdown — a BaseException, so it is
    NOT caught by `_pump`'s `except Exception`, and its `finally` used to
    call `on_complete` (`_finalise_to_journal` in production) unconditionally
    anyway. That journaled the still-RUNNING row as "Room on AAPL — running
    ... without reaching a verdict" for a run that has not finished — wrong
    on its own, and duplicated once the retry's own real verdict entry
    lands. Fix: `_pump` skips `on_complete` entirely when
    `self._shutting_down` is set; the retry (or the sweep's failed branch)
    writes the real entry once the run actually reaches a terminal state.
    """
    from app.services.journal_store import get_journal_store

    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = _billed_user()
        on_complete_calls: list["UUID"] = []

        async def _on_complete(run_id) -> None:
            on_complete_calls.append(run_id)

        run_id = await runner.start_run(
            user_id=user_id,
            ticker="AAPL",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
            on_complete=_on_complete,
        )

        # Let two agents speak, then simulate the real shutdown sequence:
        # mark_shutting_down() first (main.py's lifespan ordering), THEN
        # cancel the background _pump task directly — the same thing
        # asyncio's own teardown does to every outstanding task.
        agents_done = 0
        async for ev in runner.subscribe(run_id):
            if ev.kind == "agent_done":
                agents_done += 1
                if agents_done >= 2:
                    break

        runner.mark_shutting_down()
        pump_task = next(
            t for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
        )
        pump_task.cancel()
        await asyncio.gather(pump_task, return_exceptions=True)

        return run_id, on_complete_calls

    run_id, on_complete_calls = asyncio.run(_run())

    assert on_complete_calls == [], (
        "on_complete must not fire on the shutdown path — the run has not "
        "reached a terminal state, and the retry/sweep own writing the real "
        "journal entry"
    )
    row = _row(run_id)
    assert row.status == "running"
    assert row.interrupted_at is not None

    entries, _total, _retention = get_journal_store().list_for_user(row.user_id)
    assert not any(e.reference_id == run_id for e in entries), (
        "no journal entry may exist for a run that has not reached a "
        "terminal state"
    )


# ── round 3, MINOR-1: the RESPAWN pump's own journal write ────────────────


def test_respawn_pump_skips_journal_write_on_second_shutdown_mid_retry():
    """Round 3 (auditor U68, round-2 MINOR-1): `start_run()`'s `_pump` got the
    `not self._shutting_down` guard in round 2, but `_respawn_run_from_row`'s
    OWN `_pump` — the one that drives an already-retried run — has its own
    separate `finally` block that writes the journal entry directly (not via
    `on_complete`), with no such guard. Auditor's drill C: a SECOND SIGTERM
    lands mid-retry. Before this fix that `finally` still fired and wrote
    "Room on TICKER — running ... without reaching a verdict" for a row that
    is still RUNNING and will be retried (or failed-with-refund) again on the
    NEXT boot — round 1's drill-3 finding, reached through the retry path
    instead of the first attempt. If retries are then exhausted, this false
    "running" entry is left as the ONLY record of a run that is actually
    failed and refunded.

    Fix: the same `if self._shutting_down: return` guard `start_run()`'s
    `_pump` uses for `on_complete`, applied to this `finally` block's own
    journal-write section.
    """
    from app.services.journal_store import get_journal_store
    from app.services.mandate_store import get_mandate_store

    async def _run():
        user_id = _billed_user()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        get_mandate_store().upsert(user_id, mandate)

        stale_at = datetime.now(timezone.utc) - timedelta(hours=2)
        run_id = uuid4()
        with get_session() as s:
            s.add(RoomRunRow(
                id=run_id,
                user_id=user_id,
                ticker="AAPL",
                triggered_at=stale_at,
                started_at=stale_at,
                mandate_version=1,
                model_tier="mid",
                rounds=1,
                transcript=[],
                verdict=None,
                credit_cost=8,
                status="running",
                retry_count=0,
            ))

        # Boot 1: sweep claims the stuck row (retry_count 0 -> 1, still
        # running) and queues it. Boot 2 respawns it — this IS the retry
        # whose OWN _pump is under test, not the original attempt's.
        runner = RoomRunner()
        assert len(runner._pending_retry) == 1

        await runner.resume_pending_retries()

        agents_done = 0
        async for ev in runner.subscribe(run_id):
            if ev.kind == "agent_done":
                agents_done += 1
                if agents_done >= 2:
                    break

        # The SECOND shutdown, mid-retry: mark first (main.py's lifespan
        # ordering), then cancel the respawn's background _pump task
        # directly — the same thing asyncio's own teardown does to every
        # outstanding task at process exit.
        runner.mark_shutting_down()
        pump_task = next(
            t for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
        )
        pump_task.cancel()
        await asyncio.gather(pump_task, return_exceptions=True)

        return run_id, user_id

    run_id, user_id = asyncio.run(_run())

    row = _row(run_id)
    assert row.status == "running", (
        "still mid-retry when the second shutdown landed — the row stays "
        "RUNNING (marked interrupted_at) for the NEXT boot's sweep, exactly "
        "like the first attempt's shutdown-cancel path"
    )
    assert row.interrupted_at is not None
    assert row.retry_count == 1

    entries, _total, _retention = get_journal_store().list_for_user(user_id)
    assert not any(e.reference_id == run_id for e in entries), (
        "the respawn's own _pump must not journal a run that has not "
        "reached a terminal state — this is round-2 MINOR-1's false "
        "'running' entry, reached through the retry path instead of the "
        "original attempt"
    )


def _ledger(user_id) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow)
            .where(SubscriptionEventRow.user_id == user_id)
            .order_by(SubscriptionEventRow.created_at)
        ).scalars())
