"""DEF425 round 4 (auditor u66, round-3 MINOR-1) — the interrupted-at mark
must not depend on uvicorn being PID 1.

Round 3 made `mark_shutting_down()` reachable (bounded uvicorn shutdown wait),
but the `interrupted_at` stamp itself is only written once something cancels
the Room's `_pump` task. The lifespan (`main.py`) only cancels its OWN
tracked tick tasks — the Room's `_pump` tasks are bare `asyncio.create_task`
calls, so what cancelled them depended on asyncio's teardown cascade, which
in turn depended on uvicorn's captured SIGTERM being dropped for want of a
handler — true only because the exec-form Dockerfile CMD makes uvicorn PID 1.
A compose `command:` override, a shell-form entrypoint, or `init: true` would
silently remove the mark on every Room while all unit tests stayed green,
because those tests call `mark_shutting_down()` and `task.cancel()` by hand.

Fix: `RoomRunner` now keeps a set of its own `_pump` tasks (`self._pump_tasks`,
populated by `_track_pump()` at both `create_task` sites — start_run's and the
respawn's — and self-pruned via a done-callback). `main.py`'s lifespan
`finally` calls `RoomRunner.cancel_pumps_for_shutdown(timeout=3.0)` right
after `mark_shutting_down()`, cancelling and awaiting every tracked pump
directly — no longer relying on the teardown cascade reaching them at all,
so the mark lands whatever the process's PID or entrypoint shape.

This test drives `cancel_pumps_for_shutdown` itself (the function the
lifespan calls) against a REAL `start_run()`-spawned pump, without the test
ever calling `task.cancel()` by hand — the whole point being that this
method, not the test, does the cancelling.
"""

from __future__ import annotations

import asyncio

from app.db import get_session
from app.db.models import RoomRunRow
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import RoomRunner
from sqlalchemy import select
from tests.unit.test_def425_shutdown_cancel_no_refund_gap import _billed_user

import pytest

pytestmark = pytest.mark.allow_ledger_drift


def test_cancel_pumps_for_shutdown_cancels_a_live_tracked_pump_and_marks_the_row():
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = _billed_user()

        run_id = await runner.start_run(
            user_id=user_id,
            ticker="AAPL",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )

        # Let two agents speak so the pump is genuinely mid-flight, then
        # simulate the real shutdown ORDERING: mark_shutting_down() first
        # (main.py's lifespan calls it before cancel_pumps_for_shutdown),
        # exactly as the lifespan's finally block does.
        agents_done = 0
        async for ev in runner.subscribe(run_id):
            if ev.kind == "agent_done":
                agents_done += 1
                if agents_done >= 2:
                    break

        assert len(runner._pump_tasks) == 1, (
            "start_run's _pump must be tracked via _track_pump() at its "
            "create_task call site"
        )
        tracked_task = next(iter(runner._pump_tasks))
        assert not tracked_task.done()

        runner.mark_shutting_down()
        # The test never calls task.cancel() itself — cancel_pumps_for_shutdown
        # is the thing under test, and it must do the cancelling.
        await runner.cancel_pumps_for_shutdown(timeout=3.0)

        # Asserted INSIDE the running event loop, immediately after the call
        # under test returns — not after asyncio.run()'s own cleanup, which
        # cancels every still-pending task on its way out and would silently
        # paper over a no-op cancel_pumps_for_shutdown (observed: a mutated
        # early-`return` version of that method still left this test green
        # if these checks ran after asyncio.run(), because asyncio.run()
        # itself cancelled the leftover task before this function got to see
        # it — the checks must not depend on that unrelated cleanup).
        assert tracked_task.done(), (
            "cancel_pumps_for_shutdown must actually cancel the tracked pump "
            "itself, not rely on asyncio.run()'s own end-of-loop cleanup"
        )
        assert tracked_task.cancelled(), (
            "the pump must end up cancelled, not merely finished some other way"
        )

        with get_session() as s:
            row = s.execute(
                select(RoomRunRow).where(RoomRunRow.id == run_id)
            ).scalar_one()

        assert row.status == "running", (
            "the row is left RUNNING for _sweep_stuck_runs to claim next "
            "boot — the shutdown branch must not flip it to CANCELLED/failed"
        )
        assert row.interrupted_at is not None, (
            "the interrupted-at mark must land from cancel_pumps_for_shutdown "
            "alone, with no hand-cancellation and no reliance on uvicorn "
            "being PID 1"
        )

    asyncio.run(_run())


def test_a_pump_that_finishes_on_its_own_is_pruned_from_the_tracked_set():
    """The done-callback must remove a pump from `_pump_tasks` once it
    completes normally — otherwise the set would grow unbounded across many
    Rooms, and a later shutdown would try to cancel tasks that are long
    finished."""
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id = _billed_user()

        run_id = await runner.start_run(
            user_id=user_id,
            ticker="AAPL",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
        assert len(runner._pump_tasks) == 1

        async for _ in runner.subscribe(run_id):
            pass  # drain to completion, no shutdown involved

        # Give the done-callback a tick to run.
        await asyncio.sleep(0)
        return runner

    runner = asyncio.run(_run())
    assert len(runner._pump_tasks) == 0, (
        "a finished pump must be pruned from _pump_tasks by its done-callback"
    )


def test_no_tracked_pumps_is_a_cheap_no_op():
    async def _run():
        runner = RoomRunner()
        runner.mark_shutting_down()
        await runner.cancel_pumps_for_shutdown(timeout=3.0)

    asyncio.run(_run())  # must not raise, must not hang
