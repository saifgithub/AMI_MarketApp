"""DEF136 — the Room convene path must not run its portfolio builders on the
event loop thread.

`room_runner.run()` calls `_build_sim_holdings_block` and
`_build_room_sector_context`. Both reach `SimEngine.current_marks` ->
`_marks_with_quotes`, which opens a `ThreadPoolExecutor` and `pool.map`s a real
yfinance quote per holding. Called bare from an `async def`, that fan-out runs
ON the loop thread and every other Room stream, SSE heartbeat and request served
by the same worker waits for it — on every single convene.

**Why this file exists at all.** DEF116 found the class, DEF120 built the AST
guard, and four rounds of DEF120 reasoned about this call site *statically* —
the loop was never once observed. `test_no_blocking_io_in_async_routes.py` can
only prove the `to_thread` wrapper is present in the source; it cannot prove the
loop is actually free. This file measures it.

Two assertions, deliberately of different kinds:

  1. **Thread identity** — the builders must execute on a thread that is NOT the
     loop's. Deterministic: no timing, no flake, and it fails the instant either
     `await asyncio.to_thread(...)` is removed.
  2. **Loop responsiveness** — a concurrent heartbeat task keeps ticking while
     the builders block. This is the property users feel, and it is the one the
     defect is actually about; asserted with a wide margin so a loaded CI box
     does not turn it red.
"""

from __future__ import annotations

import asyncio
import threading
import time
from uuid import uuid4

from app.services import room_runner as rr_mod
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import RoomRunner

# Long enough that a blocked loop is unmistakable, short enough to keep the
# suite fast. Two builders => 2 x this is the total blocking window.
_BLOCK_S = 0.30
_TICK_S = 0.01


class _SilentGateway:
    """Minimal LLM stand-in — this file measures the loop, not the agents."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        yield "AMI agent live reply."


class _ThreadProbe:
    """Replaces a builder with one that BLOCKS and records where it ran."""

    def __init__(self, name: str, result):
        self.name = name
        self.result = result
        self.thread_ids: list[int] = []

    def __call__(self, *_args, **_kwargs):
        self.thread_ids.append(threading.get_ident())
        time.sleep(_BLOCK_S)  # deliberately BLOCKING, not awaitable
        return self.result


def _drive(monkeypatch) -> tuple[_ThreadProbe, _ThreadProbe, int, float, float, float]:
    """Run one convene with both builders blocking.

    Returns the two probes, the loop thread id, a **baseline** longest-gap
    measured on an idle loop moments earlier, the **longest gap between
    consecutive heartbeat ticks** during the convene, and the elapsed wall time.

    The max-gap metric is the one that matters and it was not obvious. A tick
    *count* over the whole convene looked reasonable and is nearly useless:
    measured here, clean = 197 ticks, one builder un-wrapped = 171, both = 141.
    The signal is real but it is a ~13% dip buried in a 2.1s run, so any floor
    loose enough to survive a loaded CI box is also loose enough to miss a
    single un-wrapped call site — the first version of this test did exactly
    that and passed under mutation.

    The longest inter-tick gap has no such problem: a blocked loop cannot run
    the heartbeat AT ALL for the duration of the block, so the gap jumps
    straight to `_BLOCK_S`. Clean it stays at scheduler jitter. That is a
    ~10x separation instead of 13%, and it does not care how fast the machine
    is or how long the convene takes.

    **DEF304 — the baseline window.** The sentence above ends "does not care how
    fast the machine is", and that was the part that was wrong. The gap the
    convene produces is `jitter`, and the gap an un-wrapped builder produces is
    `jitter + _BLOCK_S`; only the SECOND term is a constant. The original
    threshold compared `jitter` against a constant measured on an idle Mac, so
    once jitter approached `_BLOCK_S / 2` the guard went red on correct code —
    measured at 0.273s against a 0.150s threshold, 1 failure in 5 runs at load
    average 3.0.

    So the reasoning is unchanged and only the reference point moves: measure
    the idle loop's own worst gap in this same process, moments before the
    convene, and require the convene's gap to stay under `baseline + _BLOCK_S/2`
    rather than under a number from another machine on another day. Under load
    both terms rise together and the separation survives; on an idle box the
    baseline is ~0.01s and the threshold is what it always was.
    """
    sim_probe = _ThreadProbe("_build_sim_holdings_block", "")
    sector_probe = _ThreadProbe(
        "_build_room_sector_context", ([], {}, {}, {})
    )
    monkeypatch.setattr(rr_mod, "_build_sim_holdings_block", sim_probe)
    monkeypatch.setattr(rr_mod, "_build_room_sector_context", sector_probe)

    async def go():
        loop_thread_id = threading.get_ident()
        max_gap = 0.0
        stop = asyncio.Event()

        async def heartbeat():
            nonlocal max_gap
            last = time.monotonic()
            while not stop.is_set():
                await asyncio.sleep(_TICK_S)
                now = time.monotonic()
                max_gap = max(max_gap, now - last)
                last = now

        hb = asyncio.create_task(heartbeat())

        # DEF304 — what this machine's idle loop is worth RIGHT NOW. Same
        # process, same scheduler pressure, seconds apart from the measurement
        # it calibrates. Held for the same wall time the convene's blocking
        # window occupies, so both samples get a comparable chance to catch a
        # bad scheduling slice.
        await asyncio.sleep(2 * _BLOCK_S)
        baseline_gap = max_gap
        max_gap = 0.0

        runner = RoomRunner(llm=_SilentGateway())  # type: ignore[arg-type]
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

        started = time.monotonic()
        async for _ev in runner.run(
            user_id=uuid4(), ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        ):
            pass
        elapsed = time.monotonic() - started

        stop.set()
        await hb
        return (
            sim_probe, sector_probe, loop_thread_id,
            baseline_gap, max_gap, elapsed,
        )

    return asyncio.run(go())


def test_both_builders_run_off_the_loop_thread(monkeypatch):
    """The deterministic half. Un-wrap either call site and this goes red."""
    sim_probe, sector_probe, loop_thread_id, _base, _gap, _elapsed = _drive(monkeypatch)

    assert sim_probe.thread_ids, "_build_sim_holdings_block was never called"
    assert sector_probe.thread_ids, "_build_room_sector_context was never called"

    for probe in (sim_probe, sector_probe):
        for tid in probe.thread_ids:
            assert tid != loop_thread_id, (
                f"{probe.name} ran ON the event loop thread. Its yfinance "
                "fan-out therefore blocks every other Room stream, SSE "
                "heartbeat and request on this worker for its full duration. "
                "Wrap the call site in `await asyncio.to_thread(...)`."
            )


def test_the_loop_never_stalls_while_the_builders_block(monkeypatch):
    """The half that measures what a user on another Room stream actually feels.

    While each builder sits in `time.sleep(_BLOCK_S)`, a heartbeat task on the
    loop must keep firing. If the builder runs on the loop thread the heartbeat
    cannot run at all for that whole window, so the longest gap between ticks
    jumps from scheduler jitter to `_BLOCK_S`.

    Measured on an idle machine (2 runs each, ±1ms):

        both wrapped (correct)   max gap ~0.01s
        one un-wrapped           max gap ~0.30s
        both un-wrapped          max gap ~0.30s

    The threshold is `baseline + _BLOCK_S / 2` — half a block above whatever
    this machine's idle loop is managing right now, which is an order of
    magnitude above jitter and well below a real stall in both conditions. Note
    the metric catches a SINGLE un-wrapped call site, which a tick-count floor
    did not. See DEF304 in `_drive` for why the baseline term is not optional.
    """
    _sim, _sector, _loop_id, baseline_gap, max_gap, elapsed = _drive(monkeypatch)

    # Guard the guard: if the probes never blocked, everything below is vacuous.
    assert elapsed >= 2 * _BLOCK_S, (
        f"elapsed {elapsed:.3f}s < {2 * _BLOCK_S:.3f}s — the blocking probes "
        "did not run, so this test proves nothing"
    )

    # DEF304 — and guard the baseline too. A baseline at or above _BLOCK_S would
    # make the threshold below unfalsifiable: an un-wrapped builder adds
    # _BLOCK_S, so the test can only ever detect it while the idle loop's own
    # worst gap is comfortably under that. A box that loaded is not one this
    # measurement can be taken on, and saying so is better than passing.
    assert baseline_gap < _BLOCK_S / 2, (
        f"the idle loop's own worst gap is {baseline_gap:.3f}s, at or above the "
        f"{_BLOCK_S / 2:.3f}s this test needs as headroom. The machine is too "
        "loaded for the measurement to mean anything — this is not a DEF136 "
        "regression, and it must not be read as one."
    )

    assert max_gap < baseline_gap + _BLOCK_S / 2, (
        f"the event loop STALLED for {max_gap:.3f}s in a single gap (threshold "
        f"{baseline_gap + _BLOCK_S / 2:.3f}s = this machine's idle baseline "
        f"{baseline_gap:.3f}s + {_BLOCK_S / 2:.3f}s). A builder is running on "
        "the loop thread, so its yfinance fan-out freezes every other Room "
        "stream, SSE heartbeat and request on this worker for its full "
        "duration — DEF136."
    )
