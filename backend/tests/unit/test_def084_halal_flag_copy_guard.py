"""GUARD (DEF084 → CR069) — a mandate flag's user-facing copy must describe the
mechanism that actually enforces it.

DEF084 shipped Option 2: the `halal` flag was a literal 7-ticker *demonstration
universe* and the copy had to say so (not claim a screen ran). CR069 ships
DEF084's Option 1: the flag now enforces a **sourced allowlist** — the published
constituents of the S&P 500 Sharia Industry Exclusions Index (AAOIFI, via SPUS),
three-state with provenance.

So the guard evolved rather than relaxed (as the original header instructed):
  - the enforcement path reads the SOURCED universe (not a literal set), and
  - the copy NAMES the standard + as-of it read, and
  - it still must not claim AMI *computed* a ratio screen — the three-ratio math
    (`trading_math.screening.sharia_screen`) stays dormant (CR069 constraint 4),
    so reading S&P's published result is honest but "AMI ran a debt-to-equity
    screen" would not be.

The broad "every mandate flag is enforced by the mechanism its copy describes"
guard lives in test_cr069_halal_guard.py.
"""

from datetime import date

import app.agents.safety_floor as safety_floor_mod
import app.services.sim_engine as sim_engine_mod
from app.agents.safety_floor import check_mandate_compliance
from app.schemas import Compliance, Mandate
from app.schemas.trade import ProposedTrade
from app.services.sharia_universe import HalalUniverse, default_halal_universe

# Phrases that would assert AMI itself ran the ratio *computation*. The sourced
# allowlist runs none of these, so none may appear in copy a client renders.
_COMPUTED_SCREEN_PHRASES = (
    "debt-to-equity",
    "debt to equity",
    "interest income",
    "impermissible income",
    "we screened",
    "ami screened",
    "ami ran",
    "ratio check",
)


def _halal(base_mandate: Mandate) -> Mandate:
    return base_mandate.model_copy(
        update={"compliance": Compliance(halal=True, long_only=True, liquid_only=True)}
    )


def test_halal_enforcement_reads_a_sourced_universe_not_a_literal_set() -> None:
    """The retired 7-ticker literal is gone; enforcement reads a HalalUniverse that
    carries a named standard. The ratio math stays dormant (constraint 4)."""
    universe = default_halal_universe()
    assert isinstance(universe, HalalUniverse)
    assert universe.standard == "AAOIFI"
    # The 7-ticker demo constant must be gone — not merely re-pointed.
    assert not hasattr(sim_engine_mod, "DEFAULT_HALAL_DEMO_UNIVERSE")
    # Constraint 4: no ratio screen is wired into the enforcement modules.
    assert not hasattr(safety_floor_mod, "sharia_screen")
    assert not hasattr(sim_engine_mod, "sharia_screen")


def test_halal_screened_out_copy_names_the_standard_and_does_not_claim_a_computation(
    base_mandate: Mandate, proposed_buy_nvda: ProposedTrade
) -> None:
    """A screened-out rejection must name the standard + as-of it read (provenance,
    CR069 constraint 1) and must NOT claim AMI computed a ratio screen."""
    universe = HalalUniverse(
        {"AAPL", "MSFT"},  # NVDA in the parent index but not compliant → screened out
        parent_index={"AAPL", "MSFT", "NVDA"},
        as_of=date(2026, 7, 22),
    )
    result = check_mandate_compliance(
        proposed_buy_nvda,
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=_halal(base_mandate),
        halal_universe=universe,
    )
    assert not result.passed
    text = " ".join(result.violations).lower()
    # It positively names the standard and the as-of date it read...
    assert "aaoifi" in text, "screened-out copy must name the standard (CR069)"
    assert "2026-07-22" in text, "screened-out copy must carry the as-of date (CR069)"
    # ...and must not claim AMI ran the ratio computation.
    offending = [p for p in _COMPUTED_SCREEN_PHRASES if p in text]
    assert not offending, (
        f"halal copy claims a computed ratio screen {offending}, but CR069 ships a "
        f"sourced allowlist — the ratio math stays dormant (constraint 4)."
    )
