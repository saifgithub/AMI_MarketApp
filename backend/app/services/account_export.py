"""CR276 (CR267 WP-30) — the signed-in user's own data, as one JSON document.

`GET /v1/account/export` serves the result as a download. It holds what the
user made or did in AMI: trades (sim), Room runs with their verdicts, the
mandate, the journal, lesson progress and settings, plus the smaller personal
tables (watchlist, alerts, analyst conversations, daily-challenge answers,
badges, their own bug reports).

What it never holds:
  - another user's data: every query is keyed on the caller's id;
  - secrets: nothing here reads a credential, and Alpaca keys live only in the
    device keychain (CR202). `alpaca_linked_at` is included as a plain fact;
  - Room transcripts and the CIO context snapshot (large generated analysis, not
    data the user supplied) and the LLM / HTTP audit logs (operational logs,
    not user content). The document says so in `not_included`.

The user row is a WHITELIST, not a dump: a column added to `users` later does
not leak into exports until someone decides it belongs here.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select

from app.db import get_session
from app.db.models import (
    AgentActivationRow,
    BadgeRow,
    BugReportRow,
    DailyChallengeAttemptRow,
    JournalEntryRow,
    LessonProgressRow,
    MandateRow,
    NotificationPreferenceRow,
    OneOnOneMessageRow,
    PriceAlertRow,
    RoomRunRow,
    SimHoldingRow,
    SimOptionLegRow,
    SimOptionTradeRow,
    SimPortfolioRow,
    SimShortPositionRow,
    SimTradeRow,
    SimWatchlistRow,
    User,
    UserOverlayRow,
    VerdictOutcomeRow,
)

EXPORT_SCHEMA_VERSION = 1

_PROFILE_FIELDS = (
    "id", "email", "display_name", "handle", "plan", "credit_balance", "locale",
    "timezone", "daily_reminder_hour", "show_display_name", "is_anonymous",
    "claimed_at", "age_confirmed_at", "alpaca_linked_at", "created_at",
)

_NOT_INCLUDED = [
    "Room transcripts and the analysts' working context for each run (the "
    "verdicts are included)",
    "operational request and LLM logs",
    "Alpaca keys, which are stored only on your device and never reach AMI's servers",
    "other users' data",
]


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return value


def _row_dict(row: Any, *, exclude: frozenset[str] = frozenset()) -> dict[str, Any]:
    return {
        c.key: _json_safe(getattr(row, c.key))
        for c in row.__mapper__.column_attrs
        if c.key not in exclude
    }


def _rows(s, model, where, order=None, *, exclude: frozenset[str] = frozenset()):
    q = select(model).where(where)
    if order is not None:
        q = q.order_by(order)
    return [_row_dict(r, exclude=exclude) for r in s.execute(q).scalars()]


def build_export(user_id: UUID) -> dict[str, Any]:
    with get_session() as s:
        user = s.execute(select(User).where(User.id == user_id)).scalar_one()
        profile = {f: _json_safe(getattr(user, f)) for f in _PROFILE_FIELDS}

        portfolios = _rows(s, SimPortfolioRow, SimPortfolioRow.user_id == user_id,
                           SimPortfolioRow.created_at, exclude=frozenset({"holdings"}))
        holdings: list[dict[str, Any]] = []
        for p in portfolios:
            holdings.extend(_rows(
                s, SimHoldingRow, SimHoldingRow.portfolio_id == UUID(p["id"]),
                SimHoldingRow.ticker, exclude=frozenset({"portfolio"}),
            ))

        return {
            "schema_version": EXPORT_SCHEMA_VERSION,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "not_included": _NOT_INCLUDED,
            "profile": profile,
            "settings": {
                "locale": user.locale,
                "timezone": user.timezone,
                "daily_reminder_hour": user.daily_reminder_hour,
                "show_display_name": user.show_display_name,
                "notification_preferences": _rows(
                    s, NotificationPreferenceRow,
                    NotificationPreferenceRow.user_id == user_id,
                    NotificationPreferenceRow.type,
                ),
            },
            "mandates": _rows(s, MandateRow, MandateRow.user_id == user_id,
                              MandateRow.version),
            "agent_briefs": _rows(s, UserOverlayRow, UserOverlayRow.user_id == user_id,
                                  UserOverlayRow.created_at),
            "journal": _rows(
                s, JournalEntryRow,
                (JournalEntryRow.user_id == user_id) & JournalEntryRow.deleted_at.is_(None),
                JournalEntryRow.created_at,
            ),
            "lesson_progress": _rows(s, LessonProgressRow,
                                     LessonProgressRow.user_id == user_id,
                                     LessonProgressRow.lesson_id),
            "agent_activations": _rows(s, AgentActivationRow,
                                       AgentActivationRow.user_id == user_id,
                                       AgentActivationRow.activated_at),
            "sim_portfolios": portfolios,
            "sim_holdings": holdings,
            "sim_trades": _rows(s, SimTradeRow, SimTradeRow.user_id == user_id,
                                SimTradeRow.opened_at),
            "sim_short_positions": _rows(s, SimShortPositionRow,
                                         SimShortPositionRow.user_id == user_id,
                                         SimShortPositionRow.opened_at),
            "sim_option_legs": _rows(s, SimOptionLegRow,
                                     SimOptionLegRow.user_id == user_id,
                                     SimOptionLegRow.opened_at),
            "sim_option_trades": _rows(s, SimOptionTradeRow,
                                       SimOptionTradeRow.user_id == user_id,
                                       SimOptionTradeRow.opened_at),
            "rooms": _rows(
                s, RoomRunRow, RoomRunRow.user_id == user_id, RoomRunRow.triggered_at,
                exclude=frozenset({"transcript", "cio_context_snapshot"}),
            ),
            "verdict_outcomes": _rows(s, VerdictOutcomeRow,
                                      VerdictOutcomeRow.user_id == user_id,
                                      VerdictOutcomeRow.created_at),
            "watchlist": _rows(s, SimWatchlistRow, SimWatchlistRow.user_id == user_id,
                               SimWatchlistRow.added_at),
            "price_alerts": _rows(s, PriceAlertRow, PriceAlertRow.user_id == user_id,
                                  PriceAlertRow.created_at),
            "analyst_conversations": _rows(
                s, OneOnOneMessageRow, OneOnOneMessageRow.user_id == user_id,
                OneOnOneMessageRow.created_at,
            ),
            "daily_challenge_attempts": _rows(
                s, DailyChallengeAttemptRow, DailyChallengeAttemptRow.user_id == user_id,
                DailyChallengeAttemptRow.created_at,
            ),
            "badges": _rows(s, BadgeRow, BadgeRow.user_id == user_id, BadgeRow.earned_at),
            "bug_reports": _rows(
                s, BugReportRow, BugReportRow.user_id == user_id, BugReportRow.created_at,
                exclude=frozenset({"assigned_branch", "attachment_path"}),
            ),
        }
