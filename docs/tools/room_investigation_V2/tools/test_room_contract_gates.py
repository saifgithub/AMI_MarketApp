#!/usr/bin/env python3
"""Tests for room_contract_gates.py (stdlib unittest, no DB, no services).

Fake run_psql returns the json_agg payload a chunk read would produce; fake
gate where the wiring itself is under test. Everything runs against the real
library.scoring.gate_report / library.audit_db semantics — faking those would
defeat the point of an acceptance validator.

Run from anywhere:
    python3 -m unittest test_room_contract_gates   # inside tools/
    python3 tools/test_room_contract_gates.py      # from room_investigation_V2/
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import room_contract_gates as rcg  # noqa: E402
from library import audit_db, scoring  # noqa: E402

AFTER_ISO = "2026-10-27T10:00:00+00:00"
BEFORE_ISO = "2026-10-27T10:05:00+00:00"
UID_1 = "11111111-1111-5111-8111-111111111111"
UID_2 = "22222222-2222-5222-8222-222222222222"

PROSE_TEXT = "Coverage of the name. [STANCE: BULL | CONVICTION: HIGH]"
PM_TEXT = '{"action": "PASS", "size_pct": 1.0} — rationale'


def _psql_ts(base_second: float) -> str:
    """A psql -A timestamptz rendering inside the standard window."""
    sec = int(base_second)
    usec = int(round((base_second - sec) * 1_000_000))
    return f"2026-10-27 10:00:{sec:02d}.{usec:06d}+00"


def _row(uid: str, agent: str, ts: str, *, flow: str = "room",
         text: str = PROSE_TEXT, tokens: int = 100,
         error: str | None = None,
         constraint_status: str | None = "pass") -> dict:
    return {
        "user_id": uid, "agent_id": agent, "flow": flow,
        "provider": "ami-llm", "created_at": ts,
        "response_text": text, "output_tokens": tokens,
        "error": error, "constraint_status": constraint_status,
    }


def healthy_rows(uid: str) -> list[dict]:
    """A complete legacy-shape convene: 11 prose agents + 5 PM draws = 16
    base-flow rows, every prose turn enveloped, every PM draw parseable."""
    rows = [
        _row(uid, agent, _psql_ts(1 + i))
        for i, agent in enumerate(scoring.EXPECTED_PROSE_AGENTS)
    ]
    rows += [
        _row(uid, "portfolio_manager", _psql_ts(12 + i), flow="room_pm",
             text=PM_TEXT)
        for i in range(scoring.MIN_PM_DRAWS)
    ]
    return rows


def arm_record(key: str = "AAPL-r4-rep1", uid: str = UID_1,
               status: str = "completed", after: str = AFTER_ISO,
               before: str = BEFORE_ISO, **extra) -> dict:
    rec = {
        "arm_key": key, "user_id": uid, "status": status,
        "triggered_at": after, "finished_at": before,
        "error_message": None,
    }
    rec.update(extra)
    return rec


class FakePsql:
    """Records (sql, params) per call; returns the chunk's rows as one
    json_agg payload ("" when none — psql's NULL-aggregate output)."""

    def __init__(self, rows_by_uid: dict[str, list[dict]]):
        self.rows_by_uid = rows_by_uid
        self.calls: list[tuple[str, list]] = []

    def __call__(self, sql: str, params) -> str:
        params = list(params)
        self.calls.append((sql, params))
        rows = [r for uid in params for r in self.rows_by_uid.get(uid, [])]
        return json.dumps(rows) if rows else ""


class ParseTsTests(unittest.TestCase):
    def test_runner_iso_and_psql_formats_parse_equal(self) -> None:
        iso = rcg._parse_ts("2026-10-27T10:00:00.123456+00:00")
        psql = rcg._parse_ts("2026-10-27 10:00:00.123456+00")
        self.assertEqual(iso, psql)
        self.assertIsNotNone(iso.tzinfo)

    def test_z_suffix_and_naive(self) -> None:
        self.assertEqual(
            rcg._parse_ts("2026-10-27T10:00:00Z"),
            rcg._parse_ts("2026-10-27T10:00:00+00:00"),
        )
        naive = rcg._parse_ts("2026-10-27T10:00:00")
        self.assertEqual(naive.utcoffset().total_seconds(), 0)

    def test_minute_less_offset_padded(self) -> None:
        self.assertEqual(
            rcg._parse_ts("2026-10-27 10:00:00+03"),
            rcg._parse_ts("2026-10-27T10:00:00+03:00"),
        )

    def test_unparseable_is_loud(self) -> None:
        with self.assertRaises(ValueError):
            rcg._parse_ts("not-a-timestamp")


class LoadArmsTests(unittest.TestCase):
    def _write(self, tmp: Path, records: list[dict]) -> Path:
        p = tmp / "runs.jsonl"
        with open(p, "w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return p

    def test_latest_record_per_arm_key_wins(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        p = self._write(tmp, [
            arm_record("AAPL-rep1", status="script_error"),
            arm_record("AAPL-rep1", status="completed"),
        ])
        arms = rcg.load_arms(p)
        self.assertEqual(len(arms), 1)
        self.assertEqual(arms[0]["status"], "completed")

    def test_malformed_line_and_missing_key_are_loud(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        p = tmp / "runs.jsonl"
        p.write_text(json.dumps(arm_record()) + "\n{bad json\n")
        with self.assertRaisesRegex(ValueError, "line 2"):
            rcg.load_arms(p)
        p2 = self._write(tmp, [{"user_id": UID_1, "status": "completed"}])
        with self.assertRaisesRegex(ValueError, "arm_key"):
            rcg.load_arms(p2)


class FetchChunkTests(unittest.TestCase):
    """Chunk shape: one psql read per chunk, placeholders == params, values
    never interpolated into the SQL text."""

    def _gate_stub(self):
        class _Rep:
            ok = True
            findings = []
            stances = {}
        return lambda *a, **k: _Rep()

    def test_two_chunks_two_reads_parameterized(self) -> None:
        arms = [arm_record(f"T{i}-rep1", uid=f"00000000-0000-4000-8000-{i:012d}")
                for i in range(3)]
        fake = FakePsql({})
        rcg.gate_arms(arms, chunk_size=2, psql=fake, gate=self._gate_stub())
        self.assertEqual(len(fake.calls), 2)
        sql0, params0 = fake.calls[0]
        sql1, params1 = fake.calls[1]
        self.assertEqual(len(params0), 2)
        self.assertEqual(len(params1), 1)
        for sql, params in fake.calls:
            self.assertEqual(sql.count("%s"), len(params))
            for uid in params:
                self.assertNotIn(str(uid), sql)  # values travel as params
            self.assertIn("json_agg(", sql)
            self.assertIn("json_build_object(", sql)
            self.assertIn("FROM llm_audit", sql)
            self.assertIn("ORDER BY created_at, ctid) sub", sql)
            for field in ("agent_id", "flow", "provider", "created_at",
                          "response_text", "output_tokens", "error",
                          "constraint_status", "user_id"):
                self.assertIn(f"'{field}', {field}", sql)

    def test_default_chunk_size_is_25(self) -> None:
        arms = [arm_record(f"T{i}-rep1", uid=f"00000000-0000-4000-8000-{i:012d}")
                for i in range(30)]
        fake = FakePsql({})
        rcg.gate_arms(arms, psql=fake, gate=self._gate_stub())
        self.assertEqual(len(fake.calls), 2)
        self.assertEqual([len(c[1]) for c in fake.calls], [25, 5])

    def test_empty_chunk_read_yields_no_rows(self) -> None:
        self.assertEqual(rcg.fetch_chunk_rows([UID_1], FakePsql({})), [])
        self.assertEqual(rcg.fetch_chunk_rows([], FakePsql({})), [])

        def null_agg(sql, params):
            return "null"

        self.assertEqual(rcg.fetch_chunk_rows([UID_1], null_agg), [])


class BulkAuditTests(unittest.TestCase):
    def _audit(self) -> rcg.BulkAudit:
        # listed in the fetch order the real subquery guarantees
        # (ORDER BY created_at, ctid)
        rows = [
            _row(UID_1, "trader", "2026-10-27 10:00:00.000000+00",
                 text="first"),
            _row(UID_1, "bear_researcher", "2026-10-27 10:00:30.000000+00"),
            _row(UID_1, "trader", "2026-10-27 10:01:00.000000+00",
                 text="second"),
            _row(UID_2, "trader", "2026-10-27 10:00:15.000000+00",
                 text="other arm"),
        ]
        return rcg.BulkAudit(rows)

    def test_window_is_inclusive_both_formats(self) -> None:
        rows = [
            _row(UID_1, "trader", "2026-10-27 10:00:00.000000+00"),  # == after
            _row(UID_1, "trader", "2026-10-27 10:05:00.000000+00"),  # == before
            _row(UID_1, "trader", "2026-10-27 09:59:59.999999+00"),  # outside
            _row(UID_1, "trader", "2026-10-27 10:05:00.000001+00"),  # outside
        ]
        audit = rcg.BulkAudit(rows)
        in_window = audit.window_rows(UID_1, AFTER_ISO, BEFORE_ISO)
        self.assertEqual(len(in_window), 2)
        self.assertEqual(
            len(audit.window_rows(UID_1, None, None)), 4)
        self.assertEqual(len(audit.window_rows(UID_1, AFTER_ISO, None)), 3)

    def test_list_calls_scopes_user_and_window_in_fetch_order(self) -> None:
        audit = self._audit()
        calls = audit.list_calls(UID_1, after=AFTER_ISO, before=BEFORE_ISO)
        self.assertEqual([c.agent_id for c in calls],
                         ["trader", "bear_researcher", "trader"])
        self.assertEqual(calls[0].created_at,
                         "2026-10-27 10:00:00.000000+00")
        self.assertEqual(calls[0].provider, "ami-llm")
        self.assertEqual(calls[0].flow, "room")
        self.assertEqual([c.agent_id for c in audit.list_calls(UID_2)],
                         ["trader"])

    def test_get_field_nth_ambiguity_and_no_rows(self) -> None:
        audit = self._audit()
        with self.assertRaises(audit_db.AmbiguousQueryError):
            audit.get_field(UID_1, "trader", "response_text")
        self.assertEqual(audit.get_field(UID_1, "trader", "response_text",
                                         nth=0), "first")
        self.assertEqual(audit.get_field(UID_1, "trader", "response_text",
                                         nth=1), "second")
        with self.assertRaises(audit_db.NoRowsError):
            audit.get_field(UID_1, "trader", "response_text", nth=2)
        with self.assertRaises(audit_db.NoRowsError):
            audit.get_field(UID_1, "neutral_debator", "response_text")
        with self.assertRaises(ValueError):
            audit.get_field(UID_1, "trader", "bogus_field")

    def test_get_field_call_level_window_narrows_further(self) -> None:
        audit = self._audit()
        self.assertEqual(
            audit.get_field(UID_1, "trader", "response_text",
                            after="2026-10-27T10:00:30+00:00"), "second")
        with self.assertRaises(audit_db.AmbiguousQueryError):
            audit.get_field(UID_1, "trader", "response_text",
                            after="2026-10-27T09:00:00+00:00")

    def test_null_response_text_parity_with_psql_empty_output(self) -> None:
        audit = rcg.BulkAudit(
            [_row(UID_1, "trader", "2026-10-27 10:00:00+00", text=None)])
        self.assertEqual(audit.get_field(UID_1, "trader", "response_text"), "")

    def test_call_metrics_nth_per_agent_and_nulls(self) -> None:
        rows = [
            _row(UID_1, "trader", "2026-10-27 10:00:00+00", tokens=None,
                 error="", constraint_status=None),
            _row(UID_1, "bear_researcher", "2026-10-27 10:00:10+00"),
            _row(UID_1, "trader", "2026-10-27 10:00:20+00", tokens=5000),
        ]
        metrics = rcg.BulkAudit(rows).call_metrics(UID_1)
        self.assertEqual([(m.agent_id, m.nth) for m in metrics],
                         [("trader", 0), ("bear_researcher", 0),
                          ("trader", 1)])
        self.assertIsNone(metrics[0].output_tokens)
        self.assertIsNone(metrics[0].error)
        self.assertIsNone(metrics[0].constraint_status)
        self.assertEqual(metrics[2].output_tokens, 5000)

    def test_exceptions_are_audit_dbs_classes(self) -> None:
        self.assertIs(rcg.BulkAudit.NoRowsError, audit_db.NoRowsError)
        self.assertIs(rcg.BulkAudit.AmbiguousQueryError,
                      audit_db.AmbiguousQueryError)


class GateArmsTests(unittest.TestCase):
    def test_success_current_and_legacy_keys_pass(self) -> None:
        arms = [
            arm_record("RIOT-r4-rep1", uid=UID_1),
            arm_record("AAPL-rep1", uid=UID_2),  # legacy key shape
        ]
        fake = FakePsql({UID_1: healthy_rows(UID_1),
                         UID_2: healthy_rows(UID_2)})
        report = rcg.gate_arms(arms, psql=fake, gate=scoring.gate_report)
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(len(fake.calls), 1)  # both arms in one chunk
        for entry in report["arms"]:
            self.assertEqual(entry["audit_rows_in_window"], 16)
            self.assertTrue(entry["gate"]["ok"])
            self.assertEqual(entry["gate"]["findings"], [])
        self.assertEqual(report["arms"][0]["arm_key"], "RIOT-r4-rep1")
        self.assertIn("trader", report["arms"][0]["gate"]["stances"])
        self.assertEqual(report["arms"][0]["gate"]["stances"]
                         ["portfolio_manager"], "PASS,PASS,PASS,PASS,PASS")

    def test_exact_window_threads_to_gate_and_excludes_strays(self) -> None:
        calls = []

        def fake_gate(user_id, *, audit_module, after=None, before=None,
                      **kw):
            calls.append((user_id, after, before, audit_module))
            class _Rep:
                ok = True
                findings = []
                stances = {}
            return _Rep()

        stray = _row(UID_1, "trader", "2026-10-27 12:00:00+00",
                     text="later retry outside the window")
        rows = healthy_rows(UID_1) + [stray]
        report = rcg.gate_arms([arm_record()], psql=FakePsql({UID_1: rows}),
                               gate=fake_gate)
        self.assertTrue(report["ok"])
        (uid, after, before, audit_module), = calls
        self.assertEqual(uid, UID_1)
        self.assertEqual(after, AFTER_ISO)
        self.assertEqual(before, BEFORE_ISO)
        self.assertIsInstance(audit_module, rcg.BulkAudit)
        self.assertEqual(report["arms"][0]["audit_rows_in_window"], 16)

    def test_noncompleted_arm_is_a_loud_failure(self) -> None:
        fake = FakePsql({UID_1: healthy_rows(UID_1)})
        report = rcg.gate_arms(
            [arm_record(status="script_error",
                        error_message="boom"),
             arm_record("MSFT-r2-rep1", uid=UID_2)],
            psql=fake, gate=scoring.gate_report)
        self.assertFalse(report["ok"])
        self.assertTrue(any("script_error" in f for f in report["failures"]))
        self.assertEqual(len(fake.calls), 1)  # only the completed arm read
        self.assertEqual(len(fake.calls[0][1]), 1)

    def test_completed_arm_without_window_is_a_loud_failure(self) -> None:
        report = rcg.gate_arms([arm_record(finished_at=None)],
                               psql=FakePsql({}), gate=scoring.gate_report)
        self.assertFalse(report["ok"])
        self.assertTrue(any("window" in f for f in report["failures"]))

    def test_gate_finding_fails_the_run(self) -> None:
        bad_pm = _row(UID_1, "portfolio_manager",
                      "2026-10-27 10:00:12.000000+00", flow="room_pm",
                      text="no json here")
        rows = healthy_rows(UID_1)
        rows[-1] = bad_pm  # one PM draw unparseable
        report = rcg.gate_arms([arm_record()],
                               psql=FakePsql({UID_1: rows}),
                               gate=scoring.gate_report)
        self.assertFalse(report["ok"])
        kinds = [f["kind"] for f in report["arms"][0]["gate"]["findings"]]
        self.assertIn("PM_JSON_UNPARSEABLE", kinds)
        self.assertTrue(any("PM_JSON_UNPARSEABLE" in f
                            for f in report["failures"]))

    def test_no_audit_rows_is_a_failure_not_a_vacuous_pass(self) -> None:
        report = rcg.gate_arms([arm_record()], psql=FakePsql({}),
                               gate=scoring.gate_report)
        self.assertFalse(report["ok"])
        entry = report["arms"][0]
        self.assertEqual(entry["audit_rows_in_window"], 0)
        self.assertFalse(entry["gate"]["ok"])
        kinds = {f["kind"] for f in entry["gate"]["findings"]}
        self.assertIn("UNEXPECTED_CALL_COUNT", kinds)
        self.assertIn("MISSING_CALL", kinds)

    def test_empty_runs_file_refuses_vacuous_pass(self) -> None:
        report = rcg.gate_arms([], psql=FakePsql({}),
                               gate=scoring.gate_report)
        self.assertFalse(report["ok"])
        self.assertTrue(any("vacuous" in f for f in report["failures"]))

    def test_chunk_read_failure_fails_loudly_without_traceback(self) -> None:
        def boom(sql, params):
            raise RuntimeError("psql failed: connection lost")
        report = rcg.gate_arms([arm_record()], psql=boom,
                               gate=scoring.gate_report)
        self.assertFalse(report["ok"])
        self.assertTrue(any("chunk read failed" in f
                            for f in report["failures"]))
        self.assertIn("error", report["arms"][0])


class CliTests(unittest.TestCase):
    def _write_runs(self, tmp: Path, records: list[dict]) -> Path:
        p = tmp / "runs.jsonl"
        with open(p, "w") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")
        return p

    def _run_main(self, argv):
        try:
            return rcg.main(argv)
        except SystemExit as exc:
            return exc.code

    def test_exit_0_on_full_pass_writes_report(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        runs = self._write_runs(tmp, [arm_record()])
        out = tmp / "report.json"
        original = rcg.audit_db.run_psql
        rcg.audit_db.run_psql = FakePsql({UID_1: healthy_rows(UID_1)})
        try:
            code = self._run_main(["--runs", str(runs), "--out", str(out)])
        finally:
            rcg.audit_db.run_psql = original
        self.assertEqual(code, 0)
        report = json.loads(out.read_text())
        self.assertTrue(report["ok"])
        self.assertEqual(report["arms_total"], 1)
        self.assertEqual(report["runs"], str(runs))

    def test_exit_1_on_failure_still_writes_report(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        runs = self._write_runs(
            tmp, [arm_record(status="no_verdict", finished_at=BEFORE_ISO)])
        out = tmp / "report.json"
        original = rcg.audit_db.run_psql
        rcg.audit_db.run_psql = FakePsql({})
        try:
            code = self._run_main(["--runs", str(runs), "--out", str(out)])
        finally:
            rcg.audit_db.run_psql = original
        self.assertEqual(code, 1)
        report = json.loads(out.read_text())
        self.assertFalse(report["ok"])
        self.assertTrue(report["failures"])

    def test_missing_runs_and_bad_chunk_size_are_loud(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        out = tmp / "report.json"
        self.assertIsNotNone(self._run_main(
            ["--runs", str(tmp / "nope.jsonl"), "--out", str(out)]))
        runs = self._write_runs(tmp, [arm_record()])
        self.assertIsNotNone(self._run_main(
            ["--runs", str(runs), "--out", str(out), "--chunk-size", "0"]))

    def test_no_skip_option_exists(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        runs = self._write_runs(tmp, [arm_record()])
        with self.assertRaises(SystemExit):
            rcg.build_parser().parse_args(
                ["--runs", str(runs), "--out", "r.json", "--skip"])


if __name__ == "__main__":
    unittest.main()
