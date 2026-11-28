"""CR289 — a Room pinned to a desk provider talks to that provider and no other.

The pin exists so two benchmark arms (Ling on `vllm_fallback`, CheapLLM on
`deepseek`) can run side by side on one backend without ever mixing models. These
pin the structural guarantees, not the prompts:

1. Every desk call and the CIO review of a pinned Room hit only the pinned slot.
2. A pinned slot that fails is a failed Room: it is never re-asked on ami-llm or
   the backup, never restarted on another model, and the failover state is cleared.
3. A pin on an unregistered slot refuses to run rather than falling through to the
   default model.
4. The bank key of a pinned Room is built from the PINNED slot's model root.
5. No live-traffic provider pick can reach `deepseek` or `vllm_fallback` as the
   desk of an unpinned Room.
"""

from __future__ import annotations

import ast
import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.schemas.mandate import Plan
from app.services import llm_gateway as gw
from app.services import room_runner as rr
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for, spend
from app.services.llm_gateway import LLMGateway, RoomFailoverState, arm_room_failover
from app.services.room_runner import RoomRunner, is_outage_shaped_verdict
from tests.unit.test_cr272_provider_slots_failover import _FakeProvider
from tests.unit.test_def425_shutdown_cancel_no_refund_gap import _billed_user

pytestmark = pytest.mark.allow_ledger_drift

CREDIT_COST = 12


def _gateway(*, vllm="ok", backup="ok", deepseek="ok") -> tuple[LLMGateway, dict]:
    g = LLMGateway()
    fakes = {
        "vllm": _FakeProvider("vllm", vllm),
        "vllm_fallback": _FakeProvider("vllm_fallback", backup),
        "deepseek": _FakeProvider("deepseek", deepseek),
    }
    g._providers.update(fakes)
    return g, fakes


def _run_room(g: LLMGateway, *, desk_provider: str | None):
    user_id = _billed_user()
    before = balance_for(user_id)[0]
    spend(user_id, CREDIT_COST, reason="room:AAPL:test-charge")
    runner = RoomRunner(llm=g)

    async def go():
        events = [ev async for ev in runner.run(
            user_id=user_id, ticker="AAPL",
            mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
            char_delay_min=0.0, char_delay_max=0.0, credit_cost=CREDIT_COST,
            desk_provider=desk_provider,
        )]
        return events, gw._ROOM_FAILOVER.get()

    events, leaked = asyncio.run(go())
    return events, runner.get_run(events[0].run_id), user_id, before, leaked


# ── 1. a healthy pinned Room never touches another provider ──────────────────


@pytest.mark.parametrize("slot", ["vllm_fallback", "deepseek"])
def test_pinned_room_hits_only_the_pinned_provider(slot):
    g, fakes = _gateway()
    events, run, user_id, before, leaked = _run_room(g, desk_provider=slot)

    assert fakes[slot].calls > 0
    for name, fake in fakes.items():
        if name != slot:
            assert fake.calls == 0, f"{name} was called inside a Room pinned to {slot}"
    assert not [e for e in events if e.kind == "provider_switch"]
    assert run.status == "completed"
    assert all(f"reply from {slot}" in m.content
               for m in run.transcript if m.agent_id.value != "portfolio_manager")
    review = run.verdict.verdict_review
    assert review is not None and review.provider == slot
    assert review.same_model_review is True
    assert run.verdict.llm_backup_used is False
    assert leaked is None, "the Room's failover state must not outlive the run"


def test_unpinned_room_is_unchanged_and_never_asks_the_pin_slots():
    g, fakes = _gateway()
    events, run, user_id, before, leaked = _run_room(g, desk_provider=None)

    assert fakes["vllm"].calls > 0
    assert fakes["deepseek"].calls == 0
    assert fakes["vllm_fallback"].calls == 0
    assert leaked is None


# ── 2. a failing pinned provider is a failed Room, never served elsewhere ────


@pytest.mark.parametrize("slot", ["vllm_fallback", "deepseek"])
@pytest.mark.parametrize("mode", ["http503", "connect"])
def test_pinned_failure_never_reaches_another_provider(slot, mode):
    g, fakes = _gateway(**{("backup" if slot == "vllm_fallback" else "deepseek"): mode})
    events, run, user_id, before, leaked = _run_room(g, desk_provider=slot)

    for name, fake in fakes.items():
        if name != slot:
            assert fake.calls == 0, f"{name} served a Room pinned to {slot} that failed"
    assert not [e for e in events if e.kind == "provider_switch"]
    assert run.verdict.llm_backup_used is False
    assert is_outage_shaped_verdict(run.verdict.model_dump())
    assert run.refund_recorded is True
    assert balance_for(user_id)[0] == before
    assert leaked is None


# ── 3. an unregistered pin refuses to run ────────────────────────────────────


def test_unregistered_pin_refuses_and_calls_nothing():
    g = LLMGateway()
    other = _FakeProvider("vllm", "ok")
    g._providers["vllm"] = other

    with pytest.raises(RuntimeError, match="not registered"):
        _run_room(g, desk_provider="deepseek")

    assert other.calls == 0
    assert gw._ROOM_FAILOVER.get() is None


def test_stream_chat_under_a_strict_pin_never_falls_through_to_the_default():
    g = LLMGateway()
    default = _FakeProvider("vllm", "ok")
    g._providers["vllm"] = default

    async def go():
        arm_room_failover(RoomFailoverState(pinned_provider="deepseek", strict_pin=True))
        try:
            async for _ in g.stream_chat(
                system_prompt="x",
                messages=[gw.ChatMessage(role="user", content="hi")],
            ):
                pass
        finally:
            arm_room_failover(None)

    with pytest.raises(ValueError, match="never falls through"):
        asyncio.run(go())
    assert default.calls == 0


def test_has_provider_reports_registration():
    g, _ = _gateway()
    assert g.has_provider("deepseek") and g.has_provider("vllm_fallback")
    assert not g.has_provider("kimi") and not g.has_provider("")


# ── 3b. the review follows the pin ───────────────────────────────────────────


def test_pick_review_provider_returns_the_pin_under_a_strict_pin():
    g, _ = _gateway()
    for slot in ("vllm_fallback", "deepseek"):
        arm_room_failover(RoomFailoverState(pinned_provider=slot, strict_pin=True))
        try:
            assert g.pick_review_provider() == slot
        finally:
            arm_room_failover(None)


def test_pick_review_provider_unpinned_never_returns_deepseek():
    g, _ = _gateway()
    assert g.pick_review_provider() != "deepseek"


# ── 4. the bank key of a pinned Room is built from the pinned slot's root ────


class _RootGateway(LLMGateway):
    def __init__(self, roots: dict[str | None, str | None]):
        super().__init__()
        self.roots = roots
        self.asked: list[str | None] = []

    async def room_model_root(self, provider_name: str | None = None):
        self.asked.append(provider_name)
        return self.roots.get(provider_name)


def _prepare(runner: RoomRunner, desk_provider: str | None):
    user_id = _billed_user()
    return asyncio.run(runner._prepare_bank(
        user_id=user_id, ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        roster=rr.resolve_roster_for_user(uuid4()),
        decision=runner._decide_feeds(uuid4(), "AAPL"),
        desk_provider=desk_provider,
    )), user_id


def test_pinned_bank_key_uses_the_pinned_slots_root():
    g = _RootGateway({None: "/models/ami", "deepseek": "/models/ds", "vllm_fallback": "/models/ling"})
    runner = RoomRunner(llm=g)

    ds, _ = _prepare(runner, "deepseek")
    ling, _ = _prepare(runner, "vllm_fallback")
    default, _ = _prepare(runner, None)

    assert g.asked == ["deepseek", "vllm_fallback", None]
    assert ds.parts["model_root"] == "/models/ds"
    assert ling.parts["model_root"] == "/models/ling"
    assert default.parts["model_root"] == "/models/ami"
    assert len({ds.parts["model_root"], ling.parts["model_root"], default.parts["model_root"]}) == 3


def test_pinned_room_with_an_unreadable_root_runs_unbanked_not_on_the_default_root():
    g = _RootGateway({None: "/models/ami", "deepseek": None})
    runner = RoomRunner(llm=g)

    prep, _ = _prepare(runner, "deepseek")

    assert prep.key is None and prep.parts is None
    assert "model root" in prep.reason


# ── 5. no live-traffic pick can select the benchmark slots as a desk ─────────

_BENCH = {"deepseek", "vllm_fallback"}


@pytest.mark.parametrize("tier", ["cheap", "mid", "premium"])
@pytest.mark.parametrize("locale", ["en", "ar", "ms"])
def test_unpinned_desk_pick_never_returns_a_benchmark_slot(tier, locale):
    g, _ = _gateway()
    assert g._pick_provider(locale, tier).name not in _BENCH
    assert g._active_provider_name() not in _BENCH
    assert g._review_desk() not in _BENCH
    assert not (_BENCH & set(g._PREFERENCE))


def test_no_app_call_site_opts_into_plan_routing():
    """`_pick_provider` only consults `provider_policy` (whose table routes `pro`
    to `deepseek`) when a caller passes BOTH `plan` and `agent_id`. None does; if
    one ever does, deepseek becomes reachable by live users, so this fails first."""
    app_dir = Path(__file__).resolve().parents[2] / "app"
    offenders = []
    for path in app_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "stream_chat":
                    kws = {k.arg for k in node.keywords}
                    if {"plan", "agent_id"} <= kws:
                        offenders.append(f"{path.relative_to(app_dir)}:{node.lineno}")
    assert offenders == []


@pytest.mark.parametrize("plan", list(Plan))
@pytest.mark.parametrize("tier", ["cheap", "mid", "premium"])
def test_plan_routing_without_the_benchmark_slots_registered_cannot_pick_them(plan, tier):
    g = LLMGateway()
    g._providers["vllm"] = _FakeProvider("vllm", "ok")
    picked = g._pick_provider("en", tier, plan=plan, agent_id=AgentId.MARKET_ANALYST)
    assert picked.name not in _BENCH
