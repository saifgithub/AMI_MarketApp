"""CR266 workstream 3 — the calibration/outcome report over the CR219 ledger.

The report must stay a *calibration floor* in every shape it can be read:
coverage first, distributions second, loud uncertainty, and an interpretation
string that forbids the performance reading. These tests pin:

  * an empty ledger reports zero coverage and says the floor is unanswerable,
    never prints an empty distribution as evidence;
  * scored rows land in coverage / by_action / conviction with correct counts,
    and conviction buckets carry APPROVEs only;
  * thin samples surface limitation notes instead of confident numbers;
  * the consensus alignment block appears ONLY with a consensus file, is
    labelled calibration context (never independent outcome truth), joins by
    ticker, and counts unmapped tickers loudly;
  * the CLI writes JSON, exits 0 on a clean run and 1 on a bad consensus file.

Paths derive from `__file__`, so the file passes from the repo root and from
`backend/` alike.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.db import get_session, init_schema
from app.db.models import PriceHistoryDailyRow, RoomRunRow, User
from app.schemas.room import Verdict, VerdictAction
from app.services import verdict_outcomes as vo
from scripts import room_outcome_report as report


def _mk_user() -> None:
    init_schema()
    with get_session() as s:
        s.add(User(
            id=uuid4(), plan="floor_pass", credit_balance=8, is_anonymous=True,
            last_app_version="0.1.0+70",
            created_at=datetime.now(timezone.utc),
        ))


def _seed_scored(
    ticker: str,
    action: VerdictAction,
    *,
    fwd: float,
    approve_votes: int | None = None,
    samples: int | None = None,
) -> None:
    """One banked + scored row with a controlled forward return."""
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            last_app_version="0.1.0+70",
            created_at=datetime.now(timezone.utc),
        ))
        rid = uuid4()
        s.add(RoomRunRow(
            id=rid, user_id=uid, ticker=ticker,
            started_at=datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status="completed",
        ))
    verdict = Verdict(
        action=action, reason="fixture", size_pct=2.0,
        approve_votes=approve_votes, samples=samples,
    )
    ref_at = datetime.now(timezone.utc) - timedelta(days=400)
    vo.bank_verdict_outcome(
        room_run_id=rid, user_id=uid, ticker=ticker, verdict=verdict,
        reference_price=100.0, reference_at=ref_at, mandate_horizon="short",
    )
    with get_session() as s:
        s.add(PriceHistoryDailyRow(
            ticker=ticker,
            date=(ref_at + timedelta(days=21)).date(),
            close=100.0 * (1.0 + fwd), adj_close=100.0 * (1.0 + fwd),
            source="yfinance", fetched_at=datetime.now(timezone.utc),
        ))
    vo.score_pending(now=datetime.now(timezone.utc))


# ── 1. Empty ledger ──────────────────────────────────────────────────────────


def test_empty_ledger_reports_no_coverage_and_unanswerable_floor() -> None:
    _mk_user()
    rep = report.build_report()
    assert rep["coverage"]["scored"] == 0
    assert rep["coverage"]["scored_share_of_banked"] is None
    assert rep["by_action"] == {}
    assert rep["conviction"] == {}
    assert any("nothing to calibrate" in n for n in rep["limitations"])
    assert "NOT a performance claim" in rep["interpretation"]
    assert "calibration floor" in rep["interpretation"]


# ── 2. Scored rows: coverage, distributions, conviction ──────────────────────


def test_scored_rows_land_in_coverage_distributions_and_conviction() -> None:
    _mk_user()
    _seed_scored("AAPL", VerdictAction.APPROVE, fwd=0.10,
                 approve_votes=5, samples=5)
    _seed_scored("MSFT", VerdictAction.APPROVE, fwd=-0.05,
                 approve_votes=1, samples=5)
    _seed_scored("NVDA", VerdictAction.PASS, fwd=0.02)
    _seed_scored("AMD", VerdictAction.PASS, fwd=-0.03)

    rep = report.build_report()
    cov = rep["coverage"]
    assert cov["banked"] == 4
    assert cov["scored"] == 4
    assert cov["scored_share_of_banked"] == 1.0

    approve = rep["by_action"]["APPROVE"]
    assert approve["n"] == 2
    assert approve["mean"] == pytest.approx(0.025)
    assert rep["by_action"]["PASS"]["n"] == 2

    conv = rep["conviction"]
    assert set(conv) == {"high", "low"}
    assert conv["high"]["hit_rate"] == 1.0
    assert conv["high"]["n"] == 1
    assert conv["low"]["hit_rate"] == 0.0
    # conviction is APPROVEs only — the PASS rows never enter a bucket
    assert conv["high"]["n"] + conv["low"]["n"] == 2


def test_unscorable_row_is_coverage_not_distribution() -> None:
    _mk_user()
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            last_app_version="0.1.0+70",
            created_at=datetime.now(timezone.utc),
        ))
        rid = uuid4()
        s.add(RoomRunRow(
            id=rid, user_id=uid, ticker="AAPL",
            started_at=datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status="completed",
        ))
    vo.bank_verdict_outcome(
        room_run_id=rid, user_id=uid, ticker="AAPL",
        verdict=Verdict(action=VerdictAction.APPROVE, reason="x", size_pct=2.0),
        reference_price=None, reference_at=datetime.now(timezone.utc),
        mandate_horizon="short",
    )
    rep = report.build_report()
    assert rep["coverage"]["banked"] == 1
    assert rep["coverage"]["scored"] == 0
    assert rep["coverage"]["unscorable"] == 1
    assert rep["coverage"]["exclusion_reasons"].get("no_reference_price") == 1
    assert rep["by_action"] == {}
    assert any("No scored rows" in n for n in rep["limitations"])


# ── 3. Limitations fire on thin samples, never p-values ──────────────────────


def test_thin_samples_surface_limitation_notes() -> None:
    _mk_user()
    _seed_scored("AAPL", VerdictAction.APPROVE, fwd=0.10,
                 approve_votes=5, samples=5)
    rep = report.build_report()
    assert any("below" in n and "floor" in n for n in rep["limitations"])
    assert any("conviction 'high'" in n for n in rep["limitations"])
    joined = " ".join(rep["limitations"])
    assert "p-value" not in joined
    assert not any("t-stat" in n or "p =" in n for n in rep["limitations"])


# ── 4. Consensus alignment: optional, labelled, ticker-joined ────────────────


def test_consensus_block_only_with_file_and_labelled_calibration_context() -> None:
    _mk_user()
    rep = report.build_report()
    assert "consensus_alignment" not in rep

    _seed_scored("AAPL", VerdictAction.APPROVE, fwd=0.10)
    _seed_scored("MSFT", VerdictAction.PASS, fwd=-0.02)
    _seed_scored("TSLA", VerdictAction.APPROVE, fwd=0.04)
    consensus = {"AAPL": "buy", "MSFT": "hold", "XYZ": "sell"}
    rep = report.build_report(consensus)
    block = rep["consensus_alignment"]
    assert "CALIBRATION CONTEXT" in block["label"]
    assert "NOT independent outcome truth" in block["label"]
    assert block["categories"]["buy"]["APPROVE"]["n"] == 1
    assert block["categories"]["buy"]["APPROVE"]["hit_rate"] == 1.0
    assert block["categories"]["hold"]["PASS"]["n"] == 1
    # TSLA has no consensus entry and XYZ has no scored row — both loud, never
    # silently dropped or fabricated.
    assert block["unmapped_count"] == 1
    assert block["unmapped_tickers"] == ["TSLA"]
    assert "sell" in block["categories"]


def test_align_consensus_normalises_case_and_buckets_unknown() -> None:
    block = report.align_consensus(
        [("aapl", "APPROVE", 0.1), ("aapl", "PASS", 0.0),
         ("FCEL", "APPROVE", -0.2)],
        {"AAPL": "BUY", "FCEL": "strong buy"},
    )
    assert block["categories"]["buy"]["APPROVE"]["n"] == 1
    assert block["unmapped_tickers"] == ["FCEL"]
    assert block["unmapped_count"] == 1


# ── 5. CLI ───────────────────────────────────────────────────────────────────


def test_cli_writes_json_and_exits_zero(tmp_path) -> None:
    _mk_user()
    out = tmp_path / "report.json"
    assert report.main(["--out", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert "interpretation" in payload
    assert "NOT a performance claim" in payload["interpretation"]


def test_cli_bad_consensus_file_exits_one(tmp_path) -> None:
    bad = tmp_path / "consensus.json"
    bad.write_text(json.dumps(["not", "an", "object"]))
    proc = subprocess.run(
        [sys.executable, "-m", "scripts.room_outcome_report",
         "--consensus", str(bad)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True, text=True,
    )
    assert proc.returncode == 1
    assert "room_outcome_report failed" in proc.stderr


def test_cli_consensus_round_trip(tmp_path) -> None:
    _mk_user()
    _seed_scored("AAPL", VerdictAction.APPROVE, fwd=0.10)
    consensus = tmp_path / "c.json"
    consensus.write_text(json.dumps({"AAPL": "buy"}))
    out = tmp_path / "report.json"
    assert report.main(["--consensus", str(consensus), "--out", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert payload["consensus_alignment"]["categories"]["buy"]["APPROVE"]["n"] == 1
