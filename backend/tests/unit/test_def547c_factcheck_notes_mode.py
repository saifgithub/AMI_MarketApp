"""DEF547 round 3 — `ROOM_FACTCHECK_NOTES`: the quotation checks keep running and
logging, and (in `log` mode) stop writing into user-visible Room text.

Saiful, 2026-11-25: "Dilemma + log-only meanwhile". `annotate` is the code default
(today's behaviour); Alpha sets `log`. Covered here: every surface the checks write
to (the agent-text note, the CIO's kill criterion, a nulled stance headline, the Risk
Officer's `[AMI: unverifiable]` tag; CR288: the Risk Officer's headline demotion happens in both modes), the finding log's fields,
the unknown-value refusal, and that the mode rides in the Room policy version.
"""

from __future__ import annotations

import json
from uuid import uuid4

import pytest
import structlog
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.schemas.agents import AgentId
from app.services import numeric_quotation as nq
from app.services import room_bank
from app.services.coach_engine import hydrate_coach_mandate
from app.services.risk_officer import (
    _UNVERIFIABLE_MARK,
    _rung_derived_headline,
    render_officer_turns,
)
from app.services.room_runner import _RoomContext, _parse_pm_verdict
from app.trading_math.option_ladder import build_option_ladder

_SHEET = {"pe": 60.0}
_WRONG = "The trailing P/E of 25 looks cheap."
_ROWS = build_option_ladder(
    reference_size_pct=3.0, entry=100.0, stop=94.0, target=113.0,
    cap_pts=30.0, current_drawdown_pct=0.0,
)


@pytest.fixture
def mode(monkeypatch):
    def _set(value: str) -> None:
        monkeypatch.setattr(settings, "room_factcheck_notes", value)
    return _set


@pytest.fixture(autouse=True)
def _uncached_logger(monkeypatch):
    """`cache_logger_on_first_use` freezes a module logger's processors the first
    time any earlier test makes it emit, which blinds `capture_logs`; a fresh
    proxy per test is not frozen."""
    monkeypatch.setattr(nq, "logger", structlog.get_logger())


def _findings(logs):
    return [e for e in logs if e.get("event") == "room_factcheck_finding"]


def _ctx(profile):
    return _RoomContext(
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        halal_universe=set(),
        classification_universe=None,
        locale_allowed_universe=None,
        profile=profile,
    )


def _payload(**kw):
    p = {
        "options": [
            {"size_pct": s, "case_for": "f", "case_against": "a", "key_number": f"kn-{s}"}
            for s in (1.5, 3.0, 5.0)
        ],
        "recommended": 3.0,
        "confidence": "medium",
        "decisive_number": "0.18",
    }
    p.update(kw)
    return p


# ── the setting ───────────────────────────────────────────────────────────


def test_default_is_log():
    assert Settings.model_fields["room_factcheck_notes"].default == "log"


def test_unknown_value_refuses_at_startup():
    with pytest.raises(ValidationError):
        Settings(room_factcheck_notes="silent")


def test_the_runtime_reader_refuses_an_unknown_value_too(mode):
    mode("silent")
    with pytest.raises(ValueError, match="ROOM_FACTCHECK_NOTES"):
        nq.factcheck_notes_mode()
    with pytest.raises(ValueError):
        nq.annotate_sheet_mismatches(_WRONG, _SHEET)


def test_the_mode_is_part_of_the_room_policy_version(mode):
    assert "room_factcheck_notes" in room_bank.ROOM_POLICY_SETTINGS
    mode("annotate")
    a = room_bank.policy_version()
    mode("log")
    assert room_bank.policy_version() != a


# ── sheet-figure check: agent text ────────────────────────────────────────


def test_annotate_mode_writes_the_note_and_logs(mode):
    mode("annotate")
    with structlog.testing.capture_logs() as logs:
        out = nq.annotate_sheet_mismatches(
            _WRONG, _SHEET, surface="agent_text", run_id=uuid4(),
            agent_id=AgentId.FUNDAMENTALS_ANALYST,
        )
    assert "AMI checked" in out and "figures of record" in out
    (f,) = _findings(logs)
    assert f["text_changed"] is True and f["mode"] == "annotate"


def test_log_mode_leaves_the_text_untouched_and_logs_every_field(mode):
    mode("log")
    run_id = uuid4()
    with structlog.testing.capture_logs() as logs:
        out = nq.annotate_sheet_mismatches(
            _WRONG, _SHEET, surface="agent_text", run_id=run_id,
            agent_id=AgentId.FUNDAMENTALS_ANALYST,
        )
    assert out == _WRONG
    (f,) = _findings(logs)
    assert f["run_id"] == str(run_id)
    assert f["agent_id"] == AgentId.FUNDAMENTALS_ANALYST.value
    assert f["surface"] == "agent_text"
    assert f["checker"] == "sheet_figure"
    assert f["claimed"] == "25"
    assert f["sheet_field"] == "pe_trailing"
    assert f["sheet_value"] == 60.0
    assert f["mode"] == "log" and f["text_changed"] is False


def test_log_mode_a_clean_turn_logs_nothing(mode):
    mode("log")
    with structlog.testing.capture_logs() as logs:
        assert nq.annotate_sheet_mismatches("The P/E of 60 is rich.", _SHEET) == (
            "The P/E of 60 is rich."
        )
    assert _findings(logs) == []


# ── kill criterion (the verdict card) ─────────────────────────────────────


def _kill(mode_value, mode_setter, run_id):
    mode_setter(mode_value)
    text = json.dumps({
        "action": "PASS",
        "narration": "The synthesis holds and the mandate clears here today.",
        "kill_criterion": "A daily close where the P/E falls back under 25 on volume.",
    })
    _, verdict = _parse_pm_verdict(text, _ctx(_SHEET), run_id)
    return verdict.kill_criterion


def test_kill_criterion_annotated_in_annotate_mode(mode):
    assert "figures of record" in _kill("annotate", mode, uuid4())


def test_kill_criterion_untouched_in_log_mode_and_logged_with_the_run_id(mode):
    run_id = uuid4()
    with structlog.testing.capture_logs() as logs:
        kc = _kill("log", mode, run_id)
    assert kc == "A daily close where the P/E falls back under 25 on volume."
    (f,) = _findings(logs)
    assert f["surface"] == "kill_criterion"
    assert f["agent_id"] == AgentId.PORTFOLIO_MANAGER.value
    assert f["run_id"] == str(run_id)


# ── stance headline ───────────────────────────────────────────────────────


def test_headline_nulled_only_in_annotate_mode(mode):
    mode("annotate")
    assert nq.headline_conflicts_with_sheet("P/E at 25, cheap", _SHEET) is True
    mode("log")
    with structlog.testing.capture_logs() as logs:
        assert nq.headline_conflicts_with_sheet(
            "P/E at 25, cheap", _SHEET, run_id=uuid4(), agent_id=AgentId.BULL_RESEARCHER,
        ) is False
    (f,) = _findings(logs)
    assert f["surface"] == "stance_headline" and f["sheet_field"] == "pe_trailing"


# ── Risk Officer ──────────────────────────────────────────────────────────


def _press(turns):
    return next(t for t in turns if t.agent_id is AgentId.AGGRESSIVE_DEBATOR)


def test_risk_officer_tags_and_demotes_in_annotate_mode(mode):
    mode("annotate")
    payload = _payload()
    payload["options"][2]["key_number"] = "a made-up 987.6"
    press = _press(render_officer_turns(payload, _ROWS, headline_max_chars=80))
    assert _UNVERIFIABLE_MARK in press.text
    assert press.headline == _rung_derived_headline(_ROWS[2])


def test_risk_officer_log_mode_no_tag_but_demoted_and_logs(mode):
    mode("log")
    run_id = uuid4()
    payload = _payload()
    payload["options"][2]["key_number"] = "a made-up 987.6"
    with structlog.testing.capture_logs() as logs:
        press = _press(
            render_officer_turns(payload, _ROWS, headline_max_chars=80, run_id=run_id)
        )
    assert _UNVERIFIABLE_MARK not in press.text
    assert "Key figure: a made-up 987.6" in press.text
    # CR288: no text is written, but an uncorroborated figure is never the headline.
    assert press.headline == _rung_derived_headline(_ROWS[2])
    (f,) = _findings(logs)
    assert f["checker"] == "risk_quotation"
    assert f["surface"] == "key_figure"
    assert f["run_id"] == str(run_id)
    assert f["agent_id"] == AgentId.AGGRESSIVE_DEBATOR.value
    assert f["claimed"] == "a made-up 987.6"
    assert f["uncorroborated"] == ["987.6"]
    assert f["mode"] == "log" and f["text_changed"] is False


def test_risk_officer_log_mode_decisive_number_unmarked_but_not_promoted(mode):
    mode("log")
    payload = _payload(decisive_number="a fabricated 555.5")
    with structlog.testing.capture_logs() as logs:
        turns = render_officer_turns(payload, _ROWS, headline_max_chars=80)
    neu = next(t for t in turns if t.agent_id is AgentId.NEUTRAL_DEBATOR)
    assert _UNVERIFIABLE_MARK not in neu.text
    assert "decided by a fabricated 555.5" in neu.text
    assert neu.headline != "a fabricated 555.5"
    assert {f["surface"] for f in _findings(logs)} == {
        "decisive_number_headline", "decisive_number_call",
    }
