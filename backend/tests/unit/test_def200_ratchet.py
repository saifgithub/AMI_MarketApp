"""DEF200 — stop the bleeding before scheduling the cure.

DEF200's deliverable was a census: which async handlers do blocking I/O on the
event loop, so that any slow upstream (Apple, Google, yfinance, Adanos, Reddit)
stalls the single uvicorn worker and freezes every request and every SSE stream.
`backend/scripts/def200_sync_io_census.py` produces it, re-runnably.

The census was **75 of 93 handlers** when it shipped on 2026-07-30. Re-run today
(2026-08-18) it is **87 of 120**. Nobody regressed anything — the list grew
because 27 new handlers were written in the intervening three weeks, in the same
style as the ones already on it, which is the correct style to copy if nothing
tells you otherwise. A schedulable list that grows faster than it is worked is
not schedulable.

So this is a **ratchet**, not a fix. It freezes today's flagged set as a
baseline and fails on the *next* one. The existing entries stay exactly as they
are — shipping a guard that reds on 87 of 120 handlers would be a gate whose
failing state is its normal state, which this project has paid for three times
(DEF277, the tree gate, the `/v1/llm/status` 403) and which teaches an operator
that firing does not mean stop.

Two directions, deliberately asymmetric:

  - a **new** flagged handler fails, with the three fixes named;
  - a handler **leaving** the list fails too, because the baseline must shrink
    when work lands or it silently stops being a ratchet and becomes a record
    of how things used to be.

Removing an entry from the baseline is the celebration, not the chore. Adding
one is a decision that needs a reason in the commit message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_BASELINE = Path(__file__).with_suffix(".baseline.json")

sys.path.insert(0, str(_REPO / "backend" / "scripts"))
from def200_sync_io_census import census  # noqa: E402


def _flagged() -> set[str]:
    """Every handler the census flags, by `file::handler` — the `(via: …)`
    detail is stripped, so re-ordering or adding an intermediate module does not
    churn the baseline. What is being ratcheted is *whether* a handler blocks
    the loop, not the route it takes to do so."""
    result = census()
    sites = set(result["section_a_direct_sync_db"])
    sites |= {entry.split(" (via:")[0] for entry in result["section_c_onehop_reachable"]}
    return sites


def test_no_new_handler_blocks_the_event_loop():
    baseline = set(json.loads(_BASELINE.read_text(encoding="utf-8"))["flagged"])
    current = _flagged()

    added = sorted(current - baseline)
    assert not added, (
        "new async handler(s) doing blocking I/O on the event loop:\n"
        + "".join(f"    {s}\n" for s in added)
        + "\n"
        "One uvicorn worker serves everything here, so a slow upstream inside an\n"
        "`async def` freezes every other request AND every open SSE stream —\n"
        "unauthenticated, from outside (DEF200, CR123).\n"
        "\n"
        "Three fixes, pick per handler:\n"
        "  1. Drop `async` — Starlette runs a plain `def` handler in a threadpool.\n"
        "     Simplest, and right whenever the handler does not `await` anything.\n"
        "  2. `await run_in_threadpool(...)` around the blocking call.\n"
        "  3. Use an async client for the I/O.\n"
        "\n"
        "Do NOT add the handler to the baseline to get past this. The baseline is\n"
        "87 entries of pre-existing debt frozen so this guard could ship green;\n"
        "extending it converts a ratchet into a rubber stamp."
    )


def test_the_baseline_shrinks_when_a_handler_is_fixed():
    """A ratchet that only ever holds is a record, not a ratchet. When a handler
    is converted, its baseline entry must go in the same commit — otherwise the
    number stops meaning 'outstanding debt' and starts meaning 'debt as of the
    day someone last looked'."""
    baseline = set(json.loads(_BASELINE.read_text(encoding="utf-8"))["flagged"])
    current = _flagged()

    fixed = sorted(baseline - current)
    assert not fixed, (
        "these handlers no longer block the loop — good. Remove them from\n"
        f"{_BASELINE.name} in the same commit so the count keeps meaning\n"
        "'still outstanding':\n" + "".join(f"    {s}\n" for s in fixed)
    )


def test_the_ratchet_is_not_vacuous():
    """If the census ever resolved nothing — a moved API dir, a rename, a broken
    import registry — both tests above would pass over an empty set and this
    guard would be silently inert (P21)."""
    current = _flagged()
    assert len(current) >= 50, (
        f"the census flagged only {len(current)} handlers; it flagged 87 when this "
        "baseline was taken. A collapse that large means the census is broken, not "
        "that the debt was paid."
    )


def test_the_baseline_only_ever_shrinks_from_here():
    """Pins the size the baseline was frozen at, so growing it is a visible,
    deliberate edit to this number rather than a quiet append."""
    baseline = json.loads(_BASELINE.read_text(encoding="utf-8"))["flagged"]
    assert len(baseline) <= 87, (
        f"the DEF200 baseline has grown to {len(baseline)}. It was frozen at 87 on "
        "2026-08-18 and is meant to go down. If a new blocking handler was genuinely "
        "unavoidable, say why in the commit and lower this bound in the same edit."
    )
