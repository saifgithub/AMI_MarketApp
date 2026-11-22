"""DEF200 part 2 — the service-level ratchet.

The handler census (test_def200_ratchet.py) is one hop: a handler that `await`s a
service method is exempt, so sync I/O inside that method was never traced
(BriefEngine.stream_chat reading the overlay store, RoomRunner.start_run's
pre-spend path, bug_attachments.save_attachment_streaming's plain file writes).
`census_services()` reads every `async def` under app/services/ and flags a
blocking call made directly in its own body. 18 were found on 2026-11-22 and all
moved to `asyncio.to_thread` the same day; this holds the count at zero.

Same two-direction shape as the handler ratchet: a NEW flagged function fails,
and a function LEAVING the baseline fails too, so the number keeps meaning
"outstanding debt". The baseline is empty; growing it is a decision, not an edit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_BASELINE = Path(__file__).with_suffix(".baseline.json")

sys.path.insert(0, str(_REPO / "backend" / "scripts"))
from def200_sync_io_census import census_services  # noqa: E402


def _flagged() -> set[str]:
    """`file::qualified.function`, with the `(via: ...)` detail stripped so a
    change in WHICH blocking call it is does not churn the baseline."""
    return {s.split(" (via:")[0] for s in census_services()["service_level_flagged"]}


def test_no_new_async_service_function_blocks_the_event_loop():
    baseline = set(json.loads(_BASELINE.read_text(encoding="utf-8"))["flagged"])
    added = sorted(_flagged() - baseline)
    assert not added, (
        "async service function(s) making a blocking call on the event loop:\n"
        + "".join(f"    {s}\n" for s in added)
        + "\n"
        "One uvicorn worker serves everything, so a sync DB session, sync HTTP call\n"
        "or plain file I/O inside an `async def` stalls every request and every\n"
        "open SSE stream (DEF200). Fix by handing the blocking call to\n"
        "`asyncio.to_thread(fn, *args)` (a reference, not a call), or by making the\n"
        "helper sync and threadpooling the whole of it. Mind a streaming generator:\n"
        "a DB session must not be held open across an `await`/`yield`.\n"
        "Do NOT add it to the baseline to get past this guard.\n"
        "A pure call that merely lives beside DB code belongs in\n"
        "`_REVIEWED_NON_BLOCKING` in the census, with a reason."
    )


def test_the_baseline_shrinks_when_a_function_is_fixed():
    baseline = set(json.loads(_BASELINE.read_text(encoding="utf-8"))["flagged"])
    fixed = sorted(baseline - _flagged())
    assert not fixed, (
        f"these no longer block the loop — remove them from {_BASELINE.name} in the "
        "same commit:\n" + "".join(f"    {s}\n" for s in fixed)
    )


def test_the_service_baseline_only_ever_shrinks():
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))["flagged"]
    assert len(baseline) == 0, (
        f"the DEF200 service-level baseline has grown to {len(baseline)}; it was "
        "measured at 18 and cleared to 0 on 2026-11-22. A blocking call that cannot "
        "be threadpooled needs a stated reason in the commit, not a baseline entry."
    )


def test_the_service_census_is_not_vacuous():
    """Watches the scanned POPULATION, never the flagged subset (which is meant to
    be zero): if the census stopped finding app/services/, both ratchet tests would
    pass over an empty set."""
    result = census_services()
    assert result["total_async_service_functions"] >= 40, (
        f"scanned only {result['total_async_service_functions']} async service "
        "functions; it scanned 80 on 2026-11-22. SERVICES_DIR moved, or the walk broke."
    )
