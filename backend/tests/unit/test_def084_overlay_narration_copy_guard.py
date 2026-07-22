"""GUARD (DEF084-ROOM) — the AGENT-NARRATION surface must describe the halal
flag's real mechanism, not claim a Sharia *screen* that no code runs.

Companion to `test_def084_halal_flag_copy_guard.py` (DEF084-BE, which binds the
*deterministic* rejection copy in safety_floor/sim_engine). This guard binds the
*prompt-narration* copy that `overlay_generator.generate_overlay()` injects into
the 12 Room agents' system prompts.

The `halal` compliance flag is enforced by membership in a fixed, curated
*demonstration universe* (`sim_engine.DEFAULT_HALAL_DEMO_UNIVERSE`) — NOT by a
computed Sharia ratio screen. So no agent prompt may tell the user a
Sharia/compliance *screen* was performed, and none may narrate a ratio cutoff
(≤33% D/E, ≤5% interest income) that nothing checks.

RED against the pre-DEF084-ROOM narration (`overlay_generator.py:88,157,300` said
"...Sharia screen..."); GREEN only while every agent overlay tells the truth about
the demonstration universe. If a future change wires the real screen in (Option 1),
update this guard to assert the computation runs — do not relax it.
"""

from app.agents.overlay_generator import generate_overlay
from app.schemas import TWELVE_AGENT_IDS, Compliance, Mandate

# Phrases that assert a *computation* ran (shared with the DEF084-BE guard). A
# literal-set allowlist runs none of these, so none may be AFFIRMED in any prompt
# copy rendered for a halal mandate.
_SCREEN_CLAIM_PHRASES = ("sharia compliance screen", "sharia screen", "compliance screen")

# Explicit disclaimers are the honest thing to say ("...NOT a Sharia screen") and
# must NOT trip the guard — the guard forbids *claiming* a screen ran, not denying
# one. Strip negated forms before scanning for an affirmative claim.
_NEGATED_DISCLAIMERS = (
    "not a sharia compliance screen",
    "not a sharia screen",
    "not a compliance screen",
)

# Ratio cutoffs the pre-DEF084 narration falsely attributed to the halal flag.
# The deterministic path computes no ratio, so a halal overlay must not narrate one.
_RATIO_CLAIM_PHRASES = ("debt-to-equity", "interest income", "interest-income")


def _halal(base_mandate: Mandate) -> Mandate:
    return base_mandate.model_copy(
        update={"compliance": Compliance(halal=True, long_only=True, liquid_only=True)}
    )


def _strip_disclaimers(text: str) -> str:
    for disclaimer in _NEGATED_DISCLAIMERS:
        text = text.replace(disclaimer, "")
    return text


def test_no_halal_overlay_claims_a_computed_screen(base_mandate: Mandate) -> None:
    """Across all 12 trading agents, no halal-mandate overlay may AFFIRM a
    Sharia/compliance *screen* (negated disclaimers are allowed)."""
    mandate = _halal(base_mandate)
    for agent_id in TWELVE_AGENT_IDS:
        text = _strip_disclaimers(generate_overlay(agent_id, mandate).lower())
        offending = [p for p in _SCREEN_CLAIM_PHRASES if p in text]
        assert not offending, (
            f"{agent_id} overlay claims a computed screen {offending} but the halal "
            f"flag is enforced by a curated demonstration universe (DEF084). Keep the "
            f"narration honest, or wire trading_math.sharia_screen() into the path."
        )


def test_no_halal_overlay_narrates_a_ratio_cutoff(base_mandate: Mandate) -> None:
    """No halal-mandate overlay may narrate a D/E or interest-income ratio cutoff —
    nothing computes one on the halal enforcement path (DEF084)."""
    mandate = _halal(base_mandate)
    for agent_id in TWELVE_AGENT_IDS:
        text = generate_overlay(agent_id, mandate).lower()
        offending = [p for p in _RATIO_CLAIM_PHRASES if p in text]
        assert not offending, (
            f"{agent_id} overlay narrates a ratio cutoff {offending} for the halal "
            f"flag, but no ratio is computed (DEF084). Remove the false narration."
        )


def test_halal_compliance_block_names_the_demonstration_universe(
    base_mandate: Mandate,
) -> None:
    """The common compliance block (present in every trading agent's overlay) must
    positively name the curated demonstration universe for a halal mandate."""
    mandate = _halal(base_mandate)
    # The common block is identical across all trading agents; sample one.
    text = generate_overlay(TWELVE_AGENT_IDS[0], mandate).lower()
    assert "demonstration universe" in text, (
        "halal overlay must name the curated demonstration universe (DEF084)"
    )
