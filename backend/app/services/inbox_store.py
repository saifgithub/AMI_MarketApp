"""InboxStore — CR102 in-app tester messaging (broadcast + reply).

Send-time fan-out: a send resolves its audience ONCE, writes one
BroadcastRow with the measured recipient_count, and one InboxMessageRow
per recipient. Retention: none — broadcasts and inbox_messages rows are
permanent (CR102 explicitly specifies no purge policy; ~100-user alpha
scale).

`resolve_audience` is the load-bearing piece: every audience mode —
including explicit `mode=user` ids — passes through the base real-tester
filter, so a blast can never reach a suspended user, a house desk, a
CR035 synthetic, a seed fixture, or a by-id-excluded probe row.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete, func, select

from app.db import get_session, init_schema
from app.db.models import BroadcastRow, InboxMessageRow, User, UserDeviceRow
from app.schemas.messages import (
    AdminSendRequest,
    Audience,
    BroadcastOut,
    InboxMessageOut,
    ReplyOut,
    SendResponse,
)

# The 12 by-id exclusions from memory/feedback_user_report_exclusions.md —
# 2 CR125 promotion probes + 10 DEF227/228/229 live-verification convene
# users. Excluded BY ID because their shape (device-less anon rows) is
# indistinguishable from a genuine bare session. Keep in sync with that file.
EXCLUDED_USER_IDS: frozenset[UUID] = frozenset(
    UUID(x)
    for x in (
        # CR125 promotion probes (2026-08-07 17:21 UTC)
        "ea99a8bc-e612-4569-928d-6ed4d1a0d708",
        "8735d3f2-3cff-43e5-a670-ecd5677226b7",
        # DEF227/228/229 convene users (2026-08-07 19:17-19:22 UTC)
        "8f45cd0e-565d-4c7d-b621-a956a4f99339",  # GRAB
        "f16d093d-dd9b-41a9-8315-e18e205c09ec",  # AMD
        "d7edc328-aa28-41d3-9828-795f145b9879",  # NVDA
        "4ae1436a-3aa8-45c0-a502-f4151c8879b6",  # ANET
        "5d6a5550-895e-45e5-92ca-56891609e7fd",  # KTOS
        "1a6be9ff-6d35-468e-855e-bbaeb187a242",  # MU
        "1c5bb79c-920e-4152-a29a-e6a2d41adcbb",  # SNDK
        "fa724aab-83fb-4bbb-a84e-0774f6721226",  # AVGO
        "0310202b-e2ac-42ff-b44e-8d25b8d0e36c",  # LITE
        "92518daf-b2f7-49dd-857c-60060e2ceef1",  # NBIS
    )
)

# The 2026-05-24 seed-fixture burst window (device-less, version-less rows
# created inside this minute are seed data, not people).
_SEED_WINDOW_START = datetime(2026, 5, 24, 5, 10, 0, tzinfo=timezone.utc)
_SEED_WINDOW_END = datetime(2026, 5, 24, 5, 11, 0, tzinfo=timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    # sqlite hands back naive datetimes; the app writes UTC everywhere.
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _build_int(app_version: str | None) -> int | None:
    """The integer after '+' in a Flutter version string, else None.

    Plain int compare on the build number, never semver — CR121 precedent
    (ClientReleaseFloorRow docstring, app/db/models.py).
    """
    if not app_version or "+" not in app_version:
        return None
    try:
        return int(app_version.split("+", 1)[1])
    except ValueError:
        return None


def _is_real_tester(u: User) -> bool:
    """The base filter every audience mode applies (incl. mode=user)."""
    if u.suspended_at is not None:
        return False
    if u.is_desk:
        return False
    if (u.last_app_version or "") == "room-benchmark":  # CR035 synthetics
        return False
    if (
        u.device_model is None
        and u.last_app_version is None
        and _SEED_WINDOW_START <= _as_utc(u.created_at) < _SEED_WINDOW_END
    ):
        return False  # 2026-05-24 seed fixtures
    if u.id in EXCLUDED_USER_IDS:
        return False
    return True


def resolve_audience(session, audience: Audience) -> list[UUID]:
    """Resolve an audience spec to concrete user ids at this moment.

    Called once, at send (or preview) time — never re-evaluated at read
    time. Devices: a user's newest install wins (max build int across
    device rows; max last_seen_at for activity). A user with no device
    row, or no parseable build, is EXCLUDED from build/activity modes —
    absent over fabricated (CR040), we cannot prove they match.
    """
    users = [
        u
        for u in session.scalars(select(User)).all()
        if _is_real_tester(u)
    ]
    if audience.mode == "user":
        wanted = set(audience.user_ids or [])
        return [u.id for u in users if u.id in wanted]
    if audience.mode == "all":
        return [u.id for u in users]

    devices = session.scalars(select(UserDeviceRow)).all()
    by_user: dict[UUID, list[UserDeviceRow]] = {}
    for d in devices:
        by_user.setdefault(d.user_id, []).append(d)

    if audience.mode == "build":
        target = _build_int(audience.app_version_lt)
        out: list[UUID] = []
        for u in users:
            builds = [
                b for d in by_user.get(u.id, ())
                if (b := _build_int(d.app_version)) is not None
            ]
            if builds and max(builds) < target:  # type: ignore[operator]
                out.append(u.id)
        return out

    # mode == "activity"
    now = datetime.now(timezone.utc)
    out = []
    for u in users:
        seen = [_as_utc(d.last_seen_at) for d in by_user.get(u.id, ())]
        if not seen:
            continue
        last = max(seen)
        if audience.active_within_days is not None:
            if last >= now - timedelta(days=audience.active_within_days):
                out.append(u.id)
        else:
            if last < now - timedelta(days=audience.dormant_beyond_days):
                out.append(u.id)
    return out


class InboxStore:
    def __init__(self) -> None:
        init_schema()

    # ── admin side ────────────────────────────────────────────────────────

    def preview(self, audience: Audience) -> int:
        """Resolve and count. Writes NOTHING — the mistargeted-blast guard."""
        with get_session() as s:
            return len(resolve_audience(s, audience))

    def send(self, req: AdminSendRequest, created_by: str | None = None) -> SendResponse:
        now = datetime.now(timezone.utc)
        with get_session() as s:
            recipients = resolve_audience(s, req.audience)
            broadcast = BroadcastRow(
                title=req.title,
                body=req.body,
                body_i18n=req.body_i18n,
                priority=req.priority,
                audience_json=req.audience.model_dump(mode="json"),
                created_by=created_by,
                recipient_count=len(recipients),
                created_at=now,
            )
            s.add(broadcast)
            s.flush()
            for uid in recipients:
                s.add(
                    InboxMessageRow(
                        user_id=uid,
                        broadcast_id=broadcast.id,
                        direction="out",
                        title=req.title,
                        body=req.body,
                        created_at=now,
                    )
                )
            return SendResponse(
                broadcast_id=broadcast.id, recipient_count=len(recipients)
            )

    def list_broadcasts(self) -> list[BroadcastOut]:
        with get_session() as s:
            rows = s.scalars(
                select(BroadcastRow).order_by(BroadcastRow.created_at.desc())
            ).all()
            counts = dict(
                s.execute(
                    select(InboxMessageRow.broadcast_id, func.count())
                    .where(InboxMessageRow.direction == "in")
                    .group_by(InboxMessageRow.broadcast_id)
                ).all()
            )
            return [
                BroadcastOut(
                    id=b.id,
                    title=b.title,
                    body=b.body,
                    priority=b.priority,
                    audience=b.audience_json,
                    recipient_count=b.recipient_count,
                    reply_count=counts.get(b.id, 0),
                    created_at=b.created_at,
                )
                for b in rows
            ]

    def list_replies(self, since: datetime | None = None) -> list[ReplyOut]:
        with get_session() as s:
            q = select(InboxMessageRow).where(InboxMessageRow.direction == "in")
            if since is not None:
                q = q.where(InboxMessageRow.created_at >= since)
            rows = s.scalars(q.order_by(InboxMessageRow.created_at.desc())).all()
            return [
                ReplyOut(
                    id=r.id,
                    user_id=r.user_id,
                    broadcast_id=r.broadcast_id,
                    reply_to_id=r.reply_to_id,
                    body=r.body,
                    created_at=r.created_at,
                )
                for r in rows
            ]

    # ── user side ─────────────────────────────────────────────────────────
    # The user_id predicate in every method below is the authorization
    # check, not a filter — same rationale as FeedbackStore.acknowledge.

    def list_inbox(self, user_id: UUID) -> list[InboxMessageOut]:
        with get_session() as s:
            rows = s.execute(
                select(InboxMessageRow, BroadcastRow.priority)
                .outerjoin(
                    BroadcastRow,
                    (InboxMessageRow.broadcast_id == BroadcastRow.id)
                    & (InboxMessageRow.direction == "out"),
                )
                .where(InboxMessageRow.user_id == user_id)
                .order_by(InboxMessageRow.created_at.desc())
            ).all()
            return [
                InboxMessageOut(
                    id=m.id,
                    broadcast_id=m.broadcast_id,
                    direction=m.direction,  # type: ignore[arg-type]
                    title=m.title,
                    body=m.body,
                    priority=priority,
                    reply_to_id=m.reply_to_id,
                    created_at=m.created_at,
                    read_at=m.read_at,
                    toasted_at=m.toasted_at,
                )
                for m, priority in rows
            ]

    def _own_row(self, s, user_id: UUID, message_id: UUID) -> InboxMessageRow | None:
        return s.scalars(
            select(InboxMessageRow).where(
                InboxMessageRow.id == message_id,
                InboxMessageRow.user_id == user_id,
            )
        ).one_or_none()

    def mark_read(self, user_id: UUID, message_id: UUID) -> bool:
        """Stamp read_at once. Idempotent on own rows; False = not yours/absent."""
        with get_session() as s:
            row = self._own_row(s, user_id, message_id)
            if row is None:
                return False
            if row.read_at is None:
                row.read_at = datetime.now(timezone.utc)
            return True

    def mark_toasted(self, user_id: UUID, message_id: UUID) -> bool:
        """Stamp toasted_at once — server-side, so the high-priority toast
        fires exactly once even across a reinstall."""
        with get_session() as s:
            row = self._own_row(s, user_id, message_id)
            if row is None:
                return False
            if row.toasted_at is None:
                row.toasted_at = datetime.now(timezone.utc)
            return True

    def reply(self, user_id: UUID, message_id: UUID, body: str) -> ReplyOut | None:
        """Write a direction='in' row threaded to the caller's own message.

        None when the parent row isn't the caller's — the API turns that
        into the same 404 a nonexistent id gets.
        """
        with get_session() as s:
            parent = self._own_row(s, user_id, message_id)
            if parent is None:
                return None
            row = InboxMessageRow(
                user_id=user_id,
                broadcast_id=parent.broadcast_id,
                direction="in",
                body=body,
                reply_to_id=parent.id,
                created_at=datetime.now(timezone.utc),
            )
            s.add(row)
            s.flush()
            return ReplyOut(
                id=row.id,
                user_id=row.user_id,
                broadcast_id=row.broadcast_id,
                reply_to_id=row.reply_to_id,
                body=row.body,
                created_at=row.created_at,
            )

    def clear(self) -> None:
        """Wipe all rows — used by tests."""
        with get_session() as s:
            s.execute(delete(InboxMessageRow))
            s.execute(delete(BroadcastRow))


_store: InboxStore | None = None


def get_inbox_store() -> InboxStore:
    global _store
    if _store is None:
        _store = InboxStore()
    return _store
