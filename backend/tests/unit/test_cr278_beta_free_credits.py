"""CR278 (WP-36, D-076) — Beta "credits free": one switch at the charge point.

`BETA_FREE_CREDITS=true` makes `credit_service.spend` debit nothing and report a
charge of 0, so a Room still runs and records `credit_cost=0`, the 402 wall is
unreachable, and the mandate advertises a free Room. Off (the default) is
byte-for-byte today's metering — pinned here beside the on-case so a flipped
default is caught.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from app.core.config import Settings, settings
from app.db import get_session
from app.db.models import RoomRunRow, User
from app.schemas.mandate import Plan
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import (
    ALLOWANCE,
    ROOM_COST_BASIC,
    InsufficientCredits,
    balance_for,
    credits_are_free,
    spend,
)
from app.services.room_runner import RoomRunner


def _new_user(plan: str = "floor_pass") -> UUID:
    u, _t, _ = AuthService().ensure_anonymous(device_user_id=None)
    if plan != "floor_pass":
        with get_session() as s:
            s.get(User, u.id).plan = plan
    return u.id


def test_default_is_off():
    assert Settings.model_fields["beta_free_credits"].default is False


def test_off_is_todays_metering(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", False)
    uid = _new_user()
    balance, cost = spend(uid, None, reason="room:AAPL")
    assert cost == ROOM_COST_BASIC
    assert balance == ALLOWANCE[Plan.FLOOR_PASS] - ROOM_COST_BASIC
    with pytest.raises(InsufficientCredits):
        spend(uid, None, reason="room:MSFT")


def test_on_spend_debits_nothing_and_never_hits_the_wall(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", True)
    assert credits_are_free()
    uid = _new_user()
    start = balance_for(uid)[0]
    for _ in range(5):
        _, cost = spend(uid, None, reason="room:AAPL")
        assert cost == 0
    _, cost = spend(uid, 99, reason="room:AAPL:live+4")
    assert cost == 0
    assert balance_for(uid)[0] == start


def test_on_room_runs_and_records_credit_cost_zero(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", True)

    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        uid = _new_user(plan="trader")
        before = balance_for(uid)[0]
        run_id = await runner.start_run(
            user_id=uid, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        async for _ in runner.subscribe(run_id):
            pass
        run = runner.get_run(run_id)
        assert run is not None and run.status == "completed"
        assert run.credit_cost == 0
        with get_session() as s:
            assert s.get(RoomRunRow, run_id).credit_cost == 0
        assert balance_for(uid)[0] == before

    asyncio.run(_run())


def test_off_room_records_the_real_charge(monkeypatch):
    monkeypatch.setattr(settings, "beta_free_credits", False)

    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        uid = _new_user(plan="trader")
        run_id = await runner.start_run(
            user_id=uid, ticker="MSFT", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        async for _ in runner.subscribe(run_id):
            pass
        run = runner.get_run(run_id)
        assert run is not None and run.credit_cost == ROOM_COST_BASIC

    asyncio.run(_run())


def test_mandate_advertises_a_free_room_only_when_on(monkeypatch):
    from app.api.mandate import _with_plan_state

    uid = _new_user()
    with get_session() as s:
        user = s.get(User, uid)
        s.expunge(user)
    mandate = hydrate_coach_mandate({"plan": "floor_pass", "risk_score": 3})

    monkeypatch.setattr(settings, "beta_free_credits", True)
    assert _with_plan_state(mandate, user).room_cost == 0
    monkeypatch.setattr(settings, "beta_free_credits", False)
    assert _with_plan_state(mandate, user).room_cost == ROOM_COST_BASIC
