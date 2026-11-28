"""DEF555 (device lab AMI-DL-43, US ticker): the CIO wrote the same Year-2 debt maturity
once as "$1.133B" and once as "$1,133B". "$1,133B" reads as 1.133 trillion - a 1000x
misstatement the user reads as fact, and the fact-check is log-only.

`fix_billion_comma` rewrites "$X,XXXB" to "$X.XXXB" only when the same symbol and digits
appear as "$X.XXXB" elsewhere in the same text; without a twin it may be a genuine figure
and is left untouched. The Room applies it to every desk turn, the Risk Officer turns, and
the CIO's text, verdict reason and kill criterion, logging `room_billion_comma_rewrite`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _FsPath
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.schemas.room import Verdict, VerdictAction
from app.services import room_runner
from app.services.room_market import fix_billion_comma

_THIS_DIR = _FsPath(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))


def _fix(text: str) -> str:
    return fix_billion_comma(text)[0]


def test_twin_present_rewrites_the_comma_form():
    text = "Year-2 maturity of $1.133B is covered; the $1,133B wall is not."
    assert _fix(text) == "Year-2 maturity of $1.133B is covered; the $1.133B wall is not."


def test_twin_after_the_comma_form_also_counts():
    assert _fix("$1,133B due, i.e. $1.133B.") == "$1.133B due, i.e. $1.133B."


def test_every_comma_occurrence_is_rewritten_and_reported():
    out, rewrites = fix_billion_comma("$2.500B, $2,500B and again $2,500B")
    assert out == "$2.500B, $2.500B and again $2.500B"
    assert rewrites == [("$2,500B", "$2.500B")] * 2


def test_no_twin_is_untouched_and_the_same_object():
    text = "Total debt is $1,133B, a large figure."
    out, rewrites = fix_billion_comma(text)
    assert out is text and rewrites == []


def test_different_digits_are_untouched():
    text = "Maturity $1.133B but total debt $2,500B."
    assert _fix(text) == text


def test_same_digits_other_symbol_is_untouched():
    text = "RM1.133B maturity against $1,133B."
    assert _fix(text) == text


def test_rm_case():
    assert _fix("Maturity RM1.133B; the RM1,133B bullet") == "Maturity RM1.133B; the RM1.133B bullet"
    assert _fix("RM1,133B alone") == "RM1,133B alone"


@pytest.mark.parametrize("raw, fixed", [
    ("-$1,133B and $1.133B", "-$1.133B and $1.133B"),
    ("$-1,133B and $1.133B", "$-1.133B and $1.133B"),
    ("-RM1,133B and RM1.133B", "-RM1.133B and RM1.133B"),
    ("$1,133B and -$1.133B", "$1.133B and -$1.133B"),
    ("$1,133bn and $1.133bn", "$1.133bn and $1.133bn"),
    ("$1,133B and $1.133bn", "$1.133B and $1.133bn"),
])
def test_sign_and_bn_variants(raw, fixed):
    assert _fix(raw) == fixed


@pytest.mark.parametrize("text", [
    "$1,133M and $1.133M",  # millions: a genuine form, not this mistake class
    "$1,133,000B and $1.133B",  # a grouped number, not X,XXX
    "$1,1334B and $1.133B",
    "$1,133Bn and $1.133B",  # a different token
    "CAD$1,133B and CAD$1.133B",
    "XRM1,133B and RM1.133B",
    "$11,133B and $1.133B",  # different digits
    "$1.133B and $1.133B",
])
def test_lookalikes_are_untouched(text):
    assert _fix(text) == text


def test_idempotent():
    once = _fix("$1.133B and $1,133B")
    assert _fix(once) == once


# ── wiring: the rewrite reaches the user on the covered turns ──


def _capture(monkeypatch) -> list[dict]:
    """Collect `room_runner.logger.warning` calls (structlog's capture_logs is
    order-dependent once another test has configured the logger)."""
    logs: list[dict] = []
    monkeypatch.setattr(
        room_runner.logger, "warning", lambda event, **kw: logs.append({"event": event, **kw})
    )
    return logs


def _desk_turn(agent: AgentId, reply: str, ticker: str = "AAPL") -> str:
    import test_cr266_room_gate as R

    ctx, _, _ = R._ctx()
    ctx.ticker = ticker
    profile = {"field_state": {}}
    ctx.profile = profile
    text, *_ = asyncio.run(room_runner._compute_agent_text(
        agent_id=agent, ctx=ctx, profile=profile, formatter={}, transcript=[],
        gateway=R._GateGateway([reply]), live=True, agent_timeout_s=30.0,
    ))
    return text


def test_a_live_desk_turn_is_rewritten_and_logged(monkeypatch):
    reply = (
        "[STANCE: against | CONVICTION: high | HEADLINE: debt wall]\n"
        "Year-2 maturity is $1.133B, then a $1,133B refinancing."
    )
    logs = _capture(monkeypatch)
    text = _desk_turn(AgentId.BEAR_RESEARCHER, reply)
    assert "$1,133B" not in text and text.count("$1.133B") == 2
    hits = [e for e in logs if e["event"] == "room_billion_comma_rewrite"]
    assert len(hits) == 1
    assert hits[0]["ticker"] == "AAPL"
    assert hits[0]["turn"] == AgentId.BEAR_RESEARCHER.value
    assert (hits[0]["before"], hits[0]["after"]) == ("$1,133B", "$1.133B")


def test_a_desk_turn_without_a_twin_is_left_alone_and_silent(monkeypatch):
    reply = (
        "[STANCE: against | CONVICTION: high | HEADLINE: debt wall]\n"
        "Total debt is $1,133B."
    )
    logs = _capture(monkeypatch)
    text = _desk_turn(AgentId.BEAR_RESEARCHER, reply)
    assert "$1,133B" in text
    assert not [e for e in logs if e["event"] == "room_billion_comma_rewrite"]


def test_the_cio_text_and_verdict_reason_are_rewritten_each_on_its_own_text(monkeypatch):
    monkeypatch.setattr(settings, "output_guard_mode", "log")
    v = Verdict(
        action=VerdictAction.PASS,
        reason="Maturity $1.133B vs a $1,133B wall; separately $2,500B stands.",
    )
    logs = _capture(monkeypatch)
    text, v2 = room_runner._guard_pm_text(
        "Pass: $1,133B only here.", v, run_id=uuid4(), ticker="AAPL",
    )
    assert text == "Pass: $1,133B only here."  # no twin in this text
    assert v2.reason == "Maturity $1.133B vs a $1.133B wall; separately $2,500B stands."
    assert v2.action == VerdictAction.PASS
    hits = [e for e in logs if e["event"] == "room_billion_comma_rewrite"]
    assert [(h["turn"], h["ticker"]) for h in hits] == [("cio_reason", "AAPL")]

    text, _ = room_runner._guard_pm_text(
        "Maturity $1.133B; the $1,133B wall.", v, run_id=uuid4(), ticker="AAPL",
    )
    assert text == "Maturity $1.133B; the $1.133B wall."
