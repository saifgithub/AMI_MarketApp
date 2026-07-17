"""CR039 (AT:R60) — Convene the Room is metered, and the trial has a cliff.

Before this, `users.credit_balance` was write-only: `reputation_service` granted
into it and nothing ever spent. No route in the backend returned 402, so of the
24 axes in paywall_axes.md only #1 (model tier) was enforced — invisibly. Floor
Pass and Floor Manager were the same product from the user's seat, and trial
expiry was a silent model downgrade nobody could feel.

These tests pin the three things that make the meter real:
  1. the wall exists and reports itself (402 + balance/cost/resets_at),
  2. billing happens exactly once per real run — never on a dedup reconnect,
     and never on a run that failed on our side,
  3. an expired trial re-grants *immediately*, not at month rollover.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.room import get_room_runner
from app.api.room import router as room_router
from app.db import get_session
from app.db.models import SubscriptionEventRow, User
from app.schemas.mandate import Plan
from app.services import room_runner as room_runner_mod
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import (
    ALLOWANCE,
    ROOM_COST_BASIC,
    ROOM_COST_PREMIUM,
    InsufficientCredits,
    balance_for,
    refund,
    room_cost_for_plan,
    spend,
)
from app.services.room_runner import RoomRunner


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(room_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _new_user(plan: str = "floor_pass") -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    if plan != "floor_pass":
        with get_session() as s:
            s.get(User, u.id).plan = plan
    return u.id, t


def _set_trial(user_id: UUID, expires_in: timedelta) -> None:
    with get_session() as s:
        s.get(User, user_id).trial_expires_at = datetime.now(timezone.utc) + expires_in


def _ledger(user_id: UUID) -> list[SubscriptionEventRow]:
    with get_session() as s:
        return list(s.execute(
            select(SubscriptionEventRow)
            .where(SubscriptionEventRow.user_id == user_id)
            .order_by(SubscriptionEventRow.created_at)
        ).scalars())


# ── The price list matches the spec ──────────────────────────────────────

def test_allowance_and_room_cost_match_the_monetization_spec():
    """tiers_and_pricing.md:12 (13/150/500) x credits.md:19-20 (8 / 25).

    The derived rooms-per-month is the number a user actually feels, so pin it:
    Floor Pass gets exactly the "1 free Room" of paywall_axes.md #3, and Floor
    Manager's 500 buys exactly the "~20 premium Rooms" the pricing table sells.
    """
    rooms = lambda p: ALLOWANCE[p] // room_cost_for_plan(p)  # noqa: E731
    assert rooms(Plan.FLOOR_PASS) == 1
    assert rooms(Plan.FLOOR_MANAGER) == 20
    assert ALLOWANCE[Plan.TRIAL_TRADER] == ALLOWANCE[Plan.TRADER] == 150


def test_trader_room_is_billed_basic_not_premium():
    """Regression for a live miscomputation CR039 found and corrected.

    room_runner priced the Room as `25 if pick_tier(plan, PM) == "premium"`.
    But tier_policy deliberately routes a *Trader*-plan PM to a premium model
    ("a TRADER-plan PM still gets premium-class judgment") — a model-quality
    override that says nothing about which Room product was bought. credits.md:19
    is explicit that the Basic Room is "Floor Pass / Trader". The old expression
    charged a Trader 25 — 3x spec, ~6 Rooms/month instead of ~18. Inert while
    nothing billed; real the moment it did.
    """
    assert room_cost_for_plan(Plan.TRADER) == ROOM_COST_BASIC
    assert room_cost_for_plan(Plan.TRIAL_TRADER) == ROOM_COST_BASIC
    assert room_cost_for_plan(Plan.FLOOR_PASS) == ROOM_COST_BASIC
    assert room_cost_for_plan(Plan.FLOOR_MANAGER) == ROOM_COST_PREMIUM


# ── The wall ─────────────────────────────────────────────────────────────

def test_floor_pass_gets_one_room_then_hits_the_wall():
    user_id, _ = _new_user()

    balance, cost = spend(user_id, None, reason="room:AAPL")
    assert cost == ROOM_COST_BASIC
    assert balance == ALLOWANCE[Plan.FLOOR_PASS] - ROOM_COST_BASIC  # 13 - 8 = 5

    with pytest.raises(InsufficientCredits) as e:
        spend(user_id, None, reason="room:MSFT")
    assert e.value.balance == 5
    assert e.value.cost == ROOM_COST_BASIC
    assert e.value.plan == Plan.FLOOR_PASS
    assert e.value.resets_at > datetime.now(timezone.utc)


def test_refused_spend_does_not_debit():
    user_id, _ = _new_user()
    spend(user_id, None, reason="room:AAPL")
    with pytest.raises(InsufficientCredits):
        spend(user_id, None, reason="room:MSFT")
    # The wall must not nibble — balance is untouched by the refusal.
    assert balance_for(user_id)[0] == 5


# ── The cliff ────────────────────────────────────────────────────────────

def test_trial_lapse_regrants_immediately_not_at_month_rollover():
    """The conversion moment. A 7-day trial almost always lapses mid-month, so
    a purely calendar-keyed allowance would leave an expired trial sitting on
    150 credits for up to three more weeks — the user would never feel it.
    """
    user_id, _ = _new_user()
    _set_trial(user_id, timedelta(days=7))

    balance, allowance, _ = balance_for(user_id)
    assert allowance == 150 and balance == 150
    assert spend(user_id, None, reason="room:AAPL")[0] == 142

    # Trial lapses. Nothing else changes — same calendar month.
    _set_trial(user_id, timedelta(days=-1))

    balance, allowance, _ = balance_for(user_id)
    assert allowance == ALLOWANCE[Plan.FLOOR_PASS]
    assert balance == 13, "expired trial must re-grant now, not at month rollover"

    # And the wall arrives right behind it: 13 buys one Room, not eighteen.
    spend(user_id, None, reason="room:MSFT")
    with pytest.raises(InsufficientCredits):
        spend(user_id, None, reason="room:GOOGL")


def test_active_trial_does_not_regrant_on_every_read():
    """`_ensure_period` is called on every read; it must be idempotent or the
    balance would silently reset to full between two Rooms."""
    user_id, _ = _new_user()
    _set_trial(user_id, timedelta(days=7))

    spend(user_id, None, reason="room:AAPL")
    assert balance_for(user_id)[0] == 142
    assert balance_for(user_id)[0] == 142
    spend(user_id, None, reason="room:MSFT")
    assert balance_for(user_id)[0] == 134


def test_month_rollover_regrants():
    user_id, _ = _new_user()
    spend(user_id, None, reason="room:AAPL")
    assert balance_for(user_id)[0] == 5

    with get_session() as s:
        user = s.get(User, user_id)
        user.credits_period_start = datetime.now(timezone.utc) - timedelta(days=40)

    assert balance_for(user_id)[0] == ALLOWANCE[Plan.FLOOR_PASS]


# ── The ledger ───────────────────────────────────────────────────────────

def test_spend_and_refund_are_recorded_on_the_existing_ledger():
    """SubscriptionEventRow is documented as the trail for "every app-side
    credit consumption" — CR039 reuses it rather than adding a table."""
    user_id, _ = _new_user()
    spend(user_id, None, reason="room:AAPL")
    refund(user_id, ROOM_COST_BASIC, reason="room_failed:test")

    events = [e for e in _ledger(user_id) if e.event_type.startswith("credits_")]
    kinds = [e.event_type for e in events]
    assert kinds == ["credits_reset", "credits_spent", "credits_refunded"]
    assert all(e.source == "app" for e in events)

    reset, spent, refunded = events
    assert (reset.from_value, reset.to_value) == ("0", "13")
    assert (spent.from_value, spent.to_value) == ("13", "5")
    assert (refunded.from_value, refunded.to_value) == ("5", "13")


def test_refund_restores_the_balance():
    user_id, _ = _new_user()
    spend(user_id, None, reason="room:AAPL")
    refund(user_id, ROOM_COST_BASIC, reason="room_failed:test")
    assert balance_for(user_id)[0] == ALLOWANCE[Plan.FLOOR_PASS]


# ── Billing happens exactly once per real run ────────────────────────────

def test_start_run_charges_once_and_a_dedup_reconnect_is_free():
    """start_run's dedup exists to "prevent double-billing on mobile retries".
    Charging in the API layer instead would bill every reconnect — turning a
    flaky LTE handoff into a paywall.
    """
    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id, _ = _new_user(plan="trader")
        before = balance_for(user_id)[0]

        run_1 = await runner.start_run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        async for _ in runner.subscribe(run_1):
            pass
        after_first = balance_for(user_id)[0]
        assert after_first == before - ROOM_COST_BASIC

        # Same user, same ticker → dedup attaches to the completed run.
        run_2 = await runner.start_run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        assert run_2 == run_1
        assert balance_for(user_id)[0] == after_first, "reconnect must be free"

    asyncio.run(_run())


def test_a_failed_run_refunds_the_user(monkeypatch):
    """A bad deploy must not silently eat a Floor Pass user's whole month."""
    def _boom(**_kwargs):
        raise RuntimeError("simulated agent failure")

    monkeypatch.setattr(room_runner_mod, "_speak_one_agent", _boom)

    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        user_id, _ = _new_user()
        before = balance_for(user_id)[0]

        run_id = await runner.start_run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        async for _ in runner.subscribe(run_id):
            pass

        run = runner.get_run(run_id)
        assert run is not None and run.status == "failed"
        assert balance_for(user_id)[0] == before, "failed run must not bill"

    asyncio.run(_run())


# ── The endpoint translates the wall ─────────────────────────────────────

class _BrokeRunner:
    """Stands in for a runner whose start_run refuses on credits."""

    async def start_run(self, **_kwargs):
        raise InsufficientCredits(
            balance=5, cost=8, plan=Plan.FLOOR_PASS,
            resets_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

    def is_active(self, run_id) -> bool:
        return False

    def get_run(self, run_id):
        return None


def test_stream_returns_402_carrying_everything_the_wall_needs(app, client):
    """The client must be able to render the wall from this one response —
    no follow-up call, and never a generic 'HTTP 500' toast mid-stream.
    """
    user_id, token = _new_user()
    app.dependency_overrides[get_room_runner] = lambda: _BrokeRunner()

    r = client.post(
        "/v1/room/stream",
        json={"user_id": str(user_id), "ticker": "AAPL", "locale": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 402
    detail = r.json()["detail"]
    assert detail["code"] == "insufficient_credits"
    assert detail["balance"] == 5
    assert detail["cost"] == 8
    assert detail["plan"] == "floor_pass"
    assert detail["resets_at"].startswith("2026-08-01")


def test_ownership_403_precedes_any_billing(app, client):
    """Never bill for a request we're about to reject."""
    victim_id, _ = _new_user()
    attacker_id, attacker_token = _new_user()
    before = balance_for(attacker_id)[0]

    r = client.post(
        "/v1/room/stream",
        json={"user_id": str(victim_id), "ticker": "AAPL", "locale": "en"},
        headers={"Authorization": f"Bearer {attacker_token}"},
    )

    assert r.status_code == 403
    assert balance_for(attacker_id)[0] == before
    assert balance_for(victim_id)[0] == ALLOWANCE[Plan.FLOOR_PASS]
