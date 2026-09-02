"""CR219 R49 — the Chief Investment Officer can finally see the floor that overrides it.

`enforce_safety_floor` deterministically overrides the CIO's verdict on three
limits the CIO's prompt never carried: the post-loss cooldown (safety_floor.py
6c), the over-trading brake (6e) and the total open-risk cap (6f). The CIO
argued for entries the floor then vetoed, and the user read a transcript that
approves against a verdict that blocks.

What this file pins is narrower than "the preview renders", and deliberately so:

1. **The preview is VERDICT-only.** The eleven arguing agents already get the
   raw consumption figures from `_risk_state_block` at every phase; what they
   do not get, and must not, is a statement about a decision only the CIO makes.

2. **Every number matches what the floor will actually decide.** The tests
   below assert the preview's figures against `enforce_safety_floor`'s own
   outcome on the SAME inputs, not against literals. That is the property
   worth having: a preview that renders beautifully and disagrees with the
   floor is worse than no preview, because it teaches the CIO to trust a
   number that is about to be overruled. DEF263 is the precedent — a prompt
   counting trades over a different window than the brake — and its fix was to
   import the brake's own helpers rather than to match its arithmetic by eye.

3. **The three absences stay distinct** (CR040 / DEF059), exactly as
   `_risk_state_block` keeps them: a failed computation says the floor blocks
   on it, an unsupplied one renders nothing, a real value is stated as fact.

The floor itself is unchanged — this is a prompt addition and decides nothing.
`test_the_preview_never_decides_anything` is the standing guard for that.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED, enforce_safety_floor
from app.schemas import AgentId
from app.schemas.room import Verdict, VerdictAction
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import _floor_state_preview, build_room_messages

NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def _mandate(**over):
    return hydrate_coach_mandate({"plan": "trader", "risk_score": 3, **over})


def _prompt(agent_id=AgentId.PORTFOLIO_MANAGER, **risk):
    sp, _ = build_room_messages(
        agent_id=agent_id, mandate=_mandate(), user_id=None, ticker="AAPL",
        profile={"field_state": {}}, transcript=[], **risk,
    )
    return sp


def _floor_verdict(mandate, **kw):
    """What `enforce_safety_floor` actually does with a BUY on these inputs."""
    return enforce_safety_floor(
        llm_verdict=Verdict(
            action=VerdictAction.APPROVE, size_pct=2.0, entry=100.0,
            stop=94.0, target=115.0, reason="test",
        ),
        proposed=ProposedTrade(
            ticker="AAPL", side=Side.BUY, order_type=OrderType.LIMIT,
            quantity=20, limit_price=100.0,
        ),
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
        now=NOW,
        **kw,
    )


# ── the cooldown line ─────────────────────────────────────────────────────────


def test_a_profile_in_cooldown_puts_the_cooldown_line_in_the_pm_prompt():
    """WP08's stated acceptance: profile in cooldown -> the PM prompt says so."""
    sp = _prompt(last_loss_closed_at=datetime.now(timezone.utc) - timedelta(minutes=10))
    assert "IN POST-LOSS COOLDOWN until" in sp
    assert "The floor will BLOCK any BUY until then" in sp
    assert "An APPROVE here will be overridden to PASS" in sp


def test_the_previewed_cooldown_agrees_with_what_the_floor_does():
    """The property, not the wording. A preview that says CLEAR while the floor
    blocks (or the reverse) is the whole defect, re-created one layer up."""
    mandate = _mandate()
    for delta, expect_blocked in ((timedelta(minutes=10), True), (timedelta(days=3), False)):
        last_loss = NOW - delta
        preview = _floor_state_preview(
            mandate, 0.0, last_loss, [], now=NOW,
        )
        verdict = _floor_verdict(
            mandate, last_loss_closed_at=last_loss,
            trade_open_timestamps=[], existing_open_risk_pct=0.0,
        )
        floor_blocked = any("cooldown" in v for v in verdict.violations)
        assert floor_blocked is expect_blocked, verdict.violations
        assert ("IN POST-LOSS COOLDOWN" in preview) is floor_blocked, preview


def test_the_cooldown_hours_are_the_resolved_tier_value_not_the_raw_field():
    """CR129: an unset `post_loss_cooldown_hours` resolves to the risk-tier
    preset and the check is ALWAYS active. A preview reading the raw mandate
    field would render nothing here and imply the check is off."""
    assert _mandate().post_loss_cooldown_hours is None
    preview = _floor_state_preview(_mandate(), 0.0, None, [], now=NOW)
    assert "Post-loss cooldown (1h)" in preview  # risk_score 3 preset
    preview_conservative = _floor_state_preview(
        _mandate(risk_score=1), 0.0, None, [], now=NOW
    )
    assert "Post-loss cooldown (4h)" in preview_conservative


def test_an_explicit_zero_override_turns_the_cooldown_line_off():
    """"Off" is expressible only as an explicit 0 (the Day Trader preset), and a
    check that is off must not be previewed as if it were live."""
    preview = _floor_state_preview(
        _mandate(post_loss_cooldown_hours=0), 0.0, None, [], now=NOW
    )
    assert "cooldown" not in preview.lower()


# ── the over-trading brake ────────────────────────────────────────────────────


def test_the_brake_at_its_cap_is_previewed_as_a_block():
    at_cap = [NOW - timedelta(minutes=m) for m in (5, 10, 15, 20)]  # 4/day cap
    preview = _floor_state_preview(_mandate(), 0.0, None, at_cap, now=NOW)
    assert "OVER-TRADING BRAKE ALREADY AT ITS CAP" in preview
    assert "4/4 today" in preview

    verdict = _floor_verdict(
        _mandate(), last_loss_closed_at=None,
        trade_open_timestamps=at_cap, existing_open_risk_pct=0.0,
    )
    assert any("max trades per day" in v for v in verdict.violations), verdict.violations


def test_headroom_is_previewed_when_the_brake_is_clear():
    preview = _floor_state_preview(
        _mandate(), 0.0, None, [NOW - timedelta(minutes=5)], now=NOW
    )
    assert "1/4 trades today" in preview
    assert "room for 3 more today" in preview
    assert "OVER-TRADING BRAKE ALREADY AT ITS CAP" not in preview


def test_the_two_windows_are_counted_over_the_floors_own_boundaries():
    """DEF263's exact defect, one layer up: a trade opened before the UTC day
    start counts toward the week and not the day, and the preview must split
    them the same way the brake does."""
    yesterday = NOW - timedelta(days=1)
    preview = _floor_state_preview(_mandate(), 0.0, None, [yesterday], now=NOW)
    assert "0/4 trades today" in preview
    assert "1/12 this ISO week" in preview


# ── the open-risk cap ─────────────────────────────────────────────────────────


def test_open_risk_headroom_is_previewed_against_the_resolved_cap():
    """CR129 derives an unset cap from THIS mandate's own `max_drawdown_pct`,
    so it is per-user. risk_score 3 at a 30 pt drawdown cap resolves to 10.5%."""
    mandate = _mandate(max_drawdown_pct=30)
    preview = _floor_state_preview(mandate, 4.0, None, [], now=NOW)
    assert "Open-risk headroom: 6.50 pt" in preview
    assert "4.00% committed of a 10.5% cap" in preview


def test_an_exceeded_open_risk_cap_is_previewed_as_a_block():
    mandate = _mandate(max_drawdown_pct=30)
    preview = _floor_state_preview(mandate, 12.0, None, [], now=NOW)
    assert "OPEN-RISK CAP ALREADY EXCEEDED" in preview

    verdict = _floor_verdict(
        mandate, last_loss_closed_at=None,
        trade_open_timestamps=[], existing_open_risk_pct=12.0,
    )
    assert any("total open risk" in v for v in verdict.violations), verdict.violations


# ── the three absences, kept distinct (CR040 / DEF059) ────────────────────────


def test_a_failed_computation_says_the_floor_blocks_on_it():
    """`CONTEXT_NOT_SUPPLIED` is not zero and not "no prior loss". The floor
    hard-blocks rather than silently skipping (CR101-BE2 round 2), so the
    preview must say the entry is unavailable, never render an all-clear."""
    preview = _floor_state_preview(
        _mandate(), CONTEXT_NOT_SUPPLIED, CONTEXT_NOT_SUPPLIED, None, now=NOW,
    )
    assert "COULD NOT BE READ this run" in preview
    assert "COULD NOT BE COMPUTED this run" in preview
    assert preview.count("BLOCK any BUY") == 3  # cooldown, brake, open risk
    assert "CLEAR" not in preview


def test_an_unsupplied_caller_gets_no_preview_at_all():
    """A caller that passes none of the three kwargs — `prompt_version.py` and
    every non-Room surface — must get nothing.

    This is not cosmetic. On the floor's own contract a `None`
    `trade_open_timestamps` means "the caller did not supply trade history, so
    hard-block" (safety_floor.py 6e), which is true for the Room and false for
    a caller that never had a proposal. Without the gate those surfaces would
    render a preview announcing the floor is blocking a BUY nobody proposed —
    a fabricated alarm, the same class of harm as silence pointed the other
    way, and the wrong fix DEF263 records being tried first on
    `_risk_state_block`.
    """
    assert _floor_state_preview(_mandate(), None, None, None, now=NOW) == ""

    sp, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER, mandate=_mandate(), user_id=None,
        ticker="AAPL", profile={"field_state": {}}, transcript=[],
    )
    assert "Safety-floor pre-check" not in sp


def test_a_none_last_loss_is_a_real_value_not_an_absence():
    """The asymmetry is the floor's, not the preview's. `last_loss_closed_at`
    is the one input whose `None` is a REAL, common state ("never had a loss")
    — which is why `CONTEXT_NOT_SUPPLIED` exists for the absent case at all.
    So a Room caller supplying the other two gets a CLEAR cooldown line, not
    silence and not an alarm."""
    preview = _floor_state_preview(_mandate(), 0.0, None, [], now=NOW)
    assert "Post-loss cooldown (1h): CLEAR — no losing trade on record." in preview


def test_a_real_zero_open_risk_is_stated_as_a_fact():
    preview = _floor_state_preview(_mandate(max_drawdown_pct=30), 0.0, None, [], now=NOW)
    assert "0.00% committed of a 10.5% cap" in preview
    assert "COULD NOT" not in preview


# ── scope: the CIO, and only the CIO ──────────────────────────────────────────


@pytest.mark.parametrize("agent_id", [
    AgentId.NEUTRAL_DEBATOR, AgentId.TRADER, AgentId.RESEARCH_MANAGER,
    AgentId.BULL_RESEARCHER, AgentId.MARKET_ANALYST,
])
def test_only_the_verdict_phase_carries_the_preview(agent_id):
    """The eleven arguing agents keep the consumption figures and lose the
    verdict-shaped statement — the judgement their turn exists to exercise."""
    risk = dict(
        last_loss_closed_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert "Safety-floor pre-check" not in _prompt(agent_id, **risk)
    assert "Safety-floor pre-check" in _prompt(AgentId.PORTFOLIO_MANAGER, **risk)


def test_the_arguing_agents_still_see_the_raw_consumption_figures():
    """The preview must not have displaced `_risk_state_block` for anyone."""
    sp = _prompt(AgentId.NEUTRAL_DEBATOR, existing_open_risk_pct=4.2)
    assert "Open risk already committed: 4.2%" in sp


# ── the preview is not a second enforcement site ──────────────────────────────


def test_the_preview_never_decides_anything():
    """`enforce_safety_floor` stays the sole vetoer (DEF059). This returns a
    string; it has no path to a Verdict, and a floor-blocked state does not
    change what the floor itself returns."""
    mandate = _mandate()
    in_cooldown_at = NOW - timedelta(minutes=10)
    before = _floor_verdict(
        mandate, last_loss_closed_at=in_cooldown_at,
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    _floor_state_preview(mandate, 0.0, in_cooldown_at, [], now=NOW)
    after = _floor_verdict(
        mandate, last_loss_closed_at=in_cooldown_at,
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert before.model_dump() == after.model_dump()
    assert isinstance(_floor_state_preview(mandate, 0.0, in_cooldown_at, [], now=NOW), str)
