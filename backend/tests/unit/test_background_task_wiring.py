"""Every background tick is actually registered in `lifespan()` — the one line whose absence is invisible to the rest of the suite.

CR136-M03 m1 raised this against `_portfolio_snapshot_tick`: nothing asserted
`asyncio.create_task(_portfolio_snapshot_tick())` at `main.py:229`, and every
Tier-2 number plus F16's entire validation layer exists only if that line runs.
Deleting it produces an **empty series**, not an error — the tick's own tests
keep passing, because they call `run_portfolio_snapshot_tick()` directly.

That is DEF038 / DEF063's shape, which `failure_patterns.md` P1 is about: a
feature that ships, runs dead, and is discovered months later because nothing
went red. The generalisation to *every* tick is deliberate — M03 found it for
one, and the same hole exists for each of the others by construction.

Read from source with `ast` rather than by importing and inspecting a running
app: `lifespan` is an async context manager whose body only executes under a
real server, so an import-time check would assert nothing and a runtime one
would need uvicorn. This asserts the wiring exists where the wiring lives.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

_MAIN = Path(__file__).resolve().parents[2] / "app" / "main.py"

# Every periodic task this backend depends on, and what goes quiet if its
# registration is dropped. The consequence column is the point: each of these
# fails by producing NOTHING, which is why the suite cannot see it.
_TICKS = {
    "_nightly_audit_trim": "audit tables grow without bound",
    # CR109 slice 7 removed `_league_roll_tick` — the reputation league it
    # rolled is retired (Amendment A). Deleted from this list deliberately,
    # which is the only correct way to leave it: the guard reads main.py, so a
    # tick that is defined-but-unregistered fails here, and a tick that is
    # gone entirely must leave with its entry or the guard fails forever on a
    # name nothing defines.
    "_sharia_universe_refresh": "the Sharia universe silently goes stale",
    "_classification_universe_refresh": "sector classifications go stale",
    "_ticker_reference_refresh": "the ticker existence table goes stale",
    "_price_alert_evaluation_tick": "price alerts never fire",
    "_portfolio_snapshot_tick": (
        "no Tier-2 history accumulates — realised drawdown and realised return "
        "stay empty forever, and F16 has nothing to validate against"
    ),
}


def _registered_tasks() -> set[str]:
    """Names passed to `asyncio.create_task(<name>())` anywhere in main.py."""
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "create_task" or not node.args:
            continue
        inner = node.args[0]
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
            found.add(inner.func.id)
    return found


def _defined_coroutines() -> set[str]:
    tree = ast.parse(_MAIN.read_text(encoding="utf-8"))
    return {
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
    }


def test_the_scan_finds_registrations_at_all() -> None:
    """Vacuity: if `create_task` were ever renamed or the tasks moved out of
    `main.py`, every assertion below would pass by finding nothing."""
    assert len(_registered_tasks()) >= 5, "create_task scan returned almost nothing"


@pytest.mark.parametrize("tick,consequence", sorted(_TICKS.items()))
def test_every_background_tick_is_registered(tick: str, consequence: str) -> None:
    assert tick in _registered_tasks(), (
        f"{tick} is defined but never passed to asyncio.create_task in main.py. "
        f"Consequence if it ships this way: {consequence}. This fails silently — "
        "the tick's own unit tests call it directly and stay green."
    )


def test_no_tick_is_defined_and_left_unwired() -> None:
    """The other direction, and the one that actually catches a NEW tick: a
    `_*_tick` / `_*_refresh` coroutine that was written and never registered.

    Without this, adding a tick and forgetting the `create_task` line passes —
    the parametrized list above only knows about ticks someone remembered to
    add to it."""
    suffixes = ("_tick", "_refresh", "_trim")
    candidates = {
        name for name in _defined_coroutines()
        if name.startswith("_") and name.endswith(suffixes)
    }
    unwired = candidates - _registered_tasks()
    assert unwired == set(), (
        f"background coroutine(s) defined in main.py but never registered: "
        f"{sorted(unwired)}. Either wire them into lifespan() or move them out "
        "of main.py — a periodic task that no one starts fails by doing nothing."
    )
