#!/usr/bin/env python3
"""Offline tests for ling_regrade.py (stdlib unittest, no DB, no network, no gateway call).

Covers what decides whether the re-grade can be trusted: the Execution Desk's side is read the way
`room_runner._trader_side` reads it, the Bursa proposed-trade block is built the way
`_coded_transcript` builds it, a Room's own trade replaces the WP-20 stand-in, and the compare / diff
tables count what they claim to against the real decision rule.

Run from anywhere:
    python3 -m unittest test_ling_regrade   # inside tools/
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ling_regrade as lr  # noqa: E402
import wp22_score as w  # noqa: E402

ARM = {"arm_key": "AAA-r5-rep1", "user_id": "u", "ticker": "AAA", "risk_score": 5,
       "triggered_at": "2026-11-25T05:00:00+00:00", "status": "completed", "run_id": "r1",
       "verdict": {"action": "PASS", "reference_price": 10.0}}


def answers(**yes: str) -> dict:
    base = {q: {"answer": "no", "confidence": 0.9, "close": False} for q in lr.QIDS}
    for q, a in yes.items():
        base[q] = {"answer": a, "confidence": 0.9, "close": False}
    return base


def row(arm_key: str, ticker: str, risk: int, rep: str, **ans: str) -> dict:
    return {"arm_key": arm_key, "run_id": arm_key, "ticker": ticker, "risk": risk, "rep": rep,
            "answers": answers(**ans), "error": None, "rule": None}


class TraderSideTests(unittest.TestCase):
    def test_reads_the_last_trader_turns_side_line(self):
        turns = [{"agent_id": "trader", "content": "Instrument: X\nSide:  WAIT\nSize: 0%"},
                 {"agent_id": "research_manager", "content": "Side: BUY"},
                 {"agent_id": "trader", "content": "Instrument: X\nSide:           BUY\nSize: 2%"}]
        self.assertEqual(lr.trader_side(turns), "buy")

    def test_no_stated_side_is_none_never_guessed(self):
        self.assertIsNone(lr.trader_side([{"agent_id": "trader", "content": "no side here"}]))
        self.assertIsNone(lr.trader_side([]))


class BursaTradeTests(unittest.TestCase):
    def test_wait_and_hold_carry_size_zero_and_no_levels(self):
        for side in ("wait", "hold"):
            t = lr.bursa_trade(ARM, side)
            self.assertEqual((t["action"], t["size_pct"]), (side, 0.0))
            self.assertNotIn("entry", {k for k, v in t.items() if v is not None})

    def test_buy_carries_the_mandate_cap_and_the_base_price_levels(self):
        t = lr.bursa_trade(ARM, "buy")
        self.assertEqual(t["action"], "buy")
        self.assertEqual((t["entry"], t["stop"], t["target"]), (10.0, 9.4, 11.3))

    def test_a_rooms_own_trade_replaces_the_wp20_stand_in(self):
        room = {"id": "r1", "transcript": [{"agent_id": "trader", "content": "Side: WAIT"},
                                           {"agent_id": "portfolio_manager", "content": "verdict"}],
                "proposed_trade": lr.bursa_trade(ARM, "wait")}
        tr = lr.build_transcript(ARM, room)
        self.assertEqual(tr.proposed_trade["action"], "wait")
        self.assertEqual([t["agent_id"] for t in tr.turns], ["trader"])  # the CIO turn never reaches the grader


class CompareTests(unittest.TestCase):
    def setUp(self):
        # risk 5 needs only trade_proposed and no terminal vulnerability to APPROVE
        self.ref = [row("A-r5-rep1", "A", 5, "1", trade_proposed="yes"),
                    row("A-r5-rep2", "A", 5, "2", trade_proposed="yes"),
                    row("B-r5-rep1", "B", 5, "1", trade_proposed="yes"),
                    row("B-r5-rep2", "B", 5, "2")]
        self.new = [row("A-r5-rep1", "A", 5, "1", trade_proposed="yes"),
                    row("A-r5-rep2", "A", 5, "2", trade_proposed="yes", terminal_vulnerability="yes"),
                    row("B-r5-rep1", "B", 5, "1", trade_proposed="yes"),
                    row("B-r5-rep2", "B", 5, "2")]

    def test_rep_disagreement_counts_pairs_with_different_outcomes(self):
        self.assertEqual(lr.rep_disagreement(self.ref), (1, 2))
        self.assertEqual(lr.rep_disagreement(self.new), (2, 2))

    def test_the_table_counts_same_outcome_and_the_split(self):
        md = lr.compare_tables([("ref", self.ref), ("new", self.new)])
        self.assertIn("| APPROVE / CONTESTED / PASS | 3 / 0 / 1 | 2 / 0 / 2 |", md)
        self.assertIn("| Same outcome as ref | - | 3 |", md)
        self.assertIn("| Rep outcome disagreement | 1/2 | 2/2 |", md)
        self.assertIn("| APPROVE by risk 1-5 | 0 / 0 / 0 / 0 / 3 | 0 / 0 / 0 / 0 / 2 |", md)

    def test_per_question_agree_and_yes(self):
        md = lr.compare_tables([("ref", self.ref), ("new", self.new)])
        self.assertIn("| terminal_vulnerability | 0 | 3 / 1 |", md)


class DiffTests(unittest.TestCase):
    def test_lists_each_flip_with_the_questions_that_changed(self):
        old = [{"run_id": "r1", "ticker": "AAA", "risk_score": 5,
                "verdict": {"coded_decision": {"outcome": "APPROVE", "answers": [
                    {"question": "catalyst_in_horizon", "answer": "yes"},
                    {"question": "terminal_vulnerability", "answer": "no"},
                    {"question": "trade_proposed", "answer": "yes"}]}}},
               {"run_id": "r2", "ticker": "BBB", "risk_score": 5,
                "verdict": {"coded_decision": {"outcome": "PASS", "answers": [
                    {"question": "trade_proposed", "answer": "no"}]}}}]
        rows = [{**row("AAA-r5-rep1", "AAA", 5, "1", trade_proposed="yes", catalyst_in_horizon="no"),
                 "run_id": "r1", "answers": answers(trade_proposed="yes", terminal_vulnerability="yes")},
                {**row("BBB-r5-rep1", "BBB", 5, "1"), "run_id": "r2"}]
        md, info = lr.diff_report(old, rows)
        self.assertEqual([(f[0], f[2], f[3]) for f in info["flips"]], [("AAA", "APPROVE", "PASS")])
        self.assertIn("terminal_vulnerability no->yes", md)
        self.assertIn("catalyst_in_horizon yes->no", md)
        self.assertEqual(info["tally"][("PASS", "PASS")], 1)


class ArmsTests(unittest.TestCase):
    def test_bursa_arms_get_a_rep_suffix_and_skip_unfinished_runs(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "runs.jsonl"
            p.write_text("\n".join(json.dumps(r) for r in [
                {**ARM}, {**ARM, "ticker": "BBB", "status": "failed", "run_id": None}]), encoding="utf-8")
            arms = lr.arms_from_bursa(p)
        self.assertEqual([a["arm_key"] for a in arms], ["AAA-r5-rep1"])
        self.assertEqual(w.parse_rep(arms[0]["arm_key"]), "1")


if __name__ == "__main__":
    unittest.main()
