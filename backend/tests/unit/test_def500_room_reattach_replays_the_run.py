"""DEF500 guard: reattaching to an in-flight Room replays the whole run so far.

AMI-DL-3 (E5-ROOM-01): the app was killed during the second desk and reopened
27 s later. The Convene sheet attached to the same run (correct, no second
charge) but the transcript came back with 6 desks of 12, the already-reported
ones as NO RESPONSE. Cause: `subscribe()` drained a single shared queue
destructively, so everything the dead connection had read was gone for the
next subscriber.

Test our logic: the channel's replay-and-fan-out contract, and that the SSE
route announces a reattachment and replays from the first desk.
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    RoomEvent,
    RoomRunner,
    _RunEventChannel,
    get_room_runner,
)
from tests.unit.test_room_runner import _billed_user


def _ev(kind: str, text: str | None = None) -> RoomEvent:
    return RoomEvent(kind=kind, text=text, run_id=uuid4())


def test_second_subscriber_gets_every_event_the_first_already_read():
    async def _run():
        ch = _RunEventChannel()
        await ch.put(_ev("started"))
        await ch.put(_ev("agent_token", "desk one"))
        first, first_re = ch.attach()
        assert first_re is False
        assert (await first.get()).kind == "started"
        assert (await first.get()).text == "desk one"
        # First connection dies after consuming both events.
        ch.detach(first)
        await ch.put(_ev("agent_token", "desk two"))

        second, second_re = ch.attach()
        assert second_re is True
        got = [(await second.get()).text for _ in range(3)]
        assert got == [None, "desk one", "desk two"]

        await ch.put(None)
        assert await second.get() is None

    asyncio.run(_run())


def test_attach_after_close_replays_and_terminates():
    async def _run():
        ch = _RunEventChannel()
        await ch.put(_ev("agent_token", "x"))
        await ch.put(None)
        q, _ = ch.attach()
        assert (await q.get()).text == "x"
        assert await q.get() is None

    asyncio.run(_run())


def test_two_live_subscribers_both_receive_new_events():
    async def _run():
        ch = _RunEventChannel()
        a, _ = ch.attach()
        b, _ = ch.attach()
        await ch.put(_ev("phase"))
        assert (await a.get()).kind == "phase"
        assert (await b.get()).kind == "phase"

    asyncio.run(_run())


def test_reattached_runner_subscription_replays_from_the_first_desk():
    """End to end on the runner: a subscriber that quits after 40 events, then a
    second one that joins while the run is still going, sees `reattached`
    first and then at least every event the first one saw."""

    async def _run():
        runner = RoomRunner()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
        run_id = await runner.start_run(
            user_id=_billed_user(),
            ticker="MSFT",
            mandate=mandate,
            char_delay_min=0.0,
            char_delay_max=0.0,
        )
        seen_first: list[RoomEvent] = []
        async for ev in runner.subscribe(run_id):
            seen_first.append(ev)
            if len(seen_first) >= 40:
                break
        assert not any(e.kind == "reattached" for e in seen_first)

        assert runner.is_active(run_id), "run finished before the reattach; test would be vacuous"
        replay: list[RoomEvent] = []
        async for ev in runner.subscribe(run_id):
            replay.append(ev)
        assert replay[0].kind == "reattached"
        body = replay[1:]
        assert [e.kind for e in body[: len(seen_first)]] == [e.kind for e in seen_first]
        assert [e.text for e in body[: len(seen_first)]] == [e.text for e in seen_first]
        assert body[-1].kind == "verdict"

    asyncio.run(_run())


def test_sse_route_announces_reattachment_before_the_replay():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.dependencies import get_current_user
    from app.api.room import router as room_router
    from app.services.auth_service import AuthService

    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    app = FastAPI()
    app.include_router(room_router)
    app.dependency_overrides[get_current_user] = lambda: user

    class _FakeRunner:
        def __init__(self) -> None:
            self.run_id = uuid4()

        async def start_run(self, **kw):
            return self.run_id

        def is_active(self, run_id):
            return True

        async def subscribe(self, run_id):
            yield RoomEvent(kind="reattached", run_id=run_id)
            yield RoomEvent(kind="started", run_id=run_id)
            yield RoomEvent(kind="agent_token", text="hi", run_id=run_id)

        def get_run(self, run_id):
            return None

    fake = _FakeRunner()
    app.dependency_overrides[get_room_runner] = lambda: fake
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.post(
        "/v1/room/stream",
        json={"user_id": str(user.id), "ticker": "MSFT"},
    )
    assert resp.status_code == 200, resp.text
    kinds = [
        line.split(":", 1)[1].strip()
        for line in resp.text.splitlines()
        if line.startswith("event:")
    ]
    assert kinds[0] == "reattached"
    assert kinds.index("started") > kinds.index("reattached")
    data = [
        line.split(":", 1)[1].strip()
        for line in resp.text.splitlines()
        if line.startswith("data:")
    ]
    assert json.loads(data[0])["run_id"] == str(fake.run_id)
