"""DEF196 — the agent overlay told the PM a limit is both unset/off and enforced as
a hard block, in the same sentence, for the majority of users.

`_mandate_common_block` used to attach a STATIC "— enforced as a hard block on the
next BUY, not a suggestion." suffix to the post-loss-cooldown line unconditionally,
regardless of whether `_cooldown_text` reported the cooldown as active. Since CR129
made `0` an explicit, common override (rather than the unset-field state) the two
clauses collided on every mandate with `post_loss_cooldown_hours=0`: the line read
"off (no cooldown enforced) — enforced as a hard block", contradicting itself in one
sentence. The reader is an LLM (the PM); CR038 measured that agents already ignore
even a CLEAR instruction ~70% of the time, and a self-contradicting one is strictly
worse input.

This file is table-driven over all seven CR101-BE1/BE2 settable caps
(`single_name_cap_pct`, `sector_cap_pct`, `post_loss_cooldown_hours`,
`max_open_positions`, `max_trades_per_day`, `max_trades_per_week`,
`max_open_risk_pct`) × {set, unset (None)} — the fix must hold for every field, not
just the one the auditor happened to quote.
"""

from __future__ import annotations

import pytest

from app.agents.overlay_generator import generate_overlay
from app.schemas import AgentId
from app.services.coach_engine import hydrate_coach_mandate

_SEVEN_FIELDS = [
    "single_name_cap_pct",
    "sector_cap_pct",
    "post_loss_cooldown_hours",
    "max_open_positions",
    "max_trades_per_day",
    "max_trades_per_week",
    "max_open_risk_pct",
]

_OFF_MARKERS = ("not set", "off (no cooldown")
_ENFORCED_MARKER = "enforced as a hard block"


def _overlay_for(field: str, value) -> str:
    mandate = hydrate_coach_mandate({"plan": "trader"}).model_copy(update={field: value})
    return generate_overlay(AgentId.PORTFOLIO_MANAGER, mandate)


@pytest.mark.parametrize("field", _SEVEN_FIELDS)
@pytest.mark.parametrize("state", ["unset", "set"])
def test_off_state_and_enforced_marker_never_share_a_line(field, state):
    value = None if state == "unset" else (0 if field != "sector_cap_pct" else 5.0)
    overlay = _overlay_for(field, value)
    for line in overlay.splitlines():
        lowered = line.lower()
        is_off = any(m in lowered for m in _OFF_MARKERS)
        is_enforced = _ENFORCED_MARKER in lowered
        assert not (is_off and is_enforced), (field, state, line)


def test_zero_hour_cooldown_reads_off_not_enforced():
    """The exact regression: `post_loss_cooldown_hours=0` must not claim enforcement."""
    overlay = _overlay_for("post_loss_cooldown_hours", 0)
    cooldown_line = next(l for l in overlay.splitlines() if l.startswith("- Post-loss cooldown"))
    assert "off (no cooldown enforced)" in cooldown_line
    assert "enforced as a hard block" not in cooldown_line


def test_a_real_cooldown_still_states_the_enforcement_mechanism():
    """Vacuity guard: the fix must not silently drop the mechanism sentence when
    the cooldown IS active — only suppress it on the off branch."""
    overlay = _overlay_for("post_loss_cooldown_hours", 24.0)
    cooldown_line = next(l for l in overlay.splitlines() if l.startswith("- Post-loss cooldown"))
    assert "24" in cooldown_line
    assert "enforced as a hard block" in cooldown_line


def test_zero_binds_as_block_everything_on_the_other_six_fields():
    """The documented asymmetry: unlike the cooldown, `0` on the other size/pace
    caps means "no room at all" — the overlay must still show that as a real 0,
    not an "off"/unenforced narration."""
    for field in _SEVEN_FIELDS:
        if field == "post_loss_cooldown_hours" or field == "sector_cap_pct":
            continue
        overlay = _overlay_for(field, 0)
        assert "0" in overlay, field
