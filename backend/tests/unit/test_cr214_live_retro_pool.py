"""CR214 Step 4 — the live-retro pooling scorer, and the trap it exists to avoid.

`weekly_room_retro.py`'s output is CUMULATIVE: each week's file contains every
run scored in every earlier week, not just that week's new ones. Measured
2026-09-01, W34 (141 runs) is a strict subset of W35 (162 runs) — overlap 141
of 141. Reading the directory with a glob-and-concatenate therefore reports 303
runs over 46 dates where the truth is 162 over 28, and inflates the date count
that every clustered interval is computed against. These tests pin the refusal.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.live_retro_pool import load_rows, newest_scored


def _write(dir_path: Path, week: str, rows: list[dict]) -> Path:
    p = dir_path / f"scored_{week}.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return p


def _row(run_id: str, as_of: str, action: str, ex20: float | None) -> dict:
    return {"run_id": run_id, "as_of": as_of, "action": action, "ticker": "AAPL",
            "excess5": 0.01, "excess20": ex20, "partition": "unversioned"}


def test_it_reads_the_newest_week_not_the_concatenation(tmp_path):
    _write(tmp_path, "2026-W34", [_row("a", "2026-05-14", "APPROVE", 0.02)])
    _write(tmp_path, "2026-W35", [_row("a", "2026-05-14", "APPROVE", 0.02),
                                  _row("b", "2026-05-21", "PASS", 0.01)])
    assert newest_scored(tmp_path).name == "scored_2026-W35.jsonl"
    assert len(load_rows(newest_scored(tmp_path))) == 2


def test_weeks_sort_chronologically_not_lexically_by_accident(tmp_path):
    """ISO-week names sort lexically = chronologically; W9 would not, so it is W09."""
    _write(tmp_path, "2026-W09", [_row("a", "2026-02-27", "PASS", 0.0)])
    _write(tmp_path, "2026-W10", [_row("a", "2026-02-27", "PASS", 0.0),
                                  _row("b", "2026-03-06", "PASS", 0.0)])
    assert newest_scored(tmp_path).name == "scored_2026-W10.jsonl"


def test_an_empty_directory_is_refused_not_reported_as_zero(tmp_path):
    with pytest.raises(SystemExit):
        newest_scored(tmp_path)


def test_the_long_horizon_is_none_because_the_live_scorer_stops_at_20d(tmp_path):
    """None, not 0.0 — the backtest's ~13w cell has no live counterpart yet."""
    p = _write(tmp_path, "2026-W35", [_row("a", "2026-05-14", "APPROVE", 0.02)])
    assert load_rows(p)[0].excess62 is None


def test_an_unscoreable_run_keeps_its_none(tmp_path):
    p = _write(tmp_path, "2026-W35", [_row("a", "2026-08-21", "APPROVE", None)])
    assert load_rows(p)[0].excess20 is None


def test_a_missing_partition_is_named_not_blank(tmp_path):
    p = tmp_path / "scored_2026-W35.jsonl"
    p.write_text(json.dumps({"run_id": "a", "as_of": "2026-05-14", "action": "PASS",
                             "ticker": "AAPL", "excess5": None, "excess20": None}) + "\n")
    assert load_rows(p)[0].partition == "unversioned"
