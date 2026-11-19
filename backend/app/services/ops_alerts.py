"""Operator alerts: 5xx rate, LLM spend vs ceiling, Room failure rate (CR267 WP-44).

Why: Beta is run by one founder with no pager. The signals already exist in the
database (`http_audit`, `llm_audit`, `room_runs`); nothing watched them. A
background tick (`app.main._ops_alert_tick`) calls `run_ops_alert_pass`, which
reads those tables, and posts to `OPS_ALERT_WEBHOOK_URL` (plus Sentry) when a
threshold is crossed.

Degrade loudly (CR040):
  * `OPS_ALERTS_ENABLED=true` with no webhook URL logs an ERROR every pass and
    raises a Sentry message once per day; it never quietly does nothing.
  * A webhook that fails to deliver does NOT start the cooldown, so the next
    pass retries instead of believing the operator was told.
  * A DB read that errors is itself an alert ("ops_alert_read_failed").

Each alert kind has an in-process cooldown so one bad hour is one message, not
twelve. A restart forgets the cooldown, which at worst repeats one message.

CLI (proves the destination end to end, WP-44 acceptance "a test alert"):
    docker exec ami_api_alpha python -m app.services.ops_alerts test
Exit 0 only if the webhook accepted the message.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import case, func, select

from app.core.config import settings
from app.core.logging import logger
from app.db.models import HTTPAuditRow, RoomRunRow
from app.db.session import get_session

HTTP_WINDOW = timedelta(minutes=15)
HTTP_MIN_REQUESTS = 20
ROOM_WINDOW = timedelta(minutes=60)
ROOM_MIN_FINISHED = 5
COOLDOWN_SECONDS = 60 * 60
_TIMEOUT = httpx.Timeout(10.0)

_lock = threading.Lock()
_last_sent: dict[str, float] = {}
_missing_url_reported_day: set[str] = set()


@dataclass(frozen=True)
class Alert:
    kind: str
    message: str


def reset_state() -> None:
    with _lock:
        _last_sent.clear()
        _missing_url_reported_day.clear()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _monotonic() -> float:
    return time.monotonic()


def evaluate_5xx(now: datetime) -> Alert | None:
    since = now - HTTP_WINDOW
    with get_session() as s:
        total, errors = s.execute(
            select(
                func.count(HTTPAuditRow.id),
                func.coalesce(func.sum(case((HTTPAuditRow.status_code >= 500, 1), else_=0)), 0),
            ).where(HTTPAuditRow.created_at >= since)
        ).one()
    total, errors = int(total), int(errors)
    if total < HTTP_MIN_REQUESTS:
        return None
    rate = errors / total
    if rate >= settings.ops_alert_5xx_rate:
        return Alert(
            "http_5xx",
            f"5xx rate {rate:.1%} ({errors}/{total} requests) in the last "
            f"{int(HTTP_WINDOW.total_seconds() // 60)} min; threshold {settings.ops_alert_5xx_rate:.1%}",
        )
    return None


def evaluate_spend() -> Alert | None:
    ceiling = settings.llm_daily_spend_ceiling_usd
    if ceiling is None:
        return None
    from app.services.llm_spend import todays_spend

    reading = todays_spend()
    if reading.spend_usd >= ceiling * settings.ops_alert_spend_fraction:
        return Alert(
            "llm_spend",
            f"LLM spend ${reading.spend_usd:.2f} today (UTC {reading.day}) is "
            f"{reading.spend_usd / ceiling:.0%} of the ${ceiling:.2f} ceiling; alert at "
            f"{settings.ops_alert_spend_fraction:.0%}. At 100% new Rooms are refused.",
        )
    return None


def evaluate_room_failures(now: datetime) -> Alert | None:
    since = now - ROOM_WINDOW
    with get_session() as s:
        finished, failed = s.execute(
            select(
                func.count(RoomRunRow.id),
                func.coalesce(func.sum(case((RoomRunRow.status == "failed", 1), else_=0)), 0),
            ).where(
                RoomRunRow.finished_at >= since,
                RoomRunRow.status.in_(("completed", "failed")),
            )
        ).one()
    finished, failed = int(finished), int(failed)
    if finished < ROOM_MIN_FINISHED:
        return None
    rate = failed / finished
    if rate >= settings.ops_alert_room_failure_rate:
        return Alert(
            "room_failures",
            f"Room failure rate {rate:.0%} ({failed}/{finished} finished Rooms) in the last "
            f"{int(ROOM_WINDOW.total_seconds() // 60)} min; threshold "
            f"{settings.ops_alert_room_failure_rate:.0%}",
        )
    return None


def collect_alerts(now: datetime | None = None) -> list[Alert]:
    """Every threshold currently crossed. A failing probe becomes its own alert."""
    now = now or _utcnow()
    alerts: list[Alert] = []
    probes = (
        ("http_5xx", lambda: evaluate_5xx(now)),
        ("llm_spend", evaluate_spend),
        ("room_failures", lambda: evaluate_room_failures(now)),
    )
    for kind, probe in probes:
        try:
            alert = probe()
        except Exception as exc:
            logger.exception("ops_alert_probe_failed", kind=kind)
            alert = Alert(
                "read_failed:" + kind,
                f"Alert check '{kind}' could not read its data ({type(exc).__name__}); "
                "this signal is unmonitored until it recovers",
            )
        if alert is not None:
            alerts.append(alert)
    return alerts


def send_webhook(text: str) -> bool:
    """POST the message. True only on a 2xx; every other outcome is logged."""
    url = settings.ops_alert_webhook_url.strip()
    if not url:
        return False
    try:
        resp = httpx.post(url, json={"text": text, "content": text}, timeout=_TIMEOUT)
    except httpx.HTTPError as exc:
        logger.error("ops_alert_webhook_error", error=type(exc).__name__)
        return False
    if resp.status_code >= 300:
        logger.error("ops_alert_webhook_rejected", status=resp.status_code)
        return False
    return True


def _sentry(message: str) -> None:
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message, level="error")
    except Exception:
        pass


def _report_missing_url(now: datetime) -> None:
    logger.error(
        "ops_alerts_enabled_without_webhook",
        detail="OPS_ALERTS_ENABLED=true but OPS_ALERT_WEBHOOK_URL is empty: no operator is being told",
    )
    day = now.strftime("%Y-%m-%d")
    with _lock:
        first = day not in _missing_url_reported_day
        _missing_url_reported_day.add(day)
    if first:
        _sentry("ops_alerts_enabled_without_webhook")


def run_ops_alert_pass(now: datetime | None = None) -> dict[str, int]:
    """One evaluation pass. Returns counts for the tick's log line."""
    now = now or _utcnow()
    stats = {"crossed": 0, "sent": 0, "cooling": 0, "failed": 0}
    if not settings.ops_alerts_enabled:
        return stats
    if not settings.ops_alert_webhook_url.strip():
        _report_missing_url(now)
        stats["failed"] = 1
        return stats
    for alert in collect_alerts(now):
        stats["crossed"] += 1
        with _lock:
            last = _last_sent.get(alert.kind)
        if last is not None and _monotonic() - last < COOLDOWN_SECONDS:
            stats["cooling"] += 1
            continue
        logger.error("ops_alert", kind=alert.kind, message=alert.message)
        _sentry(f"ops_alert {alert.kind}: {alert.message}")
        if send_webhook(f"[AMI {settings.env}] {alert.message}"):
            with _lock:
                _last_sent[alert.kind] = _monotonic()
            stats["sent"] += 1
        else:
            stats["failed"] += 1
    return stats


def main(argv: list[str]) -> int:
    if argv[1:] != ["test"]:
        print("usage: python -m app.services.ops_alerts test", file=sys.stderr)
        return 2
    if not settings.ops_alert_webhook_url.strip():
        print("FAIL: OPS_ALERT_WEBHOOK_URL is empty", file=sys.stderr)
        return 1
    ok = send_webhook(f"[AMI {settings.env}] test alert from ops_alerts ({_utcnow().isoformat()})")
    print("sent" if ok else "FAIL: webhook did not accept the message", file=None if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
