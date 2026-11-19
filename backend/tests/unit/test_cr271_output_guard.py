"""CR271 (CR267 WP-13) - the deterministic output text guard.

Covers the pure rules (positive and negative tables, including the agents'
normal analyst voice), the three modes, the log-only markets heuristic, the
structured log event, each surface seam (Room desk turn, CIO narration, 1-on-1,
Brief), the replay tool's counting core, and the setting itself.
"""

from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
import structlog

from app.core.config import Settings, settings
from app.schemas import AgentId
from app.schemas.brief import BriefMode
from app.schemas.one_on_one import OneOnOneSession
from app.schemas.room import Verdict, VerdictAction
from app.services import output_guard
from app.services.coach_engine import hydrate_coach_mandate
from app.services.output_guard import check
from app.services.room_runner import RoomRunner, _guard_pm_text

from tests.unit.test_room_runner import _FakeGateway, _collect

# ── rule tables ───────────────────────────────────────────────────────────

ADVICE_POSITIVE = [
    "You should buy AAPL now.",
    "you shouldn't sell here, hold on",
    "I recommend you buy the dip.",
    "I recommend that you sell before earnings.",
    "I advise you to wait for the print.",
    "I'd advise you to hold.",
    "We suggest you sell into strength.",
    "My advice is to buy.",
    "You really must go long on this one.",
    "You need to take profits today.",
    "You should be buying here.",
    "Go ahead and sell.",
    "This is a guaranteed return.",
    "These are guaranteed profits.",
    "Trust me, you can't lose.",
    "It is a risk-free profit.",
    "You will make money on this.",
    "You'll definitely profit from the move.",
    "You are going to get rich.",
    "You ought to invest in this stock.",
    # CR271 replay: tuning must not loosen these.
    "A larger position captures more of this guaranteed return before volatility hits.",
    "This trade can't lose money.",
    "The utility earns an allowed ROE on rate base. Separately, this is a guaranteed return for you.",
    "The stock can't lose, trust me.",
    "The thesis breaks (i.e., you should buy) if Q4 beats.",
]

ADVICE_NEGATIVE = [
    # The agents' normal analytical voice: no second person, or no action.
    "The desk should buy 2% of capital.",
    "I recommend APPROVE.",
    "The bull case recommends a long position at $150.",
    "The CIO should size this at 3% with a stop at $141.",
    "We recommend the committee sell half into the target.",
    "Trader: BUY 3% at $150, stop $141, target $172.",
    # Teaching and disclaimers.
    "There are no guaranteed returns in equities.",
    "Returns are not guaranteed.",
    "Dividends are not guaranteed returns.",
    "With a stop in place you can't lose more than 2% of the position.",
    "The risk-free rate is 4.2%, so the hurdle is higher.",
    "You should review the lesson on stop placement.",
    "You should size the position at no more than 2%.",
    "You should invest time in reading the 10-K.",
    "Your mandate caps single names at 5%.",
    "A short-term pullback does not change the thesis.",
    # CR271 replay false positives (WP-13, 2026-11-19): price levels and the
    # regulated-utility term of art are not promises.
    "The 200-day average defines the line the primary uptrend cannot lose, and the stop sits there.",
    "The narrative implies the stock can't lose that ground because buybacks support the price.",
    "Regulated capex earns a guaranteed return on rate base over time.",
    "Plant that enters the regulated rate base and earns a guaranteed return.",
    "The Bull's guaranteed return on rate base argument understates regulatory lag.",
    "The decline eroded the pricing power that once guaranteed returns.",
]

ABUSE_POSITIVE = [
    "You are an idiot for holding this.",
    "You're a moron.",
    "Only a moron would short this.",
    "That is a retarded take.",
    "Go kill yourself.",
    "This is some fucking nonsense.",
    "What a shit setup.",
    "You're so stupid.",
]

ABUSE_NEGATIVE = [
    "The oxymoron of a safe leveraged ETF.",
    "Shipping costs rose and the supplier reported a delay.",
    "Growth slowed on the supply shock.",
    "The stop was hit and the position closed.",
    "Analysts raised the price target.",
    "A class action was filed against the company.",
]


@pytest.mark.parametrize("text", ADVICE_POSITIVE)
def test_advice_rule_hits(text):
    r = check(text, surface="t", mode="log")
    assert output_guard.RULE_ADVICE in r.rules, text


@pytest.mark.parametrize("text", ADVICE_NEGATIVE)
def test_advice_rule_passes_analyst_voice(text):
    r = check(text, surface="t", mode="log")
    assert output_guard.RULE_ADVICE not in r.rules, text


@pytest.mark.parametrize("text", ABUSE_POSITIVE)
def test_abuse_rule_hits(text):
    r = check(text, surface="t", mode="log")
    assert output_guard.RULE_ABUSE in r.rules, text


@pytest.mark.parametrize("text", ABUSE_NEGATIVE)
def test_abuse_rule_passes(text):
    r = check(text, surface="t", mode="log")
    assert output_guard.RULE_ABUSE not in r.rules, text


def test_hit_carries_span_not_whole_text():
    text = "Some context first. You should buy AAPL now. Then more context."
    (hit,) = [h for h in check(text, surface="t", mode="log").hits if h.rule == "advice"]
    assert hit.span == "You should buy"
    assert text[hit.start:hit.end] == hit.span


def test_empty_and_none_text_never_hit():
    for t in (None, "", "   \n"):
        assert check(t, surface="t", mode="enforce").hits == ()


# ── modes ─────────────────────────────────────────────────────────────────

ADVICE_TEXT = "You should buy AAPL now."


def test_off_mode_scans_nothing():
    r = check(ADVICE_TEXT, surface="t", mode="off")
    assert r.hits == () and not r.withhold


def test_log_mode_reports_but_never_withholds():
    r = check(ADVICE_TEXT, surface="t", mode="log")
    assert r.hits and not r.withhold


def test_enforce_mode_withholds_on_advice_and_on_abuse():
    assert check(ADVICE_TEXT, surface="t", mode="enforce").withhold
    assert check("You're an idiot.", surface="t", mode="enforce").withhold


def test_enforce_mode_leaves_clean_text_alone():
    assert not check("The desk should buy 2% of capital.", surface="t", mode="enforce").withhold


def test_default_mode_is_log_and_comes_from_settings():
    assert Settings.model_fields["output_guard_mode"].default == "log"
    r = check(ADVICE_TEXT, surface="t")
    assert r.mode == settings.output_guard_mode


def test_invalid_mode_fails_boot_not_silently_off():
    with pytest.raises(Exception):
        Settings(output_guard_mode="enfroce")


# ── markets heuristic: logs, never blocks ─────────────────────────────────

OFF_TOPIC_TEXT = (
    "The best way to make a lasagna is to layer the noodles with a slow "
    "cooked sauce, fresh basil, ricotta and plenty of cheese, then bake it "
    "in a hot oven until the top is golden brown and the edges are bubbling "
    "away nicely before letting it rest for ten minutes on the counter."
)
ON_TOPIC_TEXT = (
    "AAPL trades at 28x earnings with revenue growth of 6% and a 25% operating "
    "margin; the RSI is 58, volume is above average and the stop sits at $141 "
    "against a target of $172, a reward to risk ratio of 2.1 for the position."
)


def test_off_topic_heuristic_flags_long_non_market_text():
    r = check(OFF_TOPIC_TEXT, surface="t", mode="log")
    assert output_guard.RULE_OFF_TOPIC in r.rules


def test_off_topic_heuristic_passes_market_text_and_short_text():
    assert output_guard.RULE_OFF_TOPIC not in check(ON_TOPIC_TEXT, surface="t", mode="log").rules
    assert check("Nice weather today.", surface="t", mode="log").hits == ()


@pytest.mark.parametrize("mode", ["off", "log", "enforce"])
def test_off_topic_never_withholds_in_any_mode(mode):
    r = check(OFF_TOPIC_TEXT, surface="t", mode=mode)
    assert r.withhold is False
    assert output_guard.RULE_OFF_TOPIC not in output_guard.ENFORCING_RULES
    if mode != "off":
        assert r.hits and all(not h.enforcing for h in r.hits)


# ── structured log event ──────────────────────────────────────────────────


def test_hit_logs_structured_event_without_full_text(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "log")
    long_tail = " filler" * 200
    text = ADVICE_TEXT + long_tail
    with structlog.testing.capture_logs() as logs:
        output_guard.inspect(
            text, surface="room_turn", agent_id="trader", run_id="run-1",
        )
    events = [e for e in logs if e["event"] == "output_guard_hit"]
    assert {e["rule"] for e in events} == {"advice", "off_topic"}
    assert all(len(e["span"]) <= output_guard.SPAN_LOG_CHARS for e in events)
    (ev,) = [e for e in events if e["rule"] == "advice"]
    assert ev["surface"] == "room_turn"
    assert ev["rule"] == "advice"
    assert ev["mode"] == "log"
    assert ev["agent_id"] == "trader" and ev["run_id"] == "run-1"
    assert ev["already_streamed"] is False
    assert ev["span"] == "You should buy"
    assert long_tail not in str(ev)


def test_no_event_when_off_or_clean(monkeypatch):
    with structlog.testing.capture_logs() as logs:
        monkeypatch.setattr(settings, "output_guard_mode", "off")
        output_guard.inspect(ADVICE_TEXT, surface="s")
        monkeypatch.setattr(settings, "output_guard_mode", "enforce")
        output_guard.inspect("The desk should buy 2% of capital.", surface="s")
    assert [e for e in logs if e["event"] == "output_guard_hit"] == []


# ── Room desk turn seam ───────────────────────────────────────────────────

BAD_TRADER = (
    "[STANCE: for | CONVICTION: high | HEADLINE: trader view]\n"
    "Trader: you should buy this now, guaranteed returns."
)


def _run_room(replies):
    runner = RoomRunner(llm=_FakeGateway(replies=replies))  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    run_id = events[0].run_id
    transcript = runner.get_run(run_id).transcript
    verdict = next(e.verdict for e in events if e.kind == "verdict")
    return events, transcript, verdict


def _trader_streamed(events) -> str:
    return "".join(
        e.text or "" for e in events
        if e.kind == "agent_token" and e.agent_id == AgentId.TRADER.value
    )


def _trader_stored(transcript) -> str:
    return next(m.content for m in transcript if m.agent_id == AgentId.TRADER.value)


def test_room_turn_enforce_takes_the_scripted_fallback_path(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    with structlog.testing.capture_logs() as logs:
        events, transcript, verdict = _run_room({"trader": BAD_TRADER})

    assert "guaranteed returns" not in _trader_streamed(events)
    assert "guaranteed returns" not in _trader_stored(transcript)
    assert _trader_streamed(events), "the scripted template was streamed instead"
    # labelled and counted as scripted, like a transport failure
    assert AgentId.TRADER.value in (verdict.scripted_agents or [])
    reasons = [
        e["reason"] for e in logs
        if e["event"] == "room_agent_scripted_fallback" and e["agent_id"] == "trader"
    ]
    assert reasons == ["output_guard"]
    hit = [e for e in logs if e["event"] == "output_guard_hit" and e["agent_id"] == "trader"]
    assert hit and hit[0]["surface"] == "room_turn" and hit[0]["withheld"] is True
    assert hit[0]["run_id"] == str(events[0].run_id)


def test_room_turn_log_mode_logs_and_leaves_text_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "log")
    with structlog.testing.capture_logs() as logs:
        events, transcript, verdict = _run_room({"trader": BAD_TRADER})

    assert "guaranteed returns" in _trader_stored(transcript)
    assert "guaranteed returns" in _trader_streamed(events)
    assert AgentId.TRADER.value not in (verdict.scripted_agents or [])
    hit = [e for e in logs if e["event"] == "output_guard_hit" and e["agent_id"] == "trader"]
    assert hit and hit[0]["withheld"] is False


def test_room_turn_off_mode_changes_and_logs_nothing(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "off")
    with structlog.testing.capture_logs() as logs:
        _events, transcript, verdict = _run_room({"trader": BAD_TRADER})
    assert "guaranteed returns" in _trader_stored(transcript)
    assert [e for e in logs if e["event"] == "output_guard_hit"] == []


# ── CIO / PM narration seam ───────────────────────────────────────────────

BAD_PM = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
    '"target": 172, "horizon_days": 42, '
    '"narration": "You should buy more of this, guaranteed returns."}'
)


def _pm_message(transcript) -> str:
    return next(
        m.content for m in transcript
        if m.agent_id == AgentId.PORTFOLIO_MANAGER.value
    )


def test_pm_narration_enforce_replaces_rationale_not_the_decision(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "log")
    _e, t_log, v_log = _run_room({"portfolio_manager": BAD_PM})
    assert "guaranteed returns" in _pm_message(t_log)

    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    events, transcript, verdict = _run_room({"portfolio_manager": BAD_PM})
    sentinel = "AMI withheld this explanation because it read as personal advice"
    assert sentinel in _pm_message(transcript)
    assert "guaranteed returns" not in _pm_message(transcript)
    assert "guaranteed returns" not in (verdict.reason or "")
    assert sentinel in verdict.reason
    pm_streamed = "".join(
        e.text or "" for e in events
        if e.kind == "agent_token" and e.agent_id == AgentId.PORTFOLIO_MANAGER.value
    )
    assert "guaranteed returns" not in pm_streamed
    # the guard never changes the action or the numbers
    assert verdict.action == v_log.action
    assert verdict.size_pct == v_log.size_pct


def test_guard_pm_text_unit_modes(monkeypatch):
    v = Verdict(action=VerdictAction.PASS, reason="You should sell now.")
    monkeypatch.setattr(settings, "output_guard_mode", "log")
    assert _guard_pm_text("You should sell now.", v, run_id=uuid4()) == (
        "You should sell now.", v,
    )
    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    text, v2 = _guard_pm_text("You should sell now.", v, run_id=uuid4())
    assert text.startswith("AMI withheld")
    assert v2.reason.startswith("AMI withheld")
    assert v2.action == VerdictAction.PASS
    clean = Verdict(action=VerdictAction.PASS, reason="The debate does not support entry.")
    assert _guard_pm_text("clean", clean, run_id=uuid4()) == ("clean", clean)


# ── 1-on-1 seam ───────────────────────────────────────────────────────────


class _StreamGateway:
    """Yields a fixed reply in chunks; stands in for LLMGateway."""

    def __init__(self, reply: str):
        self._reply = reply

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, meta=None, **_kw):
        mid = len(self._reply) // 2
        yield self._reply[:mid]
        yield self._reply[mid:]


def _one_on_one_session(user_id):
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    from datetime import datetime, timezone
    return OneOnOneSession(
        id=uuid4(),
        agent_id=AgentId.TRADER,
        started_at=datetime.now(timezone.utc),
        mandate_used=mandate.model_dump(mode="json"),
        locale=mandate.locale,
        user_id=user_id,
    )


def _drive_one_on_one(reply, monkeypatch, *, meta):
    from app.services import audit
    from app.services.agent_runner import AgentRunner

    stored: list[str] = []
    monkeypatch.setattr(
        audit, "record_one_on_one_message",
        lambda **kw: stored.append(kw["content"]) if kw["role"] == "assistant" else None,
    )
    runner = AgentRunner(_StreamGateway(reply))  # type: ignore[arg-type]
    session = _one_on_one_session(uuid4())

    async def go():
        return "".join([c async for c in runner.stream_one_on_one_message(
            session=session, history=[], user_message="hello", meta=meta,
        )])

    return asyncio.run(go()), stored


def test_one_on_one_enforce_buffering_consumer_gets_sentinel_and_stores_it(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    meta = {output_guard.META_CONSUMER_BUFFERS: True}
    with structlog.testing.capture_logs() as logs:
        _yielded, stored = _drive_one_on_one(ADVICE_TEXT, monkeypatch, meta=meta)
    sentinel = meta[output_guard.META_SENTINEL]
    assert sentinel.startswith("AMI withheld this reply")
    assert stored == [sentinel]
    (ev,) = [e for e in logs if e["event"] == "output_guard_hit"]
    assert ev["surface"] == "one_on_one" and ev["already_streamed"] is False


def test_one_on_one_enforce_live_consumer_cannot_withhold_and_says_so(monkeypatch):
    """A consumer that did not declare buffering has already shown the chunks:
    the hit is logged `already_streamed=true`; the stored copy is still the
    sentinel (the only part AMI still controls)."""
    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    with structlog.testing.capture_logs() as logs:
        yielded, stored = _drive_one_on_one(ADVICE_TEXT, monkeypatch, meta={})
    assert yielded == ADVICE_TEXT
    assert stored and stored[0].startswith("AMI withheld")
    (ev,) = [e for e in logs if e["event"] == "output_guard_hit"]
    assert ev["already_streamed"] is True


def test_one_on_one_log_mode_stores_text_unchanged(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "log")
    meta = {output_guard.META_CONSUMER_BUFFERS: True}
    _yielded, stored = _drive_one_on_one(ADVICE_TEXT, monkeypatch, meta=meta)
    assert stored == [ADVICE_TEXT]
    assert output_guard.META_SENTINEL not in meta


def test_one_on_one_api_replaces_the_buffered_reply(monkeypatch):
    """End to end through the HTTP handler: the SSE frame carries the sentinel,
    never the advice."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.one_on_one import router
    from app.services import agent_runner as agent_runner_mod
    from tests.unit.test_def424_llm_down_branded_fallback import _new_user

    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    runner = agent_runner_mod.AgentRunner(_StreamGateway(ADVICE_TEXT))  # type: ignore[arg-type]
    app = FastAPI()
    app.include_router(router)
    # One shared runner: `start` stores the session on it, `message` reads it.
    from app.api.one_on_one import get_agent_runner as dep
    app.dependency_overrides[dep] = lambda: runner
    client = TestClient(app, raise_server_exceptions=False)

    _uid, headers = _new_user()
    start = client.post(
        "/v1/agents/one_on_one/start", json={"agent_id": "trader"}, headers=headers,
    )
    assert start.status_code == 201, start.text
    r = client.post(
        "/v1/agents/one_on_one/message",
        json={"session_id": start.json()["id"], "user_message": "hello"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert "You should buy" not in r.text
    assert "AMI withheld this reply" in r.text


# ── Brief seam ────────────────────────────────────────────────────────────


def _drive_brief(reply):
    from app.services.brief_engine import BriefEngine, hydrate_brief_mandate
    from app.services.overlay_store import OverlayStore

    engine = BriefEngine(_StreamGateway(reply), OverlayStore())  # type: ignore[arg-type]
    mandate = hydrate_brief_mandate({"plan": "trader", "user_id": str(uuid4())})
    session, _, _ = engine.open_session(
        user_id=uuid4(), agent_id=AgentId.BEAR_RESEARCHER,
        mode=BriefMode.FROM_SCRATCH, mandate=mandate,
    )

    async def go():
        return [c async for c in engine.stream_chat(
            session=session, history=[], user_message="coach me",
        )]

    return asyncio.run(go())


def test_brief_streams_live_so_hit_is_logged_already_streamed(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "log")
    with structlog.testing.capture_logs() as logs:
        chunks = _drive_brief(ADVICE_TEXT)
    assert "".join(chunks) == ADVICE_TEXT
    (ev,) = [e for e in logs if e["event"] == "output_guard_hit"]
    assert ev["surface"] == "brief" and ev["already_streamed"] is True


def test_brief_enforce_cannot_withhold_but_appends_a_retraction(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    chunks = _drive_brief(ADVICE_TEXT)
    assert "".join(chunks).startswith(ADVICE_TEXT)
    assert len(chunks) == 3 and "AMI flags the reply above" in chunks[-1]


def test_brief_clean_reply_gets_no_notice(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "enforce")
    assert "".join(_drive_brief("The desk should buy 2% of capital.")) == (
        "The desk should buy 2% of capital."
    )


# ── replay tool ───────────────────────────────────────────────────────────


def _load_replay():
    path = Path(__file__).resolve().parents[2] / "scripts" / "output_guard_replay.py"
    spec = importlib.util.spec_from_file_location("output_guard_replay", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_replay_counts_hits_per_rule_and_surface_on_in_memory_rows():
    replay = _load_replay()
    rows = [
        {"flow": "room", "agent_id": "trader", "response_text": "You should buy AAPL now."},
        {"flow": "room", "agent_id": "bull_researcher", "response_text": "Bull: 4% size, RSI 58."},
        {"flow": "room_pm", "agent_id": "portfolio_manager", "response_text": "guaranteed returns"},
        {"flow": "one_on_one", "agent_id": "trader", "response_text": "You're an idiot."},
        {"flow": "one_on_one", "agent_id": "trader", "response_text": OFF_TOPIC_TEXT},
        {"flow": "coach_chat", "agent_id": "bear_researcher", "response_text": None},
        {"flow": "translate", "agent_id": None, "response_text": "You should buy"},
    ]
    out = replay.summarize(rows)
    assert out["rows_scanned"] == 6  # the translate flow is not a user-visible agent surface
    assert out["scanned_per_flow"] == {"room": 2, "room_pm": 1, "one_on_one": 2, "coach_chat": 1}
    assert out["hits_per_rule"] == {"advice": 2, "abuse": 1, "off_topic": 1}
    assert out["hits_per_surface_and_rule"] == {
        "room_turn": {"advice": 1},
        "room_verdict": {"advice": 1},
        "one_on_one": {"abuse": 1, "off_topic": 1},
    }
    assert out["rows_with_any_hit_per_flow"] == {"room": 1, "room_pm": 1, "one_on_one": 2}
    # off_topic alone never counts as "would be withheld"
    assert out["rows_that_would_be_withheld"] == 3
    spans = {s["span"] for s in out["samples"]["advice"]}
    assert spans == {"You should buy", "guaranteed returns"}


def test_replay_sample_cap_and_no_full_text():
    replay = _load_replay()
    rows = [
        {"flow": "room", "agent_id": "x", "response_text": "You should buy " + "z" * 500}
        for _ in range(30)
    ]
    out = replay.summarize(rows, samples_per_rule=3)
    assert out["hits_per_rule"]["advice"] == 30
    assert len(out["samples"]["advice"]) == 3
    assert all(len(s["span"]) <= 80 for s in out["samples"]["advice"])


def test_replay_refuses_a_non_postgres_url():
    replay = _load_replay()
    with pytest.raises(SystemExit):
        replay.require_postgres("sqlite:///x.db")
    replay.require_postgres("postgresql://u:p@h/db")
    replay.require_postgres("postgresql+psycopg2://u:p@h/db")
