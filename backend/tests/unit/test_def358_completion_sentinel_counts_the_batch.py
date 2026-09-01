"""DEF358 — the sweep's completion sentinel must describe the BATCH, not the process.

DEF345 built `complete_<batch>.json` so nothing downstream could mistake a
killed sweep for a finished one: the file is written on the line after the
loop, so absence is the signal and a dead process cannot fake it.

The counting was wrong in the one case the file exists for. `backtest_sweep`
is resumable — on restart it skips every pair already terminal on disk — and
those skips incremented nothing. So a batch that finished across supervisor
relaunches stamped only the final process's tally: `r70-outcome-2` ran all 450
pairs and recorded `completed: 50`, which `backtest_report` printed verbatim,
labelled **COMPLETE**, one line above `Index rows: 450`. The field built to
tell whole from truncated was reporting the state it exists to rule out, and
the label was derived from the file existing rather than from what it said.

Two properties, one per half:
  * the sentinel's `completed` counts pairs terminal in the batch — run now or
    already on disk — with `ran_this_process` carrying the resume story;
  * the report's label is derived from the numbers, so a sweep that reached its
    end with pairs unrun says so instead of claiming COMPLETE.
"""

from __future__ import annotations

import json
import sys

import scripts.backtest_sweep as sweep
from scripts.backtest_report import _sentinel_line
from scripts.backtest_sweep import write_completion_sentinel


def _sentinel(tmp_path, **kw):
    write_completion_sentinel(tmp_path, "b1", **kw)
    return json.loads((tmp_path / "complete_b1.json").read_text())


def test_a_resumed_sweep_counts_the_whole_batch(tmp_path):
    """400 pairs already on disk, 50 run now — the batch completed 450."""
    s = _sentinel(
        tmp_path, planned=450, completed=450, ran_this_process=50,
        failed=0, outages=0,
    )
    assert s["completed"] == 450
    assert s["ran_this_process"] == 50
    assert s["planned_pairs"] == 450


def test_the_resume_story_survives_in_its_own_field(tmp_path):
    """`ran_this_process` is what the old `completed` meant — kept, not lost."""
    s = _sentinel(
        tmp_path, planned=450, completed=450, ran_this_process=50,
        failed=0, outages=0,
    )
    assert s["ran_this_process"] != s["completed"]


def test_a_whole_batch_reads_complete():
    line = _sentinel_line({
        "planned_pairs": 450, "completed": 450, "ran_this_process": 450,
        "failed": 0, "finished_at": "2026-08-22T00:00:00+00:00",
    })
    assert "**COMPLETE**" in line
    assert "INCOMPLETE" not in line


def test_a_resumed_whole_batch_reads_complete_and_says_it_resumed():
    """The exact r70-outcome-2 shape: 50 run by the last process, 450 done."""
    line = _sentinel_line({
        "planned_pairs": 450, "completed": 450, "ran_this_process": 50,
        "failed": 0, "finished_at": "2026-08-22T00:00:00+00:00",
    })
    assert "**COMPLETE**" in line
    assert "50 run by the final process" in line
    assert "400 already on disk" in line


def test_pairs_left_unrun_never_read_as_complete():
    """The sentinel exists — the sweep was not killed — but 400 never ran."""
    line = _sentinel_line({
        "planned_pairs": 450, "completed": 50, "ran_this_process": 50,
        "failed": 0, "finished_at": "2026-08-22T00:00:00+00:00",
    })
    assert "INCOMPLETE" in line
    assert "400 of 450 pairs never reached a completed status" in line
    assert "**COMPLETE**" not in line


def test_a_pre_def358_sentinel_never_false_alarms():
    """The r70-outcome-2 sentinel itself: planned 450, completed 50, no marker.

    That batch is whole — 450 index rows — but its `completed` carries the old
    per-process meaning. Deriving INCOMPLETE from it would make this very fix
    slander the batch that exposed it, so a legacy sentinel is labelled and
    the reader is pointed at `Index rows` instead of being given a verdict.
    """
    line = _sentinel_line({
        "planned_pairs": 450, "completed": 50,
        "failed": 0, "finished_at": "2026-08-21T10:20:54.960227+00:00",
    })
    assert "INCOMPLETE" not in line
    assert "**COMPLETE**" not in line
    assert "predates DEF358" in line
    assert "Index rows" in line


# ── The caller-side half ──────────────────────────────────────────────────
#
# Everything above proves `write_completion_sentinel` records what it is
# handed. The defect was never there — it was at the call site in `main()`,
# which handed it `done`, a counter the skip branch stepped straight past.
# Proving the writer and not the caller is exactly the shape DEF357 was
# (P18: "a feature proven on the builder, never on the caller that must feed
# it"), so the caller gets its own test.
#
# The whole batch is seeded as already-terminal on disk, which is the resumed
# case: the loop skips every pair, touches no network, and the sentinel it
# writes must still describe 3 completed pairs — not the 0 it personally ran.


class _Resp:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"status": "ok"}


class _Client:
    def __init__(self, *a, **kw):
        pass

    def get(self, *a, **kw):
        return _Resp()

    def close(self):
        return None


def test_the_call_site_counts_pairs_it_skipped(tmp_path, monkeypatch):
    pairs = [("AAPL", "2025-03-07"), ("MSFT", "2025-03-07"), ("NVDA", "2025-03-14")]

    pairs_file = tmp_path / "plan.jsonl"
    pairs_file.write_text(
        "".join(
            json.dumps({"ticker": t, "as_of": d, "status": "completed"}) + "\n"
            for t, d in pairs
        )
    )
    universe = tmp_path / "universe.txt"
    universe.write_text("AAPL\nMSFT\nNVDA\n")

    out = tmp_path / "out"
    out.mkdir()
    # Every pair already terminal → the loop skips all three and runs nothing.
    (out / "runs_b2.jsonl").write_text(
        "".join(
            json.dumps({
                "batch_id": "b2", "ticker": t, "as_of": d, "status": "completed",
                "verdict": {"action": "PASS"},
            }) + "\n"
            for t, d in pairs
        )
    )

    # DEF387 — the sweep refuses an unsupervised launch. This is an in-process
    # call exercising the sentinel's pair counting, not a bare multi-hour
    # launch, so it declares itself supervised rather than the guard being
    # weakened to admit it.
    monkeypatch.setenv(sweep.SUPERVISOR_ENV, "1")
    monkeypatch.setattr(sweep, "_admin_secret", lambda: "secret")
    monkeypatch.setattr(sweep.httpx, "Client", _Client)
    monkeypatch.setattr(
        sweep, "load_or_create_batch_user",
        lambda *a, **kw: {"user_id": "u1", "plan": "trader"},
    )
    monkeypatch.setattr(sys, "argv", [
        "backtest_sweep.py", "--batch-id", "b2",
        "--window-start", "2025-02-28", "--window-end", "2025-03-21",
        "--n-pairs", "3", "--seed", "164",
        "--pairs-file", str(pairs_file),
        "--universe-file", str(universe),
        "--out-dir", str(out),
    ])

    assert sweep.main() == 0

    s = json.loads((out / "complete_b2.json").read_text())
    assert s["planned_pairs"] == 3
    assert s["completed"] == 3, (
        "a resumed sweep that skipped every pair reported the batch as unrun — "
        "this is DEF358 itself"
    )
    assert s["ran_this_process"] == 0
    assert "INCOMPLETE" not in _sentinel_line(s)
