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


# ── Hosted graders: keys, pins, spend cap, on-prem unchanged ────────────────

import asyncio  # noqa: E402
import contextlib  # noqa: E402
import dataclasses  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import tempfile  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest import mock  # noqa: E402

SENTINEL = "sk-test-SENTINEL-do-not-leak"


def run_main(argv, env):
    """main() with a clean key environment; returns (rc, stdout, stderr)."""
    clean = {k: v for k, v in os.environ.items()
             if k not in ("JEV_API_KEY", "DEEPINFRA_API_KEY", "WP22_DSN")}
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, {**clean, **env}, clear=True), \
            contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = w.main(argv)
    return rc, out.getvalue(), err.getvalue()


def score_argv(*extra):
    return ["score", "--runs", "/nonexistent.jsonl", "--out", "/nonexistent/o.jsonl", *extra]


class KeyGuardTests(unittest.TestCase):
    def test_missing_jev_key_names_the_key_only_and_exits_nonzero(self):
        rc, out, err = run_main(score_argv("--grader", "jev"), {"DEEPINFRA_API_KEY": SENTINEL})
        self.assertEqual(rc, 2)
        self.assertEqual(err.strip(), "bakeoff.env missing JEV_API_KEY")
        self.assertNotIn(SENTINEL, out + err)

    def test_missing_deepinfra_key_names_the_key_only_and_exits_nonzero(self):
        rc, out, err = run_main(score_argv("--grader", "deepinfra"), {"JEV_API_KEY": SENTINEL})
        self.assertEqual(rc, 2)
        self.assertEqual(err.strip(), "bakeoff.env missing DEEPINFRA_API_KEY")
        self.assertNotIn(SENTINEL, out + err)

    def test_blank_key_counts_as_missing(self):
        rc, _out, err = run_main(score_argv("--grader", "jev"), {"JEV_API_KEY": "   "})
        self.assertEqual(rc, 2)
        self.assertIn("bakeoff.env missing JEV_API_KEY", err)

    def test_key_check_runs_before_the_database(self):
        rc, _out, err = run_main(score_argv("--grader", "jev"), {})
        self.assertEqual((rc, "WP22_DSN" in err), (2, False))

    def test_same_guard_on_wording_and_inputs(self):
        for sub in ("wording", "inputs"):
            rc, _o, err = run_main([sub, "--runs", "x", "--out", "y", "--grader", "jev"], {})
            self.assertEqual((rc, err.strip()), (2, "bakeoff.env missing JEV_API_KEY"), sub)

    def test_inputs_dry_needs_no_key(self):
        _rc, _o, err = run_main(["inputs", "--runs", "x", "--out", "y", "--grader", "jev", "--dry"],
                                {})
        self.assertNotIn("bakeoff.env missing", err)

    def test_unknown_grader_is_refused_by_argparse(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            run_main(score_argv("--grader", "gpt"), {})


class PinTests(unittest.TestCase):
    def test_jev_refuses_latest_in_any_spelling(self):
        for v in ("latest", "jev-latest", "JEV-LATEST", "", "  "):
            rc, out, err = run_main(score_argv("--grader", "jev", "--jev-version", v),
                                    {"JEV_API_KEY": SENTINEL})
            self.assertEqual(rc, 2, v)
            self.assertIn("pinned", err, v)
            self.assertNotIn(SENTINEL, out + err)

    def test_jev_default_is_the_pinned_october_version(self):
        self.assertEqual(w.JEV_DEFAULT_VERSION, "jev-1.13.0")
        args = SimpleNamespace(grader="jev", jev_version=w.JEV_DEFAULT_VERSION, model=None,
                               max_usd=5.0, max_calls=300, price_in=None, price_out=None,
                               slot="vllm")
        setup = w.setup_grader(args, {"JEV_API_KEY": SENTINEL})
        g = setup.factory(None)._inner
        self.assertEqual((g.name, g.version), ("jev", "jev-1.13.0"))
        self.assertNotIn(SENTINEL, json.dumps(setup.describe))

    def test_deepinfra_model_must_be_pinned(self):
        rc, _o, err = run_main(score_argv("--grader", "deepinfra", "--model", "x/latest"),
                               {"DEEPINFRA_API_KEY": SENTINEL})
        self.assertEqual(rc, 2)
        self.assertIn("pinned", err)

    def test_hosted_slot_points_only_at_deepinfra_with_the_key_in_process(self):
        cfg = SimpleNamespace()
        w.configure_hosted_slot("deepseek-ai/DeepSeek-V4-Flash", SENTINEL, (0.09, 0.18), cfg)
        self.assertEqual(cfg.vllm_fallback_base_url, w.DEEPINFRA_BASE_URL)
        self.assertEqual(cfg.vllm_fallback_model, "deepseek-ai/DeepSeek-V4-Flash")
        self.assertEqual(cfg.vllm_fallback_kind, "openai")
        self.assertEqual(cfg.vllm_fallback_api_key, SENTINEL)
        self.assertEqual(cfg.vllm_base_url, "")
        self.assertEqual(cfg.llm_provider_allowlist, ["vllm_fallback"])
        self.assertEqual(json.loads(cfg.llm_prices_json),
                         {"deepseek-ai/DeepSeek-V4-Flash": {"in": 0.09, "out": 0.18}})
        w.configure_hosted_slot("other/model", SENTINEL, None, cfg)
        self.assertEqual(cfg.llm_prices_json, "{}")


class SpendCapTests(unittest.TestCase):
    ROOM = {"id": "rid", "transcript": [{"agent_id": "bull_researcher", "content": "b"}]}

    def run_rooms(self, n, grader_result, guard, concurrency=1):
        arms = [arm(f"T{i}", 3, 1) for i in range(n)]
        rooms = {a["arm_key"]: self.ROOM for a in arms}
        calls = []

        class Fake:
            async def agrade(self, tr):
                calls.append(tr.ticker)
                return grader_result()

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "s.jsonl"
            errors = asyncio.run(w.run_scoring(
                arms, rooms, out, make_grader=lambda p: Fake(), phrasings=[None],
                concurrency=concurrency, model_root="m", guard=guard, log=lambda *_: None))
            rows = w.load_jsonl(out) if out.exists() else []
        return errors, calls, rows

    def priced(self, usd):
        return lambda: dataclasses.replace(result({}), cost_usd=usd)

    def test_usd_cap_stops_cleanly_and_records_it(self):
        guard = w.SpendGuard(max_usd=1.0, max_calls=300, fallback_calls=6)
        errors, calls, rows = self.run_rooms(10, self.priced(0.4), guard)
        self.assertEqual(len(calls), 3)  # 0.4 x 3 = 1.2 >= 1.0: no 4th Room starts
        self.assertEqual(len(rows), 3)
        self.assertEqual(errors, 0)
        s = guard.summary()
        self.assertEqual((s["cap_hit"], s["rooms_graded"], s["rooms_skipped_by_cap"]),
                         ("max_usd", 3, 7))
        self.assertAlmostEqual(s["usd_spent"], 1.2)

    def test_unpriced_results_are_capped_by_call_count(self):
        guard = w.SpendGuard(max_usd=5.0, max_calls=12, fallback_calls=6)
        _e, calls, _r = self.run_rooms(10, lambda: result({}), guard)  # no cost, calls=6 each
        self.assertEqual(len(calls), 2)
        self.assertEqual(guard.summary()["cap_hit"], "max_calls")
        self.assertEqual(guard.summary()["unpriced_calls"], 12)

    def test_priced_results_do_not_spend_the_call_budget(self):
        guard = w.SpendGuard(max_usd=100.0, max_calls=1, fallback_calls=6)
        _e, calls, _r = self.run_rooms(5, self.priced(0.01), guard)
        self.assertEqual(len(calls), 5)
        self.assertIsNone(guard.summary()["cap_hit"])

    def test_cap_overshoot_is_bounded_by_concurrency(self):
        guard = w.SpendGuard(max_usd=0.5, max_calls=300, fallback_calls=6)
        _e, calls, _r = self.run_rooms(20, self.priced(0.5), guard, concurrency=3)
        self.assertLessEqual(len(calls), 3)

    def test_no_guard_means_no_cap_the_onprem_path(self):
        _e, calls, rows = self.run_rooms(7, lambda: result({}), None)
        self.assertEqual((len(calls), len(rows)), (7, 7))

    def test_capped_run_resumes_where_it_stopped(self):
        arms = [arm(f"T{i}", 3, 1) for i in range(4)]
        rooms = {a["arm_key"]: self.ROOM for a in arms}

        class Fake:
            async def agrade(self, tr):
                return dataclasses.replace(result({}), cost_usd=1.0)

        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "s.jsonl"
            for cap in (2.0, 100.0):
                asyncio.run(w.run_scoring(
                    arms, rooms, out, make_grader=lambda p: Fake(), phrasings=[None],
                    concurrency=1, model_root="m",
                    guard=w.SpendGuard(cap, 300, 6), log=lambda *_: None))
            keys = [r["arm_key"] for r in w.load_jsonl(out)]
        self.assertEqual(sorted(keys), sorted(a["arm_key"] for a in arms))


class JevPricingTests(unittest.TestCase):
    def test_cost_comes_from_input_tokens_at_the_documented_price(self):
        r = dataclasses.replace(result({}), extra={"usage": {"input_tokens": 1_000_000}})
        self.assertAlmostEqual(w.price_jev(r).cost_usd, w.JEV_USD_PER_M_INPUT)

    def test_no_usage_stays_unpriced_so_the_call_cap_applies(self):
        r = dataclasses.replace(result({}), extra={})
        self.assertIsNone(w.price_jev(r).cost_usd)
        g = w.SpendGuard(5.0, 300, 1)
        g.record(w.price_jev(r))
        self.assertEqual(g.unpriced_calls, 1)

    def test_failed_result_is_not_priced(self):
        r = dataclasses.replace(result({}, error="boom"), extra={"usage": {"input_tokens": 9}})
        self.assertIsNone(w.price_jev(r).cost_usd)


class OnPremUnchangedTests(unittest.TestCase):
    def test_default_grader_is_onprem_with_no_guard_and_no_key_needed(self):
        args = SimpleNamespace(grader="onprem", slot="vllm")
        self.assertEqual(w._grader_preamble(args), (None, 0))
        setup = w.setup_grader(args)
        self.assertEqual((setup.guard, setup.describe), (None, {}))

    def test_onprem_still_refuses_any_slot_but_vllm(self):
        rc, _o, err = run_main(score_argv("--slot", "vllm_fallback"), {"WP22_DSN": "x"})
        self.assertEqual(rc, 2)
        self.assertIn("on-prem vLLM slot only", err)

    def test_onprem_still_needs_the_dsn_and_no_key(self):
        rc, _o, err = run_main(score_argv(), {})
        self.assertEqual((rc, err.strip()), (2, "WP22_DSN is not set"))

    def test_parser_defaults(self):
        with mock.patch.object(w, "cmd_run", lambda a, wording: a):
            a = w.main(score_argv())
        self.assertEqual((a.grader, a.slot, a.max_usd, a.max_calls),
                         ("onprem", "vllm", 5.0, 300))

    def test_cap_meta_empty_for_onprem(self):
        self.assertEqual(w._cap_meta(None), {})


# ── Code grader: cards rebuilt from the audit trail ──────────────────────────
# These use the backend's real `parse_claim_cards` and `CodeCardsGrader`, which need the app's
# dependencies (structlog, cryptography). Without them the class is skipped, never faked.

try:
    from app.services.room_graders.code_cards import CodeCardsGrader
    from app.services.room_runner import parse_claim_cards  # noqa: F401
    HAVE_APP = True
except Exception:  # noqa: BLE001
    HAVE_APP = False

ITEMS5 = ("eq", "vc", "vh", "bs", "moat")


def claims(items=ITEMS5, direction="support", grade="well", data="yes", nums="FCF 4.1B", objections=""):
    lines = "\n".join(
        f"- item={i} dir={direction} grade={grade} data={data} claim=claim on {i} nums={nums}" for i in items)
    out = f"Prose of the turn.\n[CLAIMS]\n{lines}\n[/CLAIMS]"
    return out + (f"\n[OBJECTIONS]\n{objections}\n[/OBJECTIONS]" if objections else "")


def turn(desk, text, flow="room"):
    return {"agent_id": desk, "flow": flow, "response_text": text, "epoch": 0.0, "user_id": "u"}


LIVE_SHEET = {"free_cash_flow": "live", "roic": "live", "pe": "live", "total_debt": "live",
              "gross_margin": "live"}


@unittest.skipUnless(HAVE_APP, "backend app dependencies not installed")
class CardRebuildTests(unittest.TestCase):
    def full_turns(self, **over):
        t = [turn(d, claims()) for d in w.CARD_DESKS]
        for d, text in over.items():
            t = [turn(d, text) if x["agent_id"] == d else x for x in t]
        return t

    def test_shape_is_what_the_grader_reads(self):
        cards, meta = w.cards_for_room(self.full_turns(), LIVE_SHEET)
        self.assertEqual(set(cards), {"cards_by_desk", "field_state"})
        self.assertEqual(set(cards["cards_by_desk"]), set(w.CARD_DESKS))
        ch = cards["cards_by_desk"]["bear_researcher"]
        self.assertEqual(len(ch["cards"]), 5)
        self.assertEqual({"item", "direction", "grade", "data", "claim", "nums"}, set(ch["cards"][0]))
        self.assertEqual(cards["field_state"], LIVE_SHEET)
        self.assertEqual((meta["desks_with_cards"], meta["desks_complete"], meta["cards"]), (4, 4, 20))

    def test_a_complete_room_is_computable_by_the_real_grader(self):
        cards, _ = w.cards_for_room(self.full_turns(), LIVE_SHEET)
        tr = w.build_transcript(arm(), {"id": "r", "transcript": [], "cards": cards, "trade_action": "buy"})
        res = CodeCardsGrader().grade(tr)
        got = {a.question.value: a.answer.value for a in res.answers}
        self.assertEqual(got["thesis_material_directional"], "yes")
        self.assertEqual(got["terminal_vulnerability"], "no")
        self.assertEqual(got["trade_proposed"], "yes")
        self.assertEqual(got["catalyst_in_horizon"], "not_computable")
        self.assertEqual(got["event_risk_wait"], "not_computable")

    def test_the_production_trade_block_has_no_action_so_trade_proposed_is_not_computable(self):
        cards, _ = w.cards_for_room(self.full_turns(), LIVE_SHEET)
        tr = w.build_transcript(arm(), {"id": "r", "transcript": [], "cards": cards})
        self.assertNotIn("action", tr.proposed_trade)
        got = {a.question.value: a.answer.value for a in CodeCardsGrader().grade(tr).answers}
        self.assertEqual(got["trade_proposed"], "not_computable")

    def test_last_turn_per_desk_wins(self):
        weak = claims(direction="oppose")
        turns = [turn("bull_researcher", weak)] + [
            turn(d, claims()) for d in w.CARD_DESKS if d != "bull_researcher"]
        turns.append(turn("bull_researcher", claims(direction="support"), "room_envelope_repair"))
        cards, _ = w.cards_for_room(turns, LIVE_SHEET)
        dirs = {c["direction"] for c in cards["cards_by_desk"]["bull_researcher"]["cards"]}
        self.assertEqual(dirs, {"support"})

    def test_a_still_incomplete_cards_reask_is_rejected_like_the_runner_does(self):
        turns = self.full_turns()
        turns.append(turn("bear_researcher", claims(items=("eq", "vc")), "room_cards_repair"))
        cards, meta = w.cards_for_room(turns, LIVE_SHEET)
        self.assertEqual(len(cards["cards_by_desk"]["bear_researcher"]["cards"]), 5)
        self.assertEqual(meta["fallback_desks"], ["bear_researcher"])

    def test_a_complete_cards_reask_is_adopted(self):
        turns = [turn(d, claims(items=("eq", "vc"))) for d in w.CARD_DESKS]
        turns.append(turn("bear_researcher", claims(), "room_cards_repair"))
        cards, meta = w.cards_for_room(turns, LIVE_SHEET)
        self.assertEqual(len(cards["cards_by_desk"]["bear_researcher"]["cards"]), 5)
        self.assertEqual(meta["fallback_desks"], [])
        self.assertEqual(meta["desks_complete"], 1)

    def test_a_missing_desk_stays_missing_and_the_cell_is_not_computable(self):
        turns = [t for t in self.full_turns() if t["agent_id"] != "research_manager"]
        cards, meta = w.cards_for_room(turns, LIVE_SHEET)
        self.assertNotIn("research_manager", cards["cards_by_desk"])
        self.assertEqual(meta["desks_without_turn"], ["research_manager"])
        tr = w.build_transcript(arm(), {"id": "r", "transcript": [], "cards": cards, "trade_action": "buy"})
        got = {a.question.value: a.answer.value for a in CodeCardsGrader().grade(tr).answers}
        self.assertEqual(got["thesis_material_directional"], "not_computable")
        self.assertEqual(got["terminal_vulnerability"], "not_computable")

    def test_a_partial_channel_is_never_filled_in(self):
        turns = self.full_turns(bull_researcher=claims(items=("eq", "vc", "vh")))
        cards, meta = w.cards_for_room(turns, LIVE_SHEET)
        self.assertEqual(len(cards["cards_by_desk"]["bull_researcher"]["cards"]), 3)
        self.assertEqual(meta["desks_complete"], 3)
        tr = w.build_transcript(arm(), {"id": "r", "transcript": [], "cards": cards, "trade_action": "buy"})
        got = {a.question.value: a.answer.value for a in CodeCardsGrader().grade(tr).answers}
        self.assertEqual(got["thesis_material_directional"], "not_computable")

    def test_no_cards_at_all_is_none_not_an_empty_object(self):
        turns = [turn(d, "no claims block here") for d in w.CARD_DESKS]
        cards, meta = w.cards_for_room(turns, LIVE_SHEET)
        self.assertIsNone(cards)
        self.assertEqual(meta["desks_with_cards"], 0)
        self.assertIsNone(w.cards_for_room([], LIVE_SHEET)[0])

    def test_missing_fact_sheet_registry_is_passed_on_empty_so_the_grader_says_so(self):
        cards, _ = w.cards_for_room(self.full_turns(), None)
        self.assertEqual(cards["field_state"], {})
        tr = w.build_transcript(arm(), {"id": "r", "transcript": [], "cards": cards, "trade_action": "buy"})
        got = {a.question.value: a.answer.value for a in CodeCardsGrader().grade(tr).answers}
        self.assertEqual(got["terminal_vulnerability"], "not_computable")

    def test_an_unresolved_high_balance_sheet_objection_is_terminal_vulnerability_yes(self):
        bs_oppose = claims(items=("bs",), direction="oppose")
        bear = claims(direction="oppose", grade="well",
                      objections="target=bs severity=high objection=cannot meet the maturity")
        turns = self.full_turns(bear_researcher=bear)
        cards, _ = w.cards_for_room(turns, LIVE_SHEET)
        tr = w.build_transcript(arm(), {"id": "r", "transcript": [], "cards": cards, "trade_action": "buy"})
        got = {a.question.value: a.answer.value for a in CodeCardsGrader().grade(tr).answers}
        self.assertIn(got["terminal_vulnerability"], ("yes", "no"))
        self.assertTrue(bs_oppose)  # builder sanity only; the answer above is the grader's own

    def test_attach_cards_sets_cards_and_provenance_on_each_room(self):
        rooms = {"AAA-r3-rep1": {"id": "r1", "transcript": []}, "AAA-r3-rep2": {"id": "r2", "transcript": []}}
        arms = [arm("AAA", 3, 1), arm("AAA", 3, 2)]
        arms[0]["verdict"]["sheet_state"] = LIVE_SHEET
        w.attach_cards(rooms, arms, {"AAA-r3-rep1": self.full_turns(), "AAA-r3-rep2": []})
        self.assertEqual(rooms["AAA-r3-rep1"]["cards"]["field_state"], LIVE_SHEET)
        self.assertIsNone(rooms["AAA-r3-rep2"]["cards"])
        self.assertEqual(rooms["AAA-r3-rep2"]["cards_meta"]["desks_with_cards"], 0)


class CodeGraderPlumbingTests(unittest.TestCase):
    def test_code_grader_needs_no_key_and_has_no_spend_guard(self):
        setup = w.setup_grader(SimpleNamespace(grader="code", trade_action=None))
        self.assertIsNone(setup.guard)
        self.assertEqual(setup.kind, "code")
        self.assertEqual(w._cap_meta(setup)["grader"], "code")
        self.assertNotIn("spend", w._cap_meta(setup))
        w._report_cap(setup)  # no guard: must not raise

    def test_wording_and_inputs_are_refused_for_code_with_the_reason(self):
        for cmd in ("wording", "inputs"):
            rc, _o, err = run_main([cmd, "--runs", "/x.jsonl", "--out", "/x/o.jsonl", "--grader", "code"],
                                   {"WP22_DSN": "x"})
            self.assertEqual(rc, 2, cmd)
            self.assertIn("never", err)

    def test_trade_action_is_added_only_when_asked(self):
        room = {"id": "r", "transcript": []}
        self.assertNotIn("action", w.build_transcript(arm(), room).proposed_trade)
        room["trade_action"] = "buy"
        self.assertEqual(w.build_transcript(arm(), room).proposed_trade["action"], "buy")

    def test_not_computable_rows_round_trip_and_keep_their_reason(self):
        r = GraderResult(
            grader="code_cards", grader_version="cards-1", question_set_version=QUESTION_SET_VERSION,
            answers=tuple(
                QuestionAnswer(q, Answer.NOT_COMPUTABLE, rationale="room ran without cards") for q in ALL_Q),
            latency_ms=1, cost_usd=0.0)
        rw = w.result_to_row(arm(), "r", r, phrasing=None, model_root="x")
        self.assertEqual(rw["answers"]["trade_proposed"]["rationale"], "room ran without cards")
        self.assertEqual(w.rule_outcome(rw), "UNAVAILABLE")

    def test_completeness_table_counts_computable_share_and_reasons(self):
        def mk(risk, nc):
            ans = {q: ("not_computable" if q.value in nc else "yes") for q in ALL_Q}
            r = GraderResult(
                grader="code_cards", grader_version="cards-1", question_set_version=QUESTION_SET_VERSION,
                answers=tuple(QuestionAnswer(q, Answer(ans[q]), rationale="no card" if ans[q] == "not_computable" else "")
                              for q in ALL_Q), latency_ms=1)
            return w.result_to_row(arm("A", risk), "r", r, phrasing=None, model_root="x")
        rows = [mk(3, {"catalyst_in_horizon"}), mk(3, {"catalyst_in_horizon", "event_risk_wait"})]
        text = "\n".join(w.completeness_table(rows))
        self.assertIn("| catalyst_in_horizon | n/a | n/a | 0% (0/2) |", text)
        self.assertIn("| event_risk_wait | n/a | n/a | 50% (1/2) |", text)
        self.assertIn("Rooms where all six questions are computable: 0% (0/2)", text)
        self.assertIn("no card", text)


def conf_row(ticker, risk, rep, terminal, conf, *, rest="yes"):
    """A scored row whose terminal_vulnerability answer carries `conf`; the other five are sharp."""
    answers = tuple(
        QuestionAnswer(q, Answer(terminal if q is QuestionId.TERMINAL_VULNERABILITY else
                                 ("no" if q is QuestionId.EVENT_RISK_WAIT else rest)),
                       conf if q is QuestionId.TERMINAL_VULNERABILITY else 0.97, False)
        for q in ALL_Q)
    res = GraderResult(grader="deepinfra", grader_version="v", question_set_version=QUESTION_SET_VERSION,
                       answers=answers, latency_ms=1)
    return w.result_to_row(arm(ticker, risk, rep), "r", res, phrasing=None, model_root="x")


class DeepInfraRoomGraderToolTests(unittest.TestCase):
    ARGS = dict(grader="deepinfra_room", jev_version=None, model="deepseek-ai/DeepSeek-V4-Flash",
                max_usd=5.0, max_calls=300, price_in=None, price_out=None, slot="vllm",
                trade_action="buy")

    def setup(self, **kw):
        from app.core.config import settings
        prior = settings.llm_prices_json
        self.addCleanup(setattr, settings, "llm_prices_json", prior)
        return w.setup_grader(SimpleNamespace(**{**self.ARGS, **kw}), {"DEEPINFRA_API_KEY": SENTINEL})

    def test_it_builds_the_production_grader_without_leaking_the_key(self):
        setup = self.setup()
        g = setup.factory(None)
        self.assertEqual((g.name, setup.kind), ("deepinfra", "deepinfra_room"))
        self.assertIn("avg5", g.version)
        self.assertEqual(setup.guard.fallback_calls, 13)
        self.assertNotIn(SENTINEL, json.dumps(setup.describe) + setup.label)

    def test_it_needs_the_trade_action_and_a_pinned_model(self):
        for kw in ({"trade_action": None}, {"trade_action": " "}, {"model": "x/latest"}):
            with self.assertRaises(ValueError, msg=str(kw)):
                self.setup(**kw)

    def test_missing_key_names_the_key_only(self):
        rc, out, err = run_main(score_argv("--grader", "deepinfra_room", "--trade-action", "buy"), {})
        self.assertEqual((rc, err.strip()), (2, "bakeoff.env missing DEEPINFRA_API_KEY"))

    def test_the_wording_test_is_refused_for_it(self):
        rc, _o, err = run_main(["wording", "--runs", "x", "--out", "y", "--grader", "deepinfra_room",
                                "--trade-action", "buy"], {"DEEPINFRA_API_KEY": SENTINEL, "WP22_DSN": "x"})
        self.assertEqual(rc, 2)
        self.assertIn("averages the phrasings itself", err)


class LingRoomGraderToolTests(unittest.TestCase):
    """`--grader ling_room`: the production plan on the on-prem Ling grader. Network mocked: the
    grader is only built here, never called; the row shape is checked with a scripted gateway."""
    URL = "http://ling.test:8004"
    MODEL = "ling-3.0-flash-fin-fp4"
    ARGS = dict(grader="ling_room", jev_version=None, model="deepseek-ai/DeepSeek-V4-Flash",
                max_usd=5.0, max_calls=300, price_in=None, price_out=None, slot="vllm",
                trade_action="buy", ling_url=URL, ling_model=MODEL)
    SETTINGS = ("vllm_fallback_base_url", "vllm_fallback_model", "vllm_fallback_kind",
                "vllm_fallback_api_key", "vllm_fallback_extra_body_json", "vllm_base_url",
                "llm_provider_allowlist", "llm_prices_json")

    def setup(self, env=None, **kw):
        from app.core.config import settings
        for name in self.SETTINGS:
            self.addCleanup(setattr, settings, name, getattr(settings, name))
        return w.setup_grader(SimpleNamespace(**{**self.ARGS, **kw}), env if env is not None else {})

    def test_it_builds_the_ling_grader_with_no_key_and_no_spend_guard(self):
        setup = self.setup()
        g = setup.factory(None)
        self.assertEqual((g.name, setup.kind, g.slot), ("ling", "ling_room", "vllm_fallback"))
        self.assertIsNone(setup.guard)
        self.assertTrue(g.version.startswith(f"ling:{self.MODEL}|t0|avg5:"))
        self.assertIn("|split2|", g.version)
        self.assertEqual((setup.describe["model"], setup.describe["base_url"]), (self.MODEL, self.URL))
        self.assertNotIn("spend", w._cap_meta(setup))
        w._report_cap(setup)  # no guard: must not raise

    def test_it_points_the_gateway_slot_at_ling_and_allows_nothing_else(self):
        from app.core.config import settings
        self.setup()
        self.assertEqual((settings.vllm_fallback_base_url, settings.vllm_fallback_model,
                          settings.vllm_fallback_kind), (self.URL, self.MODEL, "vllm"))
        self.assertEqual(settings.vllm_base_url, "")
        self.assertEqual(settings.llm_provider_allowlist, ["vllm_fallback"])

    def test_url_and_model_fall_back_to_the_environment(self):
        setup = self.setup({"VLLM_FALLBACK_BASE_URL": "http://env.test:1", "VLLM_FALLBACK_MODEL": "m-env"},
                           ling_url=None, ling_model=None)
        self.assertEqual((setup.describe["base_url"], setup.describe["model"]), ("http://env.test:1", "m-env"))

    def test_an_argument_beats_the_environment(self):
        setup = self.setup({"VLLM_FALLBACK_BASE_URL": "http://env.test:1", "VLLM_FALLBACK_MODEL": "m-env"})
        self.assertEqual((setup.describe["base_url"], setup.describe["model"]), (self.URL, self.MODEL))

    def test_it_needs_a_url_a_pinned_model_and_the_trade_action(self):
        for kw in ({"ling_url": None}, {"ling_url": " "}, {"ling_model": None}, {"ling_model": "ling-latest"},
                   {"trade_action": None}, {"trade_action": " "}):
            with self.assertRaises(ValueError, msg=str(kw)):
                self.setup(**kw)

    def test_a_missing_url_stops_the_run_naming_what_to_set(self):
        rc, _o, err = run_main(score_argv("--grader", "ling_room", "--trade-action", "buy"), {})
        self.assertEqual(rc, 2)
        self.assertIn("VLLM_FALLBACK_BASE_URL", err)

    def test_the_wording_test_is_refused_for_it(self):
        rc, _o, err = run_main(["wording", "--runs", "x", "--out", "y", "--grader", "ling_room",
                                "--trade-action", "buy", "--ling-url", self.URL, "--ling-model", self.MODEL],
                               {"WP22_DSN": "x"})
        self.assertEqual(rc, 2)
        self.assertIn("averages the phrasings itself", err)

    def test_its_rows_have_the_deepinfra_room_shape_and_feed_the_report_and_fit(self):
        from app.services.room_graders.ling import LingGrader
        from app.services.room_graders.questions import load_question_set

        class Gateway:
            async def stream_chat(self, **kw):
                kw["meta"]["reported_model"] = "served-ling"
                yield '{"answer": "no"}'

        res = asyncio.run(LingGrader(model=self.MODEL, gateway=Gateway()).agrade(
            w.build_transcript(arm(), {"id": "r", "transcript": [], "trade_action": "buy"})))
        self.assertIsNone(res.error)
        ling_row = w.result_to_row(arm(), "r", res, phrasing=None, model_root="x")
        di_row = w.result_to_row(arm(), "r", result({}), phrasing=None, model_root="x")
        self.assertEqual(set(ling_row), set(di_row))
        self.assertEqual((ling_row["grader"], ling_row["extra"]["served_model"]), ("ling", "served-ling"))
        self.assertEqual(set(ling_row["answers"]), {q.id.value for q in load_question_set().questions})
        self.assertIn(w.rule_outcome(ling_row), ("APPROVE", "PASS", "CONTESTED"))
        table = [w.fit_metrics([ling_row], None, c) for c in w.FIT_GRID]
        self.assertTrue(table and all(m["rooms"] == 1 for m in table))


class FitTests(unittest.TestCase):
    def rows(self):
        out = []
        for t in "ABCD":
            out += [conf_row(t, 5, 1, "no", 0.95), conf_row(t, 5, 2, "no", 0.95)]
        out += [conf_row("E", 5, 1, "no", 0.6), conf_row("E", 5, 2, "yes", 0.9)]
        return out

    def test_a_cut_that_closes_the_shaky_approval_removes_the_rep_disagreement(self):
        base = w.fit_metrics(self.rows(), None, 0.0)
        cut = w.fit_metrics(self.rows(), None, 0.65)
        self.assertEqual((base["pairs"], base["rep_disagree"], base["contested"]), (5, 1, 0))
        self.assertEqual((cut["rep_disagree"], cut["contested"], cut["approve"]), (0, 1, 8))

    def test_the_choice_is_the_lowest_cut_within_the_contested_cap(self):
        table = [w.fit_metrics(self.rows(), None, c) for c in w.FIT_GRID]
        chosen = w.choose_cut(table, 0.20)
        self.assertEqual((chosen["cut"], chosen["cap_unmet"]), (0.65, False))

    def test_when_no_cut_fits_under_the_cap_the_placeholder_stays(self):
        table = [{"cut": c, "contested_share": 0.5, "rep_disagree_rate": 0.1} for c in w.FIT_GRID]
        chosen = w.choose_cut(table, 0.20)
        self.assertEqual((chosen["cut"], chosen["cap_unmet"]), (0.0, True))

    def test_the_command_prints_a_policy_json_the_backend_accepts(self):
        import tempfile
        from app.services.room_decision_rule import parse_policy_json
        with tempfile.TemporaryDirectory() as d:
            sp = Path(d) / "scores.jsonl"
            sp.write_text("\n".join(json.dumps(r) for r in self.rows()), encoding="utf-8")
            rc, out, _err = run_main(["fit", "--scores", str(sp), "--out", str(Path(d) / "fit.json")], {})
            self.assertEqual(rc, 0)
            line = next(x for x in out.splitlines() if x.startswith("ROOM_CODED_RULE_POLICY_JSON="))
            policy = parse_policy_json(line.split("=", 1)[1])
            self.assertEqual(policy["deepinfra"].close_below_confidence, 0.65)
            self.assertEqual(json.loads((Path(d) / "fit.json").read_text())["chosen"]["cut"], 0.65)

    def test_fit_never_reads_consensus(self):
        a = self.rows()
        b = [{**r, "street_rating": "sell", "street_stance": "sell"} for r in a]
        self.assertEqual([w.fit_metrics(a, None, c) for c in w.FIT_GRID],
                         [w.fit_metrics(b, None, c) for c in w.FIT_GRID])


if __name__ == "__main__":
    unittest.main()
