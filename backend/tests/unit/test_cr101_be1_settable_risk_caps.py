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

import datetime as _dt
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as _tz
from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.overlay_generator import _max_position_pct, _sector_cap_pct, generate_overlay
from app.agents.safety_floor import (
    check_mandate_compliance,
    check_option_open,
    single_name_cap_pct,
)
from app.schemas import AgentId, Mandate, RiskComponents
from app.schemas.mandate import enforced_limit_field_names
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


# ── acceptance 6: the four-leg invariant, DERIVED (DEF191) ─────────────────
#
# DEF191: this used to be one giant test hand-enumerating its subjects — three
# blocks from CR101-BE1, five more appended by hand in CR101-BE2, with nothing
# checking the list against the schema. CR101-BE2 proved the failure mode: the
# guard picked up none of its five new fields and stayed green throughout.
#
# Fix: `Mandate.enforced_limit_field_names()` (backend/app/schemas/mandate.py)
# derives the subject list from `Field(json_schema_extra={"enforced_limit":
# True})` markers on the schema itself — see that function's docstring for why
# a per-field marker was picked over a class-level registry. Below, each
# field's four-leg check is still a bespoke function (verifying "enforced"
# means exercising the real business-logic scenario that trips THAT specific
# limit — that can't be generic), but which fields get checked, and whether
# every derived field HAS a check, is now asserted structurally rather than
# left to whoever remembers to append a block.

_NOW = datetime(2026, 7, 30, 12, 0, tzinfo=_tz.utc)


def _probe_max_drawdown_pct(base_mandate: Mandate, store: MandateStore) -> None:
    dd_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=base_mandate.max_drawdown_pct,
        mandate=base_mandate, holdings=[], quotes={"AAPL": 100.0},
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not dd_result.passed and any("drawdown" in v for v in dd_result.violations)  # (a) enforced
    assert f"{base_mandate.max_drawdown_pct}%" in generate_overlay(AgentId.AGGRESSIVE_DEBATOR, base_mandate)  # (c) overlay
    dd_user = uuid4()
    dd_patched = store.patch(dd_user, {"max_drawdown_pct": 20})
    assert dd_patched.max_drawdown_pct == 20  # (d) settable
    assert store.get_or_default(dd_user).max_drawdown_pct == 20  # (b) disclosed verbatim, own units, on read-back


def _probe_sector_cap_pct(base_mandate: Mandate, store: MandateStore) -> None:
    tight_sector = base_mandate.model_copy(update={"sector_cap_pct": 20.0})
    sector_result = _sector_breach_check(tight_sector, buy_value=500.0)
    assert not sector_result.passed and sector_result.blocked_by == "compliance"  # (a) enforced
    assert sector_concentration_cap(tight_sector) == pytest.approx(0.20)  # (b) own units (fraction)
    assert f"{_sector_cap_pct(tight_sector)}% of portfolio" in generate_overlay(AgentId.MARKET_ANALYST, tight_sector)  # (c)
    assert store.patch(uuid4(), {"sector_cap_pct": 45.0}).sector_cap_pct == 45.0  # (d) settable


def _probe_single_name_cap_pct(base_mandate: Mandate, store: MandateStore) -> None:
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


def _probe_post_loss_cooldown_hours(base_mandate: Mandate, store: MandateStore) -> None:
    cooldown_mandate = base_mandate.model_copy(update={"post_loss_cooldown_hours": 24.0})
    cooldown_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=cooldown_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, last_loss_closed_at=_NOW - timedelta(hours=1),
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not cooldown_result.passed and cooldown_result.blocked_by == "cooldown"  # (a)
    assert cooldown_mandate.post_loss_cooldown_hours == 24.0  # (b) own units (hours)
    assert "24.0h after a stop-out" in generate_overlay(AgentId.PORTFOLIO_MANAGER, cooldown_mandate)  # (c)
    assert store.patch(uuid4(), {"post_loss_cooldown_hours": 6.0}).post_loss_cooldown_hours == 6.0  # (d)


def _probe_max_open_positions(base_mandate: Mandate, store: MandateStore) -> None:
    positions_mandate = base_mandate.model_copy(update={"max_open_positions": 1})
    positions_result = check_mandate_compliance(
        ProposedTrade(ticker="MSFT", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=positions_mandate,
        holdings=[Holding(ticker="AAPL", quantity=1, avg_cost=100.0, opened_at=_NOW)],
        quotes={"AAPL": 100.0, "MSFT": 100.0}, now=_NOW, last_loss_closed_at=None,
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not positions_result.passed and positions_result.blocked_by == "max_open_positions"  # (a)
    assert positions_mandate.max_open_positions == 1  # (b) own units (count)
    assert "Max open positions: 1" in generate_overlay(AgentId.PORTFOLIO_MANAGER, positions_mandate)  # (c)
    assert store.patch(uuid4(), {"max_open_positions": 5}).max_open_positions == 5  # (d)


def _probe_max_trades_per_day(base_mandate: Mandate, store: MandateStore) -> None:
    day_mandate = base_mandate.model_copy(update={"max_trades_per_day": 1})
    day_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=day_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, trade_open_timestamps=[_NOW],
        last_loss_closed_at=None, existing_open_risk_pct=0.0,
    )
    assert not day_result.passed and day_result.blocked_by == "over_trading"  # (a)
    assert day_mandate.max_trades_per_day == 1  # (b) own units (count/day)
    assert "1 per day" in generate_overlay(AgentId.PORTFOLIO_MANAGER, day_mandate)  # (c)
    assert store.patch(uuid4(), {"max_trades_per_day": 3}).max_trades_per_day == 3  # (d)


def _probe_max_trades_per_week(base_mandate: Mandate, store: MandateStore) -> None:
    week_mandate = base_mandate.model_copy(update={"max_trades_per_week": 1})
    week_result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=week_mandate,
        holdings=[], quotes={"AAPL": 100.0}, now=_NOW, trade_open_timestamps=[_NOW],
        last_loss_closed_at=None, existing_open_risk_pct=0.0,
    )
    assert not week_result.passed and week_result.blocked_by == "over_trading"  # (a)
    assert week_mandate.max_trades_per_week == 1  # (b) own units (count/week)
    assert "1 per week" in generate_overlay(AgentId.PORTFOLIO_MANAGER, week_mandate)  # (c)
    assert store.patch(uuid4(), {"max_trades_per_week": 8}).max_trades_per_week == 8  # (d)


def _probe_max_open_risk_pct(base_mandate: Mandate, store: MandateStore) -> None:
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


# ── CR172 §9 (D5) — the four option limits ─────────────────────────────────
#
# Each probe drives the REAL floor entry point, `check_option_open`, rather
# than asserting on the arithmetic underneath it. That is deliberate and it is
# DEF190's rule: assert at the fence, not on the layer in front of it. A probe
# that called `book_exposure` directly would stay green if the floor stopped
# calling it at all — which is exactly the state these fields were in before
# they existed, and exactly what this invariant is here to prevent.

_OPT_EXPIRY = "2027-03-19"
_OPT_TODAY = _dt.date(2026, 8, 24)


def _opt_leg(right, strike, qty, premium, expiry=_OPT_EXPIRY):
    from app.trading_math.option_strategy import StrategyLeg

    return StrategyLeg(
        right=right, strike=strike, quantity=qty, premium=premium,
        multiplier=100.0, expiry=expiry,
    )


def _derivatives_mandate(base_mandate: Mandate, **limits) -> Mandate:
    """The base mandate with derivatives permitted — otherwise the gate
    returns first and every probe below would pass for the wrong reason."""
    # `long_only=False` too: the base mandate is long-only, and a short-put
    # probe would otherwise be refused by THAT rule and never reach the cap
    # under test — passing for the wrong reason, which is the whole failure
    # mode this invariant exists to catch.
    compliance = base_mandate.compliance.model_copy(
        update={"derivatives_allowed": True, "long_only": False}
    )
    return base_mandate.model_copy(update={"compliance": compliance, **limits})


def _probe_max_option_premium_pct(base_mandate: Mandate, store: MandateStore) -> None:
    m = _derivatives_mandate(base_mandate, max_option_premium_pct=5.0)
    # $910 of premium on a $10,000 book is 9.1%, over the 5% cap.
    result = check_option_open(
        [_opt_leg("call", 195.0, 1.0, 9.10)], m,
        portfolio_value=10_000.0, existing_structures=(), today=_OPT_TODAY,
    )
    assert not result.passed and result.blocked_by == "concentration"  # (a)
    assert any("9.1%" in v and "5.0%" in v for v in result.violations)  # (b) own units
    assert m.max_option_premium_pct == 5.0
    assert "5.0%" in generate_overlay(AgentId.PORTFOLIO_MANAGER, m)  # (c)
    assert store.patch(
        uuid4(), {"max_option_premium_pct": 12.0}
    ).max_option_premium_pct == 12.0  # (d)


def _greek_leg(delta: float, vega: float, contracts: float, sym: str = "X"):
    from app.trading_math.greeks import GreekLeg, Greeks
    return GreekLeg(
        occ_symbol=sym,
        greeks=Greeks(delta=delta, gamma=0.0, theta_per_day=0.0,
                      vega_per_point=vega, rho_per_point=0.0),
        contracts=contracts, multiplier=100.0,
    )


def _probe_max_portfolio_delta(base_mandate: Mandate, store: MandateStore) -> None:
    from app.trading_math.greeks import aggregate_book_greeks

    m = _derivatives_mandate(base_mandate, max_portfolio_delta=200.0)
    # 1 contract at 0.60 delta x 100 = 60 share equivalents, plus 500 shares
    # held = 560, over the 200 cap.
    book = aggregate_book_greeks([_greek_leg(0.60, 0.0, 1.0)], equity_shares=500.0)
    result = check_option_open(
        [_opt_leg("call", 195.0, 1.0, 9.10)], m,
        portfolio_value=10_000.0, existing_structures=(), today=_OPT_TODAY,
        book_greeks=book,
    )
    assert not result.passed and result.blocked_by == "concentration"  # (a)
    assert any("560" in v and "200" in v for v in result.violations)  # (b) own units
    assert "200" in generate_overlay(AgentId.PORTFOLIO_MANAGER, m)  # (c)
    assert store.patch(
        uuid4(), {"max_portfolio_delta": 900.0}
    ).max_portfolio_delta == 900.0  # (d)


def _probe_max_portfolio_vega(base_mandate: Mandate, store: MandateStore) -> None:
    from app.trading_math.greeks import aggregate_book_greeks

    m = _derivatives_mandate(base_mandate, max_portfolio_vega=100.0)
    # 1 contract at 12.0 vega/point x 100 = $1,200 per point, over the $100 cap.
    book = aggregate_book_greeks([_greek_leg(0.0, 12.0, 1.0)])
    result = check_option_open(
        [_opt_leg("call", 195.0, 1.0, 9.10)], m,
        portfolio_value=10_000.0, existing_structures=(), today=_OPT_TODAY,
        book_greeks=book,
    )
    assert not result.passed and result.blocked_by == "concentration"  # (a)
    assert any("1,200" in v and "100" in v for v in result.violations)  # (b)
    assert "100" in generate_overlay(AgentId.PORTFOLIO_MANAGER, m)  # (c)
    assert store.patch(
        uuid4(), {"max_portfolio_vega": 250.0}
    ).max_portfolio_vega == 250.0  # (d)


def _probe_max_option_notional_pct(base_mandate: Mandate, store: MandateStore) -> None:
    m = _derivatives_mandate(base_mandate, max_option_notional_pct=100.0)
    # 1 contract at strike 195 controls $19,500 of stock — 195% of a $10k book.
    result = check_option_open(
        [_opt_leg("call", 195.0, 1.0, 9.10)], m,
        portfolio_value=10_000.0, existing_structures=(), today=_OPT_TODAY,
    )
    assert not result.passed and result.blocked_by == "concentration"  # (a)
    assert any("195.0%" in v for v in result.violations)  # (b)
    assert "100.0%" in generate_overlay(AgentId.PORTFOLIO_MANAGER, m)  # (c)
    assert store.patch(
        uuid4(), {"max_option_notional_pct": 50.0}
    ).max_option_notional_pct == 50.0  # (d)


def _probe_max_assignment_exposure_pct(
    base_mandate: Mandate, store: MandateStore,
) -> None:
    m = _derivatives_mandate(base_mandate, max_assignment_exposure_pct=25.0)
    # A short put at 180 would need $18,000 if assigned — 180% of a $10k book.
    result = check_option_open(
        [_opt_leg("put", 180.0, -1.0, 4.50)], m,
        portfolio_value=10_000.0, existing_structures=(), today=_OPT_TODAY,
    )
    assert not result.passed and result.blocked_by == "concentration"  # (a)
    assert any("180.0%" in v for v in result.violations)  # (b)
    assert "25.0%" in generate_overlay(AgentId.PORTFOLIO_MANAGER, m)  # (c)
    assert store.patch(
        uuid4(), {"max_assignment_exposure_pct": 40.0}
    ).max_assignment_exposure_pct == 40.0  # (d)


def _probe_min_days_to_expiry(base_mandate: Mandate, store: MandateStore) -> None:
    m = _derivatives_mandate(base_mandate, min_days_to_expiry=30)
    # Expires in 2 days against a 30-day floor.
    soon = (_OPT_TODAY + _dt.timedelta(days=2)).isoformat()
    result = check_option_open(
        [_opt_leg("call", 195.0, 1.0, 9.10, expiry=soon)], m,
        portfolio_value=10_000.0, existing_structures=(), today=_OPT_TODAY,
    )
    assert not result.passed  # (a)
    assert any("2 day(s)" in v and "30" in v for v in result.violations)  # (b) days
    assert "30" in generate_overlay(AgentId.PORTFOLIO_MANAGER, m)  # (c)
    assert store.patch(
        uuid4(), {"min_days_to_expiry": 7}
    ).min_days_to_expiry == 7  # (d)


# Every derived enforced-limit field must have a probe. This dict, not the
# schema markers, is what a developer edits to add coverage for a new field —
# but the NEXT test proves the two are kept in lockstep.
_FOUR_LEG_PROBES = {
    "max_drawdown_pct": _probe_max_drawdown_pct,
    "sector_cap_pct": _probe_sector_cap_pct,
    "single_name_cap_pct": _probe_single_name_cap_pct,
    "post_loss_cooldown_hours": _probe_post_loss_cooldown_hours,
    "max_open_positions": _probe_max_open_positions,
    "max_trades_per_day": _probe_max_trades_per_day,
    "max_trades_per_week": _probe_max_trades_per_week,
    "max_open_risk_pct": _probe_max_open_risk_pct,
    "max_portfolio_delta": _probe_max_portfolio_delta,
    "max_portfolio_vega": _probe_max_portfolio_vega,
    "max_option_premium_pct": _probe_max_option_premium_pct,
    "max_option_notional_pct": _probe_max_option_notional_pct,
    "max_assignment_exposure_pct": _probe_max_assignment_exposure_pct,
    "min_days_to_expiry": _probe_min_days_to_expiry,
}


def test_every_enforced_limit_field_is_enforced_disclosed_and_settable(base_mandate: Mandate):
    """The four-leg invariant guard (DEF191): every field
    `Mandate.enforced_limit_field_names()` derives from the schema must have a
    registered probe verifying (a) enforced, (b) disclosed in its own units,
    (c) disclosed in the agent overlay, (d) settable — or the guard fails
    naming exactly which derived field has no probe. The vacuity leg: if the
    derivation itself breaks and finds nothing, that is a FAIL, not a vacuous
    pass — an empty guard is worse than no guard (DEF191)."""
    derived = enforced_limit_field_names()

    assert derived, (
        "enforced_limit_field_names() returned nothing — either every enforced "
        "limit was removed from the schema (unlikely) or the "
        "ENFORCED_LIMIT_MARKER derivation itself is broken. A guard that finds "
        "zero subjects must fail loudly, never pass vacuously."
    )

    missing_probes = sorted(set(derived) - set(_FOUR_LEG_PROBES))
    assert not missing_probes, (
        f"{missing_probes} carries Field(json_schema_extra={{'enforced_limit': True}}) "
        "but has no entry in _FOUR_LEG_PROBES above — add one covering all four "
        "legs (enforced / disclosed own-units / disclosed overlay / settable) "
        "before this can pass."
    )
    stale_probes = sorted(set(_FOUR_LEG_PROBES) - set(derived))
    assert not stale_probes, (
        f"{stale_probes} has a probe in _FOUR_LEG_PROBES but is no longer marked "
        "enforced_limit on Mandate — delete the probe or restore the marker."
    )

    store = MandateStore()
    for field_name in derived:
        _FOUR_LEG_PROBES[field_name](base_mandate, store)


# ── DEF191 acceptance 4: catching a field that forgot the marker entirely ──


def _is_numeric_annotation(annotation: object) -> bool:
    """True for `int`, `float`, `Optional[int|float]`, and numeric `Literal`s
    — the shapes an enforced-limit field is plausibly declared with."""
    import types
    from typing import Literal, Union, get_args, get_origin

    if annotation in (int, float):
        return True
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        return any(_is_numeric_annotation(a) for a in get_args(annotation) if a is not type(None))
    if origin is Literal:
        return all(isinstance(v, (int, float)) for v in get_args(annotation))
    return False


# Numeric Mandate fields that are NOT enforced limits. DEF191 acceptance 4:
# the reason is part of the entry, not a comment above the set — an exemption
# without one is indistinguishable from a field somebody could not be bothered
# to mark, and this list is the only place the difference is recorded.
_NON_LIMIT_NUMERIC_FIELDS: dict[str, str] = {
    "version": "bookkeeping — the mandate's own revision counter, not a limit on anything",
    "risk_score": "an INPUT to the resolver that produces limits, not a limit itself",
    "credit_balance": "entitlement state stamped server-side; client-unwritable per "
                      "CLIENT_UNWRITABLE_MANDATE_FIELDS",
    "credit_allowance": "entitlement state stamped server-side; client-unwritable",
    "room_cost": "pricing, stamped server-side; client-unwritable",
}

# Files where an enforced limit's business logic actually reads
# `mandate.<field>` — enforcement (safety_floor, sector_allocation),
# disclosure (overlay_generator), the Room LLM-facing prompt builder, the
# backfill migration, and the mandate API's resolved-caps stamping. Not
# exhaustive by construction — see the test docstring below for what this
# cross-check does and does not prove.
_ENFORCEMENT_ADJACENT_SOURCE_FILES = (
    "app/agents/safety_floor.py",
    "app/agents/overlay_generator.py",
    "app/services/sector_allocation.py",
    "app/services/room_runner.py",
    "app/services/room_prompts.py",
    "app/services/risk_limit_backfill.py",
    "app/api/mandate.py",
)


def test_no_unmarked_numeric_field_is_referenced_by_enforcement_code():
    """DEF191 acceptance 4 — the harder half of the guard: catching a
    developer who wires up enforcement/disclosure for a NEW numeric Mandate
    field but never adds `Field(json_schema_extra={"enforced_limit": True})`
    at all, so `enforced_limit_field_names()` never sees it and the four-leg
    guard above silently never runs for it.

    This is a HEURISTIC cross-check, not a closed proof: it greps the known
    enforcement/disclosure/prompt call sites for a literal `mandate.<field>`
    attribute read and fails if an unmarked, non-exempt numeric field shows
    up there. Stated explicitly, per the DEF191 row's acceptance 4: this does
    NOT catch a field wired through a mechanism that never spells
    `mandate.<name>` in one of the listed files — e.g. threaded through
    `mandate.model_dump()` and read by key, aliased to a local variable
    before use, or enforced from a file not in
    `_ENFORCEMENT_ADJACENT_SOURCE_FILES`. The class this DOES catch — by far
    the common case, since every existing enforced limit is read this exact
    way — is a developer implementing the (a)/(c) legs in the usual places
    and forgetting the marker. The class it disclaims is a developer who
    forgets BOTH the marker and reads the field unconventionally; no
    mechanism here claims to close that."""
    marked = set(enforced_limit_field_names())
    numeric_fields = {
        name
        for name, field in Mandate.model_fields.items()
        if _is_numeric_annotation(field.annotation) and name not in _NON_LIMIT_NUMERIC_FIELDS
    }
    unmarked = numeric_fields - marked

    backend_root = Path(__file__).resolve().parents[2]  # backend/tests/unit/ -> backend/
    offenders: dict[str, list[str]] = {}
    for rel_path in _ENFORCEMENT_ADJACENT_SOURCE_FILES:
        src = (backend_root / rel_path).read_text()
        for field_name in unmarked:
            if re.search(rf"mandate\.{re.escape(field_name)}\b", src):
                offenders.setdefault(field_name, []).append(rel_path)

    assert not offenders, (
        f"unmarked numeric Mandate field(s) referenced by enforcement-adjacent "
        f"code: {offenders} — add Field(json_schema_extra={{'enforced_limit': "
        f"True}}) to declare it an enforced limit (and a probe in "
        f"_FOUR_LEG_PROBES above), or add it to _NON_LIMIT_NUMERIC_FIELDS with "
        f"a reason if it genuinely isn't one."
    )


def test_every_numeric_mandate_field_is_classified_as_a_limit_or_explicitly_not():
    """DEF191 acceptance 4, closed — by changing the question.

    The grep above searches CODE for an unmarked field, and a code search can
    never be complete: the row's own disclaimer lists three ways round it
    (`model_dump()` read by key, aliased to a local before use, enforcement
    added to a file outside `_ENFORCEMENT_ADJACENT_SOURCE_FILES`). Widening
    the file list or the pattern narrows that gap without closing it, because
    the set of ways to read a field is unbounded.

    The set of FIELDS is not. So this asks the bounded question instead: every
    numeric field on `Mandate` must be either marked `enforced_limit` — which
    drags in the four-leg probe requirement above — or listed in
    `_NON_LIMIT_NUMERIC_FIELDS` with a reason. A developer who adds a numeric
    field and forgets the marker now fails HERE, on the commit that adds the
    field, no matter how the enforcement code reads it, and whether or not any
    enforcement exists yet.

    That is the same move as CR136-M01's P15 guard: matching on a NAME (or on
    a call site) tests whether someone followed a convention; matching on the
    SHAPE tests the thing you actually care about. It also inverts the failure
    mode the DEF191 row objects to most — the old guard's green asserted
    universality (`every_enforced_limit_field`) over a frozen list, which is a
    positive, misleading signal. This one's green is a statement about the
    schema, because it is derived from the schema.

    The grep test stays. It is now a second net catching MISclassification —
    a field exempted here but read by enforcement code anyway — rather than
    the only net catching omission.
    """
    numeric = {
        name for name, field in Mandate.model_fields.items()
        if _is_numeric_annotation(field.annotation)
    }
    assert numeric, (
        "vacuity: no numeric fields were derived from Mandate at all, so this "
        "guard is asserting nothing — _is_numeric_annotation is broken or the "
        "schema moved"
    )

    marked = set(enforced_limit_field_names())
    unclassified = numeric - marked - set(_NON_LIMIT_NUMERIC_FIELDS)

    assert not unclassified, (
        f"numeric Mandate field(s) that are neither declared an enforced limit "
        f"nor declared not to be one: {sorted(unclassified)}.\n"
        f"Add Field(json_schema_extra={{'enforced_limit': True}}) to the field "
        f"(and a probe in _FOUR_LEG_PROBES), or add it to "
        f"_NON_LIMIT_NUMERIC_FIELDS with the reason it is not a limit. "
        f"DEF191: an enforced limit that nobody declared is exactly the "
        f"'settable but unenforced' class CR101 exists to prevent, and the old "
        f"guard only noticed if the field also happened to appear in one of "
        f"{len(_ENFORCEMENT_ADJACENT_SOURCE_FILES)} grepped files."
    )


def test_the_exemption_list_carries_a_reason_and_no_dead_entries():
    """Non-vacuity for the classification above, both directions.

    An exemption without a reason is indistinguishable from a field somebody
    could not be bothered to mark, and a STALE exemption is worse than a
    missing one: it silently re-exempts a field that has since become a real
    limit, or hides the next one behind a name that no longer exists. Same
    reasoning as the exact `_UNREVIEWED` pin in CR136-M01's P15 guard — a
    pin left behind after the thing it pinned is gone stops being a guard.
    """
    numeric = {
        name for name, field in Mandate.model_fields.items()
        if _is_numeric_annotation(field.annotation)
    }
    stale = set(_NON_LIMIT_NUMERIC_FIELDS) - numeric
    assert not stale, (
        f"exemption(s) for field(s) that are no longer numeric fields on "
        f"Mandate: {sorted(stale)} — remove them, or the list is hiding "
        f"whatever takes their place"
    )
    overlap = set(_NON_LIMIT_NUMERIC_FIELDS) & set(enforced_limit_field_names())
    assert not overlap, (
        f"field(s) both marked an enforced limit and exempted from being one: "
        f"{sorted(overlap)} — the two lists disagree and the exemption wins "
        f"silently in the grep test"
    )
    for name, reason in _NON_LIMIT_NUMERIC_FIELDS.items():
        assert len(reason.split()) >= 4, (
            f"{name}'s exemption reason is too short to be a reason: {reason!r}"
        )
