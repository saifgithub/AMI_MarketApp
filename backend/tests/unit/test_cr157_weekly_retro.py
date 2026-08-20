"""CR157 — weekly Room retrospective batch (scripts/weekly_room_retro.py).

What must hold:
  * scoring joins live room_runs to price_history_daily with CR164's exact
    entry convention (last stored adj close <= the convene UTC date) and
    +5/+20 trading-day horizons vs SPY;
  * the DEF059 LLM-outage fail-safe PASS is excluded (DEF336: scoring it
    measures provider uptime, not judgement);
  * synthetic/benchmark users are excluded exactly like
    scripts/analytics/daily_report.py's REAL_PRED;
  * backtest-indexed and too-young runs are excluded;
  * an empty week is a loud "nothing due" and exit 0 — never an error,
    never a fabricated report;
  * the script NEVER INSERTs/UPDATEs/DELETEs product tables — its only
    write path (the price_history refresh) is skippable and everything
    else is pure SELECT, proven here by capturing every SQL statement.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import event

from app.db import get_engine, get_session
from app.db.models import (
    BacktestRunIndexRow,
    LLMAuditRow,
    PriceHistoryDailyRow,
    RoomRunRow,
    User,
)
from app.services.room_runner import PM_LLM_UNAVAILABLE_REASON
from scripts.weekly_room_retro import main, select_due_runs

_NOW = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
_TRIGGERED = datetime(2026, 7, 1, 14, 30, tzinfo=timezone.utc)  # Wed, UTC date 2026-07-01
_AS_OF = date(2026, 7, 1)


def _weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _seed_bars(ticker: str, days: list[date], base: float, step: float) -> dict[date, float]:
    """Ascending real bars; returns {date: adj_close} for independent expected-value math."""
    px_by_date = {}
    with get_session() as s:
        for i, d in enumerate(days):
            px = base + step * i
            px_by_date[d] = px
            s.add(PriceHistoryDailyRow(
                ticker=ticker, date=d, close=px, adj_close=px,
                open=px - 0.5, high=px + 1.0, low=px - 1.0,
                volume=1_000_000 + i, source="yfinance", fetched_at=_NOW,
            ))
    return px_by_date


def _seed_user(*, last_app_version="1.0.0+42", device_model="iPhone 13",
               created_at=datetime(2026, 6, 1, tzinfo=timezone.utc)):
    uid = uuid4()
    with get_session() as s:
        s.add(User(id=uid, created_at=created_at, device_model=device_model,
                   last_app_version=last_app_version))
    return uid


def _verdict(action="APPROVE", **over):
    v = {
        "action": action, "size_pct": 5.0, "entry": 121.0, "target": 131.0,
        "stop": 112.0, "reason": "test verdict", "violations": [],
        "overridden_from_llm": False,
        "level_provenance": {"entry": "pm", "target": "pm", "stop": "trader"},
    }
    v.update(over)
    return v


def _seed_run(user_id, *, ticker="AAPL", triggered=_TRIGGERED, status="completed",
              verdict=None, transcript=None):
    rid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=rid, user_id=user_id, ticker=ticker, triggered_at=triggered,
            started_at=triggered, finished_at=triggered + timedelta(seconds=90),
            mandate_version=1, model_tier="standard",
            transcript=transcript or [], verdict=verdict, status=status,
        ))
    return rid


def _run_main(tmp_path, stamp="2026-08-20"):
    out = tmp_path / "retro"
    rc = main(["--no-refresh", "--out", str(out), "--stamp", stamp])
    return rc, out


def _scored_ids(out) -> dict[str, dict]:
    path = out / "scored_2026-W34.jsonl"
    if not path.exists():
        return {}
    return {json.loads(l)["run_id"]: json.loads(l) for l in path.read_text().splitlines()}


# ── scoring joins: CR164 entry/horizon conventions on live runs ─────────────


def test_scoring_joins_and_conventions(tmp_path) -> None:
    days = _weekdays(date(2026, 6, 1), 45)
    px = _seed_bars("AAPL", days, 100.0, 1.0)
    spy = _seed_bars("SPY", days, 50.0, 0.25)
    uid = _seed_user()
    rid = _seed_run(uid, verdict=_verdict(), transcript=[
        {"agent_id": "market_analyst", "role": "agent", "content": "x",
         "timestamp": _TRIGGERED.isoformat(), "stance": "for", "conviction": "high"},
        {"agent_id": "news_analyst", "role": "agent", "content": "y",
         "timestamp": _TRIGGERED.isoformat(), "stance": None, "conviction": None},
    ])
    # correlate a versioned llm_audit row inside the run's wall-clock window
    with get_session() as s:
        s.add(LLMAuditRow(
            user_id=uid, tier="standard", provider="vllm", system_prompt="p",
            created_at=_TRIGGERED + timedelta(seconds=10), prompt_version="pv-abc",
        ))

    rc, out = _run_main(tmp_path)
    assert rc == 0
    lines = _scored_ids(out)
    assert set(lines) == {str(rid)}
    row = lines[str(rid)]

    # entry = last stored adj close <= convene UTC date (2026-07-01 is a bar)
    entry_dates = [d for d in days if d <= _AS_OF]
    entry = px[entry_dates[-1]]
    fwd = [d for d in days if d > _AS_OF]
    assert row["entry"] == entry
    assert row["r5"] == (px[fwd[4]] / entry - 1.0)
    assert row["r20"] == (px[fwd[19]] / entry - 1.0)
    spy_entry = spy[entry_dates[-1]]
    assert abs(row["excess20"] - ((px[fwd[19]] / entry - 1) - (spy[fwd[19]] / spy_entry - 1))) < 1e-12
    # rising tape: target 131 (pm-stated) is touched, stop 112 never
    assert row["target_hit"] is True and row["stop_hit"] is False
    assert row["first_touch"] == "target_first"
    # prompt-version partition recovered from llm_audit, never pooled silently
    assert row["partition"] == "pv-abc"
    # null stance is a gutter, never neutral
    assert row["stances"]["market_analyst"]["stance"] == "for"
    assert row["stances"]["news_analyst"]["stance"] is None
    assert row["acted_trades"] == 0
    report = (out / "report_2026-W34.md").read_text()
    assert "prompt_version `pv-abc`" in report


# ── DEF336: the outage fail-safe PASS is not a scoreable call ────────────────


def test_outage_verdict_excluded(tmp_path) -> None:
    days = _weekdays(date(2026, 6, 1), 45)
    _seed_bars("AAPL", days, 100.0, 1.0)
    _seed_bars("SPY", days, 50.0, 0.25)
    uid = _seed_user()
    outage = _seed_run(uid, verdict=_verdict(
        action="PASS", overridden_from_llm=True, reason=PM_LLM_UNAVAILABLE_REASON))
    reasoned = _seed_run(uid, verdict=_verdict(action="PASS", reason="thesis unconvincing"))

    rc, out = _run_main(tmp_path)
    assert rc == 0
    lines = _scored_ids(out)
    assert str(reasoned) in lines
    assert str(outage) not in lines

    # and the pure selector counts it under its own reason
    with get_session() as s:
        pairs = [(r, u) for r, u in s.query(RoomRunRow, User).filter(User.id == RoomRunRow.user_id)]
        due, counts = select_due_runs(pairs, set(), now=_NOW, min_age_days=7)
    assert counts["llm_outage"] == 1
    assert {r.id for r, _ in due} == {reasoned}


# ── synthetic/benchmark users excluded exactly like daily_report.REAL_PRED ──


def test_synthetic_user_exclusion(tmp_path) -> None:
    days = _weekdays(date(2026, 6, 1), 45)
    _seed_bars("AAPL", days, 100.0, 1.0)
    _seed_bars("SPY", days, 50.0, 0.25)
    real = _seed_user()
    bench = _seed_user(last_app_version="room-benchmark")
    seed_burst = _seed_user(
        last_app_version=None, device_model=None,
        created_at=datetime(2026, 5, 24, 5, 10, 30, tzinfo=timezone.utc))
    real_run = _seed_run(real, verdict=_verdict())
    _seed_run(bench, verdict=_verdict())
    _seed_run(seed_burst, verdict=_verdict())

    rc, out = _run_main(tmp_path)
    assert rc == 0
    assert set(_scored_ids(out)) == {str(real_run)}


def test_backtest_indexed_and_young_runs_excluded(tmp_path) -> None:
    days = _weekdays(date(2026, 6, 1), 45)
    _seed_bars("AAPL", days, 100.0, 1.0)
    _seed_bars("SPY", days, 50.0, 0.25)
    uid = _seed_user()
    live = _seed_run(uid, verdict=_verdict())
    backtested = _seed_run(uid, verdict=_verdict())
    with get_session() as s:
        s.add(BacktestRunIndexRow(room_run_id=backtested, batch_id="b1",
                                  arm="A", ticker="AAPL", as_of=_AS_OF))
    _seed_run(uid, verdict=_verdict(),
              triggered=datetime.now(timezone.utc) - timedelta(days=2))

    rc, out = _run_main(tmp_path)
    assert rc == 0
    assert set(_scored_ids(out)) == {str(live)}


# ── empty week: loud nothing-due, exit 0, no files ───────────────────────────


def test_empty_week_is_loud_and_exit_zero(tmp_path, capsys) -> None:
    rc, out = _run_main(tmp_path)
    assert rc == 0
    assert "NOTHING DUE" in capsys.readouterr().out
    assert not out.exists()  # no report fabricated for an empty week


# ── read-only contract: no INSERT/UPDATE/DELETE on product tables ────────────


def test_never_writes_product_tables(tmp_path) -> None:
    days = _weekdays(date(2026, 6, 1), 45)
    _seed_bars("AAPL", days, 100.0, 1.0)
    _seed_bars("SPY", days, 50.0, 0.25)
    uid = _seed_user()
    _seed_run(uid, verdict=_verdict())

    statements: list[str] = []

    def spy_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().upper())

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", spy_sql)
    try:
        rc, _ = _run_main(tmp_path)
    finally:
        event.remove(engine, "before_cursor_execute", spy_sql)

    assert rc == 0
    writes = [s for s in statements
              if s.startswith(("INSERT", "UPDATE", "DELETE"))]
    assert writes == [], f"retro batch wrote to the database: {writes}"
