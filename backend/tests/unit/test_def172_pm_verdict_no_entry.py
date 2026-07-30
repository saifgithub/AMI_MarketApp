"""DEF172 — `_parse_pm_verdict` must not crash when neither entry source holds.

`entry = entry_raw or ctx.trader_entry` (room_runner.py:914) falls back to the
Trader's price when the PM stated none. `stop`/`target` are then minted at
`round(entry * 0.94, 2)` / `round(entry * 1.13, 2)` when the PM didn't state
those either. Both derivations assume `entry` is a float — but nothing stops
`ctx.trader_entry` itself from being `None` (the dataclass default is `100.0`,
not a guarantee), and `None * 0.94` raises `TypeError`, propagating out of the
agent turn: a crash mid-convene is a user-visible dead Room, not a missing
field (CR040 — the honest output is a visibly absent level, never a stack
trace).
"""

from __future__ import annotations

import json

import pytest

from app.schemas import Mandate
from app.schemas.room import VerdictAction
from app.services.classification_universe import default_classification_universe
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import _RoomContext, _parse_pm_verdict
from app.services.sharia_universe import default_halal_universe


def _ctx(mandate: Mandate) -> _RoomContext:
    ctx = _RoomContext(
        ticker="AAPL",
        mandate=mandate,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=default_halal_universe(),
        classification_universe=default_classification_universe(),
        locale_allowed_universe=None,
    )
    ctx.trader_entry = None  # type: ignore[assignment]  -- both entry sources absent
    return ctx


_PM_NO_ENTRY_NO_STOP_NO_TARGET = json.dumps({
    "action": "APPROVE",
    "size_pct": 3.0,
    "entry": None,
    "stop": None,
    "target": None,
    "horizon_days": 42,
    "narration": "PM: APPROVE.",
})


@pytest.fixture
def mandate() -> Mandate:
    return hydrate_coach_mandate({"plan": "trader", "risk_score": 3})


def test_the_turn_survives_when_neither_entry_source_holds(mandate: Mandate) -> None:
    """This is the actual crash: red against unfixed code with `TypeError:
    unsupported operand type(s) for *: 'NoneType' and 'float'`."""
    narration, verdict = _parse_pm_verdict(_PM_NO_ENTRY_NO_STOP_NO_TARGET, _ctx(mandate))
    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE


def test_the_derived_level_is_visibly_absent_not_silently_dropped(mandate: Mandate) -> None:
    """The absence must read as absence: `entry`/`stop`/`target` stay `None`
    on the Verdict (never a fabricated number), the provenance map carries no
    key for a price nothing can be attributed to (T-BACKFILL — an omitted key
    must never be read as 'came from the PM'), and `reason` says in words why
    the levels are missing rather than staying silent about it."""
    _, verdict = _parse_pm_verdict(_PM_NO_ENTRY_NO_STOP_NO_TARGET, _ctx(mandate))
    assert verdict is not None
    assert verdict.entry is None
    assert verdict.stop is None
    assert verdict.target is None
    assert verdict.level_provenance is None or "entry" not in verdict.level_provenance
    assert verdict.level_provenance is None or "stop" not in verdict.level_provenance
    assert "no entry price was available" in verdict.reason


def test_a_stated_stop_survives_even_with_no_entry(mandate: Mandate) -> None:
    """The PM's own numbers are never discarded just because entry is
    unresolved — only the *derived* levels (which need `entry`) go missing."""
    pm_json = json.dumps({
        "action": "APPROVE",
        "size_pct": 3.0,
        "entry": None,
        "stop": 141.0,
        "target": None,
        "horizon_days": 42,
        "narration": "PM: APPROVE.",
    })
    _, verdict = _parse_pm_verdict(pm_json, _ctx(mandate))
    assert verdict is not None
    assert verdict.stop == 141.0
    assert verdict.target is None
    assert verdict.level_provenance == {"stop": "pm"}
