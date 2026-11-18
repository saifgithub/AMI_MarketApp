"""CR276 (CR267 WP-30) — close an account, restore it, and erase it after grace.

Apple App Store 5.1.1(v) and Google Play both require in-app account deletion
that removes the user's personal data. This module is the whole mechanism:

  request_closure(user_id)   POST /v1/account/close: deactivate + revoke every
                             session in ONE write, stamp when it was asked.
  restore_closure(row)       called by an identity-verified sign-in INSIDE the
                             grace window (see auth_service); clears the stamp.
  erase_account(user_id)     the post-grace step, in one of three modes.
  run_erasure_tick()         the scheduled job: erase every account whose grace
                             has ended. Idempotent; one bad account never stops
                             the rest.

**The registry is the contract.** `RULES` states, for every table that carries
a user id, what each mode does to it and why. `test_cr276_account_erasure.py`
walks `Base.metadata` and fails if a table with a user-id column is in neither
`RULES` nor `NOT_USER_DATA` — so a table added next year cannot silently escape
deletion (CR040: a deletion that quietly skips a table is the DEF059 shape — the
user believes their data is gone).

The three modes (`settings.account_erasure_mode`):

  delete     the Beta default. Hard-deletes the user row and every row of
             personal data. What survives is listed per table below and carries
             no link to a person once the user row is gone.
  anonymise  keeps a scrubbed tombstone user row (no email / provider ids /
             device ids / handle / name) plus de-identified SIMULATED activity
             (trades, portfolios, Room verdicts, progress). Anything free-text
             or device-level is still deleted.
  archive    keeps everything; only sign-in stays blocked. Retains personal data
             after a deletion request, so it refuses to run until counsel's
             approval is recorded (`account_archive_counsel_approved`, gate S6).

Alpaca: CR202 removed credential custody — the keys live in the device keychain,
never here — so the only Alpaca trace on this host is `users.alpaca_linked_at`
and the order audit rows covered below.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from sqlalchemy import delete, or_, select, update

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import (
    AdminAuditRow,
    AgentActivationRow,
    AlpacaOrderAuditRow,
    AuthChallengeRow,
    BadgeRow,
    BugReportRow,
    CareerEventRow,
    DailyChallengeAttemptRow,
    GameDuelRow,
    GameEntryRow,
    GameFieldRow,
    GameQueuedOrderRow,
    GameShortPositionRow,
    HTTPAuditRow,
    InboxMessageRow,
    JournalEntryRow,
    LeagueMemberRow,
    LessonProgressRow,
    LLMAuditRow,
    MandateRow,
    NotificationPreferenceRow,
    NotificationRow,
    OneOnOneMessageRow,
    OverlayEditCounter,
    PersonaEventRow,
    PortfolioNavDailyRow,
    PortfolioValueSnapshotRow,
    PriceAlertRow,
    ReputationEventRow,
    RevenueCatEventRow,
    RoomRunRow,
    SimHoldingRow,
    SimOptionLegRow,
    SimOptionTradeRow,
    SimPortfolioRow,
    SimRestingOrderRow,
    SimShortPositionRow,
    SimTradeRow,
    SimWatchlistRow,
    StreakFreezeRow,
    SubscriptionEventRow,
    User,
    UserDeviceRow,
    UserOverlayRow,
    VerdictOutcomeRow,
)

ErasureMode = str  # "archive" | "anonymise" | "delete"

_ONESIGNAL_USERS_API = "https://api.onesignal.com/apps"
_RC_API_BASE = "https://api.revenuecat.com/v1"
_HTTP_TIMEOUT = httpx.Timeout(10.0)
_TICK_BATCH = 50


class ArchiveNotApproved(RuntimeError):
    """`archive` was requested without counsel's approval recorded."""


class ExternalErasureFailed(RuntimeError):
    """A third-party processor rejected or could not be asked to forget a user."""


# ── The registry ─────────────────────────────────────────────────────────────


class Act(str, Enum):
    DELETE = "delete"          # remove the rows
    KEEP = "keep"              # leave as is (pseudonymous once the user row is gone)
    SCRUB = "scrub"            # blank the listed columns, keep the row and its user id
    SCRUB_DETACH = "scrub_detach"  # blank the listed columns AND null the user column
    DETACH = "detach"          # null the user column only


@dataclass(frozen=True)
class TableRule:
    model: type
    columns: tuple[str, ...]
    delete: Act
    anonymise: Act
    why: str
    scrub: dict[str, Any] = field(default_factory=dict)
    # For a child table with no user column of its own: (parent model, this
    # table's fk column, parent's user column). Rows are matched through the parent.
    via: tuple[type, str, str] | None = None

    @property
    def table(self) -> str:
        return self.model.__tablename__  # type: ignore[attr-defined]


RULES: tuple[TableRule, ...] = (
    TableRule(UserDeviceRow, ("user_id",), Act.DELETE, Act.DELETE,
              "device model / OS / install id: device-level personal data"),
    TableRule(MandateRow, ("user_id",), Act.DELETE, Act.DELETE,
              "the user's risk profile and constraints: personal financial preferences"),
    TableRule(UserOverlayRow, ("user_id",), Act.DELETE, Act.DELETE,
              "the user's own free-text agent briefs"),
    TableRule(OverlayEditCounter, ("user_id",), Act.DELETE, Act.DELETE,
              "per-user counters for the briefs above"),
    TableRule(JournalEntryRow, ("user_id",), Act.DELETE, Act.DELETE,
              "journal entries hold the user's own notes and tags"),
    TableRule(LessonProgressRow, ("user_id",), Act.DELETE, Act.KEEP,
              "learning progress: de-identified counts once the handle and ids are gone"),
    TableRule(AgentActivationRow, ("user_id",), Act.DELETE, Act.KEEP,
              "which analysts the user unlocked: no free text"),
    TableRule(SimHoldingRow, ("portfolio_id",), Act.DELETE, Act.KEEP,
              "holdings of the simulated portfolio, matched through the portfolio",
              via=(SimPortfolioRow, "portfolio_id", "user_id")),
    TableRule(SimPortfolioRow, ("user_id",), Act.DELETE, Act.KEEP,
              "simulated cash and positions: de-identified simulated activity"),
    TableRule(SimTradeRow, ("user_id",), Act.DELETE, Act.KEEP,
              "simulated trades: de-identified simulated activity"),
    TableRule(SimShortPositionRow, ("user_id",), Act.DELETE, Act.KEEP,
              "simulated short positions"),
    TableRule(SimOptionLegRow, ("user_id",), Act.DELETE, Act.KEEP,
              "simulated option legs"),
    TableRule(SimOptionTradeRow, ("user_id",), Act.DELETE, Act.KEEP,
              "simulated option trades"),
    TableRule(SimRestingOrderRow, ("user_id",), Act.DELETE, Act.KEEP,
              "simulated resting orders"),
    TableRule(PortfolioValueSnapshotRow, ("user_id",), Act.DELETE, Act.KEEP,
              "daily value of the simulated portfolio"),
    TableRule(PortfolioNavDailyRow, ("user_id",), Act.DELETE, Act.KEEP,
              "daily NAV of the simulated portfolio"),
    TableRule(RoomRunRow, ("user_id",), Act.DELETE, Act.SCRUB,
              "Room runs: the transcript and the CIO context snapshot embed the "
              "user's mandate and holdings, so anonymise blanks them and keeps "
              "the verdict and run metadata",
              scrub={"transcript": [], "cio_context_snapshot": None}),
    TableRule(VerdictOutcomeRow, ("user_id",), Act.DELETE, Act.KEEP,
              "scored Room verdicts (ticker, action, forward return): no free text"),
    TableRule(SimWatchlistRow, ("user_id",), Act.DELETE, Act.DELETE,
              "watchlist rows carry the user's own notes"),
    TableRule(PriceAlertRow, ("user_id",), Act.DELETE, Act.DELETE,
              "the user's alerts and the commentary written for them"),
    TableRule(NotificationRow, ("user_id",), Act.DELETE, Act.DELETE,
              "the user's in-app notification centre"),
    TableRule(NotificationPreferenceRow, ("user_id",), Act.DELETE, Act.DELETE,
              "the user's notification settings"),
    TableRule(InboxMessageRow, ("user_id",), Act.DELETE, Act.DELETE,
              "inbox messages incl. the user's own replies to support"),
    TableRule(PersonaEventRow, ("user_id",), Act.DELETE, Act.DELETE,
              "per-user behavioural telemetry"),
    TableRule(BugReportRow, ("user_id",), Act.DELETE, Act.DELETE,
              "bug reports are free text plus an optional screenshot (the file is "
              "removed too)"),
    TableRule(OneOnOneMessageRow, ("user_id",), Act.DELETE, Act.DELETE,
              "the user's conversations with an analyst"),
    TableRule(HTTPAuditRow, ("user_id",), Act.DELETE, Act.DELETE,
              "request log: client IP and request/response bodies"),
    TableRule(LLMAuditRow, ("user_id",), Act.SCRUB_DETACH, Act.SCRUB_DETACH,
              "prompts, messages and replies are blanked and the user id removed; "
              "the token counts, cost, latency and model stay because the LLM "
              "spend cap and the cost accounting are computed from them",
              scrub={"system_prompt": "", "messages": [], "response_text": None}),
    TableRule(AlpacaOrderAuditRow, ("user_id",), Act.DELETE, Act.KEEP,
              "paper-order audit (symbol, side, qty, outcome); no credentials"),
    TableRule(ReputationEventRow, ("user_id",), Act.DELETE, Act.KEEP,
              "reputation point events"),
    TableRule(DailyChallengeAttemptRow, ("user_id",), Act.DELETE, Act.KEEP,
              "daily challenge answers"),
    TableRule(LeagueMemberRow, ("user_id",), Act.DELETE, Act.KEEP,
              "league standings; other members' stored ranks are not recomputed"),
    TableRule(BadgeRow, ("user_id",), Act.DELETE, Act.KEEP, "badges earned"),
    TableRule(StreakFreezeRow, ("user_id",), Act.DELETE, Act.KEEP, "streak freezes"),
    TableRule(CareerEventRow, ("user_id",), Act.DELETE, Act.KEEP,
              "game career points ledger"),
    TableRule(GameQueuedOrderRow, ("user_id",), Act.DELETE, Act.KEEP,
              "queued orders inside a game run"),
    TableRule(GameShortPositionRow, ("user_id",), Act.DELETE, Act.KEEP,
              "short positions inside a game run"),
    TableRule(GameEntryRow, ("user_id",), Act.DELETE, Act.KEEP,
              "the user's entries in games. delete: the row goes, the field's "
              "champion pointer is cleared first so no board dangles"),
    TableRule(GameDuelRow, ("user_a_id", "user_b_id"), Act.DELETE, Act.KEEP,
              "head-to-head records: delete removes the duel from the opponent's "
              "history too, since it names the deleted user"),
    TableRule(GameFieldRow, ("owner_user_id",), Act.DETACH, Act.DETACH,
              "a private field the user created keeps running for its other "
              "entrants; only the owner pointer is cleared"),
    TableRule(SubscriptionEventRow, ("user_id",), Act.KEEP, Act.KEEP,
              "billing ledger (plan changes, source, timestamps): kept as an "
              "accounting record. Free-text `note` is blanked in both modes",
              scrub={"note": None}),
    TableRule(RevenueCatEventRow, ("app_user_id",), Act.KEEP, Act.KEEP,
              "RevenueCat webhook dedup + accounting trail, keyed by the opaque "
              "user id string; no name, email or payment detail"),
)

# Tables with a user-id-shaped column that are deliberately outside RULES.
NOT_USER_DATA: dict[str, str] = {
    "users": "handled by hand in erase_account (delete / scrub / flag)",
    "auth_challenges": "handled by hand in erase_account (matched by user id AND by "
                       "the target email)",
    "admin_audit": "operator action log, no user column; `target` may name a user "
                   "id. Permanent by design (CR200) and not personal data on its own",
}

USER_ID_COLUMN_NAMES = frozenset({
    "user_id", "owner_user_id", "user_a_id", "user_b_id", "winner_user_id",
    "app_user_id",
})


def rules_by_table() -> dict[str, TableRule]:
    return {r.table: r for r in RULES}


# ── Closure / restore ────────────────────────────────────────────────────────


@dataclass
class ClosureResult:
    closure_requested_at: datetime
    erase_after: datetime
    already_closed: bool


def grace_delta() -> timedelta:
    return timedelta(days=settings.account_closure_grace_days)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def restorable_until(row: User) -> datetime | None:
    """When a closed account stops being restorable; None if it is not in grace."""
    if row.closure_requested_at is None or row.erased_at is not None:
        return None
    return _aware(row.closure_requested_at) + grace_delta()


def is_restorable(row: User, now: datetime | None = None) -> bool:
    until = restorable_until(row)
    return until is not None and (now or datetime.now(timezone.utc)) < until


def request_closure(user_id: UUID) -> ClosureResult:
    """Deactivate the account and kill every session in one write.

    `token_version` is the same revocation counter `DELETE /v1/auth/session`
    bumps (CR125): every outstanding token fails `get_current_user`'s version
    check on its very next use, including the one that made this call.
    Idempotent: a second call neither moves the timestamp nor bumps again.
    """
    now = datetime.now(timezone.utc)
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one()
        if row.is_desk:
            raise ValueError("house desk accounts cannot be closed")
        already = row.closure_requested_at is not None
        if not already:
            row.closure_requested_at = now
            row.token_version += 1
            logger.info(
                "account_closure_requested",
                user_id=str(user_id), mode=settings.account_erasure_mode,
                grace_days=settings.account_closure_grace_days,
            )
        requested = _aware(row.closure_requested_at)
    return ClosureResult(
        closure_requested_at=requested,
        erase_after=requested + grace_delta(),
        already_closed=already,
    )


class AccountClosedError(Exception):
    """A sign-in matched a closed account. `code` is the wire code the app keys on:
    `account_pending_deletion` (restorable until `restorable_until`) or
    `account_closed` (past grace, or archived: no self-service way back)."""

    def __init__(self, code: str, restorable_until: datetime | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.restorable_until = restorable_until


def gate_sign_in(row: User, *, restore: bool) -> None:
    """Called by every identity-proving sign-in once it has found the account the
    verified identity belongs to, BEFORE it mutates anything or mints a token.

    Not closed: no-op. Closed inside grace: refused with the restore date unless
    the caller explicitly asked to restore. Closed past grace or erased: refused.
    """
    if row.erased_at is not None:
        raise AccountClosedError("account_closed")
    if row.closure_requested_at is None:
        return
    if not is_restorable(row):
        raise AccountClosedError("account_closed")
    if not restore:
        raise AccountClosedError("account_pending_deletion", restorable_until(row))
    restore_closure(row)


def restore_closure(row: User) -> None:
    """Clear a closure inside the grace window. Caller holds the session and has
    already proved identity (a verified Apple / Google token or magic-link code)."""
    row.closure_requested_at = None
    logger.info("account_closure_restored", user_id=str(row.id))


# ── Third-party processors ───────────────────────────────────────────────────


def _erase_onesignal(user_id: UUID) -> str:
    if not settings.onesignal_app_id or not settings.onesignal_rest_key:
        logger.error(
            "account_erasure_external_not_configured",
            service="onesignal", user_id=str(user_id),
            effect="push subscription NOT deleted at OneSignal",
        )
        return "not_configured"
    url = f"{_ONESIGNAL_USERS_API}/{settings.onesignal_app_id}/users/by/external_id/{user_id}"
    try:
        resp = httpx.delete(
            url, headers={"Authorization": f"Key {settings.onesignal_rest_key}"},
            timeout=_HTTP_TIMEOUT,
        )
    except httpx.RequestError as exc:
        raise ExternalErasureFailed(f"onesignal: {exc}") from exc
    if resp.status_code in (200, 202, 204, 404):
        return "ok"
    raise ExternalErasureFailed(f"onesignal: HTTP {resp.status_code}")


def _erase_revenuecat(user_id: UUID) -> str:
    secret = settings.revenuecat_secret_api_key
    if not secret:
        logger.error(
            "account_erasure_external_not_configured",
            service="revenuecat", user_id=str(user_id),
            effect="RevenueCat subscriber NOT deleted",
        )
        return "not_configured"
    try:
        resp = httpx.delete(
            f"{_RC_API_BASE}/subscribers/{user_id}",
            headers={"Authorization": f"Bearer {secret}"}, timeout=_HTTP_TIMEOUT,
        )
    except httpx.RequestError as exc:
        raise ExternalErasureFailed(f"revenuecat: {exc}") from exc
    if resp.status_code in (200, 202, 204, 404):
        return "ok"
    raise ExternalErasureFailed(f"revenuecat: HTTP {resp.status_code}")


def erase_external(user_id: UUID) -> dict[str, str]:
    """Ask each processor to forget the user. Raises `ExternalErasureFailed` on a
    real failure so the tick retries the whole account next time; a missing key is
    logged at error and reported, not retried forever (it cannot succeed)."""
    return {
        "onesignal": _erase_onesignal(user_id),
        "revenuecat": _erase_revenuecat(user_id),
    }


# ── Erasure ──────────────────────────────────────────────────────────────────


@dataclass
class ErasureReport:
    user_id: UUID
    mode: str
    outcome: str  # erased | already_erased | absent | deferred
    tables: dict[str, int] = field(default_factory=dict)
    external: dict[str, str] = field(default_factory=dict)
    files_removed: int = 0


def _user_clause(rule: TableRule, user_id: UUID):
    cols = [getattr(rule.model, c) for c in rule.columns]
    if rule.model is RevenueCatEventRow:
        return or_(*[c == str(user_id) for c in cols])
    return or_(*[c == user_id for c in cols])


def _where_for(rule: TableRule, user_id: UUID):
    if rule.via is None:
        return _user_clause(rule, user_id)
    parent, fk, parent_user_col = rule.via
    ids = select(parent.id).where(getattr(parent, parent_user_col) == user_id)
    return getattr(rule.model, fk).in_(ids)


def _apply_rule(s, rule: TableRule, act: Act, user_id: UUID) -> int:
    if act is Act.KEEP:
        if rule.scrub:
            return s.execute(
                update(rule.model).where(_where_for(rule, user_id)).values(**rule.scrub)
            ).rowcount
        return 0
    where = _where_for(rule, user_id)
    if act is Act.DELETE:
        return s.execute(delete(rule.model).where(where)).rowcount
    values = dict(rule.scrub)
    if act in (Act.SCRUB_DETACH, Act.DETACH):
        for c in rule.columns:
            values[c] = None
    return s.execute(update(rule.model).where(where).values(**values)).rowcount


def _attachment_files(s, user_id: UUID) -> list[str]:
    return [
        p for p in s.execute(
            select(BugReportRow.attachment_path).where(
                BugReportRow.user_id == user_id,
                BugReportRow.attachment_path.is_not(None),
            )
        ).scalars()
    ]


def _remove_files(rels: list[str]) -> int:
    base = Path(settings.bug_attachments_dir).resolve()
    removed = 0
    for rel in rels:
        try:
            target = (base / rel).resolve()
            if base not in target.parents:
                logger.error("account_erasure_attachment_path_escapes", rel=rel)
                continue
            if target.exists():
                target.unlink()
                removed += 1
        except OSError as exc:
            logger.error("account_erasure_attachment_remove_failed", rel=rel, error=str(exc))
    return removed


def _tombstone_user(row: User) -> None:
    for col in ("email", "phone", "apple_id", "google_id", "hms_unionid",
                "display_name", "device_user_id", "device_model", "os_version",
                "last_app_version", "handle", "alpaca_linked_at",
                "daily_reminder_hour"):
        setattr(row, col, None)
    row.show_display_name = False
    row.is_anonymous = True


def _require_mode_allowed(mode: str) -> None:
    if mode == "archive" and not settings.account_archive_counsel_approved:
        logger.error(
            "account_erasure_archive_refused",
            reason="ACCOUNT_ARCHIVE_COUNSEL_APPROVED is not true (CR267 gate S6)",
        )
        raise ArchiveNotApproved(
            "archive mode retains personal data after a deletion request and is "
            "refused until counsel approves (set ACCOUNT_ARCHIVE_COUNSEL_APPROVED)"
        )
    if mode not in ("archive", "anonymise", "delete"):
        raise ValueError(f"unknown account_erasure_mode {mode!r}")


def erase_account(user_id: UUID, mode: str | None = None) -> ErasureReport:
    """The post-grace step for one account. Safe to call twice.

    The DB work is one transaction, so a crash leaves the account intact and the
    next tick redoes it. Processors are asked FIRST: if one is down the account
    stays in `deferred` (still closed, still unusable) rather than losing the
    only row that says whose data to forget.
    """
    mode = mode or settings.account_erasure_mode
    _require_mode_allowed(mode)
    report = ErasureReport(user_id=user_id, mode=mode, outcome="absent")

    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if row is None:
            return report
        if row.erased_at is not None:
            report.outcome = "already_erased"
            return report
        if row.closure_requested_at is None:
            raise ValueError("refusing to erase an account that was never closed")
        if is_restorable(row):
            # Checked before the processors too: an account restored (or still
            # inside grace) must not have its OneSignal/RevenueCat records wiped.
            report.outcome = "not_due"
            return report
        email = row.email

    if mode != "archive":
        try:
            report.external = erase_external(user_id)
        except ExternalErasureFailed as exc:
            logger.error(
                "account_erasure_deferred", user_id=str(user_id), error=str(exc),
                effect="account stays closed; retried next tick",
            )
            report.outcome = "deferred"
            return report

    files: list[str] = []
    with get_session() as s:
        # FOR UPDATE: a restore (a sign-in clearing `closure_requested_at`) holds
        # this row, so it and the erasure serialise instead of the erasure
        # deleting an account that was restored a moment before.
        row = s.execute(
            select(User).where(User.id == user_id).with_for_update()
        ).scalar_one_or_none()
        if row is None or row.erased_at is not None:
            report.outcome = "already_erased" if row else "absent"
            return report
        if row.closure_requested_at is None or is_restorable(row):
            logger.info(
                "account_erasure_skipped_not_due", user_id=str(user_id),
                reason="restored or closure restarted since it was queued",
            )
            report.outcome = "not_due"
            return report

        if mode != "archive":
            files = _attachment_files(s, user_id)
            if mode == "delete":
                s.execute(
                    update(GameFieldRow)
                    .where(GameFieldRow.champion_entry_id.in_(
                        select(GameEntryRow.id).where(GameEntryRow.user_id == user_id)
                    ))
                    .values(champion_entry_id=None)
                )
            for rule in RULES:
                act = rule.delete if mode == "delete" else rule.anonymise
                n = _apply_rule(s, rule, act, user_id)
                if n:
                    report.tables[rule.table] = n
            challenge_where = AuthChallengeRow.user_id == user_id
            if email:
                challenge_where = or_(challenge_where, AuthChallengeRow.target == email.lower().strip())
            report.tables["auth_challenges"] = s.execute(
                delete(AuthChallengeRow).where(challenge_where)
            ).rowcount
            if mode == "delete":
                s.execute(delete(User).where(User.id == user_id))
            else:
                _tombstone_user(row)
                row.erased_at = datetime.now(timezone.utc)
                row.erased_mode = mode
        else:
            row.erased_at = datetime.now(timezone.utc)
            row.erased_mode = mode

        s.add(AdminAuditRow(
            id=uuid4(), operator="system:account_erasure", auth_kind="system",
            action=f"account_erased_{mode}", target=str(user_id),
            payload={"tables": report.tables, "external": report.external},
            created_at=datetime.now(timezone.utc),
        ))

    report.files_removed = _remove_files(files)
    report.outcome = "erased"
    logger.info(
        "account_erased", user_id=str(user_id), mode=mode,
        tables=report.tables, external=report.external,
        files_removed=report.files_removed,
    )
    return report


def run_erasure_tick(now: datetime | None = None) -> dict[str, int]:
    """Erase every closed account whose grace has ended. Idempotent; per-account
    failures are logged and never stop the batch."""
    now = now or datetime.now(timezone.utc)
    mode = settings.account_erasure_mode
    cutoff = now - grace_delta()
    with get_session() as s:
        due = list(s.execute(
            select(User.id).where(
                User.closure_requested_at.is_not(None),
                User.closure_requested_at <= cutoff,
                User.erased_at.is_(None),
            ).order_by(User.closure_requested_at).limit(_TICK_BATCH)
        ).scalars())
    stats = {"due": len(due), "erased": 0, "deferred": 0, "failed": 0, "refused": 0}
    if not due:
        return stats
    try:
        _require_mode_allowed(mode)
    except ArchiveNotApproved:
        stats["refused"] = len(due)
        return stats
    for uid in due:
        try:
            outcome = erase_account(uid, mode).outcome
        except Exception:
            logger.exception("account_erasure_failed", user_id=str(uid))
            stats["failed"] += 1
            continue
        if outcome == "deferred":
            stats["deferred"] += 1
        elif outcome == "erased":
            stats["erased"] += 1
    return stats


def policy() -> dict[str, Any]:
    """What the app needs to word the deletion dialog honestly."""
    mode = settings.account_erasure_mode
    archive_live = mode == "archive" and settings.account_archive_counsel_approved
    return {
        "mode": mode,
        "wording": "close" if archive_live else "delete",
        "grace_days": settings.account_closure_grace_days,
        "export_available": True,
    }
