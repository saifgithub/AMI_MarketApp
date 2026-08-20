"""DEF345 — a truncated backtest batch must not read as a finished one.

The CR164 sweep runs as `docker compose exec`, so any recreate of
`ami_api_alpha` kills it mid-batch: no traceback, no exit line, and a partial
batch left on disk whose every record is individually valid. `r70-outcome-2`
died that way at 17 of 450 planned runs and sat undetected for 2.5 h — no
per-record filter can catch it, because nothing about a truncated batch's
records is wrong.

The sentinel is written on the line after the sweep loop ends, so a process
that died before getting there cannot have produced one. Absence is the
evidence. These tests pin both halves: that the sweep writes it with the
planned count, and that the report refuses a batch without it.
"""

from __future__ import annotations

import json

import pytest

from scripts.backtest_sweep import write_completion_sentinel


def test_sentinel_records_the_planned_count_not_just_the_completed(tmp_path):
    """The planned total is the whole point — completed alone cannot prove
    completeness, since 17-of-450 and 17-of-17 have identical record sets."""
    path = write_completion_sentinel(
        tmp_path, "b1", planned=450, completed=448, failed=2, outages=0,
    )

    body = json.loads(path.read_text())
    assert path.name == "complete_b1.json"
    assert body["planned_pairs"] == 450
    assert body["completed"] == 448
    assert body["failed"] == 2
    assert body["outage_failsafes"] == 0
    assert body["finished_at"]


def test_report_refuses_a_batch_with_no_sentinel(tmp_path, capsys, monkeypatch):
    """A killed sweep leaves no sentinel; the report must exit 5 rather than
    score a truncated sample as if it were the batch."""
    from scripts import backtest_report

    monkeypatch.setattr(
        "sys.argv",
        ["backtest_report.py", "--batch-id", "ghost", "--out-dir", str(tmp_path)],
    )
    rc = backtest_report.main()

    assert rc == 5, "a batch with no completion sentinel must not be scored"
    out = capsys.readouterr().out
    assert "TRUNCATED" in out
    assert "--allow-partial" in out


def test_report_refusal_precedes_any_db_work(tmp_path, monkeypatch):
    """The guard must fire before the report touches the database — a
    truncated batch is unscoreable regardless of what the rows contain, and a
    guard that runs after loading is a guard that can be starved by a slow or
    unavailable DB."""
    from scripts import backtest_report

    def _boom():
        raise AssertionError("init_schema ran despite a missing sentinel")

    monkeypatch.setattr(backtest_report, "init_schema", _boom)
    monkeypatch.setattr(
        "sys.argv",
        ["backtest_report.py", "--batch-id", "ghost", "--out-dir", str(tmp_path)],
    )

    assert backtest_report.main() == 5


def test_allow_partial_is_an_explicit_opt_in(tmp_path, monkeypatch):
    """--allow-partial must get PAST the sentinel refusal (it then fails on
    the empty batch, which is a different, honest error)."""
    from scripts import backtest_report

    monkeypatch.setattr(
        "sys.argv",
        ["backtest_report.py", "--batch-id", "ghost", "--out-dir", str(tmp_path),
         "--allow-partial"],
    )

    assert backtest_report.main() != 5
