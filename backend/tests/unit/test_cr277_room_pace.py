"""CR277 — the Room's typewriter pacing is configurable and capped.

Before CR277 every finished turn was replayed at 4-12 ms/char with no ceiling,
~1.7-2.0 min per Room (WP-10 scorecard). These tests pin the new contract with
a fake sleep/clock (no real waiting): per-char range, per-turn cap, per-Room
cap, every character still delivered, and the settings reaching the runner.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import Settings, settings
from app.schemas import AgentId
from app.services import room_runner
from app.services.room_runner import RoomRunner, _typewriter

# A typical live Room: ~14,000 agent-turn characters over 13 turns (scorecard:
# 1.7-2.0 min at 8 ms/char => 12,750-15,000 chars).
_TURNS = 13
_CHARS_PER_TURN = 1080


class _Fake:
    """Fake clock + sleep. sleep(x) advances the clock by `stretch * x`."""

    def __init__(self, stretch: float = 1.0) -> None:
        self.now = 0.0
        self.slept: list[float] = []
        self.stretch = stretch

    def clock(self) -> float:
        return self.now

    async def sleep(self, s: float) -> None:
        self.slept.append(s)
        self.now += s * self.stretch


def _drain(run_id, text, fake, dmin=0.0015, dmax=0.0035, **kw):
    async def go():
        out = []
        async for ev in _typewriter(
            run_id, AgentId.MARKET_ANALYST, text, dmin, dmax,
            sleep=fake.sleep, clock=fake.clock, **kw,
        ):
            out.append(ev.text)
        return out
    return asyncio.run(go())


def _fresh_run_id():
    rid = uuid4()
    room_runner._PACE_SPENT_S.pop(rid, None)
    return rid


def test_defaults_are_the_cr277_values():
    assert settings.room_char_delay_min_ms == 1.5
    assert settings.room_char_delay_max_ms == 3.5
    assert settings.room_turn_pace_cap_s == 4.0
    assert settings.room_pace_cap_s == 40.0
    assert room_runner._CHAR_DELAY_MIN == pytest.approx(0.0015)
    assert room_runner._CHAR_DELAY_MAX == pytest.approx(0.0035)


def test_min_above_max_refuses_boot():
    with pytest.raises(ValueError, match="room_char_delay_min_ms"):
        Settings(room_char_delay_min_ms=5.0, room_char_delay_max_ms=2.0)


def test_short_turn_paced_within_per_char_range():
    fake = _Fake()
    text = "x" * 500
    out = _drain(_fresh_run_id(), text, fake)
    assert "".join(out) == text
    total = sum(fake.slept)
    assert 500 * 0.0015 - 1e-6 <= total <= 500 * 0.0035 + 1e-6


def test_very_long_turn_never_exceeds_turn_cap():
    fake = _Fake()
    text = "y" * 200_000  # 200k chars would be 400+ s uncapped
    out = _drain(_fresh_run_id(), text, fake, turn_cap_s=4.0, room_cap_s=1000.0)
    assert len(out) == 200_000
    assert sum(fake.slept) <= 4.0 + 1e-6
    assert fake.now <= 4.0 + 1e-6


def test_room_cap_bounds_total_across_turns_and_every_char_still_arrives():
    rid = _fresh_run_id()
    fake = _Fake()
    delivered = 0
    for _ in range(40):  # far more turns than a real Room
        out = _drain(rid, "z" * 3000, fake, turn_cap_s=4.0, room_cap_s=40.0)
        delivered += len(out)
    assert delivered == 40 * 3000
    assert sum(fake.slept) <= 40.0 + 1e-6
    assert room_runner._PACE_SPENT_S[rid] == pytest.approx(40.0)


def test_typical_room_adds_about_30_to_40_seconds_with_defaults():
    rid = _fresh_run_id()
    fake = _Fake()
    for _ in range(_TURNS):
        _drain(
            rid, "a" * _CHARS_PER_TURN, fake,
            dmin=room_runner._CHAR_DELAY_MIN, dmax=room_runner._CHAR_DELAY_MAX,
        )
    assert 25.0 <= sum(fake.slept) <= 40.0


def test_schedule_absorbs_sleep_overshoot():
    # Event loops oversleep; a sleep that takes 30% longer than asked must not
    # stretch the turn past its plan.
    fake = _Fake(stretch=1.3)
    _drain(_fresh_run_id(), "q" * 1000, fake, turn_cap_s=4.0, room_cap_s=40.0)
    assert fake.now <= 1000 * 0.0035 + 0.01  # never beyond the plan's max


def test_zero_delay_means_no_pacing_but_still_yields():
    fake = _Fake()
    out = _drain(_fresh_run_id(), "hello", fake, dmin=0.0, dmax=0.0)
    assert "".join(out) == "hello"
    assert fake.slept == [0.0] * 5


def test_zero_caps_disable_pacing():
    fake = _Fake()
    _drain(_fresh_run_id(), "w" * 100, fake, turn_cap_s=0.0)
    assert sum(fake.slept) == 0.0


def test_room_run_releases_its_pace_budget(monkeypatch):
    from app.services.coach_engine import hydrate_coach_mandate

    async def instant(_s: float) -> None:
        return None

    monkeypatch.setattr(room_runner.asyncio, "sleep", instant)
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    rid = uuid4()

    async def go():
        async for _ in runner.run(
            run_id=rid, user_id=uuid4(), ticker="AAPL", mandate=mandate,
        ):
            pass

    asyncio.run(go())
    assert rid not in room_runner._PACE_SPENT_S
