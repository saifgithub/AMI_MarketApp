"""Agent-related backend logic — overlay generation, safety floor, TradingAgents wrapper."""

from app.agents.overlay_generator import generate_overlay
from app.agents.safety_floor import check_mandate_compliance, enforce_safety_floor

# DEF188: SAFETY_FLOOR_BLOCK (the raw, unsubstituted `[[CAP]]` template) is
# deliberately NOT re-exported here. render_safety_floor_block (in
# app.agents.safety_floor) is the only supported way to get the block —
# re-exporting the raw template made a silent-`[[CAP]]`-leak import look
# like the sanctioned shortcut.
__all__ = [
    "check_mandate_compliance",
    "enforce_safety_floor",
    "generate_overlay",
]
