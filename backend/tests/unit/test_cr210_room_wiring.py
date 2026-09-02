"""CR210 — which Room calls carry a grammar, which do not, and what a bound costs.

Three things this file pins:

1. **Prose is never constrained.** The CR's first non-goal. A grammar guarantees
   form and says nothing about content, so constraining an analyst report or a
   Bull/Bear turn would measure the schema author rather than the model — vanilla
   already scores 43/44 on CR196's S1 basis rubric. Ten of the eleven prose agents
   must receive `constraint=None` even with every flag on.
2. **Off-ladder is unrepresentable in the request.** Scoped honestly: a unit test
   can prove what the REQUEST forbids, never what the model does. The second half
   — that the model tries and fails under adversarial pressure — is the live probe
   under `probes/`, and the two claims must not be conflated.
3. **A `maxLength` stop is disclosed.** It is the one truncation that fires none
   of the three existing disclosure paths, so constraining the decoder would take
   a clipped PM narration from marked to unmarked without it.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
import structlog

from app.core import config as cfg
from app.schemas.agents import AgentId
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    RoomRunner,
    _agent_constraint,
    _parse_pm_verdict,
    _PM_TRUNCATED_NARRATION,
)
from app.services.room_prompts import PM_NARRATION_MAX_CHARS

from tests.unit.test_room_runner import _FakeGateway, _collect


PM_JSON = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 100.0, "stop": 94.0, '
    '"target": 113.0, "horizon_days": 42, "narration": "Approved on the debate."}'
)


class _ConstraintRecordingGateway(_FakeGateway):
    """Remembers the constraint each agent's call carried."""

    def __init__(self):
        super().__init__(replies={"portfolio_manager": PM_JSON})
        self.constraints: list[tuple[str | None, object]] = []

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **kw):
        self.constraints.append((kw.get("audit_agent_id"), kw.get("constraint")))
        async for chunk in super().stream_chat(
            system_prompt=system_prompt, messages=messages,
            model_tier=model_tier, locale=locale, max_tokens=max_tokens,
        ):
            yield chunk


def _run(gateway, monkeypatch, *, json_on: bool, regex_on: bool):
    monkeypatch.setattr(cfg.settings, "room_json_constraints_enabled", json_on)
    monkeypatch.setattr(cfg.settings, "room_trader_regex_enabled", regex_on)
    runner = RoomRunner(llm=gateway)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    return _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))


# ── the non-goal, enforced ────────────────────────────────────────────────

PROSE_AGENTS = [
    AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST,
    AgentId.SOCIAL_MEDIA_ANALYST, AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER,
    AgentId.RESEARCH_MANAGER, AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR, AgentId.NEUTRAL_DEBATOR,
]


@pytest.mark.parametrize("agent", PROSE_AGENTS)
def test_no_prose_agent_is_ever_constrained(agent, monkeypatch):
    """Even with both flags on. The selector is keyed on the agent, not on the
    flag, so turning the feature up can never reach these turns."""
    monkeypatch.setattr(cfg.settings, "room_trader_regex_enabled", True)
    monkeypatch.setattr(cfg.settings, "room_json_constraints_enabled", True)
    assert _agent_constraint(agent, "AAPL") is None


def test_the_trader_is_the_only_constrained_prose_agent(monkeypatch):
    monkeypatch.setattr(cfg.settings, "room_trader_regex_enabled", True)
    c = _agent_constraint(AgentId.TRADER, "AAPL")
    assert c is not None and c.kind == "regex"
    assert c.name == "trader_money_block"
    assert "AAPL" in c.regex


def test_the_trader_regex_is_off_when_its_own_flag_is_off(monkeypatch):
    monkeypatch.setattr(cfg.settings, "room_trader_regex_enabled", False)
    # …even when the OTHER flag is on. Two flags, two decisions.
    monkeypatch.setattr(cfg.settings, "room_json_constraints_enabled", True)
    assert _agent_constraint(AgentId.TRADER, "AAPL") is None


def test_a_full_run_constrains_exactly_the_machine_read_surfaces(monkeypatch):
    gw = _ConstraintRecordingGateway()
    _run(gw, monkeypatch, json_on=True, regex_on=True)

    by_flow = {}
    for agent_id, constraint in gw.constraints:
        by_flow.setdefault(agent_id, []).append(constraint)

    # the PM verdict carries the schema
    assert all(c is not None and c.kind == "json_schema"
               for c in by_flow[AgentId.PORTFOLIO_MANAGER.value])
    # the Desk carries the regex
    assert all(c is not None and c.kind == "regex"
               for c in by_flow[AgentId.TRADER.value])
    # and every prose agent that spoke carried nothing
    for agent in PROSE_AGENTS:
        for c in by_flow.get(agent.value, []):
            assert c is None, agent


def test_both_flags_off_is_byte_for_byte_todays_request(monkeypatch):
    """The flags ship `false`, so landing this CR must not move production at
    all. Anti-vacuity for every test above."""
    gw = _ConstraintRecordingGateway()
    events = _run(gw, monkeypatch, json_on=False, regex_on=False)

    assert gw.constraints, "no calls were made"
    assert all(c is None for _, c in gw.constraints)
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.APPROVE.value


# ── off-ladder, scoped to what a unit test can claim ──────────────────────


def test_an_off_ladder_size_is_absent_from_the_request_the_officer_receives(monkeypatch):
    """What the REQUEST forbids — the only claim available without the network.

    The decoder cannot emit a token sequence outside an `enum`, so this is the
    whole mechanism; a probe adds that the model TRIES and fails, and that it
    would have succeeded unconstrained. Both halves are needed and neither is
    the other.
    """
    from app.services.risk_officer import build_risk_officer_schema
    from app.trading_math.option_ladder import build_option_ladder

    rows = build_option_ladder(
        reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
        cap_pts=20.0, backstop_pct=6.0,
    )
    schema = build_risk_officer_schema(rows)
    ladder = sorted({round(r.size_pct, 1) for r in rows})

    assert schema["properties"]["recommended"]["enum"] == ladder
    for off in (7.5, 0.0, -1.0, 2.25, 100.0):
        assert off not in schema["properties"]["recommended"]["enum"]

    # Each array POSITION is pinned to exactly one rung, so the ladder is covered
    # once and only once. The earlier shape — one shared enum across three slots —
    # left `[0.5, 1.5, 1.5]` representable and the model emitted it in 19 of 69
    # held-out prompts, scoring WORSE than unconstrained. Measured, then fixed.
    positions = schema["properties"]["options"]["prefixItems"]
    assert [p["properties"]["size_pct"]["enum"] for p in positions] == [[v] for v in ladder]
    assert schema["properties"]["options"]["minItems"] == len(ladder)
    assert schema["properties"]["options"]["maxItems"] == len(ladder)

    # and there is no escape hatch: no extra key, no free-form size field
    assert schema["additionalProperties"] is False
    assert all(p["additionalProperties"] is False for p in positions)


# ── the silent guillotine ─────────────────────────────────────────────────


def _ctx():
    from app.services.room_runner import _RoomContext

    return _RoomContext(
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=None,
        classification_universe=None,
        locale_allowed_universe=None,
    )


def test_a_narration_stopped_at_the_bound_is_disclosed():
    """The one truncation nothing else catches: valid JSON, `finish_reason`
    "stop", and the backend chops mid-word. Without this the grammar would take
    a clipped narration from MARKED to UNMARKED."""
    import json

    payload = json.dumps({
        "action": "PASS", "narration": "x" * PM_NARRATION_MAX_CHARS,
    })
    with structlog.testing.capture_logs() as logs:
        display, verdict = _parse_pm_verdict(payload, _ctx())

    assert _PM_TRUNCATED_NARRATION.strip() in display
    hits = [r for r in logs if r["event"] == "room_pm_narration_at_bound"]
    assert len(hits) == 1
    assert hits[0]["bound"] == PM_NARRATION_MAX_CHARS
    # the decision itself is intact — only the explanation was cut
    assert verdict is not None and verdict.action == VerdictAction.PASS


def test_a_narration_one_char_short_of_the_bound_is_not_marked():
    """Anti-vacuity. `==` is a measurement — the bound is the only length a
    maxLength stop can produce — so a shorter narration must be left alone."""
    import json

    payload = json.dumps({
        "action": "PASS", "narration": "x" * (PM_NARRATION_MAX_CHARS - 1),
    })
    with structlog.testing.capture_logs() as logs:
        display, _ = _parse_pm_verdict(payload, _ctx())

    assert _PM_TRUNCATED_NARRATION.strip() not in display
    assert not [r for r in logs if r["event"] == "room_pm_narration_at_bound"]
