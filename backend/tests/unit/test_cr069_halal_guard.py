"""GUARD (CR069, specified by DEF084, previously unbuilt) — every mandate flag is
enforced by the mechanism its user-facing copy describes.

DEF084 established the failure class: the `halal` flag's only implementation was a
literal 7-ticker set while the copy claimed a Sharia *screen*. This guard refuses
that shape for `halal` specifically:

  1. the enforcement path reads a SOURCED universe (a HalalUniverse carrying a named
     standard + source), not a bare literal set; and
  2. the verdict a caller receives is three-state with provenance, NOT a bare boolean:
       - an in-parent-index non-compliant ticker is BLOCKED with a message naming the
         standard + source + as-of;
       - a ticker outside the parent index returns UNKNOWN and is PERMITTED (G3) — it
         must never produce a rejection; and
       - the ShariaVerdict rides on the ComplianceResult on BOTH outcomes, so a
         permitted-unknown trade still carries the disclosure.

Proven RED before the fix: at the base commit the sourced mechanism does not exist
(`default_halal_universe` / `HalalUniverse` are absent), so this file fails at import.
See the lane hand-off for the recorded red output.
"""

from datetime import date

from app.agents.safety_floor import check_mandate_compliance
from app.schemas import Compliance, Mandate
from app.schemas.sharia import ShariaStatus
from app.schemas.trade import ProposedTrade, Side
from app.services.sharia_universe import HalalUniverse, default_halal_universe

_STANDARD = "AAOIFI"
_SOURCE_TOKEN = "SPUS"  # the source the code reads, which the copy must also name


def _halal(base_mandate: Mandate) -> Mandate:
    return base_mandate.model_copy(
        update={"compliance": Compliance(halal=True, long_only=True, liquid_only=True)}
    )


def _check(mandate: Mandate, ticker: str, universe) -> object:
    return check_mandate_compliance(
        ProposedTrade(ticker=ticker, side=Side.BUY, quantity=1, limit_price=10.0),
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
        halal_universe=universe,
        holdings=[], last_loss_closed_at=None, trade_open_timestamps=[],
        existing_open_risk_pct=0.0,
    )


def test_default_universe_is_sourced_and_names_its_standard():
    u = default_halal_universe()
    assert isinstance(u, HalalUniverse)
    # The copy the code renders must name the same standard + source the code used.
    assert u.standard == _STANDARD
    assert _SOURCE_TOKEN in u.source


def test_screened_out_blocks_and_names_the_standard(base_mandate: Mandate):
    u = HalalUniverse(
        {"AAA", "AAB"}, parent_index={"AAA", "AAB", "JPMX"}, as_of=date(2026, 7, 22)
    )
    res = _check(_halal(base_mandate), "JPMX", u)
    assert not res.passed
    assert res.blocked_by == "compliance"
    text = " ".join(res.violations)
    assert _STANDARD in text and "2026-07-22" in text
    assert res.sharia_verdict.status is ShariaStatus.SCREENED_OUT


def test_unknown_is_permitted_but_verdict_still_travels(base_mandate: Mandate):
    u = HalalUniverse(
        {"AAA", "AAB"}, parent_index={"AAA", "AAB", "JPMX"}, as_of=date(2026, 7, 22)
    )
    res = _check(_halal(base_mandate), "NEVR", u)  # outside parent index → unknown
    assert res.passed  # G3: permitted, not blocked
    assert not res.violations
    # But the disclosure must be able to travel on a successful trade.
    assert res.sharia_verdict is not None
    assert res.sharia_verdict.status is ShariaStatus.UNKNOWN
    assert "not a ruling" in res.sharia_verdict.message().lower()


def test_pass_permits_and_carries_provenance(base_mandate: Mandate):
    u = HalalUniverse(
        {"AAA", "AAB"}, parent_index={"AAA", "AAB", "JPMX"}, as_of=date(2026, 7, 22)
    )
    res = _check(_halal(base_mandate), "AAA", u)
    assert res.passed
    assert res.sharia_verdict.status is ShariaStatus.PASS
    assert _STANDARD in res.sharia_verdict.message()


def test_unavailable_source_pauses_loudly(base_mandate: Mandate):
    """Degrade loudly (constraint 3): a paused source blocks with a pause message,
    never a silent pass and never a fall back to a placeholder set."""
    paused = HalalUniverse(frozenset(), as_of=None, stale=True)
    res = _check(_halal(base_mandate), "AAA", paused)
    assert not res.passed
    assert "paused" in " ".join(res.violations).lower()
