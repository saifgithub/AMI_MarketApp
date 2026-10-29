#!/usr/bin/env python3
"""CR266 — tests for evidence_card_report.py (stdlib unittest, no DB).

Pins the things that make the V2 card-pilot report trustworthy:

  1. REPAIR-AWARE FETCH: the runner's repaired desk turns live under flows
     room_envelope_repair / room_cards_repair, which base
     cards_run.fetch_turns (flow='room' only) misses. The query must filter
     the run's exact window across all three flows, success/non-null only,
     and the pure coalescing function must pick the LATEST turn per desk
     (latest successful repaired turn = the final decision input) with a
     deterministic ctid same-timestamp tiebreak — never multiplying desks.
  2. IDENTITY: ticker comes from the row's authoritative `ticker` field —
     never rsplit arm_key (that yields RIOT-r4 and breaks holdouts); rep via
     strict regex, arm_key risk cross-checked vs risk_score.
  3. GATE SHAPE: ICC(A,1) >= 0.85 and complete machine channels (4 desks x
     5 items, no duplicates) are SEPARATE requirements — ICC 1.0 on an
     incomplete room is not a pass. NaN ICC (too few tickers) is null, never
     a pass. sheet_state flows through to the score's field_state_source.
  4. CLI: bad input exits loudly; a failed gate exits 1 after writing the
     report.

Run from anywhere:
    python3 -m unittest test_evidence_card_report   # inside tools/
    python3 tools/test_evidence_card_report.py      # from room_investigation_V2/
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import evidence_card_report as ecr
import evidence_gate_fit as fit
from evidence_gate_fit import RoomScore

ALL_LIVE = {f: "live" for fields in fit.ITEM_FIELD_REGISTRY.values()
            for f in fields}


def _claims(cards: list[str]) -> str:
    return "[CLAIMS]\n" + "\n".join(cards) + "\n[/CLAIMS]"


def _complete_turns(n_well: int = 20) -> list[dict]:
    """One card per desk per item, all support/data=yes; the first n_well
    desk-major cells (of the 20-cell census) are well, the rest unsupported
    → net_support = n_well/20 under the normalized CR266 contract."""
    turns = []
    for di, desk in enumerate(fit.REQUIRED_DESKS):
        lines = []
        for ii, item in enumerate(fit.ITEM_FIELD_REGISTRY):
            grade = "well" if di * 5 + ii < n_well else "unsupported"
            lines.append(f"item={item} dir=support grade={grade} "
                         f"data=yes claim=x")
        turns.append({"agent_id": desk, "response_text": _claims(lines)})
    return turns


def _arm(ticker="RIOT", key="RIOT-r4-rep1", risk=4, status="completed",
         sheet_state=None):
    return {
        "ticker": ticker, "arm_key": key, "risk_score": risk,
        "status": status, "user_id": "u1",
        "triggered_at": "2026-10-20T00:00:00+00:00",
        "finished_at": "2026-10-20T00:05:00+00:00",
        "verdict": {"action": "APPROVE", "sheet_state": sheet_state},
    }


def _room(ticker="T1", level=4, rep="1", score=0.5, available=True,
          missing=()):
    return RoomScore(
        ticker=ticker, level=level, rep=rep,
        score=score if available else None,
        net_support=score if available else None,
        unresolved=0 if available else None,
        evidence_available=available, missing=tuple(missing),
        holdout=False, field_state_source="sheet_state",
    )


class CoalesceTests(unittest.TestCase):
    def test_latest_repair_wins(self) -> None:
        rows = [
            {"agent_id": "fundamentals_analyst", "created_at": "t1",
             "ctid": "(0,1)", "flow": "room",
             "response_text": "original"},
            {"agent_id": "fundamentals_analyst", "created_at": "t2",
             "ctid": "(0,2)", "flow": "room_envelope_repair",
             "response_text": "envelope repaired"},
            {"agent_id": "fundamentals_analyst", "created_at": "t3",
             "ctid": "(0,3)", "flow": "room_cards_repair",
             "response_text": "cards repaired"},
            {"agent_id": "bull_researcher", "created_at": "t1",
             "ctid": "(0,4)", "flow": "room", "response_text": "bull"},
        ]
        out = ecr.coalesce_latest_per_desk(rows)
        by_desk = {t["agent_id"]: t for t in out}
        self.assertEqual(by_desk["fundamentals_analyst"]["response_text"],
                         "cards repaired")
        self.assertEqual(by_desk["fundamentals_analyst"]["flow"],
                         "room_cards_repair")
        self.assertEqual(by_desk["bull_researcher"]["response_text"], "bull")

    def test_same_timestamp_ctid_tiebreak_last_wins(self) -> None:
        # rows arrive created_at ASC, ctid ASC; same created_at → the later
        # ctid (physical insert order) is the later row and wins.
        rows = [
            {"agent_id": "bear_researcher", "created_at": "t1",
             "ctid": "(0,1)", "flow": "room", "response_text": "first"},
            {"agent_id": "bear_researcher", "created_at": "t1",
             "ctid": "(0,2)", "flow": "room_cards_repair",
             "response_text": "second"},
        ]
        out = ecr.coalesce_latest_per_desk(rows)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["response_text"], "second")

    def test_never_multiplies_desks_and_desk_order(self) -> None:
        rows = [
            {"agent_id": d, "created_at": f"t{i}", "ctid": f"(0,{i})",
             "flow": "room", "response_text": d}
            for i, d in enumerate(
                ["research_manager", "bear_researcher",
                 "research_manager", "fundamentals_analyst",
                 "bull_researcher"])
        ]
        rows.append({"agent_id": "not_a_desk", "created_at": "t9",
                     "ctid": "(0,9)", "flow": "room",
                     "response_text": "ignored"})
        out = ecr.coalesce_latest_per_desk(rows)
        self.assertEqual([t["agent_id"] for t in out],
                         list(fit.REQUIRED_DESKS))

    def test_empty_input_gives_empty_turns(self) -> None:
        self.assertEqual(ecr.coalesce_latest_per_desk([]), [])


class QueryBuilderTests(unittest.TestCase):
    def test_sql_filters_flows_window_success_and_order(self) -> None:
        sql = ecr.turns_sql()
        for flow in ("'room'", "'room_envelope_repair'",
                     "'room_cards_repair'"):
            self.assertIn(flow, sql)
        self.assertIn("error IS NULL", sql)
        self.assertIn("response_text IS NOT NULL", sql)
        self.assertIn("created_at >= :after", sql)
        self.assertIn("created_at <= :before", sql)
        self.assertIn("ORDER BY created_at ASC, ctid ASC", sql)
        for i in range(4):
            self.assertIn(f":d{i}", sql)  # desks bound, not string-built

    def test_params_bind_exact_window_and_user(self) -> None:
        arm = _arm()
        p = ecr.turns_params(arm)
        self.assertEqual(p["uid"], "u1")
        self.assertEqual(p["after"], arm["triggered_at"])
        self.assertEqual(p["before"], arm["finished_at"])
        self.assertEqual([p[f"d{i}"] for i in range(4)],
                         list(fit.REQUIRED_DESKS))


class FakeFetchTests(unittest.TestCase):
    """Fake-fetch level: the DB call sends exactly the inspected SQL with the
    arm's window; sqlalchemy is stubbed, no service touched."""

    def _run_fake(self, arm, rows):
        calls = []

        class _Result:
            def __init__(self, rs):
                self._rs = rs

            def mappings(self):
                return self

            def all(self):
                return self._rs

        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def execute(self, clause, params):
                calls.append((str(clause), dict(params)))
                return _Result(rows)

        class _Eng:
            def connect(self):
                return _Conn()

        fake_sa = types.ModuleType("sqlalchemy")
        fake_sa.create_engine = lambda dsn: _Eng()
        fake_sa.text = lambda s: s
        with mock.patch.dict(sys.modules, {"sqlalchemy": fake_sa}):
            out = ecr.fetch_turns_repair_aware("postgresql://secret-dsn",
                                               arm)
        return out, calls

    def test_fetch_executes_inspected_sql_with_window_params(self) -> None:
        arm = _arm()
        rows = [{"agent_id": "fundamentals_analyst",
                 "response_text": "x", "flow": "room_cards_repair",
                 "created_at": "t2", "ctid": "(0,2)"}]
        out, calls = self._run_fake(arm, rows)
        self.assertEqual(len(calls), 1)
        sql, params = calls[0]
        self.assertEqual(sql, ecr.turns_sql())
        self.assertEqual(params, ecr.turns_params(arm))
        self.assertEqual(out, rows)  # raw rows incl. flow/ctid preserved)


class IdentityTests(unittest.TestCase):
    def test_ticker_authoritative_even_when_key_prefix_lying(self) -> None:
        # the holdout trap: rsplitting arm_key yields "RIOT-r4"; the row
        # ticker must win, so HOLDOUTS matching still works downstream.
        ticker, rep = ecr.parse_arm_identity(
            _arm(ticker="RIOT", key="AAPL-r4-rep2"))
        self.assertEqual((ticker, rep), ("RIOT", "2"))

    def test_rep_parsed_with_r4_segment_and_dash_tickers(self) -> None:
        self.assertEqual(ecr.parse_arm_identity(
            _arm(ticker="BRK-B", key="BRK-B-r4-rep1")), ("BRK-B", "1"))
        self.assertEqual(ecr.parse_arm_identity(
            _arm(ticker="X", key="X-r5-rep12", risk=5)), ("X", "12"))

    def test_bad_key_and_risk_mismatch_raise(self) -> None:
        with self.assertRaises(ecr.ArmKeyError):
            ecr.parse_arm_identity(_arm(key="RIOT-r4"))       # no -rep
        with self.assertRaises(ecr.ArmKeyError):
            ecr.parse_arm_identity(_arm(key="RIOT-r4-rep"))   # no rep digit
        with self.assertRaises(ecr.ArmKeyError):
            ecr.parse_arm_identity(_arm(key="RIOT-r3-rep1"))  # risk mismatch
        with self.assertRaises(ecr.ArmKeyError):
            ecr.parse_arm_identity(_arm(ticker=""))           # no ticker


class ReportTests(unittest.TestCase):
    def _report(self, rooms):
        return ecr.assemble_report("test-model", rooms, {})

    def test_icc_pass_and_coverage_pass_gate_pass(self) -> None:
        rooms = []
        for i, t in enumerate(("A", "B", "C", "D")):
            v = 0.5 + i * 0.1
            for rep in ("1", "2"):
                rooms.append(_room(t, 4, rep, score=v))
        r = self._report(rooms)
        self.assertEqual(r["icc_A1"], 1.0)
        self.assertTrue(r["icc_pass"])
        self.assertTrue(r["coverage_pass"])
        self.assertTrue(r["registry_state_pass"])
        self.assertTrue(r["corpus_pass"])
        self.assertTrue(r["gate_pass"])
        self.assertEqual(r["icc_required"], 0.85)
        self.assertNotIn("thresholds", json.dumps(r))

    def test_icc_fail(self) -> None:
        rooms = []
        for t in ("A", "B", "C", "D", "E"):
            rooms.append(_room(t, 4, "1", score=1.0))
            rooms.append(_room(t, 4, "2", score=0.0))
        r = self._report(rooms)
        self.assertEqual(r["icc_A1"], 0.0)
        self.assertFalse(r["icc_pass"])
        self.assertFalse(r["gate_pass"])

    def test_nan_icc_is_null_never_a_pass(self) -> None:
        rooms = [_room("A", 4, "1", 0.5), _room("A", 4, "2", 0.5),
                 _room("B", 4, "1", 0.7), _room("B", 4, "2", 0.7)]
        r = self._report(rooms)
        self.assertIsNone(r["icc_A1"])
        self.assertFalse(r["icc_pass"])
        self.assertFalse(r["gate_pass"])
        self.assertTrue(r["coverage_pass"])

    def test_coverage_prevents_false_pass_at_icc_one(self) -> None:
        # every scored room agrees perfectly across reps (ICC 1.0) but one
        # room lost a desk: coverage must fail the gate on its own. distinct
        # per-ticker values keep ICC(A,1) defined (zero subject variance is
        # 0/0 undefined, a different case pinned in test_nan_icc_*).
        rooms = []
        for i, t in enumerate(("A", "B", "C")):
            v = 0.6 + i * 0.05
            rooms.append(_room(t, 4, "1", v))
            rooms.append(_room(t, 4, "2", v))
        rooms.append(_room("D", 4, "1", 0.9))
        rooms.append(_room("D", 4, "2", available=False,
                           missing=("cards:bear_researcher",)))
        r = self._report(rooms)
        self.assertEqual(r["icc_A1"], 1.0)
        self.assertTrue(r["icc_pass"])
        self.assertFalse(r["coverage_pass"])
        self.assertFalse(r["gate_pass"])
        self.assertEqual(r["counts"]["rooms_unscorable"], 1)
        self.assertEqual(r["coverage_by_risk_rep"]["R4"]["1"],
                         {"rooms": 4, "complete": 4})
        self.assertEqual(r["coverage_by_risk_rep"]["R4"]["2"],
                         {"rooms": 4, "complete": 3})
        self.assertEqual(r["unscorable_rooms"], [{
            "ticker": "D", "rep": "2", "risk": "R4",
            "missing": ["cards:bear_researcher"],
        }])

    def test_duplicate_markers_counted_and_coverage_fails(self) -> None:
        rooms = []
        for t in ("A", "B", "C"):
            rooms.append(_room(t, 4, "1", 0.6))
            rooms.append(_room(t, 4, "2", 0.6))
        rooms.append(_room("E", 4, "1", available=False,
                           missing=("duplicate:bull_researcher:eq",)))
        r = self._report(rooms)
        self.assertEqual(r["counts"]["duplicate_markers"], 1)
        self.assertFalse(r["coverage_pass"])
        self.assertFalse(r["gate_pass"])

    def test_multi_level_keeps_icc_per_risk_and_null_headline(self) -> None:
        rooms = []
        for lvl in (4, 5):
            for i, t in enumerate(("A", "B", "C")):
                v = 0.6 + i * 0.05
                rooms.append(_room(t, lvl, "1", v))
                rooms.append(_room(t, lvl, "2", v))
        r = self._report(rooms)
        self.assertIsNone(r["icc_A1"])
        self.assertEqual(r["icc_by_risk"], {"R4": 1.0, "R5": 1.0})
        self.assertTrue(r["gate_pass"])
        self.assertTrue(any("multiple risk levels" in lim
                            for lim in r["limitations"]))

    def test_anomalies_and_field_state_surface_in_counts(self) -> None:
        rooms = [_room("A", 4, "1", 0.6), _room("A", 4, "2", 0.6),
                 _room("B", 4, "1", 0.7), _room("B", 4, "2", 0.7),
                 _room("C", 4, "1", 0.8), _room("C", 4, "2", 0.8)]
        tally = {"field_state_source:sheet_state": 4,
                 "field_state_source:card_self_report": 2}
        r = ecr.assemble_report(
            "m", rooms, tally, {"arms_bad_key": 2, "arms_not_completed": 3})
        self.assertEqual(r["counts"]["arms_bad_key"], 2)
        self.assertEqual(r["counts"]["arms_not_completed"], 3)
        self.assertEqual(r["field_state_source"],
                         {"sheet_state": 4, "card_self_report": 2})
        self.assertTrue(r["icc_pass"])       # survivors still agree
        self.assertTrue(r["coverage_pass"])
        self.assertFalse(r["registry_state_pass"])
        self.assertFalse(r["corpus_pass"])
        self.assertFalse(r["gate_pass"])

    def test_registry_state_required_for_gate(self) -> None:
        # non-vacuity: ICC and coverage perfect, anomalies zero — a single
        # card_self_report room must still fail the gate on its own.
        rooms = []
        for i, t in enumerate(("A", "B", "C", "D")):
            v = 0.5 + i * 0.1
            for rep in ("1", "2"):
                rooms.append(_room(t, 4, rep, score=v))
        tally = {"field_state_source:sheet_state": 7,
                 "field_state_source:card_self_report": 1}
        r = ecr.assemble_report("m", rooms, tally)
        self.assertTrue(r["icc_pass"])
        self.assertTrue(r["coverage_pass"])
        self.assertTrue(r["corpus_pass"])
        self.assertFalse(r["registry_state_pass"])
        self.assertFalse(r["gate_pass"])
        self.assertEqual(r["corpus"]["card_self_report_rooms"], 1)

    def test_duplicate_keys_fail_corpus_pass(self) -> None:
        # non-vacuity: same (ticker, risk, rep) scored twice — the duplicate
        # is skipped for ICC (first wins), so numbers look clean; corpus_pass
        # must catch the skipped row.
        rooms = []
        for i, t in enumerate(("A", "B", "C")):
            v = 0.5 + i * 0.1
            rooms.append(_room(t, 4, "1", v))
            rooms.append(_room(t, 4, "2", v))
        rooms.append(_room("A", 4, "1", score=0.9))  # re-run of A rep 1
        r = self._report(rooms)
        self.assertTrue(r["icc_pass"])
        self.assertTrue(r["coverage_pass"])
        self.assertTrue(r["registry_state_pass"])
        self.assertFalse(r["corpus_pass"])
        self.assertFalse(r["gate_pass"])
        self.assertEqual(r["counts"]["rooms_duplicate_key"], 1)
        self.assertEqual(r["corpus"]["duplicate_keys"], 1)

    def test_loader_anomalies_fail_corpus_pass(self) -> None:
        # non-vacuity: each loader anomaly class independently fails the
        # gate even when every loaded room is complete and agrees.
        rooms = []
        for i, t in enumerate(("A", "B", "C")):
            v = 0.5 + i * 0.1
            rooms.append(_room(t, 4, "1", v))
            rooms.append(_room(t, 4, "2", v))
        for anomaly in ({"arms_not_completed": 1},
                        {"arms_bad_key": 1},
                        {"rooms_empty_turns": 1}):
            with self.subTest(anomaly=anomaly):
                r = ecr.assemble_report("m", rooms, {}, anomaly)
                self.assertTrue(r["icc_pass"])
                self.assertTrue(r["coverage_pass"])
                self.assertTrue(r["registry_state_pass"])
                self.assertFalse(r["corpus_pass"])
                self.assertFalse(r["gate_pass"])
                self.assertEqual(r["corpus"]["loader_anomalies"], anomaly)

    def test_bad_level_rooms_fail_corpus_pass(self) -> None:
        # non-vacuity: a room dropped by score_corpus for a non R1..R5 level
        # is an excluded corpus row — the gate must not pass over it.
        rooms = [_room(t, 4, rep, 0.5 + i * 0.1)
                 for i, t in enumerate(("A", "B", "C"))
                 for rep in ("1", "2")]
        r = ecr.assemble_report("m", rooms, {"rooms_bad_level": 1})
        self.assertTrue(r["icc_pass"])
        self.assertTrue(r["coverage_pass"])
        self.assertFalse(r["corpus_pass"])
        self.assertFalse(r["gate_pass"])
        self.assertEqual(r["corpus"]["rooms_bad_level"], 1)

    def test_empty_corpus_is_not_a_pass(self) -> None:
        r = self._report([])
        self.assertFalse(r["icc_pass"])
        self.assertFalse(r["coverage_pass"])
        self.assertFalse(r["gate_pass"])


class LoaderTests(unittest.TestCase):
    def _write_runs(self, tmp: Path, arms: list[dict]) -> Path:
        p = tmp / "runs.jsonl"
        p.write_text("".join(json.dumps(a) + "\n" for a in arms))
        return p

    def test_coalescing_and_sheet_state_applied_at_load(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        arm = _arm(sheet_state=ALL_LIVE)

        block = _claims([f"item={it} dir=support grade=well data=yes claim=x"
                         for it in fit.ITEM_FIELD_REGISTRY])

        def fake_fetcher(dsn, a):
            return [
                {"agent_id": "fundamentals_analyst", "created_at": "t1",
                 "ctid": "(0,1)", "flow": "room",
                 "response_text": "original, no claims"},
                {"agent_id": "fundamentals_analyst", "created_at": "t2",
                 "ctid": "(0,2)", "flow": "room_cards_repair",
                 "response_text": block},
            ] + [{"agent_id": d, "created_at": "t1", "ctid": f"(0,{i})",
                  "flow": "room", "response_text": block}
                 for i, d in enumerate(list(fit.REQUIRED_DESKS)[1:], 2)]

        path = self._write_runs(tmp, [arm])
        records, anomalies = ecr.load_run_records(path, None,
                                                  fetcher=fake_fetcher)
        self.assertEqual(anomalies, {})
        self.assertEqual(len(records), 1)
        rec = records[0]
        self.assertEqual((rec["ticker"], rec["rep"]), ("RIOT", "1"))
        self.assertEqual(rec["risk_score"], 4)
        self.assertEqual(rec["sheet_state"], ALL_LIVE)  # verdict forwarded
        by_desk = {t["agent_id"]: t for t in rec["turns"]}
        self.assertEqual(len(rec["turns"]), 4)  # one per desk, no multiply
        self.assertEqual(by_desk["fundamentals_analyst"]["response_text"],
                         block)

        # and the repaired turns score through the real contract
        rooms, tally = fit.score_corpus(records)
        self.assertEqual(len(rooms), 1)
        self.assertEqual(rooms[0].score, 1.0)
        self.assertEqual(tally["field_state_source:sheet_state"], 1)

    def test_anomalies_counted_not_guessed(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        arms = [
            _arm(status="failed"),
            _arm(ticker="X", key="X-r4"),            # bad key
            _arm(ticker="Y", key="Y-r3-rep1", risk=4),  # risk mismatch
        ]
        path = self._write_runs(tmp, arms)
        records, anomalies = ecr.load_run_records(
            path, None, fetcher=lambda dsn, a: [])
        self.assertEqual(records, [])
        self.assertEqual(anomalies, {
            "arms_not_completed": 1, "arms_bad_key": 2,
        })

    def test_unreadable_runs_file_exits_loudly(self) -> None:
        with self.assertRaises(SystemExit):
            ecr.load_run_records(Path("/nonexistent/runs.jsonl"), None,
                                 fetcher=lambda dsn, a: [])


class PipelineTests(unittest.TestCase):
    def test_sheet_state_forwarded_to_field_state_source(self) -> None:
        # forwarding proof: sheet_state lands as sheet_state, absence lands
        # as labelled card_self_report — and under the hardened gate a mixed
        # corpus can no longer pass on the survivors' ICC.
        records = []
        for rep in ("1", "2"):
            records.append({"ticker": "AAPL", "rep": rep, "risk_score": 4,
                            "turns": _complete_turns(10),
                            "sheet_state": ALL_LIVE, "verdict_action": "x"})
            records.append({"ticker": "MSFT", "rep": rep, "risk_score": 4,
                            "turns": _complete_turns(12), "sheet_state": None,
                            "verdict_action": "x"})
            records.append({"ticker": "NVDA", "rep": rep, "risk_score": 4,
                            "turns": _complete_turns(14), "sheet_state": None,
                            "verdict_action": "x"})
        rooms, tally = fit.score_corpus(records)
        r = ecr.assemble_report("m", rooms, tally)
        self.assertEqual(r["field_state_source"],
                         {"sheet_state": 2, "card_self_report": 4})
        self.assertEqual(r["icc_A1"], 1.0)
        self.assertFalse(r["registry_state_pass"])
        self.assertFalse(r["gate_pass"])
        # deterministic per-ticker scale: 10/20, 12/20, 14/20
        self.assertEqual(r["per_ticker"]["AAPL"]["scores"],
                         {"1": 0.5, "2": 0.5})
        self.assertEqual(r["per_ticker"]["NVDA"]["scores"],
                         {"1": 0.7, "2": 0.7})

    def test_all_registry_corpus_passes(self) -> None:
        records = []
        for i, t in enumerate(("AAPL", "MSFT", "NVDA")):
            for rep in ("1", "2"):
                records.append({"ticker": t, "rep": rep, "risk_score": 4,
                                "turns": _complete_turns(10 + 2 * i),
                                "sheet_state": ALL_LIVE,
                                "verdict_action": "x"})
        rooms, tally = fit.score_corpus(records)
        r = ecr.assemble_report("m", rooms, tally)
        self.assertEqual(r["field_state_source"],
                         {"sheet_state": 6, "card_self_report": 0})
        self.assertTrue(r["registry_state_pass"])
        self.assertTrue(r["corpus_pass"])
        self.assertTrue(r["gate_pass"])


class CliTests(unittest.TestCase):
    def _write_turns(self, tmp: Path, records: list[dict]) -> Path:
        p = tmp / "turns.jsonl"
        p.write_text("".join(json.dumps(r) + "\n" for r in records))
        return p

    def _pilot_records(self, broken: bool = False,
                       one_self_report: bool = False) -> list[dict]:
        records = []
        for i, t in enumerate(("AAPL", "MSFT", "NVDA", "TSLA", "AMD")):
            for rep in ("1", "2"):
                turns = _complete_turns(10 + 2 * i)
                if broken and t == "AMD" and rep == "2":
                    turns = turns[:3]  # research_manager missing
                rec = {"ticker": t, "rep": rep, "risk_score": 4,
                       "verdict": "APPROVE", "turns": turns}
                # the passing fixture runs entirely on registry sheet_state;
                # one_self_report exercises the registry_state_pass failure
                if not (one_self_report and t == "MSFT" and rep == "1"):
                    rec["sheet_state"] = ALL_LIVE
                records.append(rec)
        return records

    def _run_main(self, argv):
        old = sys.argv
        try:
            sys.argv = argv
            ecr.main()
        finally:
            sys.argv = old

    def test_end_to_end_turns_file_gate_pass(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        turns = self._write_turns(tmp, self._pilot_records())
        out_dir = tmp / "out"
        self._run_main(["evidence_card_report", "--provider", "test-model",
                        "--turns-file", str(turns), "--out-dir", str(out_dir)])
        report = json.loads(
            (out_dir / "card_report_test-model.json").read_text())
        self.assertEqual(report["provider"], "test-model")
        self.assertTrue(report["gate_pass"])
        self.assertTrue(report["icc_pass"])
        self.assertTrue(report["coverage_pass"])
        self.assertEqual(report["icc_A1"], 1.0)
        self.assertEqual(report["icc_required"], 0.85)
        self.assertEqual(report["counts"]["rooms"], 10)
        self.assertEqual(report["counts"]["rooms_unscorable"], 0)
        self.assertEqual(report["field_state_source"],
                         {"sheet_state": 10, "card_self_report": 0})
        self.assertTrue(report["registry_state_pass"])
        self.assertTrue(report["corpus_pass"])
        self.assertTrue(report["limitations"])
        self.assertNotIn("NaN", json.dumps(report))  # null, not NaN

    def test_cli_gate_fail_writes_report_then_exits_1(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        turns = self._write_turns(tmp, self._pilot_records(broken=True))
        out_dir = tmp / "out"
        with self.assertRaises(SystemExit) as cm:
            self._run_main(["evidence_card_report", "--provider", "m",
                            "--turns-file", str(turns),
                            "--out-dir", str(out_dir)])
        self.assertEqual(cm.exception.code, 1)
        report = json.loads((out_dir / "card_report_m.json").read_text())
        self.assertFalse(report["gate_pass"])
        self.assertFalse(report["coverage_pass"])
        self.assertEqual(report["counts"]["rooms_unscorable"], 1)

    def test_cli_registry_state_fail_writes_report_then_exits_1(self) -> None:
        # one room scored under the card_self_report approximation: ICC and
        # coverage are perfect, registry_state_pass alone must fail the gate.
        tmp = Path(tempfile.mkdtemp())
        turns = self._write_turns(
            tmp, self._pilot_records(one_self_report=True))
        out_dir = tmp / "out"
        with self.assertRaises(SystemExit) as cm:
            self._run_main(["evidence_card_report", "--provider", "m",
                            "--turns-file", str(turns),
                            "--out-dir", str(out_dir)])
        self.assertEqual(cm.exception.code, 1)
        report = json.loads((out_dir / "card_report_m.json").read_text())
        self.assertTrue(report["icc_pass"])
        self.assertTrue(report["coverage_pass"])
        self.assertFalse(report["registry_state_pass"])
        self.assertFalse(report["gate_pass"])
        self.assertEqual(report["corpus"]["card_self_report_rooms"], 1)

    def test_cli_requires_runs_or_turns_file(self) -> None:
        with self.assertRaises(SystemExit):
            self._run_main(["evidence_card_report", "--provider", "m"])

    def test_cli_runs_mode_requires_dsn(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        runs = tmp / "runs.jsonl"
        runs.write_text(json.dumps(_arm()) + "\n")
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit):
                self._run_main(["evidence_card_report", "--provider", "m",
                                "--runs", str(runs)])

    def test_cli_missing_provider_rejected(self) -> None:
        with self.assertRaises(SystemExit):
            self._run_main(["evidence_card_report", "--turns-file", "/x"])

    def test_cli_bad_runs_json_exits_loudly(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        runs = tmp / "runs.jsonl"
        runs.write_text("{not json}\n")
        with self.assertRaises(SystemExit):
            ecr.load_run_records(runs, None, fetcher=lambda dsn, a: [])

    def test_cli_unreadable_turns_file_exits_loudly(self) -> None:
        with self.assertRaises(SystemExit):
            ecr.load_turns_file(Path("/nonexistent/turns.jsonl"))


if __name__ == "__main__":
    unittest.main()
