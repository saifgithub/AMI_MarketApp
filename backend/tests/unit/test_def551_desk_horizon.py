"""DEF551 — the Room reads the Execution Desk's stated horizon instead of the 6-week constant.

`ctx.trader_horizon_weeks` (6) was never replaced by what the desk said, so every consumer saw 42
days while the desks' plans said 57 to 210. These tests pin: the parser, the runner's adoption of
the desk's `Time horizon:` line (live, absent, unreadable, scripted), each consumer that now reads
it, the consumers that deliberately do not, and the CIO-retry snapshot round trip.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.schemas import AgentId
from app.schemas.agents import AgentMessage
from app.schemas.room import RoomRun
from app.services import room_runner
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    _RoomContext,
    _adopt_desk_horizon,
    _build_cio_context_snapshot,
    _coded_transcript,
    _parse_pm_verdict,
    _rebuild_ctx_from_snapshot,
    _trade_horizon_days,
)
from app.services.stated_horizon import desk_horizon_days, parse_stated_horizon_days


@pytest.mark.parametrize("phrase,days", [
    ("8 weeks", 56), ("6-8 weeks", 56), ("6 to 8 weeks", 56), ("90 days", 90),
    ("3 months", 91), ("12 months", 365), ("12-18 months", 548), ("1 year", 365),
    ("~6 wks", 42), ("2 weeks to 3 months", 91), ("**4 weeks**", 28),
    ("12+ months", 365), ("1 quarter", 91), ("1–2 quarters", 182), ("2+ years", 730),
    ("2027 Q2", None), ("until the Q3 print", None), ("", None), (None, None), ("20 minutes", None),
    ("0 days", None), ("10 years", None), ("TBD", None),
])
def test_the_phrase_parser(phrase, days):
    assert parse_stated_horizon_days(phrase) == days


def test_the_line_is_found_in_a_markdown_money_block():
    text = "[STANCE: for]\nSide: BUY\nSize: 3.00% of portfolio\n**Time horizon:** 6-8 weeks\nR:R: 2.1:1\n"
    assert desk_horizon_days(text) == (56, "6-8 weeks")
    assert desk_horizon_days("no money block here") == (None, None)
    assert desk_horizon_days("Time horizon: until the print") == (None, "until the print")


def _ctx(scripted=()):
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3, "single_name_cap_pct": 3.0})
    ctx = _RoomContext(
        ticker="AAPL", mandate=mandate, portfolio_value=100_000.0,
        current_drawdown_pct=0.0, halal_universe=set(),
        classification_universe=None, locale_allowed_universe=None,
        user_id=uuid4(), sector_holdings=[], sector_marks={},
        risk_last_loss_closed_at=None, risk_trade_open_timestamps=[],
        risk_existing_open_risk_pct=0.0, profile={},
    )
    ctx.scripted_turns = list(scripted)
    return ctx


def _run(trader_text):
    now = datetime.now(UTC)
    turns = [(AgentId.RESEARCH_MANAGER, "Synthesis. Time horizon: 99 days (not the desk)")]
    if trader_text is not None:
        turns.append((AgentId.TRADER, trader_text))
    return RoomRun(
        id=uuid4(), user_id=uuid4(), ticker="AAPL", triggered_at=now, mandate_version=1,
        model_tier="mid", credit_cost=1,
        transcript=[AgentMessage(agent_id=a, role="agent", content=c, timestamp=now) for a, c in turns],
    )


def test_a_live_desk_horizon_replaces_the_default():
    ctx = _ctx()
    assert _trade_horizon_days(ctx) == 42 and ctx.trader_horizon_source == "default"
    _adopt_desk_horizon(ctx, _run("Side: BUY\nSize: 3.00% of portfolio\nTime horizon: 6-8 weeks\n"))
    assert (ctx.trader_horizon_days, ctx.trader_horizon_source, ctx.trader_horizon_phrase) == (
        56, "desk", "6-8 weeks")
    assert _trade_horizon_days(ctx) == 56
    assert ctx.trader_horizon_weeks == 6  # the default itself is untouched


def test_only_the_execution_desks_line_counts():
    ctx = _ctx()
    _adopt_desk_horizon(ctx, _run("Side: WAIT\nSize: 0.00% of portfolio\nTime horizon: 3 months\n"))
    assert ctx.trader_horizon_days == 91  # not the Research Manager's 99 days


@pytest.mark.parametrize("text", [
    "Side: BUY\nTime horizon: until the print\n", "Side: BUY\nno horizon line\n", None,
])
def test_an_absent_or_unreadable_horizon_falls_back_loudly(text, monkeypatch):
    warnings = []
    monkeypatch.setattr(room_runner.logger, "warning", lambda event, **kw: warnings.append((event, kw)))
    ctx = _ctx()
    _adopt_desk_horizon(ctx, _run(text), uuid4())
    assert ctx.trader_horizon_days is None and ctx.trader_horizon_source == "default"
    assert _trade_horizon_days(ctx) == 42
    assert [e for e, _ in warnings] == ["room_desk_horizon_unread"]
    assert warnings[0][1]["default_days"] == 42


def test_a_scripted_desk_is_recorded_as_scripted_and_never_read_back():
    ctx = _ctx(scripted=[AgentId.TRADER])
    _adopt_desk_horizon(ctx, _run("Time horizon: 6 weeks."))
    assert ctx.trader_horizon_days is None and ctx.trader_horizon_source == "scripted"
    assert _trade_horizon_days(ctx) == 42


def test_adoption_resets_an_earlier_read():
    ctx = _ctx()
    _adopt_desk_horizon(ctx, _run("Side: BUY\nTime horizon: 8 weeks\n"))
    _adopt_desk_horizon(ctx, _run("Side: BUY\nTime horizon: soon\n"))
    assert ctx.trader_horizon_days is None and ctx.trader_horizon_phrase == "soon"


# consumers


def test_the_terminal_inputs_carry_the_desk_horizon_and_its_source():
    ctx = _ctx()
    run = _run("Side: BUY\nSize: 3.00% of portfolio\nEntry: $200.00\nTime horizon: 210 days\n")
    _adopt_desk_horizon(ctx, run)
    inputs = _coded_transcript(uuid4(), ctx, run).terminal_inputs
    assert inputs["horizon_days"] == 210 and inputs["horizon_source"] == "desk"
    assert inputs["horizon_phrase"] == "210 days"


def test_the_terminal_inputs_say_when_the_desk_horizon_was_not_read():
    ctx = _ctx()
    run = _run("Side: BUY\nTime horizon: soon\n")
    _adopt_desk_horizon(ctx, run)
    inputs = _coded_transcript(uuid4(), ctx, run).terminal_inputs
    assert inputs["horizon_days"] is None and inputs["horizon_source"] == "default"


_PM_NO_HORIZON = json.dumps({
    "action": "APPROVE", "size_pct": 3.0, "entry": 100.0, "stop": 94.0, "target": 113.0,
    "narration": "ok",
})


def test_a_pm_verdict_that_states_no_horizon_inherits_the_desks():
    ctx = _ctx()
    _adopt_desk_horizon(ctx, _run("Side: BUY\nTime horizon: 10 weeks\n"))
    _, verdict = _parse_pm_verdict(_PM_NO_HORIZON, ctx)
    assert verdict.time_horizon_days == 70


def test_a_pm_verdict_that_states_a_horizon_keeps_its_own():
    ctx = _ctx()
    _adopt_desk_horizon(ctx, _run("Side: BUY\nTime horizon: 10 weeks\n"))
    raw = json.dumps({**json.loads(_PM_NO_HORIZON), "horizon_days": 30})
    assert _parse_pm_verdict(raw, ctx)[1].time_horizon_days == 30


def test_the_pm_fallback_without_a_desk_horizon_is_the_old_42_days():
    _, verdict = _parse_pm_verdict(_PM_NO_HORIZON, _ctx())
    assert verdict.time_horizon_days == 42


def test_the_option_menu_keeps_the_pre_desk_default_by_construction():
    """The menu is built before the desk speaks (and rebuilt identically on a CIO retry); a
    horizon the desk has not stated yet cannot feed it."""
    import inspect
    src = inspect.getsource(room_runner)
    assert src.count("horizon_days=ctx.trader_horizon_weeks * 7") == 2


# the CIO-retry snapshot


def test_the_snapshot_round_trips_the_desk_horizon_and_reads_an_old_one():
    ctx = _ctx()
    _adopt_desk_horizon(ctx, _run("Side: BUY\nTime horizon: 10 weeks\n"))
    snap = _build_cio_context_snapshot(ctx, {})
    assert (snap["trader_horizon_days"], snap["trader_horizon_source"]) == (70, "desk")

    kw = dict(
        user_id=uuid4(), mandate=ctx.mandate, portfolio_value=1.0, current_drawdown_pct=0.0,
        halal_universe=set(), classification_universe=None, sector_holdings=[], sector_marks={},
        sector_map=None, sector_weights={}, risk_last_loss_closed_at=None,
        risk_trade_open_timestamps=[], risk_existing_open_risk_pct=0.0, portfolio_snapshot=None,
    )
    assert _rebuild_ctx_from_snapshot(snap, **kw).trader_horizon_days == 70

    old = {k: v for k, v in snap.items() if not k.startswith("trader_horizon_") or k == "trader_horizon_weeks"}
    rebuilt = _rebuild_ctx_from_snapshot(old, **kw)
    assert rebuilt.trader_horizon_days is None and rebuilt.trader_horizon_source == "default"
