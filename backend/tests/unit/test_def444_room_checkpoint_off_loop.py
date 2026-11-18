"""DEF444 — the Room's per-agent checkpoint must not commit on the event loop.

`_stream_agent_text` used to call a sync `_checkpoint_run` after every agent turn,
which opened a session and committed on the loop thread (0.24 s / 0.35 s stalls
under load). The checkpoint is now `await _checkpoint_run_async(run)`: snapshot on
the loop, write on a worker thread, awaited before the next event is yielded.

Moving the write off-loop naively lets a late checkpoint overwrite a later
cancel/fail/complete write (DEF425 flips the row, then the old checkpoint flips it
back to `running`). Every write therefore carries a sequence taken at snapshot
time, and a snapshot older than the last one written for that run is dropped.

Three assertions: thread identity (deterministic), loop responsiveness while the
write blocks, and ordering (a late checkpoint cannot undo a later write).
"""

from __future__ import annotations

import asyncio
import inspect
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import RoomRunRow
from app.schemas.room import RoomRun, RoomStatus
from app.services import room_runner as rr_mod

_BLOCK_S = 0.30


def _run(status: RoomStatus = RoomStatus.RUNNING) -> RoomRun:
    return RoomRun(
        id=uuid4(),
        user_id=uuid4(),
        ticker="AAPL",
        triggered_at=datetime.now(timezone.utc),
        mandate_version=1,
        model_tier="mid",
        credit_cost=0,
        status=status,
    )


def _row_status(run_id) -> str:
    with get_session() as s:
        return s.execute(
            select(RoomRunRow.status).where(RoomRunRow.id == run_id)
        ).scalar_one()


def test_checkpoint_write_runs_off_the_loop_and_does_not_stall_it(monkeypatch):
    seen: list[int] = []

    def _slow_write(seq, snap):
        seen.append(threading.get_ident())
        time.sleep(_BLOCK_S)

    monkeypatch.setattr(rr_mod, "_write_run_snapshot", _slow_write)

    async def go():
        loop_thread = threading.get_ident()
        max_gap = 0.0
        stop = asyncio.Event()

        async def heartbeat():
            nonlocal max_gap
            last = time.perf_counter()
            while not stop.is_set():
                await asyncio.sleep(0.01)
                now = time.perf_counter()
                max_gap = max(max_gap, now - last)
                last = now

        hb = asyncio.create_task(heartbeat())
        await asyncio.sleep(0.05)
        await rr_mod._checkpoint_run_async(_run())
        stop.set()
        await hb
        return loop_thread, max_gap

    loop_thread, max_gap = asyncio.run(go())
    assert seen and seen[0] != loop_thread, "checkpoint committed on the loop thread"
    assert max_gap < _BLOCK_S / 2, f"loop stalled {max_gap:.3f}s during the checkpoint"


def test_a_late_checkpoint_cannot_overwrite_a_later_cancel_write():
    run = _run()
    rr_mod._persist_run(run)  # row exists, status running
    seq_old, snap_old = rr_mod._snapshot_run(run)  # checkpoint taken, not yet written

    run.status = RoomStatus.CANCELLED
    run.error_message = "client disconnected mid-run"
    rr_mod._persist_run(run)  # the cancel write lands first
    assert _row_status(run.id) == "cancelled"

    rr_mod._write_run_snapshot(seq_old, snap_old)  # the late checkpoint arrives
    assert _row_status(run.id) == "cancelled"


def test_checkpoint_persists_the_snapshot_not_the_live_object():
    run = _run()
    rr_mod._persist_run(run)
    seq, snap = rr_mod._snapshot_run(run)
    run.status = RoomStatus.FAILED  # mutated after the snapshot was taken
    rr_mod._write_run_snapshot(seq, snap)
    assert _row_status(run.id) == "running"


def test_the_agent_turn_awaits_the_async_checkpoint():
    src = inspect.getsource(rr_mod._stream_agent_text)
    assert "await _checkpoint_run_async(run)" in src
    assert "_persist_run(" not in src
