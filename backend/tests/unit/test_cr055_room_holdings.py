"""CR055 — every Room agent must be shown the user's REAL simulated holdings.

A brand-new user convened the Room for SCHD; the Trader refused to buy, asserting
the user "already holds a 10–15% allocation" — the user held nothing. Root cause:
the only holdings block was gated on a linked Alpaca paper account, so a new user
got ZERO holdings data (silence), and the model fabricated a position from the only
number on the table (the researchers' proposed 10–15% size).

These guards pin the fix:
  1. The sim-sourced holdings block is ALWAYS present — a no-position user gets an
     explicit "you hold 0% of <TICKER> / no open positions", never silence.
  2. A sim-fetch failure degrades LOUDLY ("Portfolio unavailable this run."), never
     to an omitted/silent block (CR040 / the exact DEF059-class silence this closes).
  3. For a user who DOES hold the ticker, the shown weight == what sim holds.
  4. Bull / Bear / Research-Manager prompts carry the enforced single-name cap
     (CR046 M03), so a researcher can't propose 10–15% when the system enforces 3.0%.
  5. long_only is stated plainly to Room agents (no short/negative positions; it does
     NOT forbid buying/adding/holding), killing the "duplicate entries" misread.
"""

from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.schemas.trade import OrderType, Side
from app.services.agent_prompts import build_agent_prompt
from app.services.room_prompts import build_room_messages
from app.services.room_runner import _build_sim_holdings_block, _compose_portfolio_block
from app.services.sim_engine import get_sim_engine

_SYNTH_PROFILE = {"data_source": "synthetic"}
_RESEARCHERS = (
    AgentId.BULL_RESEARCHER,
    AgentId.BEAR_RESEARCHER,
    AgentId.RESEARCH_MANAGER,
)


# ── 1. Always-present block; the no-position case is explicit, never silent ──


def test_no_position_user_gets_explicit_zero_block_never_silence():
    block = _build_sim_holdings_block(uuid4(), "SCHD")
    assert block.strip(), "holdings block must never be empty for a real user"
    assert "YOUR SIMULATED PORTFOLIO" in block
    # The exact anti-hallucination statement: nothing held, any BUY is NEW.
    assert "0% of SCHD" in block
    assert "none" in block.lower()
    assert "NEW position" in block


def test_block_flows_into_every_agents_room_prompt():
    """The block is injected through build_agent_prompt's snapshot slot, so it lands
    in every agent's system prompt — analysts, researchers, trader, PM alike."""
    block = _build_sim_holdings_block(uuid4(), "SCHD")
    for agent_id in (
        AgentId.FUNDAMENTALS_ANALYST,
        AgentId.BULL_RESEARCHER,
        AgentId.TRADER,
        AgentId.PORTFOLIO_MANAGER,
    ):
        system_prompt, _ = build_room_messages(
            agent_id=agent_id,
            mandate=_mandate(),
            user_id=uuid4(),
            ticker="SCHD",
            profile=_SYNTH_PROFILE,
            transcript=[],
            portfolio_snapshot=block,
        )
        assert "YOUR SIMULATED PORTFOLIO" in system_prompt
        assert "0% of SCHD" in system_prompt


# ── 2. Degrade LOUDLY on fetch failure — never silence (the exact bug) ──


def test_fetch_failure_renders_loud_line_not_silence(monkeypatch):
    def _boom():
        raise RuntimeError("sim engine unreachable")

    monkeypatch.setattr("app.services.room_runner.get_sim_engine", _boom)
    block = _build_sim_holdings_block(uuid4(), "SCHD")
    assert block.strip(), "failure path must still render a block, not nothing"
    assert "Portfolio unavailable this run." in block
    # And it must still warn against assuming a holding.
    assert "SCHD" in block


# ── 3. Held user — shown weight == what sim holds ──


def test_held_user_shows_weight_matching_sim():
    sim = get_sim_engine()
    user_id = uuid4()
    price = sim.current_price("AAPL")
    result = sim.submit(
        user_id=user_id,
        ticker="AAPL",
        side=Side.BUY,
        quantity=5,
        mandate=_mandate(),
        order_type=OrderType.MARKET,
        stop=round(price * 0.94, 2),
        target=round(price * 1.13, 2),
        horizon_days=30,
    )
    assert result.accepted, "seed trade must fill for this test to mean anything"

    # What sim actually holds, computed independently (deterministic mock walk).
    total = sim.total_value(user_id)
    mark = sim.current_marks(["AAPL"])["AAPL"]
    expected_weight = 5 * mark / total * 100

    block = _build_sim_holdings_block(user_id, "AAPL")
    assert "AAPL" in block
    # shown == held, asserted against the SPECIFIC "You currently hold X% of <ticker>" sentence —
    # the literal replacement for the statement that failed in the SCHD incident — NOT a loose
    # substring a per-position line could satisfy (auditor CR055 Finding 1, run-47: a bare
    # `f"{w:.1f}%" in block` passed even when that sentence's own formula was mutated ×1.5,
    # because the untouched per-position line shared the value).
    assert f"You currently hold {expected_weight:.1f}% of AAPL" in block
    # the per-position line renders the unrealised P&L field (Finding 2, display-coverage gap).
    assert "unrealised" in block


def test_held_other_ticker_still_states_zero_for_discussed_name():
    sim = get_sim_engine()
    user_id = uuid4()
    price = sim.current_price("AAPL")
    sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=5,
        mandate=_mandate(), order_type=OrderType.MARKET,
        stop=round(price * 0.94, 2), target=round(price * 1.13, 2), horizon_days=30,
    )
    block = _build_sim_holdings_block(user_id, "SCHD")
    assert "AAPL" in block  # the held name is listed
    assert "0% of SCHD" in block  # but the DISCUSSED name is explicitly zero


def test_compose_portfolio_block_precedence_emits_one_authoritative_block():
    """sim is the portfolio of record and comes first; a linked Alpaca account is a labelled
    overlay BELOW it, never a competing 'YOUR PORTFOLIO'; None leaves the sim block unchanged.
    (auditor CR055 Finding 2, run-47 — the precedence claim had zero coverage.)"""
    sim_block = (
        "─── YOUR SIMULATED PORTFOLIO (AMI's portfolio of record — simulation-only) ───\n"
        "Cash: $100,000.00 | Portfolio value: $100,000.00"
    )
    # None → sim block returned byte-unchanged (no overlay, no mutation).
    assert _compose_portfolio_block(sim_block, None) == sim_block
    # Linked → sim first, Alpaca folded in below under the "NOT AMI's portfolio of record" label.
    alpaca = "AAPL x10 @ $150.00 (external paper account)"
    composed = _compose_portfolio_block(sim_block, alpaca)
    assert composed.startswith(sim_block)  # sim is authoritative + first
    assert alpaca in composed  # the overlay content is present
    assert "NOT AMI's" in composed  # labelled as an overlay, not a portfolio of record
    # exactly ONE portfolio-of-record block — Alpaca is NOT emitted as a second "YOUR ... PORTFOLIO".
    assert composed.count("YOUR SIMULATED PORTFOLIO") == 1


# ── 4. Researcher size cap (M03 coherence) ──


@pytest.mark.parametrize("agent_id", _RESEARCHERS)
def test_researcher_prompts_carry_enforced_size_cap(agent_id):
    """Bull / Bear / Research-Manager must see the enforced 3.0% single-name cap for
    risk_score=3 — so they cannot propose the 10–15% that seeded the hallucination."""
    system_prompt, _ = build_room_messages(
        agent_id=agent_id,
        mandate=_mandate(),
        user_id=None,
        ticker="AAPL",
        profile=_SYNTH_PROFILE,
        transcript=[],
    )
    assert "3.0%" in system_prompt
    assert "cap" in system_prompt.lower()
    assert "risk_score=3" in system_prompt


def test_analyst_prompt_does_not_carry_researcher_cap_line():
    """The cap line is targeted at the sizing agents (researchers); a pure analyst
    that never proposes a size should not inherit it."""
    system_prompt, _ = build_room_messages(
        agent_id=AgentId.NEWS_ANALYST,
        mandate=_mandate(),
        user_id=None,
        ticker="AAPL",
        profile=_SYNTH_PROFILE,
        transcript=[],
    )
    assert "single-name cap of 3.0%" not in system_prompt


# ── 5. long_only stated plainly ──


def test_long_only_is_stated_plainly_to_room_agents():
    system_prompt, _ = build_room_messages(
        agent_id=AgentId.TRADER,
        mandate=_mandate(long_only=True),
        user_id=None,
        ticker="AAPL",
        profile=_SYNTH_PROFILE,
        transcript=[],
    )
    assert "does NOT forbid" in system_prompt
    assert "no short" in system_prompt.lower()


def test_long_only_clarification_absent_when_shorts_allowed():
    system_prompt, _ = build_room_messages(
        agent_id=AgentId.TRADER,
        mandate=_mandate(long_only=False),
        user_id=None,
        ticker="AAPL",
        profile=_SYNTH_PROFILE,
        transcript=[],
    )
    assert "does NOT forbid" not in system_prompt


# ── 6. build_agent_prompt snapshot slot appends / omits correctly ──


def test_build_agent_prompt_appends_portfolio_snapshot():
    block = "─── YOUR SIMULATED PORTFOLIO ───\nsentinel-portfolio-line\n───"
    full = build_agent_prompt(
        AgentId.TRADER, _mandate(), portfolio_snapshot=block
    )
    assert "sentinel-portfolio-line" in full


def test_build_agent_prompt_omits_portfolio_snapshot_when_none():
    full = build_agent_prompt(AgentId.TRADER, _mandate(), portfolio_snapshot=None)
    assert "YOUR SIMULATED PORTFOLIO" not in full


# ── 7. Structural: the runner passes the block to BOTH build_room_messages sites ──


def test_runner_injects_portfolio_snapshot_at_every_call_site():
    """Guards the wiring so the block cannot silently stop reaching agents: every
    build_room_messages(...) call in room_runner must pass portfolio_snapshot=."""
    from app.services import room_runner

    # Anchor to the module file, not cwd — the suite is run from both repo root and
    # backend/, and a cwd-relative path only resolves from backend/.
    src = Path(room_runner.__file__).read_text(encoding="utf-8")
    call_sites = re.findall(r"build_room_messages\(\s*([^)]*?)\)", src, re.DOTALL)
    assert len(call_sites) >= 2, f"expected >=2 call sites, found {len(call_sites)}"
    for i, args in enumerate(call_sites):
        assert "portfolio_snapshot=" in args, (
            f"build_room_messages call site #{i + 1} does not pass "
            f"portfolio_snapshot= — the holdings block would go dark for that path"
        )


# ── helpers ──


def _mandate(*, long_only: bool = True):
    from datetime import datetime

    from app.schemas.mandate import (
        Compliance,
        DailyBriefing,
        Horizon,
        LearningStyle,
        Mandate,
        Path as MandatePath,
        Plan,
        PrimaryGoal,
        RiskComponents,
    )

    return Mandate(
        user_id=uuid4(),
        version=1,
        display_name="Test User",
        locale="en",
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=None,
        path=MandatePath.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3
        ),
        risk_quotes=[],
        max_drawdown_pct=30,
        compliance=Compliance(long_only=long_only, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        daily_briefing=DailyBriefing(enabled=False),
        plan=Plan.TRADER,
        trial_expires_at=None,
        credit_balance=150,
        created_at=datetime(2026, 5, 11),
        updated_at=datetime(2026, 5, 11),
    )
