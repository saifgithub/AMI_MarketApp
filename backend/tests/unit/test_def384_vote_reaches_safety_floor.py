"""DEF384 — the PM self-consistency vote must not route around the safety floor.

`room_runner`'s verdict block had three branches — voted / LLM-outage / single
draw — and only the LAST one reached `enforce_safety_floor`. The vote branch
assigned its winning `Verdict` straight to `verdict` and fell through to the UI
restream, so raising `pm_self_consistency_samples` above 1 silently disabled
every deterministic mandate check on the live-PM path: post-loss cooldown,
over-trading brake, open-risk cap, sector cap, halal and locale universes,
drawdown cap. The floor is uncoachable by design (`CLAUDE.md`); a sampling knob
must not be able to switch it off.

It had never fired in production only because CR197 shipped that knob at 1.
CR214 raises it to 5, so **the commit that changes the default is the commit
that first runs the code** — the same shape as DEF383, found in the same hour,
and the reason a defaulted-off branch deserves tests that force it on.

These tests force BOTH sample counts explicitly rather than relying on the
shipped default. A test that only exercised the default would go quiet the day
someone tuned the knob, which is precisely the failure being pinned.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

import app.agents.safety_floor as safety_floor
from app.core.config import settings
from app.schemas.room import VerdictAction
from app.services import room_runner
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import RoomRunner
from app.services.sim_engine import get_sim_engine

from tests.unit.test_cr101_be2_round2_room_wiring import (
    _FIXED_NOW,
    _collect,
    _FrozenClock,
    _insert_trade,
    _LiberalPmGateway,
)

pytestmark = pytest.mark.allow_ledger_drift


@pytest.mark.parametrize("samples", [1, 5])
def test_the_floor_vetoes_a_cooldown_approve_at_every_sample_count(
    monkeypatch: pytest.MonkeyPatch, samples: int
):
    """The PM always APPROVEs here, so any REJECT is the deterministic floor.

    At samples=5 the voted branch is the one under test; at samples=1 it is the
    single-draw branch. Both must land on the same veto — the number of times we
    ask the model is not a policy input."""
    monkeypatch.setattr(safety_floor, "datetime", _FrozenClock)
    monkeypatch.setattr(settings, "pm_self_consistency_samples", samples)

    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3}).model_copy(
        update={"post_loss_cooldown_hours": 24.0}
    )
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)
    _insert_trade(
        user_id, ticker="TSLA", status="lost",
        opened_at=_FIXED_NOW - timedelta(days=2),
        closed_at=_FIXED_NOW - timedelta(minutes=1),
    )
    events = _collect(RoomRunner(llm=_LiberalPmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=sim.total_value(user_id),
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")

    assert v.action == VerdictAction.REJECT.value, (
        f"samples={samples}: the mandate floor did not veto an APPROVE made "
        "during an active post-loss cooldown — DEF384"
    )
    assert v.overridden_from_llm is True
    # Pin the veto only the WIRED path can produce (the computed lift time), not
    # the loud missing-context fallback, which also contains "cooldown".
    assert any("active until" in vio.lower() for vio in v.violations), v.violations


def test_the_vote_carries_its_score_through_the_floors_override(
    monkeypatch: pytest.MonkeyPatch,
):
    """CR214's `approve_votes` must survive the override. The floor builds a
    FRESH Verdict on REJECT, so a field it does not name is dropped — and this is
    the row where the score matters most: a 5/5 approve the floor vetoed is a very
    different observation from a 0/5."""
    monkeypatch.setattr(safety_floor, "datetime", _FrozenClock)
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 5)

    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3}).model_copy(
        update={"post_loss_cooldown_hours": 24.0}
    )
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)
    _insert_trade(
        user_id, ticker="TSLA", status="lost",
        opened_at=_FIXED_NOW - timedelta(days=2),
        closed_at=_FIXED_NOW - timedelta(minutes=1),
    )
    events = _collect(RoomRunner(llm=_LiberalPmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=sim.total_value(user_id),
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")

    assert v.action == VerdictAction.REJECT.value
    assert v.samples == 5
    assert v.approve_votes == 5, (
        "the unanimous APPROVE that the floor overrode should still read 5/5"
    )


def test_there_is_exactly_one_enforce_safety_floor_call_in_the_verdict_block():
    """Structural guard. The fix routes all branches through ONE call site; the
    obvious wrong fix is to paste a second one into the vote branch. CR101-BE2
    round 1 is the precedent — a call site that omitted five kwargs — and two
    copies is how that returns."""
    tree = ast.parse(Path(room_runner.__file__).read_text())
    calls = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Name)
        and n.func.id == "enforce_safety_floor"
    ]
    assert len(calls) == 1, (
        f"expected exactly 1 enforce_safety_floor call site, found {len(calls)} "
        f"at lines {[c.lineno for c in calls]} — DEF384"
    )


def test_the_vote_branch_does_not_assign_the_final_verdict():
    """The bug in one line: `pm_text, verdict, _agreement = _voted` short-circuited
    the decision tail. It must bind `parsed`, which the floor then judges."""
    src = Path(room_runner.__file__).read_text()
    assert "pm_text, parsed, _agreement = _voted" in src
    assert "pm_text, verdict, _agreement = _voted" not in src, (
        "the vote branch is assigning the final verdict again — DEF384"
    )
