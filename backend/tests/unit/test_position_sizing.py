"""CR046 M03 coherence guard: the position-size cap an agent is SHOWN must equal
the cap the system ENFORCES.

Before the fix these disagreed ~9× — the Trader was told "up to 40% per name"
(overlay_generator._max_position_pct) while the Portfolio Manager silently clamped
to 4.5% (room_runner._risk_tier_size_ceiling). This test fails RED against that
state and stays green only while both read app.trading_math.sizing.risk_tier_cap.
It is the enforcing check for failure-patterns P5.
"""

from __future__ import annotations

import pytest

from app.agents.overlay_generator import _max_position_pct
from app.agents.safety_floor import single_name_cap_pct
from app.schemas import Mandate
from app.services.room_runner import _risk_tier_size_ceiling
from app.trading_math.sizing import SINGLE_NAME_ABSOLUTE_CAP_PCT, risk_tier_cap


@pytest.mark.parametrize("risk_score", [1, 2, 3, 4, 5])
def test_trader_narration_cap_equals_pm_clamp_ceiling(risk_score, base_mandate: Mandate):
    m = base_mandate.model_copy(update={"risk_score": risk_score})
    told = _max_position_pct(m)  # what the Trader agent is told in its overlay
    enforced = _risk_tier_size_ceiling(m)  # what the PM verdict is clamped to
    assert told == enforced
    assert told <= SINGLE_NAME_ABSOLUTE_CAP_PCT


def test_single_name_compliance_cap_falls_back_to_the_library_backstop(base_mandate: Mandate):
    """CR101-BE1: with no explicit `single_name_cap_pct` override, the
    deterministic compliance check's single-name cap still falls back to the
    fixed absolute backstop — measured, migration-safe (see
    safety_floor.single_name_cap_pct's docstring for why this deliberately
    differs from the risk-tier preset the Trader/PM overlay narrates)."""
    assert single_name_cap_pct(base_mandate) == SINGLE_NAME_ABSOLUTE_CAP_PCT
    assert single_name_cap_pct(base_mandate) != risk_tier_cap(base_mandate.risk_score)
