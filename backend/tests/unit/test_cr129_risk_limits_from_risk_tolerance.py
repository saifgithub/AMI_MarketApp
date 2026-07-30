"""CR129 — derive all seven risk limits from risk_score, backfill alpha, Day
Trader preset. Covers acceptance criteria 2 (full five-field migration proof,
extending test_cr101_be1_settable_risk_caps.py's single-name-only version), 3
(the diversification-floor guard), 5 (the Day Trader compliance/halal
boundary), and 7 (backfill journalling names the change) from the lane assign
(orchestration/dispatch/lanes/CR129-BE.assign.md). Acceptance 1/4/6 are
already covered in test_cr101_be2_new_risk_limits.py / test_cr101_be1_settable_
risk_caps.py, which this file does not duplicate. Acceptance 8 (mutations) is
a manual verification step recorded in the lane hand-off, not a permanent test
here — a test that inverts its own subject to prove itself isn't a test the
suite can keep.
"""

from __future__ import annotations

import math
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.safety_floor import check_mandate_compliance
from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.schemas import Compliance, Mandate
from app.schemas.journal import EntryType
from app.schemas.trade import ProposedTrade, Side
from app.services.auth_service import AuthService
from app.services.day_trader_preset import (
    DAY_TRADER_PRESET_OVERRIDES,
    is_day_trader_preset,
)
from app.services.journal_store import get_journal_store
from app.services.mandate_store import get_mandate_store
from app.services.sharia_universe import HalalUniverse
from app.trading_math.risk_limits import (
    DEFAULT_MAX_OPEN_POSITIONS,
    DEFAULT_MAX_OPEN_RISK_FRACTION_OF_DRAWDOWN,
    DEFAULT_MAX_TRADES_PER_DAY,
    DEFAULT_MAX_TRADES_PER_WEEK,
    DEFAULT_POST_LOSS_COOLDOWN_HOURS,
    DIVERSIFICATION_FLOOR,
    resolved_max_open_positions,
    resolved_max_open_risk_pct,
    resolved_max_trades_per_day,
    resolved_max_trades_per_week,
    resolved_post_loss_cooldown_hours,
)
from app.trading_math.sizing import resolved_single_name_cap_pct

# ── acceptance 2: EVERY limit for EVERY risk_score resolves to the documented
#    value, not just the single-name cap (test_cr101_be1_settable_risk_caps.py
#    already proved that one field on its own) ────────────────────────────


@pytest.mark.parametrize(
    "risk_score,max_positions,cooldown_h,trades_day,trades_week,open_risk_pct",
    [
        (1, 65, 4.0, 2, 6, 7.5),
        (2, 65, 2.0, 3, 9, 9.0),
        (3, 35, 1.0, 4, 12, 10.5),
        (4, 30, 1.0, 5, 15, 13.5),
        (5, 30, 0.5, 6, 20, 15.0),
    ],
)
def test_every_risk_score_resolves_all_five_limits_to_the_documented_table(
    risk_score: int,
    max_positions: int,
    cooldown_h: float,
    trades_day: int,
    trades_week: int,
    open_risk_pct: float,
    base_mandate: Mandate,
):
    """The CR129 README's preset table, row by row, for a mandate with none
    of the five fields set — the real shape of every one of the 13 live alpha
    mandates. `open_risk_pct` is a fraction of THIS mandate's own
    `max_drawdown_pct` (30 on `base_mandate`), so the expected values are
    pinned against base_mandate specifically, not a universal constant."""
    assert base_mandate.max_drawdown_pct == 30
    mandate = base_mandate.model_copy(update={"risk_score": risk_score})

    assert resolved_max_open_positions(mandate.risk_score, mandate.max_open_positions) == max_positions
    assert resolved_post_loss_cooldown_hours(
        mandate.risk_score, mandate.post_loss_cooldown_hours
    ) == cooldown_h
    assert resolved_max_trades_per_day(mandate.risk_score, mandate.max_trades_per_day) == trades_day
    assert resolved_max_trades_per_week(mandate.risk_score, mandate.max_trades_per_week) == trades_week
    assert resolved_max_open_risk_pct(
        mandate.risk_score, mandate.max_drawdown_pct, mandate.max_open_risk_pct
    ) == pytest.approx(open_risk_pct)

    # Same story with the fields entirely ABSENT from the stored dict (the
    # real shape on disk), not merely None in memory.
    raw = mandate.model_dump(mode="json")
    for f in (
        "max_open_positions", "post_loss_cooldown_hours",
        "max_trades_per_day", "max_trades_per_week", "max_open_risk_pct",
    ):
        del raw[f]
    loaded = Mandate.model_validate(raw)
    assert resolved_max_open_positions(loaded.risk_score, loaded.max_open_positions) == max_positions
    assert resolved_post_loss_cooldown_hours(
        loaded.risk_score, loaded.post_loss_cooldown_hours
    ) == cooldown_h
    assert resolved_max_trades_per_day(loaded.risk_score, loaded.max_trades_per_day) == trades_day
    assert resolved_max_trades_per_week(loaded.risk_score, loaded.max_trades_per_week) == trades_week
    assert resolved_max_open_risk_pct(
        loaded.risk_score, loaded.max_drawdown_pct, loaded.max_open_risk_pct
    ) == pytest.approx(open_risk_pct)


def test_preset_tables_carry_exactly_the_documented_five_scores():
    """Pins the raw tables themselves (not just the resolver) against the
    README — a future edit to any one of these dicts is what acceptance 2
    exists to catch."""
    assert DEFAULT_MAX_OPEN_POSITIONS == {1: 65, 2: 65, 3: 35, 4: 30, 5: 30}
    assert DEFAULT_POST_LOSS_COOLDOWN_HOURS == {1: 4.0, 2: 2.0, 3: 1.0, 4: 1.0, 5: 0.5}
    assert DEFAULT_MAX_TRADES_PER_DAY == {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
    assert DEFAULT_MAX_TRADES_PER_WEEK == {1: 6, 2: 9, 3: 12, 4: 15, 5: 20}
    assert DEFAULT_MAX_OPEN_RISK_FRACTION_OF_DRAWDOWN == {
        1: 0.25, 2: 0.30, 3: 0.35, 4: 0.45, 5: 0.50,
    }


# ── acceptance 3: "nobody is forced to concentrate" — >= 30 names reachable ─
#
# Reachable = capped by BOTH constraints: max_open_positions (a name-count
# ceiling) and max_open_risk_pct (a risk-budget ceiling, which — at the
# single-name cap's own size and the codebase's standard 10%-below-entry stop
# convention used throughout test_cr101_be2_new_risk_limits.py's open-risk
# tests — divides into a name count too: each fully-sized position consumes
# single_name_cap_pct * 10% / 100 points of the open-risk budget). Coupled to
# THREE numbers (max_open_positions, max_open_risk_pct's fraction, and the
# single-name cap) — a future tweak to any one, in isolation, is exactly what
# this guard exists to catch.

_ASSUMED_STOP_DISTANCE_PCT = 10.0


def _names_reachable(risk_score: int, max_drawdown_pct: float) -> int:
    max_positions = resolved_max_open_positions(risk_score, None)
    open_risk_cap = resolved_max_open_risk_pct(risk_score, max_drawdown_pct, None)
    single_name_cap = resolved_single_name_cap_pct(risk_score, None)
    risk_per_fully_sized_name = single_name_cap * _ASSUMED_STOP_DISTANCE_PCT / 100.0
    reachable_by_risk_budget = math.floor(open_risk_cap / risk_per_fully_sized_name)
    return min(max_positions, reachable_by_risk_budget)


@pytest.mark.parametrize(
    "risk_score,expected_reachable",
    [(1, 50), (2, 60), (3, 35), (4, 30), (5, 30)],
)
def test_diversification_floor_guard_names_reachable(
    risk_score: int, expected_reachable: int, base_mandate: Mandate
):
    """The CR129 README's own 'names reachable' column, for base_mandate's
    max_drawdown_pct=30. Every value must ALSO clear DIVERSIFICATION_FLOOR —
    that is the invariant; the exact expected counts pin the three coupled
    numbers so a silent change to any one is caught immediately, not just a
    slow drift below the floor."""
    reachable = _names_reachable(risk_score, base_mandate.max_drawdown_pct)
    assert reachable == expected_reachable
    assert reachable >= DIVERSIFICATION_FLOOR


# ── acceptance 5: Day Trader preset — the whole boundary ──────────────────
#
# "Takes off all the safeguards" must mean every USER risk limit goes
# permissive; it must NOT mean the floor is bypassed. safety_floor.py splits
# blocked_by into two families (README, "The 'Day Trader' preset" table) —
# compliance/halal/locale/allow-blocklist are NOT the user's to relax. This
# is the test that proves the split holds under the preset that maximally
# stresses it.


def _day_trader_mandate(base_mandate: Mandate, **compliance_kwargs) -> Mandate:
    """halal defaults OFF so tests targeting one compliance family (blocklist,
    locale, allowlist) aren't cross-contaminated by an unsupplied halal
    universe's own pause-block — each compliance leg gets its own dedicated
    test below instead."""
    compliance_kwargs.setdefault("halal", False)
    return base_mandate.model_copy(update={
        **DAY_TRADER_PRESET_OVERRIDES,
        "compliance": Compliance(long_only=True, liquid_only=True, **compliance_kwargs),
    })


def test_day_trader_preset_sets_every_user_risk_limit_permissive(base_mandate: Mandate):
    mandate = _day_trader_mandate(base_mandate)
    for field, value in DAY_TRADER_PRESET_OVERRIDES.items():
        assert getattr(mandate, field) == value
    assert is_day_trader_preset(mandate.model_dump())


def test_day_trader_preset_permits_a_trade_every_user_limit_would_otherwise_block(
    base_mandate: Mandate,
):
    """Sanity check that the preset really is maximally permissive on the
    user's-own-limits family, before proving compliance still blocks below —
    otherwise a compliance block here would be meaningless (nothing to prove
    the floor didn't just block on a risk limit instead)."""
    mandate = _day_trader_mandate(base_mandate)
    huge_buy = ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=95, limit_price=100.0)
    result = check_mandate_compliance(
        huge_buy, portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 100.0}, last_loss_closed_at=None,
        trade_open_timestamps=[], existing_open_risk_pct=0.0, proposed_stop=90.0,
    )
    assert result.passed  # 95% of the book — every risk limit at 100%/off/huge


def test_day_trader_preset_does_not_touch_compliance_halal_still_blocks(base_mandate: Mandate):
    """THE test the assign calls 'the whole boundary': every user risk limit
    permissive, but a screened-out halal ticker still fires, blocked_by ==
    'compliance' — never 'concentration'/'cooldown'/'max_open_positions'/
    'over_trading'/'open_risk', which would mean the preset leaked into the
    uncoachable family."""
    mandate = _day_trader_mandate(base_mandate, halal=True)
    universe = HalalUniverse(
        {"AAA", "AAB"}, parent_index={"AAA", "AAB", "JPMX"}, as_of=date(2026, 7, 22)
    )
    screened_out_buy = ProposedTrade(ticker="JPMX", side=Side.BUY, quantity=1, limit_price=10.0)
    result = check_mandate_compliance(
        screened_out_buy, portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        halal_universe=universe, holdings=[], quotes={"JPMX": 10.0},
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not result.passed
    assert result.blocked_by == "compliance"
    assert result.sharia_verdict is not None


def test_day_trader_preset_does_not_touch_blocklist(base_mandate: Mandate):
    mandate = _day_trader_mandate(base_mandate, ticker_blocklist=["TSLA"])
    result = check_mandate_compliance(
        ProposedTrade(ticker="TSLA", side=Side.BUY, quantity=1, limit_price=10.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"TSLA": 10.0}, last_loss_closed_at=None,
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not result.passed
    assert result.blocked_by == "blocklist"


def test_day_trader_preset_does_not_touch_locale(base_mandate: Mandate):
    mandate = _day_trader_mandate(base_mandate)
    result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=10.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 10.0}, locale_allowed_universe={"MSFT"},
        last_loss_closed_at=None, trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not result.passed
    assert result.blocked_by == "locale"


def test_day_trader_preset_does_not_touch_allowlist(base_mandate: Mandate):
    mandate = _day_trader_mandate(base_mandate, ticker_allowlist=["MSFT"])
    result = check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side=Side.BUY, quantity=1, limit_price=10.0),
        portfolio_value=10_000.0, current_drawdown_pct=0.0, mandate=mandate,
        holdings=[], quotes={"AAPL": 10.0}, last_loss_closed_at=None,
        trade_open_timestamps=[], existing_open_risk_pct=0.0,
    )
    assert not result.passed
    assert result.blocked_by == "allowlist"


def test_day_trader_preset_is_not_risk_score_6_and_does_not_bypass_the_floor(
    base_mandate: Mandate,
):
    """The README's explicit non-mechanism: risk_score is untouched (still
    1-5) and there is no bypass flag — the deterministic check still ran
    above (it found violations), it simply evaluated permissive numbers."""
    mandate = _day_trader_mandate(base_mandate)
    assert mandate.risk_score == base_mandate.risk_score
    assert 1 <= mandate.risk_score <= 5
    assert not hasattr(mandate, "skip_floor")


# ── acceptance 7: backfill journalling names the change ───────────────────


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(auth_router)
    app.include_router(mandate_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user() -> tuple[UUID, dict]:
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


def _last_journal_summary(user_id: UUID) -> str:
    entries, _, _ = get_journal_store().list_for_user(
        user_id, entry_type=EntryType.MANDATE_EDIT, limit=20,
    )
    assert entries, "expected a MANDATE_EDIT journal entry"
    return entries[0].summary or ""


def test_patching_a_cr129_limit_journals_a_summary_naming_the_change(
    client: TestClient,
):
    """DEF197: pre-fix, patching either of the two CR101-BE1 caps (sector /
    single-name) fell through to a bare 'Mandate updated.' — this asserts the
    fix for the field DEF197 named, plus one of the four CR101-BE2/CR129
    fields, so a regression in the shared loop breaks either."""
    user_id, hdr = _new_user()

    r = client.patch(
        f"/v1/mandate/{user_id}", json={"single_name_cap_pct": 8.0}, headers=hdr,
    )
    assert r.status_code == 200, r.text
    summary = _last_journal_summary(user_id)
    assert summary != "Mandate updated."
    assert "single-name cap" in summary
    assert "8.0%" in summary

    r2 = client.patch(
        f"/v1/mandate/{user_id}", json={"post_loss_cooldown_hours": 6.0}, headers=hdr,
    )
    assert r2.status_code == 200, r2.text
    summary2 = _last_journal_summary(user_id)
    assert summary2 != "Mandate updated."
    assert "post-loss cooldown" in summary2
    assert "6.0h" in summary2


def test_day_trader_preset_patch_journals_its_own_distinct_summary(client: TestClient):
    user_id, hdr = _new_user()
    r = client.patch(
        f"/v1/mandate/{user_id}", json=dict(DAY_TRADER_PRESET_OVERRIDES), headers=hdr,
    )
    assert r.status_code == 200, r.text
    summary = _last_journal_summary(user_id)
    assert summary != "Mandate updated."
    assert "Day Trader preset" in summary
    assert "Compliance" in summary or "compliance" in summary


def test_journal_names_old_and_new_value_not_just_that_something_changed(
    client: TestClient,
):
    """'Names the change' means both sides of the diff are legible — not
    merely that a change happened."""
    user_id, hdr = _new_user()
    client.patch(f"/v1/mandate/{user_id}", json={"max_open_positions": 12}, headers=hdr)
    first = _last_journal_summary(user_id)
    assert "following your risk profile" in first  # old value: unset
    assert "12" in first

    client.patch(f"/v1/mandate/{user_id}", json={"max_open_positions": 40}, headers=hdr)
    second = _last_journal_summary(user_id)
    assert "12" in second  # old value: the explicit one just set
    assert "40" in second
