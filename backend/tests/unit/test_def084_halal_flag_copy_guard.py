"""GUARD (DEF084) — a mandate flag's user-facing rejection copy must describe the
mechanism that actually enforces it.

Fourth occurrence of the CLAUDE.md "degrade loudly" class (after DEF038, DEF063,
DEF082). The `halal` compliance flag is enforced by membership in a fixed,
curated *demonstration universe* (a literal 7-ticker set) — NOT by a computed
Sharia ratio screen. `app.trading_math.screening.sharia_screen()` exists but is
wired to nothing on the `halal` enforcement path (verified DEF084). So the
rejection copy a client renders must not tell the user a Sharia/compliance
*screen* was run.

These tests fail RED against the pre-DEF084 copy ("...fails Sharia compliance
screen") and stay GREEN only while the copy tells the truth about the allowlist.
If a future change wires the real screen in (Option 1), update this guard to
assert the computation runs — do not relax it.
"""

import app.agents.safety_floor as safety_floor_mod
import app.services.sim_engine as sim_engine_mod
from app.agents.safety_floor import check_mandate_compliance
from app.schemas import Compliance, Mandate
from app.schemas.trade import ProposedTrade

# Phrases that assert a *computation* ran. A literal-set allowlist runs none of
# these, so none may be AFFIRMED in copy a client renders for a halal rejection.
_SCREEN_CLAIM_PHRASES = ("sharia compliance screen", "sharia screen", "compliance screen")

# Explicit disclaimers are the honest thing to say ("...not a Sharia screen") and
# must NOT trip the guard — the guard forbids *claiming* a screen ran, not denying
# one. Strip negated forms before scanning for an affirmative claim.
_NEGATED_DISCLAIMERS = (
    "not a sharia compliance screen",
    "not a sharia screen",
    "not a compliance screen",
)


def _halal(base_mandate: Mandate) -> Mandate:
    return base_mandate.model_copy(
        update={"compliance": Compliance(halal=True, long_only=True, liquid_only=True)}
    )


def test_halal_flag_enforcement_is_a_literal_set_not_a_screen() -> None:
    """The mechanism today IS a fixed literal set (a demonstration universe).

    Guards the Option-2 shape: if someone imports the real ratio screen into an
    enforcement module (Option 1), this trips so the copy guard below is revisited
    at the same time.
    """
    universe = sim_engine_mod.DEFAULT_HALAL_DEMO_UNIVERSE
    assert isinstance(universe, (set, frozenset)) and len(universe) > 0
    assert not hasattr(safety_floor_mod, "sharia_screen")
    assert not hasattr(sim_engine_mod, "sharia_screen")


def test_halal_rejection_copy_does_not_claim_a_computed_screen(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
) -> None:
    """The copy for a halal rejection must not claim a Sharia/compliance *screen*
    ran — the flag is enforced by membership in a curated demonstration universe.
    """
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=_halal(base_mandate),
        halal_universe={"AAPL", "MSFT"},  # NVDA excluded → rejection
    )
    assert not result.passed
    text = " ".join(result.violations).lower()
    # It must positively name the real mechanism...
    assert "demonstration universe" in text, (
        "halal rejection copy must name the curated demonstration universe (DEF084)"
    )
    # ...and must not AFFIRM a computed screen (negated disclaimers are allowed).
    for disclaimer in _NEGATED_DISCLAIMERS:
        text = text.replace(disclaimer, "")
    offending = [p for p in _SCREEN_CLAIM_PHRASES if p in text]
    assert not offending, (
        f"halal rejection copy claims a computed screen {offending} but the flag "
        f"is enforced by a literal demonstration universe (DEF084). Either wire "
        f"trading_math.sharia_screen() into the halal path, or keep the copy honest."
    )
