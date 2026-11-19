"""DEF498 — the verdict a live Room streams is the verdict it persists.

`run()` used to emit the `verdict` event from `_run_cio_step`, then stamp
`street_comparison` / `analyst_view` / `sheet_state` / `reference_price` /
`next_convene_delta` onto `run.verdict` and persist it. The stream carried the
unstamped verdict: Alpha UAT-ROOM-023 failed ("verdict has no street_comparison
block") while `GET /v1/room/{id}` had the block, and the app's live board
(`boardFromRoomState`) reads the stream, so the Street card never rendered on a
live run. Driven through a real `RoomRunner.run()` for the same reason
CR219 R51's tests are: a builder-level test cannot see a call-site ordering bug.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import RoomRunner
from tests.unit.test_cr237_cio_retry import (
    _AlwaysDownGateway,
    _CioDownThenApproveGateway,
    _billed_user,
    _pm_json,
    _retry,
    _run_outage_room,
    _seed_stored_mandate,
)

pytestmark = pytest.mark.allow_ledger_drift

_STAMPED = (
    "street_comparison", "analyst_view", "sheet_state", "reference_price",
    "next_convene_delta",
)


class _ApproveGateway:
    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            yield _pm_json(action="APPROVE")
            return
        yield "AMI agent live reply with a real contribution."


def _drive(gateway, *, user_id=None, mandate=None, credit_cost=0):
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]
    run_id = uuid4()
    mandate = mandate or hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

    async def go():
        return [ev async for ev in runner.run(
            run_id=run_id, user_id=user_id or uuid4(), ticker="AAPL",
            mandate=mandate, char_delay_min=0.0, char_delay_max=0.0,
            credit_cost=credit_cost,
        )]

    return runner, run_id, asyncio.run(go())


def test_streamed_verdict_equals_the_persisted_one_and_carries_the_street_block():
    runner, run_id, events = _drive(_ApproveGateway())
    streamed = [ev.verdict for ev in events if ev.kind == "verdict"]
    assert len(streamed) == 1
    persisted = runner.get_run(run_id).verdict
    assert streamed[0] == persisted
    assert streamed[0].action == VerdictAction.APPROVE
    assert streamed[0].street_comparison is not None
    for field in _STAMPED:
        assert getattr(streamed[0], field) == getattr(persisted, field), field
    assert streamed[0].sheet_state is not None


def test_scripted_demo_path_streams_the_stamped_verdict_too():
    runner, run_id, events = _drive(None)
    streamed = [ev.verdict for ev in events if ev.kind == "verdict"]
    assert len(streamed) == 1
    assert streamed[0] == runner.get_run(run_id).verdict
    assert streamed[0].street_comparison is not None


def test_outage_verdict_streams_stamped_with_the_refund_sentence():
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)
    runner, run_id, events = _drive(
        _AlwaysDownGateway(), user_id=user_id, mandate=mandate, credit_cost=12,
    )
    streamed = [ev.verdict for ev in events if ev.kind == "verdict"]
    assert len(streamed) == 1
    assert streamed[0] == runner.get_run(run_id).verdict
    assert streamed[0].street_comparison is not None
    assert "wasn't charged" in streamed[0].reason


def test_cio_retry_streams_the_street_block_it_persisted():
    user_id = _billed_user()
    mandate = _seed_stored_mandate(user_id, blocklist=None)
    gateway = _CioDownThenApproveGateway(_pm_json(action="APPROVE"))
    runner, run_id = _run_outage_room(user_id, mandate, gateway)
    gateway.down = False

    events = _retry(runner, run_id, user_id)

    streamed = [ev.verdict for ev in events if ev.kind == "verdict"]
    assert len(streamed) == 1
    persisted = runner.get_run(run_id).verdict
    assert streamed[0] == persisted
    assert streamed[0].street_comparison is not None
    assert streamed[0].analyst_view == persisted.analyst_view
