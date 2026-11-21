#!/usr/bin/env python3
"""Offline tests for wp22_score.py (stdlib unittest, no DB, no network, no gateway).

Covers the parts that decide whether the scoring can be trusted: the CIO's turn
never reaches the grader, the proposed-trade block mirrors production, the row
round-trips through the real decision rule, and the report's stability, consensus
and wording tables count what they claim to. The decision rule and contract are
the real backend modules, not fakes.

Run from anywhere:
    python3 -m unittest test_wp22_score   # inside tools/
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import wp22_score as w  # noqa: E402
from app.services.room_grader_contract import (  # noqa: E402
    QUESTION_SET_VERSION,
    Answer,
    GraderResult,
    QuestionAnswer,
    QuestionId,
)

ALL_Q = list(QuestionId)


def arm(ticker="AAA", risk=3, rep=1, action="PASS", stance="buy", price=100.0):
    verdict = {"action": action, "reference_price": price}
    verdict["street_comparison"] = (
        {"status": "available", "street_rating": stance, "street_stance": stance}
        if stance else {"status": "unavailable", "street_rating": None, "street_stance": None}
    )
    return {
        "arm_key": f"{ticker}-r{risk}-rep{rep}", "ticker": ticker, "risk_score": risk,
        "user_id": f"u-{ticker}-{risk}-{rep}", "status": "completed",
        "spot_price": price, "verdict": verdict,
    }


def result(answers: dict[QuestionId, str], *, error=None, latency=1000, logprobs=True):
    return GraderResult(
        grader="hosted_llm", grader_version="hosted:vllm",
        question_set_version=QUESTION_SET_VERSION,
        answers=tuple(
            QuestionAnswer(q, Answer(answers.get(q, "yes")), 0.9, False) for q in ALL_Q
        ) if not error else (),
        latency_ms=latency, error=error, extra={"logprobs": logprobs, "calls": 6},
    )


APPROVING = {
    QuestionId.BEAR_OBJECTION_ANSWERED: "yes", QuestionId.CATALYST_IN_HORIZON: "yes",
    QuestionId.TERMINAL_VULNERABILITY: "no", QuestionId.EVENT_RISK_WAIT: "no",
    QuestionId.THESIS_MATERIAL_DIRECTIONAL: "yes", QuestionId.TRADE_PROPOSED: "yes",
}
PASSING = {**APPROVING, QuestionId.TERMINAL_VULNERABILITY: "yes"}


def row(a, answers, **kw):
    return w.result_to_row(a, "room-1", result(answers, **kw), phrasing=None, model_root="/m")


class TranscriptTests(unittest.TestCase):
    ROOM = {"id": "rid", "transcript": [
        {"agent_id": "bull_researcher", "content": "bull"},
        {"agent_id": "trader", "content": "trade"},
        {"agent_id": "portfolio_manager", "content": "CIO VERDICT: APPROVE"},
    ]}

    def test_cio_turn_is_dropped(self):
        t = w.build_transcript(arm(), self.ROOM, {"horizon": "long"})
        self.assertEqual([x["agent_id"] for x in t.turns], ["bull_researcher", "trader"])
        self.assertNotIn("VERDICT", " ".join(x["content"] for x in t.turns))
        self.assertEqual(t.horizon, "long")
        self.assertIsNone(t.cards)

    def test_proposed_trade_mirrors_runner(self):
        t = w.build_transcript(arm(risk=3, price=200.0), self.ROOM, {})
        self.assertEqual(t.proposed_trade["entry"], 200.0)
        self.assertEqual(t.proposed_trade["stop"], 188.0)
        self.assertEqual(t.proposed_trade["target"], 226.0)
        self.assertGreater(t.proposed_trade["size_pct"], 0)

    def test_default_mandate_is_the_wp20_harness_one(self):
        self.assertEqual(w.build_transcript(arm(), self.ROOM).horizon, "long")


class SelectionTests(unittest.TestCase):
    def test_stride_sample_hits_every_risk(self):
        arms = [arm(t, r, rep) for r in range(1, 6) for t in "ABCDEF" for rep in (1, 2)]
        pick = w.stride_sample(arms, 10)
        self.assertEqual(len(pick), 10)
        self.assertEqual({int(a["risk_score"]) for a in pick}, {1, 2, 3, 4, 5})
        self.assertEqual(len({a["arm_key"] for a in pick}), 10)

    def test_parse_rep(self):
        self.assertEqual(w.parse_rep("RIOT-r4-rep2"), "2")
        with self.assertRaises(ValueError):
            w.parse_rep("RIOT-r4")

    def test_street_unavailable_is_none(self):
        self.assertEqual(w.street_fields(arm(stance=None)), (None, None))


class RowTests(unittest.TestCase):
    def test_rule_outcome_roundtrip(self):
        self.assertEqual(w.rule_outcome(row(arm(risk=3), APPROVING)), "APPROVE")
        self.assertEqual(w.rule_outcome(row(arm(risk=3), PASSING)), "PASS")
        self.assertEqual(row(arm(risk=3), PASSING)["rule"]["outcome"], "PASS")

    def test_error_row_is_unavailable(self):
        r = row(arm(), {}, error="boom")
        self.assertEqual(w.rule_outcome(r), "UNAVAILABLE")
        self.assertEqual(r["error"], "boom")


class ReportTests(unittest.TestCase):
    def test_stability_counts_only_paired_reps(self):
        rows = [
            row(arm("A", 3, 1), APPROVING), row(arm("A", 3, 2), PASSING),
            row(arm("B", 3, 1), APPROVING), row(arm("B", 3, 2), APPROVING),
            row(arm("C", 3, 1), APPROVING),
        ]
        per_q, agg = w.stability(rows)
        self.assertEqual(per_q["terminal_vulnerability"], (1, 2))
        self.assertEqual(agg["rule"], (1, 2))

    def test_consensus_counts_approvals_by_street_bucket(self):
        arms_rows = [
            (arm("A", 3, 1, action="APPROVE", stance="buy"), APPROVING),
            (arm("B", 3, 1, action="APPROVE", stance="sell"), PASSING),
            (arm("C", 3, 1, action="PASS", stance="hold"), APPROVING),
            (arm("D", 3, 1, action="PASS", stance=None), APPROVING),
        ]
        rows = [row(a, ans) for a, ans in arms_rows]
        for r, (a, _) in zip(rows, arms_rows):
            r["cio_action"] = a["verdict"]["action"]
            r["street_stance"] = a["verdict"]["street_comparison"]["street_stance"]
        md = "\n".join(w.consensus_table(rows))
        cio_r3 = next(line for line in md.splitlines() if line.startswith("| CIO | R3 "))
        self.assertIn("| 4 | 2 |", cio_r3)  # 4 Rooms, 2 CIO approvals
        self.assertIn("| 1 | 50% (1/2) |", cio_r3)  # one approval of a Sell name
        grader_r3 = next(line for line in md.splitlines() if line.startswith("| grader | R3 "))
        self.assertIn("| 4 | 3 |", grader_r3)  # grader approves A, C, D
        self.assertEqual(grader_r3.split("|")[-3].strip(), "1")  # D has no Street data

    def test_wording_counts_changes_against_base(self):
        base = [row(arm("A", 3, 1), APPROVING)]
        flipped = {**APPROVING, QuestionId.CATALYST_IN_HORIZON: "no"}
        wording = []
        for p in w.PHRASINGS:
            r = row(arm("A", 3, 1), flipped if p == 2 else APPROVING)
            r["phrasing"] = p
            wording.append(r)
        md = "\n".join(w.wording_table(base, wording))
        line = next(x for x in md.splitlines() if x.startswith("| catalyst_in_horizon"))
        self.assertIn("100% (1/1)", line.split("|")[-2])  # any-phrasing column
        self.assertIn("0% (0/1)", line.split("|")[2])  # phrasing 1 unchanged

    def test_report_renders_and_flags_errors(self):
        rows = [row(arm("A", 3, 1), APPROVING), row(arm("A", 3, 2), {}, error="boom")]
        for r in rows:
            r["cio_action"] = "PASS"
            r["street_stance"] = "buy"
        md = w.build_report(rows, None, {"model_root_start": "/m", "model_root_end": "/m"})
        self.assertIn("Rooms scored: **1**, errors: **1**", md)
        self.assertIn("boom", md)
        self.assertIn("Consensus scores", md)


if __name__ == "__main__":
    unittest.main()
