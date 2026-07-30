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


def test_single_name_compliance_cap_now_matches_the_risk_tier_preset(base_mandate: Mandate):
    """CR129 closes DEF187: with no explicit `single_name_cap_pct` override,
    the deterministic compliance floor's single-name cap now reads the SAME
    risk-tier preset the Trader/PM overlay narrates and the Room pre-clamps
    to — completing the CR046 "shown == enforced" invariant this file's other
    test already holds for the narration/clamp pair. Pre-CR129 this floor
    fell back to the flat `SINGLE_NAME_ABSOLUTE_CAP_PCT` (50%) backstop
    instead, a disclosed divergence DEF187 named and Saiful has now
    authorised closing (13 live alpha mandates)."""
    assert single_name_cap_pct(base_mandate) == risk_tier_cap(base_mandate.risk_score)
    assert single_name_cap_pct(base_mandate) != SINGLE_NAME_ABSOLUTE_CAP_PCT
