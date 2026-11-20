"""DEF513 — a banked Room is served only when everything the Room reads is unchanged.

WP-24 keyed the Room on the mandate, fact sheet, policy, model, portfolio, journal
and Alpaca account. `build_room_messages` also reads the user's active Brief
overlay for each desk, which the key missed, so a same-day re-convene after a
Brief edit returned the old Room. This file holds the per-input tests for what
DEF513 added (Brief, sourced compliance universes, analyst roster, global Room
settings) and the guard that fails when the Room reads an input nobody classified.
"""

from __future__ import annotations

import ast
import inspect
import re
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest

from app.api.room import RoomStartRequest
from app.core.config import Settings, settings
from app.schemas import TWELVE_AGENT_IDS, AgentId
from app.schemas.mandate import Plan
from app.services import room_bank, room_runner as rr
from app.services.classification_universe import ClassificationUniverse
from app.services.entitlements import AnalystRoster
from app.services.overlay_store import get_overlay_store
from app.services.room_prompts import build_room_messages
from app.services.room_runner import RoomRunner
from app.services.sharia_universe import HalalUniverse
from tests.unit.test_cr267_wp24_room_bank import (  # noqa: F401  (fast_room is a fixture)
    _convene,
    _convene_twice,
    _go,
    _mandate,
    _RootGateway,
    _user,
    fast_room,
)

APP = Path(rr.__file__).resolve().parents[1]


def _brief(u, agent=AgentId.BULL_RESEARCHER, text="Weigh insider selling heavily."):
    get_overlay_store().save_new_version(
        u, agent, text, "plain english", Plan.TRADER,
    )


# ── Brief Your Agent ──────────────────────────────────────────────────────


def test_unchanged_brief_is_the_same_room(fast_room):
    a, b = _convene_twice(lambda u: None)
    assert a == b


def test_a_new_brief_is_a_new_room(fast_room):
    a, b = _convene_twice(_brief)
    assert a != b


def test_an_edited_brief_is_a_new_room(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        _brief(u, text="first brief")
        a = await _convene(runner, u, "AAPL", m)
        _brief(u, text="second brief")
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a != b


@pytest.mark.parametrize("agent", list(TWELVE_AGENT_IDS))
def test_a_brief_on_any_of_the_twelve_desks_is_a_new_room(fast_room, agent):
    a, b = _convene_twice(lambda u: _brief(u, agent))
    assert a != b


def test_resaving_identical_brief_text_is_the_same_room(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        _brief(u, text="same text")
        a = await _convene(runner, u, "AAPL", m)
        _brief(u, text="  same text\n")
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a == b, "a new overlay version with the same rendered text changes nothing the desks read"


def test_another_users_brief_is_not_this_users_input(fast_room):
    other = _user()
    a, b = _convene_twice(lambda u: _brief(other))
    assert a == b


def test_brief_digest_is_the_rendered_text_per_desk():
    base = {"bull_researcher": "x", "bear_researcher": None}
    d = room_bank.brief_digest(base)
    assert room_bank.brief_digest({"bull_researcher": " x\n", "bear_researcher": "  "}) == d
    assert room_bank.brief_digest({"bull_researcher": "y", "bear_researcher": None}) != d
    assert room_bank.brief_digest({"bull_researcher": None, "bear_researcher": "x"}) != d, (
        "the same text on another desk is a different Brief"
    )
    assert room_bank.brief_digest({}) == room_bank.brief_digest({"bull_researcher": None})


# ── sourced compliance universes ──────────────────────────────────────────


def _patch_universes(monkeypatch, *, compliant=(), parent=(), fossil=(), classified=("AAPL",)):
    state = {"compliant": set(compliant), "parent": set(parent), "fossil": set(fossil),
             "classified": set(classified)}

    async def halal():
        return HalalUniverse(state["compliant"], parent_index=state["parent"])

    async def klass():
        return ClassificationUniverse(
            fossil=state["fossil"], classified=state["classified"],
        )

    monkeypatch.setattr(rr, "default_halal_universe_async", halal)
    monkeypatch.setattr(rr, "default_classification_universe_async", klass)
    return state


def test_a_changed_sharia_verdict_for_the_ticker_is_a_new_room(fast_room, monkeypatch):
    state = _patch_universes(monkeypatch, parent={"AAPL"})
    a, b = _convene_twice(lambda u: state["compliant"].add("AAPL"))
    assert a != b


def test_a_changed_exclusion_verdict_for_the_ticker_is_a_new_room(fast_room, monkeypatch):
    state = _patch_universes(monkeypatch)
    a, b = _convene_twice(lambda u: state["fossil"].add("AAPL"))
    assert a != b


def test_another_tickers_universe_change_is_the_same_room(fast_room, monkeypatch):
    state = _patch_universes(monkeypatch)
    a, b = _convene_twice(lambda u: (state["compliant"].add("MSFT"), state["fossil"].add("XOM")))
    assert a == b


def test_unreadable_universes_run_unbanked(fast_room, monkeypatch):
    async def boom():
        raise RuntimeError("snapshot table unreachable")

    monkeypatch.setattr(rr, "default_halal_universe_async", boom)
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a != b


# ── analyst roster ────────────────────────────────────────────────────────


def test_a_changed_roster_is_a_new_room(fast_room, monkeypatch):
    full = AnalystRoster(
        present=(AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST,
                 AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST),
        withheld=(), next_step=None,
    )
    thin = AnalystRoster(
        present=(AgentId.FUNDAMENTALS_ANALYST,),
        withheld=(AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST),
        next_step=None,
    )
    current = {"r": full}
    monkeypatch.setattr(rr, "resolve_roster_for_user", lambda uid: current["r"])
    a, b = _convene_twice(lambda u: current.update(r=thin))
    assert a != b


def test_roster_digest_ignores_order_and_names_the_withheld_set():
    assert room_bank.roster_digest(()) == "none"
    one = room_bank.roster_digest((AgentId.NEWS_ANALYST, AgentId.MARKET_ANALYST))
    assert one == room_bank.roster_digest((AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST))
    assert one != room_bank.roster_digest((AgentId.NEWS_ANALYST,))


# ── plan model tier ───────────────────────────────────────────────────────


def _set_plan(u, plan):
    from app.db import get_session
    from app.db.models import User

    with get_session() as s:
        s.get(User, u).plan = plan


def _convene_with_plan_change(first, second):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(first), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        _set_plan(u, second)
        return a, await _convene(runner, u, "AAPL", m)

    return _go(go())


def test_the_same_plan_is_the_same_room(fast_room):
    a, b = _convene_with_plan_change("floor_pass", "floor_pass")
    assert a == b


@pytest.mark.parametrize("old,new", [
    ("floor_pass", "trader"),
    ("trader", "floor_manager"),
    ("floor_manager", "floor_pass"),
])
def test_a_plan_change_is_a_new_room(fast_room, old, new):
    a, b = _convene_with_plan_change(old, new)
    assert a != b


def test_plans_with_identical_tiers_are_the_same_room():
    assert room_bank.tier_digest(Plan.TRADER) == room_bank.tier_digest(Plan.TRIAL_TRADER)
    assert len({room_bank.tier_digest(p) for p in
                (Plan.FLOOR_PASS, Plan.TRADER, Plan.FLOOR_MANAGER)}) == 3


def test_tier_digest_covers_every_desk_the_room_runs():
    from app.services.tier_policy import pick_tier

    seen = []
    orig = pick_tier

    import app.services.tier_policy as tp

    tp.pick_tier = lambda plan, agent: (seen.append(agent), orig(plan, agent))[1]
    try:
        room_bank.tier_digest(Plan.TRADER)
    finally:
        tp.pick_tier = orig
    assert set(seen) == set(TWELVE_AGENT_IDS) | {AgentId.RISK_OFFICER}


# ── global settings ride in the policy version ────────────────────────────


@pytest.mark.parametrize("name", sorted(room_bank.ROOM_POLICY_SETTINGS))
def test_each_policy_setting_moves_the_policy_version(monkeypatch, name):
    before = room_bank.policy_version()
    assert before is not None
    cur = getattr(settings, name)
    flipped = {bool: lambda v: not v, int: lambda v: v + 1, float: lambda v: v + 0.01,
               str: lambda v: v + "x"}
    if name == "output_guard_mode":
        new = "enforce" if cur != "enforce" else "off"
    elif name == "room_evidence_gate_thresholds_json":
        new = '{"x": 1}'
    else:
        new = flipped[type(cur)](cur)
    object.__setattr__(settings, name, new)
    try:
        assert room_bank.policy_version() != before
    finally:
        object.__setattr__(settings, name, cur)
    assert room_bank.policy_version() == before


def test_an_operational_setting_does_not_move_the_policy_version():
    before = room_bank.policy_version()
    cur = settings.room_pace_cap_s
    object.__setattr__(settings, "room_pace_cap_s", cur + 5)
    try:
        assert room_bank.policy_version() == before
    finally:
        object.__setattr__(settings, "room_pace_cap_s", cur)


# ── guards: nothing the Room reads goes unclassified ──────────────────────


def _sample_parts() -> dict[str, str]:
    return room_bank.key_parts(
        user_id=uuid4(), ticker="A", mandate=_mandate(), sheet_hash="", policy="",
        model_root="", trading_date=date(2026, 1, 1),
        portfolio="", journal="", alpaca="", brief="", universe="", roster="", tier="",
    )


def _params(fn) -> set[str]:
    return {p for p in inspect.signature(fn).parameters if p not in ("self", "cls")}


def test_every_room_input_is_classified_keyed_or_excluded():
    actual = {
        "RoomStartRequest": set(RoomStartRequest.model_fields),
        "RoomRunner.start_run": _params(RoomRunner.start_run),
        "RoomRunner.run": _params(RoomRunner.run),
        "build_room_messages": _params(build_room_messages),
    }
    assert set(room_bank.ROOM_INPUT_CLASSES) == set(actual)
    parts = set(_sample_parts()) | {"policy"}
    for entry, names in actual.items():
        classes = room_bank.ROOM_INPUT_CLASSES[entry]
        assert set(classes) == names, (
            f"{entry}: unclassified {sorted(names - set(classes))}, "
            f"stale {sorted(set(classes) - names)}. A new Room input must be keyed in "
            "room_bank.key_parts or excluded with a reason in ROOM_INPUT_CLASSES."
        )
        for name, verdict in classes.items():
            if verdict.startswith("excluded:"):
                assert len(verdict) > len("excluded:") + 3, f"{entry}.{name} needs a reason"
                continue
            m = re.match(r"keyed:(\w+)", verdict)
            assert m and m.group(1) in parts, f"{entry}.{name}: {verdict!r} names no key part"


def test_every_key_part_is_hashed():
    assert set(_sample_parts()) == set(room_bank._HASHED_PARTS)


def test_a_room_banked_before_the_new_parts_can_still_be_rekeyed():
    old = {k: "x" for k in room_bank._HASHED_PARTS if k not in room_bank._LATE_PARTS}
    new = {**old, "brief": "", "universe": "", "roster": "", "tier": ""}
    assert room_bank.key_from_parts(old) == room_bank.key_from_parts(new)
    assert room_bank.key_from_parts({**old, "brief": "b"}) != room_bank.key_from_parts(old)


_SETTINGS_SCANNED = (
    "services/room_runner.py",
    "services/room_prompts.py",
    "services/agent_prompts.py",
    "services/output_guard.py",
    "services/entitlements.py",
    "agents/safety_floor.py",
)


def test_every_room_setting_is_policy_or_explicitly_not_keyed():
    keyed, unkeyed = room_bank.ROOM_POLICY_SETTINGS, set(room_bank.ROOM_SETTINGS_NOT_KEYED)
    assert not keyed & unkeyed
    fields = set(Settings.model_fields)
    assert (keyed | unkeyed) <= fields, sorted((keyed | unkeyed) - fields)

    declared = {f for f in fields if f.startswith(("room_", "pm_"))}
    assert declared <= keyed | unkeyed, (
        f"unclassified Room settings {sorted(declared - keyed - unkeyed)}: add to "
        "room_bank.ROOM_POLICY_SETTINGS (changes a Room) or ROOM_SETTINGS_NOT_KEYED (with why)"
    )

    read: set[str] = set()
    for rel in _SETTINGS_SCANNED:
        tree = ast.parse((APP / rel).read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "settings"
            ):
                read.add(node.attr)
    assert read <= keyed | unkeyed, (
        f"the Room modules read settings nobody classified: {sorted(read - keyed - unkeyed)}"
    )
