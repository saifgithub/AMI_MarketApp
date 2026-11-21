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


class PickRoomTests(unittest.TestCase):
    def test_picks_the_room_triggered_with_the_arm(self):
        a = {**arm(), "triggered_at": "2026-11-20T12:05:58.925388+00:00"}
        t = 1795176358.925  # 2026-11-20T12:05:58.925Z
        early = {"id": "old", "triggered_epoch": t - 175}
        mine = {"id": "mine", "triggered_epoch": t + 0.00005}
        self.assertEqual(w.pick_room(a, [early, mine])["id"], "mine")

    def test_no_candidate_within_five_seconds_is_none(self):
        a = {**arm(), "triggered_at": "2026-11-20T12:05:58.925388+00:00"}
        self.assertIsNone(w.pick_room(a, [{"id": "x", "triggered_epoch": 1795176358.925 - 60}]))
        self.assertIsNone(w.pick_room(a, []))


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


BEAR = ("The downside is 35% if margins compress, and net debt is 4.5x EBITDA with $1,200 million "
        "due in 2027. Revenue grew 12% last year.\nDanaher Corporation (DHR) trades at 24x earnings.")
ROOM_PERT = {"id": "rid", "transcript": [
    {"agent_id": "market_analyst", "content": "DHR chart is flat. Danaher holds support."},
    {"agent_id": "bull_researcher", "content": "Bull case for DHR: growth of 12%."},
    {"agent_id": "bear_researcher", "content": BEAR},
    {"agent_id": "trader", "content": "Buy DHR."},
    {"agent_id": "conservative_debator", "content": "Danaher is fine."},
    {"agent_id": "portfolio_manager", "content": "CIO VERDICT: APPROVE DHR Danaher"},
]}


def pert_tr():
    return w.build_transcript(arm("DHR", 3, 1), ROOM_PERT, {"horizon": "long"})


class PerturbationTests(unittest.TestCase):
    def test_every_builder_is_deterministic_and_never_includes_the_cio(self):
        for kind in w.PERTURBATIONS:
            a = w.perturb(kind, pert_tr(), "Danaher Corporation Common Stock")
            b = w.perturb(kind, pert_tr(), "Danaher Corporation Common Stock")
            self.assertIsNotNone(a, kind)
            self.assertEqual(a[0].turns, b[0].turns, kind)
            self.assertEqual(a[1], b[1], kind)
            self.assertNotIn("portfolio_manager", [t["agent_id"] for t in a[0].turns], kind)
            self.assertNotIn("CIO VERDICT", " ".join(t["content"] for t in a[0].turns), kind)

    def test_builder_does_not_mutate_the_input(self):
        tr = pert_tr()
        before = [dict(t) for t in tr.turns]
        for kind in w.PERTURBATIONS:
            w.perturb(kind, tr, "Danaher Corporation Common Stock")
        self.assertEqual([dict(t) for t in tr.turns], before)

    def test_planted_flaw_appends_to_the_bear_turn_only(self):
        out, _ = w.perturb("planted_flaw", pert_tr())
        bear = next(t for t in out.turns if t["agent_id"] == "bear_researcher")
        self.assertTrue(bear["content"].startswith(BEAR))
        self.assertIn("going-concern", bear["content"])
        self.assertIn("$2.4 billion", bear["content"])
        others = [t for t in out.turns if t["agent_id"] != "bear_researcher"]
        self.assertNotIn("going-concern", " ".join(t["content"] for t in others))

    def test_bear_removed_leaves_no_numbers(self):
        out, _ = w.perturb("bear_removed", pert_tr())
        bear = next(t for t in out.turns if t["agent_id"] == "bear_researcher")
        self.assertEqual(bear["content"], w.BEAR_REMOVED_TEXT)
        self.assertFalse(any(ch.isdigit() for ch in bear["content"]))
        self.assertEqual(len(out.turns), len(pert_tr().turns))

    def test_strengthen_scales_only_downside_sentences(self):
        new, n = w.strengthen_numbers(BEAR)
        self.assertIn("The downside is 70% if margins compress", new)
        self.assertIn("9.0x EBITDA", new)
        self.assertIn("$2,400 million", new)
        self.assertIn("Revenue grew 12% last year.", new)  # not a downside sentence
        self.assertIn("24x earnings", new)  # separate line, no downside keyword
        self.assertEqual(n, 3)

    def test_strengthen_not_applicable_without_numbers(self):
        tr = w.build_transcript(arm("DHR", 3, 1), {"id": "r", "transcript": [
            {"agent_id": "bear_researcher", "content": "Risky name, no numbers."}]}, None)
        self.assertIsNone(w.perturb("bear_strengthened", tr))

    def test_reorder_is_a_fixed_permutation_that_moves_something(self):
        out, meta = w.perturb("turns_reordered", pert_tr())
        self.assertEqual(sorted(meta["order"]), list(range(len(pert_tr().turns))))
        self.assertNotEqual(meta["order"], sorted(meta["order"]))
        self.assertEqual(sorted(t["content"] for t in out.turns), sorted(t["content"] for t in pert_tr().turns))
        self.assertEqual(meta["order"], w.perturb("turns_reordered", pert_tr())[1]["order"])

    def test_rename_replaces_ticker_and_company_everywhere(self):
        out, meta = w.perturb("ticker_renamed", pert_tr(), "Danaher Corporation Common Stock")
        text = " ".join(t["content"] for t in out.turns)
        self.assertNotIn("DHR", text)
        self.assertNotIn("Danaher", text)
        self.assertIn("Company X", text)
        self.assertIn("TICKR", text)
        self.assertEqual(out.ticker, "TICKR")
        self.assertEqual(meta["ticker_left"], 0)
        self.assertIn("Danaher", meta["names"])

    def test_rename_does_not_touch_ticker_inside_words(self):
        self.assertEqual(w.rename_text("CARS and CAR and $CAR", "CAR", []), "CARS and TICKR and $TICKR")

    def test_name_variants_strip_suffixes(self):
        self.assertEqual(w.name_variants("The Campbell's Company Common Stock")[-1], "Campbell's")
        self.assertEqual(w.name_variants(None), [])


class JudgeTests(unittest.TestCase):
    def pair(self, kind, orig_ans, new_ans, risk=3):
        a = arm("A", risk, 1)
        return w.judge(kind, row(a, orig_ans), row(a, new_ans))[0]

    def test_planted_flaw_needs_terminal_yes_and_pass_everywhere(self):
        self.assertEqual(self.pair("planted_flaw", APPROVING, PASSING), "pass")
        self.assertEqual(self.pair("planted_flaw", APPROVING, APPROVING), "fail")

    def test_bear_removed_may_not_turn_approve_into_pass(self):
        self.assertEqual(self.pair("bear_removed", APPROVING, APPROVING), "pass")
        self.assertEqual(self.pair("bear_removed", PASSING, APPROVING), "pass")
        self.assertEqual(self.pair("bear_removed", APPROVING, PASSING), "fail")

    def test_reorder_needs_every_answer_unchanged(self):
        self.assertEqual(self.pair("turns_reordered", APPROVING, APPROVING), "pass")
        flipped = {**APPROVING, QuestionId.EVENT_RISK_WAIT: "yes"}
        self.assertEqual(self.pair("turns_reordered", APPROVING, flipped), "fail")

    def test_inputs_table_counts_pass_rate_and_lists_failures(self):
        a = arm("A", 3, 1)
        rows = []
        for kind, ans in (("original", APPROVING), ("original_repeat", APPROVING),
                          ("planted_flaw", APPROVING), ("bear_removed", APPROVING),
                          ("bear_strengthened", APPROVING), ("turns_reordered", APPROVING),
                          ("ticker_renamed", APPROVING)):
            r = row(a, ans)
            r["perturbation"], r["pert_meta"] = kind, {"numbers_scaled": 2}
            rows.append(r)
        md = "\n".join(w.inputs_table(rows))
        line = next(x for x in md.splitlines() if x.startswith("| Planted fatal flaw"))
        self.assertIn("0% (0/1)", line)
        self.assertIn("A-r3-rep1", line)
        line = next(x for x in md.splitlines() if x.startswith("| Turns reordered"))
        self.assertIn("100% (1/1)", line)

    def test_missing_grade_is_not_applicable(self):
        a = arm("A", 3, 1)
        self.assertEqual(w.judge("ticker_renamed", row(a, APPROVING), row(a, {}, error="x"))[0], "na")


if __name__ == "__main__":
    unittest.main()
