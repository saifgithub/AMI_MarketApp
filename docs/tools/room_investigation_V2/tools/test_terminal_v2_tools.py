"""Tests for terminal_v2_regrade.py / terminal_v2_report.py (pure helpers; no model, no DB, no network).

Run: cd backend && .venv/bin/python -m pytest ../docs/tools/room_investigation_V2/tools/test_terminal_v2_tools.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import terminal_v2_regrade as R  # noqa: E402
import terminal_v2_report as P  # noqa: E402
from app.services.room_grader_contract import Answer, QuestionAnswer, QuestionId  # noqa: E402

TRADER = [{"agent_id": "trader", "content": (
    "Instrument:     0174.KL\nSide:           BUY\nSize:           1.00% of portfolio\n"
    "Entry:          RM0.03\nTarget:         RM0.037\nStop:           RM0.02\n"
    "Time horizon:   3 months\nR:R:            0.7:1\n\nRationale: x")}]


def test_trader_levels_are_parsed_from_the_desk_turn():
    lv = R.trader_levels(TRADER)
    assert lv == {"side": "buy", "size_pct": 1.0, "entry": 0.03, "stop": 0.02, "target": 0.037, "rr": 0.7}
    assert R.trader_levels([])["side"] is None


def _answers(terminal: str, trade: str = "yes") -> dict:
    a = {q.value: {"answer": "no", "confidence": None, "close": False} for q in QuestionId}
    a["trade_proposed"]["answer"] = trade
    a["terminal_vulnerability"]["answer"] = terminal
    return a


def test_the_new_terminal_answer_replaces_only_the_terminal_question():
    ans = _answers("yes")
    assert R.outcome(ans, 5) == "PASS"
    no = QuestionAnswer(QuestionId.TERMINAL_VULNERABILITY, Answer.NO)
    assert R.outcome(ans, 5, no) == "APPROVE"
    close = QuestionAnswer(QuestionId.TERMINAL_VULNERABILITY, Answer.NO, close=True)
    assert R.outcome(ans, 5, close) == "CONTESTED"
    assert R.outcome(_answers("no", trade="no"), 5, no) == "PASS"


def test_leakage_scan_and_percent_helper():
    assert P.NOT_TERMINAL.search("operating margin collapsed to -204%")
    assert not P.NOT_TERMINAL.search("RM310 million notes mature on 15 March 2027")
    assert P.pct(1, 4) == "1/4 (25.0%)" and P.pct(0, 0) == "0/0"
