"""CR219 R36 — ATR(14), Execution/Risk lanes only.

The Trader currently sets stops with no volatility measure at all. Computed
from the daily bars `compute_technicals` already fetches (`_HISTORY_PERIOD =
"3m"`, ~65 candles — comfortably clears the 15-bar minimum ATR(14) needs;
verified against that comment before relying on it, not assumed). Gated
NARROWER than the technicals domain generally: the Market Analyst already
sees the range/trend/volume block this sits beside, but has no stop-sizing
job, so ATR is withheld from it specifically.
"""

from __future__ import annotations

from app.schemas import AgentId
from app.services.room_prompts import _ATR_LANE_AGENTS, _atr_line, _format_profile
from app.services.room_runner import LiveDataState


class TestTheLineItself:
    def test_a_value_renders(self):
        line = _atr_line({"atr14": 4.21})
        assert "$4.21" in line
        assert "ATR(14)" in line

    def test_no_value_renders_nothing(self):
        assert _atr_line({"atr14": None}) is None
        assert _atr_line({}) is None


class TestTheLaneGate:
    """Execution Desk (Trader) and Risk Officer only — not the Market
    Analyst, which shares the technicals domain but has no stop-sizing job."""

    def test_trader_and_risk_officer_are_in_the_lane(self):
        assert AgentId.TRADER in _ATR_LANE_AGENTS
        assert AgentId.RISK_OFFICER in _ATR_LANE_AGENTS

    def test_market_analyst_is_not(self):
        assert AgentId.MARKET_ANALYST not in _ATR_LANE_AGENTS

    def test_no_other_agent_is_in_the_lane(self):
        """Exhaustive, not just the two negative spot-checks above — an
        accidental future addition here is exactly the kind of quiet
        capability leak this WP's own guard mechanism exists to catch."""
        assert _ATR_LANE_AGENTS == frozenset({AgentId.TRADER, AgentId.RISK_OFFICER})


def _live_profile(atr14: float | None = 4.21) -> dict:
    return {
        "ticker": "TEST",
        "field_state": {"technicals": LiveDataState.LIVE.value},
        "rsi": 50, "rsi_tone": "neutral", "trend": "uptrend",
        "support": 90.0, "breakout": 110.0, "last_close": 100.0,
        "sma_short": 99.0, "sma_long": 95.0, "volume_tone": "in-line",
        "volume_ratio": 1.0, "return_period_pct": 1.0, "period_candles": 63,
        "atr14": atr14,
    }


class TestTheRenderedSheetPerAgent:
    """End-to-end through `_format_profile` — the actual acceptance
    question, not just the two helper functions in isolation."""

    def test_trader_sees_the_atr_line(self):
        sheet = _format_profile(_live_profile(), AgentId.TRADER)
        assert "ATR(14)" in sheet
        assert "$4.21" in sheet

    def test_risk_officer_sees_the_atr_line(self):
        sheet = _format_profile(_live_profile(), AgentId.RISK_OFFICER)
        assert "ATR(14)" in sheet

    def test_market_analyst_does_not_see_it(self):
        """The Market Analyst's lane includes technicals generally (it
        already gets RSI/trend/support/breakout on this exact sheet) — ATR
        specifically must still be absent."""
        sheet = _format_profile(_live_profile(), AgentId.MARKET_ANALYST)
        assert "ATR(14)" not in sheet
        # Sanity: prove the rest of the technicals block DID render for this
        # agent, so an absent ATR line is the lane gate working, not the
        # whole block failing to render for an unrelated reason.
        assert "RSI:" in sheet

    def test_fundamentals_analyst_does_not_see_it(self):
        """A different domain firewall entirely (fundamentals lane, no
        technicals at all) — ATR must be absent for the same underlying
        reason `_in_lane("technicals")` already withholds RSI/trend here,
        and the lane gate must not accidentally punch through it."""
        sheet = _format_profile(_live_profile(), AgentId.FUNDAMENTALS_ANALYST)
        assert "ATR(14)" not in sheet

    def test_full_sheet_agent_other_than_trader_or_risk_officer_does_not_see_it(self):
        """The PM is a full-sheet agent (absent from `_AGENT_LANES`, so it
        satisfies `_in_lane("technicals")`) but has no stop-sizing job —
        the narrower `_ATR_LANE_AGENTS` gate must still exclude it."""
        sheet = _format_profile(_live_profile(), AgentId.PORTFOLIO_MANAGER)
        assert "ATR(14)" not in sheet
        assert "RSI:" in sheet  # the rest of the technicals block did render

    def test_none_agent_id_does_not_see_it(self):
        """`agent_id=None` is the "no lane filtering" caller (non-Room
        surfaces, hand-built fixtures) — `agent_id in _ATR_LANE_AGENTS` is
        False for `None`, so this must degrade to absent, not to "show
        everything" the way the domain-level `_in_lane` gate does."""
        sheet = _format_profile(_live_profile())
        assert "ATR(14)" not in sheet

    def test_absent_atr_value_renders_nothing_even_in_the_lane(self):
        """A trader in the right lane with no ATR value (a real technicals
        fetch that, for whatever reason, produced no ATR) still gets an
        honest absence, never a fabricated figure."""
        sheet = _format_profile(_live_profile(atr14=None), AgentId.TRADER)
        assert "ATR(14)" not in sheet


class TestOneOnOneSurfaceDoesNotRenderIt:
    """`build_technicals_context_block` is Market-Analyst-only on the 1-on-1
    path (its own docstring says so, and `agent_runner.py` gates the call
    site on `agent_id == AgentId.MARKET_ANALYST`) — there is no Trader or
    Risk Officer 1-on-1 chat surface reaching real technicals at all, so
    ATR correctly does not render there. This is not an oversight; it is
    verified here so a future change to that surface's audience is caught
    if it silently starts leaking ATR to the wrong role."""

    def test_the_1_on_1_technicals_block_has_no_atr_line(self):
        import inspect

        from app.services import technicals

        source = inspect.getsource(technicals.build_technicals_context_block)
        assert "atr14" not in source
        assert "ATR" not in source

    def test_the_1_on_1_call_site_is_market_analyst_only(self):
        import inspect

        from app.services import agent_runner

        source = inspect.getsource(agent_runner)
        # The FIRST occurrence is the module's own `from ... import
        # build_technicals_context_block` line; the invocation
        # (`asyncio.to_thread(build_technicals_context_block, t)`, a bare
        # reference with no immediately-following paren) is the SECOND —
        # find that one specifically, not the import.
        first = source.index("build_technicals_context_block")
        idx = source.index("build_technicals_context_block", first + 1)
        # The gating `if agent_id == AgentId.MARKET_ANALYST:` sits a few
        # lines above the call in agent_runner.py — search the preceding
        # window rather than the whole file, so this doesn't pass by
        # accident if some OTHER unrelated Market-Analyst-only gate exists
        # elsewhere in the module.
        window = source[max(0, idx - 400):idx]
        assert "AgentId.MARKET_ANALYST" in window
