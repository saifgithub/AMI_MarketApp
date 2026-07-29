"""CR101-BE2 — the four risk limits that did not exist in ANY form pre-CR101:
post-loss cooldown, max open positions, max trades per day/week, total open-risk
cap. Covers acceptance criteria 1-4, 6-8 from the lane assign
(orchestration/dispatch/lanes/CR101-BE2.assign.md); criterion 5 (the four-leg
guard test) lives in test_cr101_be1_settable_risk_caps.py next to the one it
extends.

Unlike CR101-BE1's two caps, there is no legacy enforced value here — `None`
means "off", not "fall back to a preset" — so acceptance 4 (defaults are
non-binding) is a simpler claim: a mandate with all five fields unset produces
IDENTICAL enforcement to one where the fields don't exist in the dict at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.agents.overlay_generator import generate_overlay
from app.agents.safety_floor import check_holdings_against_mandate, check_mandate_compliance
from app.schemas import AgentId, Mandate
from app.schemas.trade import Holding, OrderType, ProposedTrade, Side
from app.services.mandate_store import MandateStore

_NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)  # a Thursday


@dataclass
class _H:
    ticker: str
    quantity: float
    avg_cost: float = 100.0
    opened_at: datetime = _NOW


def _buy(ticker: str = "AAPL", quantity: float = 1, limit_price: float = 100.0) -> ProposedTrade:
    return ProposedTrade(ticker=ticker, side=Side.BUY, quantity=quantity, limit_price=limit_price)


# ── acceptance 1 + 8: post-loss cooldown ───────────────────────────────────


def test_post_loss_cooldown_blocks_the_next_buy(base_mandate: Mandate):
    mandate = base_mandate.model_copy(update={"post_loss_cooldown_hours": 24.0})
    last_loss = _NOW - timedelta(hours=1)  # 1h ago, cooldown is 24h

    blocked = check_mandate_compliance(
        _buy(), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, last_loss_closed_at=last_loss,
    )
    assert not blocked.passed
    assert blocked.blocked_by == "cooldown"
    assert any("cooldown" in v for v in blocked.violations)

    # Past the cooldown window -> passes.
    old_loss = _NOW - timedelta(hours=25)
    cleared = check_mandate_compliance(
        _buy(), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, last_loss_closed_at=old_loss,
    )
    assert cleared.passed

    # No prior loss at all -> passes regardless of cooldown setting.
    no_loss = check_mandate_compliance(
        _buy(), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, last_loss_closed_at=None,
    )
    assert no_loss.passed

    # A SELL is never blocked by cooldown — it constrains new entries only.
    sell = ProposedTrade(ticker="AAPL", side=Side.SELL, quantity=1)
    sell_result = check_mandate_compliance(
        sell, portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[_H("AAPL", 1)], quotes={"AAPL": 100.0}, now=_NOW, last_loss_closed_at=last_loss,
    )
    assert sell_result.passed


# ── acceptance 1 + 8: max open positions ───────────────────────────────────


def test_max_open_positions_blocks_a_new_ticker_but_not_adding_to_a_held_one(base_mandate: Mandate):
    mandate = base_mandate.model_copy(update={"max_open_positions": 2})
    holdings = [_H("AAPL", 10), _H("MSFT", 5)]

    new_ticker = check_mandate_compliance(
        _buy("GOOG"), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=holdings, quotes={"AAPL": 100.0, "MSFT": 100.0, "GOOG": 100.0},
    )
    assert not new_ticker.passed
    assert new_ticker.blocked_by == "max_open_positions"

    add_to_existing = check_mandate_compliance(
        _buy("AAPL"), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=holdings, quotes={"AAPL": 100.0, "MSFT": 100.0},
    )
    assert add_to_existing.passed  # not a NEW position, so the cap doesn't fire

    under_cap = check_mandate_compliance(
        _buy("GOOG"), portfolio_value=10_000.0, current_drawdown_pct=0.0,
        mandate=base_mandate.model_copy(update={"max_open_positions": 3}),
        holdings=holdings, quotes={"AAPL": 100.0, "MSFT": 100.0, "GOOG": 100.0},
    )
    assert under_cap.passed


# ── acceptance 1 + 7 + 8: max trades per day / week, clock the test controls ─


def test_max_trades_per_day_and_week_use_a_pinned_utc_clock(base_mandate: Mandate):
    """Basis: UTC calendar day (midnight-to-midnight) and ISO week (Monday
    00:00 UTC), named explicitly here — not real wall-clock time, not
    `Mandate.timezone`."""
    mandate = base_mandate.model_copy(update={"max_trades_per_day": 2})

    today_start = _NOW.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today_start - timedelta(hours=1)  # different UTC day
    two_today = [today_start + timedelta(hours=1), today_start + timedelta(hours=2)]

    at_cap = check_mandate_compliance(
        _buy(), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, trade_open_timestamps=two_today,
    )
    assert not at_cap.passed
    assert at_cap.blocked_by == "over_trading"

    # A trade from yesterday (different UTC day) doesn't count toward today.
    one_today_one_yesterday = [today_start + timedelta(hours=1), yesterday]
    under_cap = check_mandate_compliance(
        _buy(), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, trade_open_timestamps=one_today_one_yesterday,
    )
    assert under_cap.passed

    # Week boundary: Monday 00:00 UTC. _NOW is Thursday 2026-07-30; Monday was
    # 2026-07-27. A trade on Sunday 2026-07-26 is the PRIOR ISO week.
    monday = datetime(2026, 7, 27, 0, 0, tzinfo=timezone.utc)
    prior_sunday = monday - timedelta(hours=1)
    week_mandate = base_mandate.model_copy(update={"max_trades_per_week": 1})
    this_week_only = check_mandate_compliance(
        _buy(), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=week_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW,
        trade_open_timestamps=[monday, prior_sunday],
    )
    assert not this_week_only.passed  # 1 trade already this week (monday) >= cap 1
    assert this_week_only.blocked_by == "over_trading"

    prior_week_doesnt_count = check_mandate_compliance(
        _buy(), portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=week_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW,
        trade_open_timestamps=[prior_sunday],
    )
    assert prior_week_doesnt_count.passed


# ── acceptance 1 + 8: total open-risk cap ──────────────────────────────────


def test_total_open_risk_cap_sums_size_x_stop_distance(base_mandate: Mandate):
    mandate = base_mandate.model_copy(update={"max_open_risk_pct": 2.0})

    # Existing open positions already contribute 1.8 pts. Proposed: $1000 of a
    # $10,000 book (10%) with a 10%-below-entry stop -> +1.0 pt. Total 2.8 > 2.0.
    over_cap = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, proposed_stop=90.0, existing_open_risk_pct=1.8,
    )
    assert not over_cap.passed
    assert over_cap.blocked_by == "open_risk"
    assert any("open risk" in v for v in over_cap.violations)

    under_cap = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, proposed_stop=90.0, existing_open_risk_pct=0.5,
    )
    assert under_cap.passed  # 0.5 + 1.0 = 1.5 <= 2.0

    # No stop on the proposal -> its own contribution is 0; only existing risk counts.
    no_stop = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, existing_open_risk_pct=1.5,
    )
    assert no_stop.passed  # 1.5 + 0 <= 2.0

    already_over = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=10, order_type=OrderType.MARKET),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, existing_open_risk_pct=2.5,
    )
    assert not already_over.passed  # existing alone already exceeds cap -> any BUY blocked


# ── acceptance 3: settable via PATCH, round-trips ──────────────────────────


def test_all_five_new_fields_settable_via_patch_round_trip():
    store = MandateStore()
    user_id = uuid4()
    updated = store.patch(user_id, {
        "post_loss_cooldown_hours": 12.0,
        "max_open_positions": 4,
        "max_trades_per_day": 3,
        "max_trades_per_week": 10,
        "max_open_risk_pct": 8.5,
    })
    assert updated.post_loss_cooldown_hours == 12.0
    assert updated.max_open_positions == 4
    assert updated.max_trades_per_day == 3
    assert updated.max_trades_per_week == 10
    assert updated.max_open_risk_pct == 8.5

    reloaded = store.get_or_default(user_id)
    assert reloaded.post_loss_cooldown_hours == 12.0
    assert reloaded.max_open_positions == 4
    assert reloaded.max_trades_per_day == 3
    assert reloaded.max_trades_per_week == 10
    assert reloaded.max_open_risk_pct == 8.5


# ── acceptance 2: disclosed in the overlay, own units, interpolated ────────


def test_overlay_discloses_all_four_limits_interpolated_not_literal(base_mandate: Mandate):
    mandate = base_mandate.model_copy(update={
        "post_loss_cooldown_hours": 18.0,
        "max_open_positions": 6,
        "max_trades_per_day": 3,
        "max_trades_per_week": 12,
        "max_open_risk_pct": 9.5,
    })
    overlay = generate_overlay(AgentId.MARKET_ANALYST, mandate)
    assert "18.0h after a stop-out" in overlay
    assert "Max open positions: 6" in overlay
    assert "3 per day, 12 per week" in overlay
    assert "9.5%" in overlay and "sum of (position" in overlay

    # Interpolated, not hardcoded: change the values, overlay text changes with it.
    mandate2 = mandate.model_copy(update={
        "post_loss_cooldown_hours": 40.0, "max_open_positions": 9,
        "max_trades_per_day": 1, "max_trades_per_week": 2, "max_open_risk_pct": 3.0,
    })
    overlay2 = generate_overlay(AgentId.MARKET_ANALYST, mandate2)
    assert "40.0h after a stop-out" in overlay2
    assert "Max open positions: 9" in overlay2
    assert "1 per day, 2 per week" in overlay2
    assert "3.0%" in overlay2


def test_overlay_discloses_unset_limits_plainly(base_mandate: Mandate):
    overlay = generate_overlay(AgentId.MARKET_ANALYST, base_mandate)
    assert "Post-loss cooldown: not set" in overlay
    assert "Max open positions: not set" in overlay
    assert "Total open-risk cap: not set" in overlay


# ── acceptance 4: defaults are non-binding ─────────────────────────────────


def test_defaults_are_non_binding_byte_identical_to_field_absent(base_mandate: Mandate):
    """A mandate with the five new fields entirely ABSENT from its stored dict
    (the real shape of every pre-CR101 snapshot) enforces identically to one
    with them explicitly None in memory — no existing user is silently
    constrained on deploy."""
    raw = base_mandate.model_dump(mode="json")
    for f in (
        "post_loss_cooldown_hours", "max_open_positions",
        "max_trades_per_day", "max_trades_per_week", "max_open_risk_pct",
    ):
        del raw[f]
    loaded = Mandate.model_validate(raw)

    holdings = [_H("AAPL", 40), _H("MSFT", 40), _H("GOOG", 40)]
    quotes = {"AAPL": 100.0, "MSFT": 100.0, "GOOG": 100.0, "TSLA": 100.0}
    trade_history = [_NOW - timedelta(days=400)] * 50  # would breach any real cap
    args = dict(
        portfolio_value=12_000.0, current_drawdown_pct=0.0, mandate=loaded,
        holdings=holdings, quotes=quotes, now=_NOW,
        last_loss_closed_at=_NOW - timedelta(minutes=1),  # would breach any cooldown
        trade_open_timestamps=trade_history,
        existing_open_risk_pct=99.0,  # would breach any real risk cap
        proposed_stop=50.0,
    )
    result = check_mandate_compliance(_buy("TSLA"), **args)
    assert result.passed
    assert result.blocked_by is None
    assert result.violations == []


# ── acceptance 6: retro-tightening flags + blocks new buys, never force-sells ─


def test_retro_tightened_max_open_positions_flags_and_blocks_new_buys_not_sell():
    store = MandateStore()
    user_id = uuid4()
    mandate = store.get_or_default(user_id)
    # Portfolio already holds 3 names; tighten the cap to 2 AFTER the fact.
    holdings = [_H("AAPL", 10), _H("MSFT", 10), _H("GOOG", 10)]
    tightened = mandate.model_copy(update={"max_open_positions": 2})

    audit = check_holdings_against_mandate(
        holdings=holdings, marks={"AAPL": 100.0, "MSFT": 100.0, "GOOG": 100.0},
        portfolio_value=13_000.0, current_drawdown_pct=0.0, mandate=tightened,
    )
    assert audit.max_open_positions_breach is True
    assert audit.passed is False

    # A new-ticker BUY is blocked (never a forced sell — nothing here liquidates).
    blocked = check_mandate_compliance(
        _buy("TSLA"), portfolio_value=13_000.0, current_drawdown_pct=0.0, mandate=tightened,
        holdings=holdings, quotes={"AAPL": 100.0, "MSFT": 100.0, "GOOG": 100.0, "TSLA": 100.0},
    )
    assert not blocked.passed
    assert blocked.blocked_by == "max_open_positions"

    # Selling an existing holding is unaffected — retro-tightening never force-sells,
    # and this proves the system doesn't even NEED to: it just blocks new exposure.
    sell = ProposedTrade(ticker="AAPL", side=Side.SELL, quantity=10)
    sell_result = check_mandate_compliance(
        sell, portfolio_value=13_000.0, current_drawdown_pct=0.0, mandate=tightened,
        holdings=holdings, quotes={"AAPL": 100.0, "MSFT": 100.0, "GOOG": 100.0},
    )
    assert sell_result.passed


def test_retro_tightened_max_open_risk_pct_flags_and_blocks_any_new_buy():
    mandate = MandateStore().get_or_default(uuid4()).model_copy(
        update={"max_open_risk_pct": 1.0}
    )
    holdings = [_H("AAPL", 10)]

    audit = check_holdings_against_mandate(
        holdings=holdings, marks={"AAPL": 100.0}, portfolio_value=10_000.0,
        current_drawdown_pct=0.0, mandate=mandate, existing_open_risk_pct=3.0,
    )
    assert audit.max_open_risk_pct_breach is True
    assert audit.passed is False

    blocked = check_mandate_compliance(
        ProposedTrade(ticker="MSFT", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=holdings, quotes={"AAPL": 100.0, "MSFT": 100.0}, existing_open_risk_pct=3.0,
    )
    assert not blocked.passed
    assert blocked.blocked_by == "open_risk"
