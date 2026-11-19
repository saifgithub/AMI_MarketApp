"""CR267 WP-28 — the scheduled run of the verdict-outcome scorer and the weekly
calibration report.

`verdict_outcomes.score_pending` is the scorer and `scripts/room_outcome_report`
is the report; both existed and nothing called them, so ~6.7k banked Room
verdicts sat unscored. This module is the thin, testable layer the
`main._verdict_outcome_scoring_tick` background task calls once a day, using the
same in-process asyncio-task mechanism as every other scheduled Alpha job.

Degrade loudly (CR040): every outcome below is logged with its counts. A run
that cannot score (mock market data) or a report that cannot be written logs at
ERROR — it never returns quietly as if it had worked.

Framing is inherited from `verdict_outcomes`: an internal calibration sanity
floor, not a performance claim, never user-facing.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import logger
from app.services import verdict_outcomes as vo

_REPORT_RE = re.compile(r"^room_outcome_(\d{4}-\d{2}-\d{2})\.json$")


def seconds_until_next_run(now: datetime, hour: int, minute: int) -> float:
    """Seconds from `now` to the next `hour:minute` UTC (today if still ahead,
    otherwise tomorrow). Never zero, so a run that finishes inside its own
    minute does not immediately re-fire."""
    now = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def latest_report_date(report_dir: Path) -> date | None:
    """Date of the newest `room_outcome_<date>.json` in `report_dir`, or None."""
    if not report_dir.is_dir():
        return None
    dates = []
    for p in report_dir.iterdir():
        m = _REPORT_RE.match(p.name)
        if m:
            dates.append(date.fromisoformat(m.group(1)))
    return max(dates) if dates else None


def write_weekly_report_if_due(now: datetime | None = None) -> str | None:
    """Write the calibration report when none exists within the interval.

    Catch-up by design: due means "newest report is >= interval days old, or
    there is none", so a missed day or a restart delays the report but never
    skips a week. The file is named by date and rewritten if the same date is
    run twice, so a re-run is idempotent. Returns the path written, or None
    when not due. Any failure logs at error level and returns None.
    """
    now = now or datetime.now(timezone.utc)
    report_dir = Path(settings.outcome_report_dir)
    try:
        newest = latest_report_date(report_dir)
        if newest is not None and (now.date() - newest).days < settings.outcome_report_interval_days:
            return None
        # scripts/ is bind-mounted into the container (compose), not baked in;
        # a missing mount is a loud failure, not a silent skip.
        from scripts.room_outcome_report import build_report

        report = build_report()
        report["generated_at"] = now.isoformat()
        report_dir.mkdir(parents=True, exist_ok=True)
        path = report_dir / f"room_outcome_{now.date().isoformat()}.json"
        path.write_text(json.dumps(report, indent=2, sort_keys=True))
        cov = report["coverage"]
        logger.info(
            "outcome_report_written", path=str(path),
            scored=cov.get("scored"), banked=cov.get("banked"),
        )
        return str(path)
    except Exception:
        logger.exception("outcome_report_failed", report_dir=str(report_dir))
        return None


def run_outcome_job(now: datetime | None = None) -> dict[str, Any]:
    """One scheduled pass: score a bounded batch, then the weekly report if due.

    Blocking (DB + Yahoo); the caller wraps it in `asyncio.to_thread`.
    """
    now = now or datetime.now(timezone.utc)
    result: dict[str, Any] = {"counts": None, "report": None, "error": None}

    if not settings.use_real_market_data:
        # Scoring against mock bars would mark every row `mock_price_source`
        # permanently. Refuse, loudly, and leave the ledger pending.
        logger.error("outcome_scoring_refused_mock_market_data")
        result["error"] = "mock_market_data"
        return result

    try:
        counts = vo.score_pending(
            now=now,
            limit=settings.outcome_scoring_batch_limit,
            refresh_bars=lambda t: vo.refresh_price_bars(t, now=now),
            max_bar_gap_days=settings.outcome_scoring_max_bar_gap_days,
            max_refreshes=settings.outcome_scoring_max_ticker_fetches,
        )
        result["counts"] = counts
        if counts["deferred"]:
            logger.error("outcome_scoring_deferred_rows", **counts)
        else:
            logger.info("outcome_scoring_run_complete", **counts)
    except Exception:
        logger.exception("outcome_scoring_run_failed")
        result["error"] = "score_failed"

    result["report"] = write_weekly_report_if_due(now)
    return result
