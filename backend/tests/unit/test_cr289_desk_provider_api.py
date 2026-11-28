"""CR289 — the `desk_provider` pin on POST /v1/room/stream is gated, loudly.

A benchmark arm pins every desk call of a Room to one provider slot. These pin who
may ask and what a refusal looks like, because a pin that silently fell back to the
default model would hand an arm the wrong model's Room and call it a clean run:

1. A non-benchmark user is refused with 403, before any charge or `start_run`.
2. A value outside the allow-set is 422; an allowed-but-unregistered slot is 422.
3. Unset is byte-identical: `start_run` is not even given the keyword.
4. A valid pin from a benchmark user reaches `start_run`.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import room as room_api
from app.api.room import get_room_runner
from app.api.room import router as room_router
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService
from app.services.credit_service import balance_for
from app.services.room_runner import RoomAlreadyInSession


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(room_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


class _Gateway:
    def __init__(self, registered: set[str]):
        self._registered = registered

    def has_provider(self, name: str) -> bool:
        return name in self._registered


class _RecordingRunner:
    """Records `start_run` kwargs, then ends the request with a 409 so no Room runs."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def start_run(self, **kwargs):
        self.calls.append(kwargs)
        raise RoomAlreadyInSession(uuid4(), "AAPL")

    def is_active(self, run_id) -> bool:
        return False

    def get_run(self, run_id):
        return None


def _user(app_version: str | None) -> tuple[UUID, str]:
    u, token, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, u.id).last_app_version = app_version
    return u.id, token


def _post(client: TestClient, user_id: UUID, token: str, **extra):
    return client.post(
        "/v1/room/stream",
        json={"user_id": str(user_id), "ticker": "AAPL", "locale": "en", **extra},
        headers={"Authorization": f"Bearer {token}"},
    )


@pytest.fixture
def runner(app: FastAPI) -> _RecordingRunner:
    r = _RecordingRunner()
    app.dependency_overrides[get_room_runner] = lambda: r
    return r


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setattr(
        room_api, "get_llm_gateway", lambda: _Gateway({"vllm", "vllm_fallback", "deepseek"}),
    )


def test_allow_set_is_exactly_the_two_benchmark_slots():
    assert room_api.PINNABLE_DESK_PROVIDERS == frozenset({"vllm_fallback", "deepseek"})
    assert "vllm" not in room_api.PINNABLE_DESK_PROVIDERS


@pytest.mark.parametrize("app_version", [None, "1.0.0+12", "Room-Benchmark"])
def test_non_benchmark_user_is_403_before_any_charge(client, runner, registered, app_version):
    user_id, token = _user(app_version)
    before = balance_for(user_id)[0]

    r = _post(client, user_id, token, desk_provider="deepseek")

    assert r.status_code == 403
    assert runner.calls == []
    assert balance_for(user_id)[0] == before


@pytest.mark.parametrize("value", ["vllm", "anthropic", "mock", "kimi", "", "DeepSeek"])
def test_unknown_or_unpinnable_provider_is_422(client, runner, registered, value):
    user_id, token = _user("room-benchmark")

    r = _post(client, user_id, token, desk_provider=value)

    assert r.status_code == 422
    assert "desk_provider" in r.text
    assert runner.calls == []


def test_allowed_but_unregistered_slot_is_422_not_a_fallback(client, runner, monkeypatch):
    monkeypatch.setattr(room_api, "get_llm_gateway", lambda: _Gateway({"vllm", "vllm_fallback"}))
    user_id, token = _user("room-benchmark")

    r = _post(client, user_id, token, desk_provider="deepseek")

    assert r.status_code == 422
    assert "not registered" in r.text
    assert runner.calls == []


def test_unset_pin_is_unchanged_and_start_run_gets_no_keyword(client, runner, registered):
    user_id, token = _user(None)

    r = _post(client, user_id, token)

    assert r.status_code == 409
    assert len(runner.calls) == 1
    assert "desk_provider" not in runner.calls[0]


@pytest.mark.parametrize("slot", ["vllm_fallback", "deepseek"])
def test_benchmark_user_pin_reaches_start_run(client, runner, registered, slot):
    user_id, token = _user("room-benchmark")

    r = _post(client, user_id, token, desk_provider=slot)

    assert r.status_code == 409
    assert runner.calls[0]["desk_provider"] == slot


def test_ownership_403_still_precedes_the_pin_check(client, runner, registered):
    victim_id, _ = _user("room-benchmark")
    attacker_id, attacker_token = _user("room-benchmark")

    r = _post(client, victim_id, attacker_token, desk_provider="deepseek")

    assert r.status_code == 403
    assert runner.calls == []
