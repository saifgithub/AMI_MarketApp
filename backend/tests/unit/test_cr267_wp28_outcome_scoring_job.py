"""CR267 WP-28 — scheduled outcome scoring + weekly calibration report.

Pins what makes the schedule trustworthy rather than merely present:

  * the background task is registered in the app lifespan and its time maths
    lands on the configured UTC minute;
  * the scorer is idempotent across runs and resumes where the batch bound
    stopped it (due rows only count against the bound; not-due rows cannot
    starve due ones);
  * a missing horizon bar is refreshed once per ticker (the price source is
    mocked — no network), a failed refresh DEFERS the row instead of closing
    it, and a stale bar is never scored as the horizon close;
  * mock market data refuses to run, loudly, and leaves the ledger pending;
  * the weekly report is written once per interval, catches up, and a
    failure to write is logged, not swallowed;
  * the new settings are forwarded by compose (the parity test also enforces).
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session, init_schema
from app.db.models import PriceHistoryDailyRow, RoomRunRow, User, VerdictOutcomeRow
from app.schemas.room import Verdict, VerdictAction
from app.services import outcome_scoring_job as job
from app.services import verdict_outcomes as vo

_BACKEND = Path(__file__).resolve().parents[2]
_NOW = datetime(2026, 11, 19, 22, 30, tzinfo=timezone.utc)


def _mk_user() -> UUID:
    init_schema()
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            last_app_version="0.1.0+70", created_at=datetime.now(timezone.utc),
        ))
    return uid


def _bank(uid: UUID, ticker: str = "AAPL", *, age_days: int = 100,
          horizon: str = "medium", price: float | None = 100.0) -> datetime:
    rid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=rid, user_id=uid, ticker=ticker, started_at=datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status="completed",
        ))
    ref = _NOW - timedelta(days=age_days)
    vo.bank_verdict_outcome(
        room_run_id=rid, user_id=uid, ticker=ticker,
        verdict=Verdict(action=VerdictAction.APPROVE, reason="fx", size_pct=2.0),
        reference_price=price, reference_at=ref, mandate_horizon=horizon,
    )
    return ref


def _bar(ticker: str, d: date, close: float) -> None:
    with get_session() as s:
        s.add(PriceHistoryDailyRow(
            ticker=ticker, date=d, close=close, adj_close=close, source="yfinance",
            fetched_at=datetime.now(timezone.utc),
        ))


def _statuses() -> list[str]:
    with get_session() as s:
        return [r.status for r in s.execute(select(VerdictOutcomeRow)).scalars().all()]


# ── 1. Schedule registration + time maths ───────────────────────────────────

def test_lifespan_registers_the_scoring_tick() -> None:
    src = (_BACKEND / "app" / "main.py").read_text()
    assert "async def _verdict_outcome_scoring_tick" in src
    assert "asyncio.create_task(_verdict_outcome_scoring_tick())" in src
    assert "outcome_scoring_disabled" in src  # the off switch is logged, not silent


def test_defaults_are_on_after_us_close() -> None:
    assert settings.outcome_scoring_enabled is True
    assert (settings.outcome_scoring_hour_utc, settings.outcome_scoring_minute_utc) == (22, 30)


def test_next_run_is_today_when_ahead_and_tomorrow_when_passed() -> None:
    morning = datetime(2026, 11, 19, 10, 0, tzinfo=timezone.utc)
    assert job.seconds_until_next_run(morning, 22, 30) == 12.5 * 3600
    at_time = datetime(2026, 11, 19, 22, 30, tzinfo=timezone.utc)
    assert job.seconds_until_next_run(at_time, 22, 30) == 24 * 3600
    late = datetime(2026, 11, 19, 23, 0, tzinfo=timezone.utc)
    assert job.seconds_until_next_run(late, 22, 30) == 23.5 * 3600


def test_compose_forwards_every_new_setting() -> None:
    compose = (_BACKEND.parent / "docker-compose.yml").read_text()
    for name in (
        "OUTCOME_SCORING_ENABLED", "OUTCOME_SCORING_HOUR_UTC",
        "OUTCOME_SCORING_MINUTE_UTC", "OUTCOME_SCORING_BATCH_LIMIT",
        "OUTCOME_SCORING_MAX_TICKER_FETCHES", "OUTCOME_SCORING_MAX_BAR_GAP_DAYS",
        "OUTCOME_REPORT_DIR", "OUTCOME_REPORT_INTERVAL_DAYS",
    ):
        assert f"{name}: ${{{name}:-" in compose


# ── 2. Idempotency + batch bound ────────────────────────────────────────────

def test_rerun_never_double_scores() -> None:
    uid = _mk_user()
    ref = _bank(uid)
    _bar("AAPL", (ref + timedelta(days=63)).date(), 110.0)

    first = vo.score_pending(now=_NOW)
    second = vo.score_pending(now=_NOW)
    assert (first["scored"], second["scored"]) == (1, 0)
    with get_session() as s:
        rows = list(s.execute(select(VerdictOutcomeRow)).scalars().all())
    assert len(rows) == 1 and rows[0].forward_return == pytest.approx(0.10)


def test_batch_bound_caps_due_rows_and_next_run_resumes() -> None:
    uid = _mk_user()
    for i in range(5):
        ref = _bank(uid, f"T{i}", age_days=100 + i)
        _bar(f"T{i}", (ref + timedelta(days=63)).date(), 110.0)

    first = vo.score_pending(now=_NOW, limit=2)
    assert first["scored"] == 2
    assert _statuses().count(vo.STATUS_PENDING) == 3

    second = vo.score_pending(now=_NOW, limit=2)
    third = vo.score_pending(now=_NOW, limit=2)
    assert (second["scored"], third["scored"]) == (2, 1)
    assert _statuses().count(vo.STATUS_SCORED) == 5


def test_not_due_rows_do_not_starve_due_rows_behind_them() -> None:
    uid = _mk_user()
    # Oldest, but a 252-day horizon: not due. Must not eat the bound.
    _bank(uid, "OLDLONG", age_days=200, horizon="very_long")
    ref = _bank(uid, "DUE", age_days=100)
    _bar("DUE", (ref + timedelta(days=63)).date(), 110.0)

    counts = vo.score_pending(now=_NOW, limit=1)
    assert counts["scored"] == 1 and counts["not_due"] == 1


# ── 3. Price refresh (mocked source) ────────────────────────────────────────

def test_missing_bar_is_refreshed_once_per_ticker_then_scored() -> None:
    uid = _mk_user()
    refs = [_bank(uid, "AAPL", age_days=100 + i) for i in range(3)]
    calls: list[str] = []

    def refresh(ticker: str) -> bool:
        calls.append(ticker)
        for r in refs:
            _bar(ticker, (r + timedelta(days=63)).date(), 110.0)
        return True

    counts = vo.score_pending(now=_NOW, refresh_bars=refresh)
    assert calls == ["AAPL"]
    assert counts["scored"] == 3


def test_failed_refresh_defers_rather_than_closing_the_row() -> None:
    uid = _mk_user()
    _bank(uid, "AAPL")
    counts = vo.score_pending(now=_NOW, refresh_bars=lambda t: False)
    assert counts["deferred"] == 1 and counts["unscorable_no_bar"] == 0
    assert _statuses() == [vo.STATUS_PENDING]


def test_successful_refresh_with_no_bar_closes_as_no_horizon_bar() -> None:
    uid = _mk_user()
    _bank(uid, "AAPL")
    counts = vo.score_pending(now=_NOW, refresh_bars=lambda t: True)
    assert counts["unscorable_no_bar"] == 1
    assert _statuses() == [vo.STATUS_UNSCORABLE]


def test_refresh_cap_defers_the_overflow_tickers() -> None:
    uid = _mk_user()
    for t in ("AAA", "BBB", "CCC"):
        _bank(uid, t)
    calls: list[str] = []

    def refresh(t: str) -> bool:
        calls.append(t)
        return False

    counts = vo.score_pending(now=_NOW, refresh_bars=refresh, max_refreshes=2)
    assert len(calls) == 2 and counts["deferred"] == 3
    assert _statuses().count(vo.STATUS_PENDING) == 3


def test_without_gap_guard_the_store_only_scorer_is_unchanged() -> None:
    uid = _mk_user()
    ref = _bank(uid, "AAPL")
    # Only bar is the Room's own reference day, ~63 days before the horizon.
    _bar("AAPL", ref.date(), 100.0)

    legacy = vo.score_pending(now=_NOW)  # CLI path: behaviour kept as CR219 shipped it
    assert legacy["scored"] == 1


def test_gap_guard_rejects_stale_bar() -> None:
    uid = _mk_user()
    ref = _bank(uid, "AAPL")
    _bar("AAPL", ref.date(), 100.0)
    counts = vo.score_pending(now=_NOW, max_bar_gap_days=5, refresh_bars=lambda t: True)
    assert counts["scored"] == 0 and counts["unscorable_no_bar"] == 1


# ── 4. The job: mock refusal, wiring, loud failures ─────────────────────────

def test_job_refuses_mock_market_data_and_leaves_ledger_pending(monkeypatch, caplog) -> None:
    uid = _mk_user()
    _bank(uid)
    monkeypatch.setattr(settings, "use_real_market_data", False)
    out = job.run_outcome_job(_NOW)
    assert out["error"] == "mock_market_data" and out["counts"] is None
    assert _statuses() == [vo.STATUS_PENDING]


def test_job_scores_with_configured_bound_and_gap(monkeypatch, tmp_path) -> None:
    uid = _mk_user()
    for i in range(3):
        ref = _bank(uid, f"T{i}", age_days=100 + i)
        _bar(f"T{i}", (ref + timedelta(days=63)).date(), 110.0)
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "outcome_scoring_batch_limit", 2)
    monkeypatch.setattr(settings, "outcome_report_dir", str(tmp_path / "rep"))
    monkeypatch.setattr(
        vo, "refresh_price_bars", lambda t, now=None: pytest.fail("no network expected"),
    )
    out = job.run_outcome_job(_NOW)
    assert out["counts"]["scored"] == 2 and out["error"] is None


def test_job_logs_error_when_scoring_raises(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "use_real_market_data", True)
    monkeypatch.setattr(settings, "outcome_report_dir", str(tmp_path / "rep"))

    def boom(**kw):
        raise RuntimeError("db down")

    monkeypatch.setattr(vo, "score_pending", boom)
    out = job.run_outcome_job(_NOW)
    assert out["error"] == "score_failed"


# ── 5. Weekly report ────────────────────────────────────────────────────────

def test_report_written_when_none_exists_then_skipped_until_interval(
    monkeypatch, tmp_path,
) -> None:
    _mk_user()
    monkeypatch.setattr(settings, "outcome_report_dir", str(tmp_path / "rep"))
    monkeypatch.setattr(settings, "outcome_report_interval_days", 7)

    p1 = job.write_weekly_report_if_due(_NOW)
    assert p1 and Path(p1).name == "room_outcome_2026-11-19.json"
    body = json.loads(Path(p1).read_text())
    assert "coverage" in body and "interpretation" in body

    assert job.write_weekly_report_if_due(_NOW + timedelta(days=6)) is None
    p2 = job.write_weekly_report_if_due(_NOW + timedelta(days=7))
    assert p2 and Path(p2).name == "room_outcome_2026-11-26.json"


def test_report_catches_up_after_a_missed_week(monkeypatch, tmp_path) -> None:
    _mk_user()
    rep = tmp_path / "rep"
    rep.mkdir()
    (rep / "room_outcome_2026-10-01.json").write_text("{}")
    monkeypatch.setattr(settings, "outcome_report_dir", str(rep))
    assert job.write_weekly_report_if_due(_NOW) is not None


def test_report_failure_is_logged_not_raised(monkeypatch, tmp_path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x")  # a file where the directory should be
    monkeypatch.setattr(settings, "outcome_report_dir", str(blocker / "sub"))
    logged: list[str] = []
    monkeypatch.setattr(job.logger, "exception", lambda event, **kw: logged.append(event))
    assert job.write_weekly_report_if_due(_NOW) is None
    assert logged == ["outcome_report_failed"]
