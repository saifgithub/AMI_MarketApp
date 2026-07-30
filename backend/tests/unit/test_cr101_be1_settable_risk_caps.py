"""CR101-BE1 — the sector-concentration and single-name caps become settable.

Covers acceptance criteria 3-6 from the lane assign
(orchestration/dispatch/lanes/CR101-BE1.assign.md); criteria 1/2 (the nested-merge
fix + DEF062 survival) live in test_mandate_store.py next to the store they patch.

  3. Both `sector_cap_pct` and `single_name_cap_pct` are settable via PATCH and
     ENFORCED — the floor's block moves with the stored value.
  4. Migration proof (the criterion read first): for every
     concentration_tolerance x risk_score (1-5 each), the post-CR101 enforced cap
     for a mandate with NO override — i.e. every existing stored snapshot, which
     has no such key at all — equals what main enforced at 73a25c7f before this
     CR. Pinned against the actual pre-CR101 numbers, not this CR's own tables,
     so a regression in either can't mark itself green.
  5. Both caps appear in the agent overlay, in their own units, interpolated from
     the canonical resolver rather than a literal.
  6. A guard test enumerating every enforced-limit field's four legs (enforced /
     disclosed in its own units / disclosed in the agent overlay / settable) —
     "no third state", the invariant CR101 exists to hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.agents.overlay_generator import _max_position_pct, _sector_cap_pct, generate_overlay
from app.agents.safety_floor import check_mandate_compliance, single_name_cap_pct
from app.schemas import AgentId, Mandate, RiskComponents
from app.schemas.trade import Holding, OrderType, ProposedTrade, Side
from app.services.mandate_store import MandateStore
from app.services.sector_allocation import OTHER, sector_concentration_cap
from app.trading_math.sizing import risk_tier_cap


@dataclass
class _H:
    ticker: str
    quantity: float


_SECTORS = {"AAPL": "Technology", "MSFT": "Technology", "JPM": "Financial Services", "XOM": "Energy"}


class _Map:
    def sector(self, ticker: str) -> str:
        return _SECTORS.get(str(ticker).upper(), OTHER)


def _sector_breach_check(mandate: Mandate, *, buy_value: float):
    """Tech 30% / FS 30% / Energy 40% book ($10k invested); proposed BUY adds
    Tech at $100/share. Mirrors test_cr026_sector_allocation.py's `_breach_check`.

    CR129/DEF187: pins a permissive single-name cap — this file's sector-cap
    tests deliberately buy 4.8-19% of the book in one name, which the
    risk-tier single-name preset (~3%) would otherwise also (and irrelevantly)
    reject before the sector check is ever reached."""
    holdings = [_H("AAPL", 30), _H("JPM", 30), _H("XOM", 40)]
    quotes = {"AAPL": 100.0, "JPM": 100.0, "XOM": 100.0}
    proposed = ProposedTrade(ticker="MSFT", side=Side.BUY, quantity=buy_value / 100.0, limit_price=100.0)
    return check_mandate_compliance(
        proposed, portfolio_value=10_000.0, current_drawdown_pct=0.0,
        mandate=mandate.model_copy(update={"single_name_cap_pct": 100.0}),
        holdings=holdings, quotes=quotes, sector_map=_Map(),
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )


# ── acceptance 3: settable + enforced ──────────────────────────────────────


def test_sector_cap_settable_and_the_floor_block_moves_with_it(base_mandate: Mandate):
    # Buying $500 MSFT (Tech) -> Tech 3500 of 10500 = 33.3%.
    default_result = _sector_breach_check(base_mandate, buy_value=500.0)
    assert default_result.passed  # 33.3% < the 40% default (tolerance=3)

    tightened = base_mandate.model_copy(update={"sector_cap_pct": 20.0})
    tight_result = _sector_breach_check(tightened, buy_value=500.0)
    assert not tight_result.passed  # 33.3% > the explicit 20% override
    assert tight_result.blocked_by == "compliance"
    assert any("sector-concentration limit" in v.lower() for v in tight_result.violations)


def test_single_name_cap_settable_and_the_floor_block_moves_with_it(base_mandate: Mandate):
    proposed = ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET)
    quotes = {"AAPL": 100.0}
    ctx = dict(last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0)
    # $1000 of a $10,000 book = 10%.
    # CR129 (closing DEF187): unset now resolves to the risk-tier preset
    # (3.0% at risk_score=3), not the pre-CR129 flat 50% backstop — so this
    # 10% buy is now ALSO blocked with no override, the inverse of what
    # this test asserted before CR129.
    default_result = check_mandate_compliance(
        proposed, portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=base_mandate,
        holdings=[], quotes=quotes, **ctx,
    )
    assert not default_result.passed
    assert default_result.blocked_by == "concentration"

    loosened = base_mandate.model_copy(update={"single_name_cap_pct": 50.0})
    loose_result = check_mandate_compliance(
        proposed, portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=loosened,
        holdings=[], quotes=quotes, **ctx,
    )
    assert loose_result.passed  # 10% < the explicit 50% override

    tightened = base_mandate.model_copy(update={"single_name_cap_pct": 5.0})
    tight_result = check_mandate_compliance(
        proposed, portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=tightened,
        holdings=[], quotes=quotes, **ctx,
    )
    assert not tight_result.passed  # 10% > the explicit 5% override
    assert tight_result.blocked_by == "concentration"
    assert any("single-name cap" in v for v in tight_result.violations)


def test_both_caps_persist_and_enforce_through_a_real_patch_round_trip():
    """The settable leg end-to-end through the real store, not just model_copy."""
    store = MandateStore()
    user_id = uuid4()
    updated = store.patch(user_id, {"sector_cap_pct": 22.0, "single_name_cap_pct": 6.0})
    assert updated.sector_cap_pct == 22.0
    assert updated.single_name_cap_pct == 6.0

    reloaded = store.get_or_default(user_id)
    assert sector_concentration_cap(reloaded) == pytest.approx(0.22)
    assert single_name_cap_pct(reloaded) == 6.0


# ── acceptance 2/4: the INVERTED migration proof — the criterion read first ──
#
# CR101-BE1 acceptance 4 proved nobody's enforcement changed on deploy. CR129
# proves the opposite, by explicit authorisation (Saiful, 13 live alpha
# mandates — see docs/forward_planning/CR129_risk_limits_from_risk_tolerance/
# README.md, "The decision this CR carries"): for a pre-CR129 stored snapshot
# (the two BE1 keys absent from the dict entirely, not merely None in memory),
# the single-name cap now enforces the NEW risk-tier preset, not the old flat
# 50% backstop. Sector cap is untouched by CR129 (it already resolved through
# the SAME preset-fallback pattern pre-CR129) and stays pinned to prove that.
_PRE_CR101_SECTOR_CAP_BY_TOLERANCE = {1: 0.25, 2: 0.30, 3: 0.40, 4: 0.50, 5: 0.60}
_PRE_CR129_SINGLE_NAME_CAP_PCT = 50.0


@pytest.mark.parametrize("concentration_tolerance", [1, 2, 3, 4, 5])
@pytest.mark.parametrize("risk_score", [1, 2, 3, 4, 5])
def test_migration_every_risk_score_now_enforces_the_new_single_name_value(
    risk_score: int, concentration_tolerance: int, base_mandate: Mandate
):
    """CR129 acceptance 2 (read first): for every risk_score 1-5, a mandate
    with NO explicit single_name_cap_pct override — the real shape of every
    one of the 13 live alpha mandates — now enforces the DOCUMENTED risk-tier
    value, never the old 50% backstop. Sector cap (untouched by CR129) stays
    pinned to its pre-existing value as the control."""
    mandate = base_mandate.model_copy(update={
        "risk_score": risk_score,
        "risk_components": RiskComponents(
            drawdown_response=3, regret_asymmetry=0,
            concentration_tolerance=concentration_tolerance,
        ),
    })
    raw = mandate.model_dump(mode="json")
    del raw["sector_cap_pct"]
    del raw["single_name_cap_pct"]
    loaded = Mandate.model_validate(raw)

    assert sector_concentration_cap(loaded) == pytest.approx(
        _PRE_CR101_SECTOR_CAP_BY_TOLERANCE[concentration_tolerance]
    )
    assert single_name_cap_pct(loaded) == risk_tier_cap(risk_score)
    assert single_name_cap_pct(loaded) != _PRE_CR129_SINGLE_NAME_CAP_PCT


# ── acceptance 5: both caps in the overlay, in their own units, interpolated ─


def test_overlay_discloses_both_caps_interpolated_not_literal(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.MARKET_ANALYST, base_mandate)
    assert f"{_max_position_pct(base_mandate)}% of portfolio in any one name" in overlay
    assert f"{_sector_cap_pct(base_mandate)}% of portfolio in any one" in overlay

    # Interpolated from the resolver, not a hardcoded literal: an explicit
    # override changes what's shown.
    overridden = base_mandate.model_copy(
        update={"single_name_cap_pct": 7.0, "sector_cap_pct": 33.0}
    )
    overlay2 = generate_overlay(AgentId.MARKET_ANALYST, overridden)
    assert "7.0% of portfolio in any one name" in overlay2
    assert "33.0% of portfolio in any one" in overlay2


# ── acceptance 6: the four-leg invariant, enumerated ───────────────────────


def test_every_enforced_limit_field_is_enforced_disclosed_and_settable(base_mandate: Mandate):
    """A Mandate field feeding an enforced limit is (a) enforced, (b) disclosed
    in its own units, (c) disclosed in the agent overlay, (d) settable — or it is
    deleted. No third state. Enumerates the three numeric enforced-limit fields
    this repo has today; a future field joins this list or fails the review that
    should have caught it missing here.

    CR101-BE2 disclosure: this list is hand-enumerated, not derived from the
    schema, so a new field does NOT automatically join it — the guard's own
    P12-shaped gap the BE2 assign asked to be named rather than silently
    inherited. Fixing it properly (auto-discovering every "enforced limit"
    field) needs a marker distinguishing them from ordinary Mandate fields,
    which doesn't exist yet; out of scope here, flagged for a DEF in the
    CR101-BE2 hand-off. The four new limits are added as five explicit blocks
    below instead (post_loss_cooldown_hours, max_open_positions,
    max_trades_per_day, max_trades_per_week, max_open_risk_pct)."""
    store = MandateStore()

    # -- max_drawdown_pct ----------------------------------------------------
    dd_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=base_mandate.max_drawdown_pct,
        mandate=base_mandate, holdings=[], quotes={"AAPL": 100.0},
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not dd_result.passed and any("drawdown" in v for v in dd_result.violations)  # (a)
    assert f"{base_mandate.max_drawdown_pct}%" in generate_overlay(AgentId.AGGRESSIVE_DEBATOR, base_mandate)  # (c)
    dd_user = uuid4()
    dd_patched = store.patch(dd_user, {"max_drawdown_pct": 20})
    assert dd_patched.max_drawdown_pct == 20  # (d) settable
    assert store.get_or_default(dd_user).max_drawdown_pct == 20  # (b) disclosed verbatim, own units, on read-back

    # -- sector_cap_pct --------------------------------------------------------
    tight_sector = base_mandate.model_copy(update={"sector_cap_pct": 20.0})
    sector_result = _sector_breach_check(tight_sector, buy_value=500.0)
    assert not sector_result.passed and sector_result.blocked_by == "compliance"  # (a)
    assert sector_concentration_cap(tight_sector) == pytest.approx(0.20)  # (b) own units (fraction)
    assert f"{_sector_cap_pct(tight_sector)}% of portfolio" in generate_overlay(AgentId.MARKET_ANALYST, tight_sector)  # (c)
    assert store.patch(uuid4(), {"sector_cap_pct": 45.0}).sector_cap_pct == 45.0  # (d)

    # -- single_name_cap_pct -----------------------------------------------------
    tight_single = base_mandate.model_copy(update={"single_name_cap_pct": 5.0})
    single_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=tight_single,
        holdings=[], quotes={"AAPL": 100.0},
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not single_result.passed and any("single-name cap" in v for v in single_result.violations)  # (a)
    assert single_name_cap_pct(tight_single) == 5.0  # (b) own units
    assert (
        f"{_max_position_pct(tight_single)}% of portfolio in any one name"
        in generate_overlay(AgentId.TRADER, tight_single)
    )  # (c)
    assert store.patch(uuid4(), {"single_name_cap_pct": 2.0}).single_name_cap_pct == 2.0  # (d)

    # -- post_loss_cooldown_hours (CR101-BE2) -------------------------------
    from datetime import datetime, timedelta, timezone as _tz
    cooldown_mandate = base_mandate.model_copy(update={"post_loss_cooldown_hours": 24.0})
    now = datetime(2026, 7, 30, 12, 0, tzinfo=_tz.utc)
    cooldown_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=cooldown_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=now, last_loss_closed_at=now - timedelta(hours=1),
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not cooldown_result.passed and cooldown_result.blocked_by == "cooldown"  # (a)
    assert cooldown_mandate.post_loss_cooldown_hours == 24.0  # (b) own units (hours)
    assert "24.0h after a stop-out" in generate_overlay(AgentId.PORTFOLIO_MANAGER, cooldown_mandate)  # (c)
    assert store.patch(uuid4(), {"post_loss_cooldown_hours": 6.0}).post_loss_cooldown_hours == 6.0  # (d)

    # -- max_open_positions (CR101-BE2) --------------------------------------
    positions_mandate = base_mandate.model_copy(update={"max_open_positions": 1})
    positions_result = check_mandate_compliance(
        ProposedTrade(ticker="MSFT", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=positions_mandate,
        holdings=[Holding(ticker="AAPL", quantity=1, avg_cost=100.0, opened_at=now)],
        quotes={"AAPL": 100.0, "MSFT": 100.0}, now=now, last_loss_closed_at=None,
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not positions_result.passed and positions_result.blocked_by == "max_open_positions"  # (a)
    assert positions_mandate.max_open_positions == 1  # (b) own units (count)
    assert "Max open positions: 1" in generate_overlay(AgentId.PORTFOLIO_MANAGER, positions_mandate)  # (c)
    assert store.patch(uuid4(), {"max_open_positions": 5}).max_open_positions == 5  # (d)

    # -- max_trades_per_day / max_trades_per_week (CR101-BE2) ----------------
    day_mandate = base_mandate.model_copy(update={"max_trades_per_day": 1})
    day_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=day_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=now, trade_open_timestamps=[now],
        last_loss_closed_at=None, existing_open_risk_pct=0.0,
    )
    assert not day_result.passed and day_result.blocked_by == "over_trading"  # (a)
    assert day_mandate.max_trades_per_day == 1  # (b) own units (count/day)
    assert "1 per day" in generate_overlay(AgentId.PORTFOLIO_MANAGER, day_mandate)  # (c)
    assert store.patch(uuid4(), {"max_trades_per_day": 3}).max_trades_per_day == 3  # (d)

    week_mandate = base_mandate.model_copy(update={"max_trades_per_week": 1})
    week_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=week_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=now, trade_open_timestamps=[now],
        last_loss_closed_at=None, existing_open_risk_pct=0.0,
    )
    assert not week_result.passed and week_result.blocked_by == "over_trading"  # (a)
    assert week_mandate.max_trades_per_week == 1  # (b) own units (count/week)
    assert "1 per week" in generate_overlay(AgentId.PORTFOLIO_MANAGER, week_mandate)  # (c)
    assert store.patch(uuid4(), {"max_trades_per_week": 8}).max_trades_per_week == 8  # (d)

    # -- max_open_risk_pct (CR101-BE2) ---------------------------------------
    # CR129/DEF187: permissive single-name cap — $1000/$10,000 = 10% is over
    # the ~3% risk-tier preset, which isn't this sub-block's point.
    risk_mandate = base_mandate.model_copy(
        update={"max_open_risk_pct": 0.5, "single_name_cap_pct": 100.0}
    )
    risk_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=risk_mandate,
        holdings=[], quotes={"AAPL": 100.0}, proposed_stop=90.0,
        last_loss_closed_at=None, trade_open_timestamps=[],
    )
    assert not risk_result.passed and risk_result.blocked_by == "open_risk"  # (a)
    assert risk_mandate.max_open_risk_pct == 0.5  # (b) own units (percentage points)
    assert "9.5%" not in generate_overlay(AgentId.PORTFOLIO_MANAGER, risk_mandate)
    assert "0.5%" in generate_overlay(AgentId.PORTFOLIO_MANAGER, risk_mandate)  # (c)
    assert store.patch(uuid4(), {"max_open_risk_pct": 4.0}).max_open_risk_pct == 4.0  # (d)
