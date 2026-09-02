"""CR218 — hand the analyst the capital-allocation arithmetic, not the operands.

The Fundamentals Analyst's role brief names "capital allocation" as its lane, and
the fact sheet gave it buybacks in DOLLARS and dividends as a YIELD. Reaching the
actual finding — how much of free cash flow the company returned — required
converting the yield back to dollars against market cap, adding it to buybacks,
and dividing by FCF. Three steps, none of them in the sheet.

Observed 2026-09-01 on a real convene (CAT @ 2025-08-08): GLM-5.3 performed that
arithmetic inside its reasoning and reached "roughly all of TTM FCF" — correct,
96.2%. The incumbent model, given the identical prompt, read the buyback line and
never made the connection at all. That asymmetry is the argument for precomputing:
it hands the weaker reader the finding for free, which is a far better trade than
adopting a 17x-slower model to get it.

`CHARS_PER_TOKEN`-style derivation rules are not the point here. The point is that
a number the sheet can compute exactly must never be left for a model to
approximate: GLM's own derivation used yield x market cap and landed on $2,707M
against the statement's $2,812M, a 3.9% error, because a TRAILING yield times a
CURRENT market cap is not the trailing payment.
"""

from __future__ import annotations

import pytest

from app.services.fundamentals import capital_return_line, dividend_line
from app.services.room_runner import _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS


class TestTheLineItself:
    def test_both_components_are_named_beside_the_total(self):
        """A total alone cannot tell two different capital-allocation stories apart.

        A company returning $8B entirely through buybacks and one splitting it
        with a dividend are different reads, and the role brief turns on which.
        """
        line = capital_return_line(8617, 5910, 2707, 96)
        assert "$8,617M" in line
        assert "buybacks $5,910M" in line
        assert "dividends $2,707M" in line
        assert "96% of TTM FCF" in line

    def test_a_pure_buyback_payer_names_only_buybacks(self):
        """No empty 'dividends $0M' — absent is not zero, the sheet's own rule."""
        line = capital_return_line(45303, 45303, None, 71)
        assert "buybacks $45,303M" in line
        assert "dividends" not in line

    def test_a_pure_dividend_payer_names_only_dividends(self):
        line = capital_return_line(2812, None, 2812, 31)
        assert "dividends $2,812M" in line
        assert "buybacks" not in line

    def test_no_total_renders_nothing(self):
        """DEF053's shape: never a header over an absence."""
        assert capital_return_line(None, None, None, None) is None

    def test_the_ratio_is_dropped_but_the_dollars_survive(self):
        """Withholding the ratio must not withhold the fact.

        FCF that is absent or non-positive makes the percentage meaningless, but
        the amount returned is still a measured fact and still renders.
        """
        line = capital_return_line(8617, 5910, 2707, None)
        assert "$8,617M" in line
        assert "of TTM FCF" not in line


class TestTheStaleDisclaimer:
    """The dividend line declared buybacks unavailable two lines after giving them."""

    def test_buybacks_are_no_longer_disclaimed_as_unavailable(self):
        """It had been wrong since CR145 Tier D added the cash-flow call.

        This matters because of how hard the rest of the sheet works to police
        available-vs-not. The Room sheet states `Buybacks (LIVE): $5,910M
        repurchased` and then, two lines later, said buybacks were "not
        available, not claimed". An agent that believed the disclaimer would
        suppress a real number it had been handed — the mirror image of the
        fabrication the disclaimer exists to prevent.
        """
        line = dividend_line(1.4, None, None, None, live=True)
        assert "buybacks" not in line.lower(), (
            "the dividend line must not declare buybacks unavailable — the sheet "
            "states them, and CR145 Tier D is what made that true"
        )

    def test_m_and_a_is_still_disclaimed(self):
        """Half the disclaimer is still true and must survive: no field backs M&A."""
        line = dividend_line(1.4, None, None, None, live=True)
        assert "M&A: not available, not claimed" in line

    def test_a_non_payer_still_gets_no_line_at_all(self):
        """DEF053 again — the disclaimer must not become a reason to render."""
        assert dividend_line(None, None, None, None, live=True) is None


class TestProvenanceRegistration:
    """CR104: a field with no recorded provenance renders as nothing at all.

    Computing these three and forgetting to register them would be the CR040
    silent-dark shape — the work happens on every convene and reaches no agent.
    """

    @pytest.mark.parametrize(
        "field",
        ["dividends_paid_ttm", "capital_return_ttm", "capital_return_pct_fcf"],
    )
    def test_the_new_fields_are_registered_as_optional_live(self, field):
        assert field in _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS, (
            f"{field} is computed but unregistered, so the renderer drops it"
        )


class TestBothSurfacesRenderIt:
    """The 1-on-1 sheet and the Room sheet must not disagree about one company.

    Same parity rule CR166 Tier B and CR179 Leg 3 state: the same analyst must
    not see a poorer sheet on one surface than the other.
    """

    def test_both_render_sites_call_the_builder(self):
        import inspect

        from app.services import fundamentals, room_prompts

        assert "capital_return_line(" in inspect.getsource(fundamentals), (
            "the 1-on-1 fact sheet does not render the line"
        )
        assert "capital_return_line(" in inspect.getsource(room_prompts), (
            "the Room fact sheet does not render the line"
        )
