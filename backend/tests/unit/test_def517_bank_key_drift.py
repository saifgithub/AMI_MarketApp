"""DEF517 — a Room the user ran must not unkey itself, nor may the daily refresh.

DEF513 added `universe` (the sourced Sharia / exclusion / liquidity verdicts with
each snapshot's as-of date) to the Room key. The snapshots rotate daily with no
user action (Alpha: 23:16Z), and the UAT's replay landed 30 minutes after one: the
as-of date moved, every verdict was identical, and the free replay became a charged
Room. This file holds the walk over EVERY key part (convene, finish, convene again,
nothing the user did changed: no part may differ) and the universe cases.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services import room_bank, room_runner as rr
from app.services.classification_universe import ClassificationUniverse
from app.services.room_runner import RoomRunner
from app.services.sharia_universe import HalalUniverse
from tests.unit.test_cr267_wp24_room_bank import (  # noqa: F401  (fast_room is a fixture)
    _convene,
    _go,
    _mandate,
    _RootGateway,
    _user,
    fast_room,
)


def _patch_dated_universes(monkeypatch, *, as_of=date(2026, 11, 19), stale=False,
                           compliant=("AAPL",), fossil=()):
    state = {"as_of": as_of, "stale": stale, "compliant": set(compliant),
             "fossil": set(fossil)}

    async def halal():
        return HalalUniverse(
            state["compliant"], as_of=state["as_of"], stale=state["stale"],
            parent_index={"AAPL"},
        )

    async def klass():
        return ClassificationUniverse(
            fossil=state["fossil"], classified={"AAPL"}, as_of=state["as_of"],
            stale=state["stale"],
        )

    monkeypatch.setattr(rr, "default_halal_universe_async", halal)
    monkeypatch.setattr(rr, "default_classification_universe_async", klass)
    return state


@pytest.fixture
def recorded_parts(monkeypatch):
    seen: list[dict[str, str]] = []
    orig = RoomRunner._prepare_bank

    async def spy(self, **kw):
        prep = await orig(self, **kw)
        assert prep.parts is not None, f"the Room ran unbanked: {prep.reason}"
        seen.append(dict(prep.parts))
        return prep

    monkeypatch.setattr(RoomRunner, "_prepare_bank", spy)
    return seen


def _convene_twice_between(between, plan="floor_pass"):
    """`floor_pass` mirrors the UAT: its 5 credits cannot pay for a second Room,
    so a key that moved fails the convene itself (InsufficientCredits)."""
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(plan), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        between()
        return a, await _convene(runner, u, "AAPL", m)

    return _go(go())


def _assert_no_part_moved(seen):
    assert len(seen) == 2
    first, second = seen
    assert set(room_bank._HASHED_PARTS) <= set(first), "a key part is missing from the key"
    moved = {p for p in room_bank._HASHED_PARTS if first.get(p) != second.get(p)}
    assert not moved, f"key parts moved with nothing the user changed: {sorted(moved)}"


def test_finishing_a_room_moves_no_key_part(fast_room, recorded_parts, monkeypatch):
    _patch_dated_universes(monkeypatch)
    a, b = _convene_twice_between(lambda: None)
    _assert_no_part_moved(recorded_parts)
    assert a == b


def test_a_daily_snapshot_refresh_with_the_same_verdicts_is_the_same_room(
    fast_room, recorded_parts, monkeypatch,
):
    state = _patch_dated_universes(monkeypatch)
    a, b = _convene_twice_between(lambda: state.update(as_of=date(2026, 11, 20)))
    _assert_no_part_moved(recorded_parts)
    assert a == b


def test_a_snapshot_going_stale_is_a_new_room(fast_room, monkeypatch):
    state = _patch_dated_universes(monkeypatch)
    a, b = _convene_twice_between(lambda: state.update(stale=True), "trader")
    assert a != b


def test_a_changed_verdict_in_a_refreshed_snapshot_is_a_new_room(fast_room, monkeypatch):
    state = _patch_dated_universes(monkeypatch)
    a, b = _convene_twice_between(
        lambda: state.update(as_of=date(2026, 11, 20), fossil={"AAPL"}), "trader",
    )
    assert a != b


def test_universe_digest_ignores_the_snapshot_date_only():
    def digest(as_of, stale=False, fossil=()):
        return room_bank.universe_digest(
            HalalUniverse({"AAPL"}, as_of=as_of, stale=stale, parent_index={"AAPL"}),
            ClassificationUniverse(
                fossil=set(fossil), classified={"AAPL"}, as_of=as_of, stale=stale,
            ),
            "AAPL",
        )

    base = digest(date(2026, 11, 19))
    assert digest(date(2026, 11, 20)) == base
    assert digest(None) == base
    assert digest(date(2026, 11, 19), stale=True) != base
    assert digest(date(2026, 11, 20), fossil={"AAPL"}) != base
