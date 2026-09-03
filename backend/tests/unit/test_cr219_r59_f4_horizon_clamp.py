"""Tests for CR219 R59 F4: time_horizon_days plausibility clamping.

The PM's `time_horizon_days` verdict field receives no plausibility bound during
parse — `int(parsed.get("horizon_days"))` with a fallback, and no range check
(room_runner.py:2157-2159). This test verifies the fix: a clamp to [1, 365] with
disclosure appended to the verdict reason when the clamp fires.

The 365-day ceiling mirrors _MAX_EVIDENCED_HORIZON_DAYS (room_runner.py:1749),
justified in _horizon_coherence_note's docstring — the widest window on the fact
sheet (52-week range) is 365 days, so a thesis beyond it is asserted from nothing
on the sheet.
"""

from __future__ import annotations

import pytest

from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import _RoomContext, _parse_pm_verdict


def _ctx(mandate=None) -> _RoomContext:
    """Create a minimal _RoomContext for testing verdict parse."""
    return _RoomContext(
        ticker="AAPL",
        mandate=mandate or hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


# Tests


def test_in_band_horizon_passes_untouched():
    """A plausible horizon [1, 365] should pass through without modification."""
    ctx = _ctx()
    text = '{"action": "APPROVE", "horizon_days": 21, "entry": 100, "size_pct": 2}'
    display, verdict = _parse_pm_verdict(text, ctx)

    assert verdict is not None
    assert verdict.time_horizon_days == 21
    # The disclosure should NOT fire for in-band values
    assert "clamp" not in verdict.reason.lower()
    assert "adjusted" not in verdict.reason.lower()


def test_zero_clamps_to_one_with_disclosure():
    """A horizon of 0 should clamp to 1 and disclose."""
    ctx = _ctx()
    text = '{"action": "APPROVE", "horizon_days": 0, "entry": 100, "size_pct": 2}'
    display, verdict = _parse_pm_verdict(text, ctx)

    assert verdict is not None
    assert verdict.time_horizon_days == 1
    # Disclosure should appear in reason, mentioning AMI
    assert "AMI" in verdict.reason
    assert "adjust" in verdict.reason.lower()


def test_negative_clamps_to_one_with_disclosure():
    """A negative horizon should clamp to 1 and disclose."""
    ctx = _ctx()
    text = '{"action": "APPROVE", "horizon_days": -5, "entry": 100, "size_pct": 2}'
    display, verdict = _parse_pm_verdict(text, ctx)

    assert verdict is not None
    assert verdict.time_horizon_days == 1
    # Disclosure should appear in reason
    assert "AMI" in verdict.reason
    assert "adjust" in verdict.reason.lower()


def test_large_horizon_clamps_to_365_with_disclosure():
    """A very large horizon (3650) should clamp to 365 and disclose."""
    ctx = _ctx()
    text = '{"action": "APPROVE", "horizon_days": 3650, "entry": 100, "size_pct": 2}'
    display, verdict = _parse_pm_verdict(text, ctx)

    assert verdict is not None
    assert verdict.time_horizon_days == 365
    # Disclosure should appear in reason, mentioning AMI
    assert "AMI" in verdict.reason
    assert "adjust" in verdict.reason.lower()


def test_none_horizon_keeps_fallback():
    """A missing/None horizon should fall back to trader_horizon_weeks * 7 (no disclosure)."""
    ctx = _ctx()
    text = '{"action": "APPROVE", "horizon_days": null, "entry": 100, "size_pct": 2}'
    display, verdict = _parse_pm_verdict(text, ctx)

    assert verdict is not None
    # The default horizon comes from the mandate's horizon field
    # Just verify it's a reasonable number and no clamp disclosure appears
    assert verdict.time_horizon_days is not None
    assert verdict.time_horizon_days > 0
    # No disclosure should fire for the fallback path
    assert "clamp" not in verdict.reason.lower()
    assert "adjusted" not in verdict.reason.lower()


def test_boundary_values_pass():
    """Test boundary values: 1 and 365 should pass untouched."""
    ctx = _ctx()
    for boundary_value in [1, 365]:
        text = f'{{"action": "APPROVE", "horizon_days": {boundary_value}, "entry": 100, "size_pct": 2}}'
        display, verdict = _parse_pm_verdict(text, ctx)

        assert verdict is not None
        assert verdict.time_horizon_days == boundary_value
        # No disclosure for in-band values
        assert "clamp" not in verdict.reason.lower()
        assert "adjusted" not in verdict.reason.lower()


def test_clamp_disclosure_contains_new_value():
    """The disclosure should state the clamped value, not the original."""
    ctx = _ctx()
    text = '{"action": "APPROVE", "horizon_days": 500, "entry": 100, "size_pct": 2}'
    display, verdict = _parse_pm_verdict(text, ctx)

    assert verdict is not None
    assert verdict.time_horizon_days == 365
    assert "365" in verdict.reason
    assert "AMI" in verdict.reason
