"""CR102 — InboxStore: send-time fan-out, preview writes nothing, replies
thread to a concrete row, read/toasted stamps are once-only and scoped to
the owner. Also proves the conftest singleton reset isolates tests."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import BroadcastRow, InboxMessageRow, User
from app.schemas.messages import AdminSendRequest, Audience
from app.services.inbox_store import get_inbox_store


def _make_user() -> "uuid4":
    uid = uuid4()
    with get_session() as s:
        s.add(User(id=uid, device_model="iPhone18,1", last_app_version="0.1.0+54"))
    return uid


def _send_all(title: str = "Build 55 is out", priority: str = "normal"):
    return get_inbox_store().send(
        AdminSendRequest(
            title=title,
            body="Please update via TestFlight.",
            priority=priority,
            audience=Audience(mode="all"),
        )
    )


def test_send_fans_out_exactly_n_rows_with_measured_count() -> None:
    users = [_make_user() for _ in range(3)]
    resp = _send_all()
    assert resp.recipient_count == 3
    with get_session() as s:
        b = s.scalars(select(BroadcastRow)).one()
        assert b.recipient_count == 3
        rows = s.scalars(select(InboxMessageRow)).all()
    assert len(rows) == 3
    assert {r.user_id for r in rows} == set(users)
    assert all(r.direction == "out" and r.broadcast_id == resp.broadcast_id for r in rows)


def test_late_installer_never_receives_old_blast() -> None:
    _make_user()
    _send_all()
    late = _make_user()  # installs after the send
    store = get_inbox_store()
    assert store.list_inbox(late) == []


def test_preview_writes_zero_rows() -> None:
    _make_user()
    store = get_inbox_store()
    assert store.preview(Audience(mode="all")) == 1
    with get_session() as s:
        assert s.scalars(select(BroadcastRow)).all() == []
        assert s.scalars(select(InboxMessageRow)).all() == []


def test_reply_threads_to_parent_and_broadcast() -> None:
    uid = _make_user()
    sent = _send_all()
    store = get_inbox_store()
    msg = store.list_inbox(uid)[0]
    out = store.reply(uid, msg.id, "Got it, updating now")
    assert out is not None
    assert out.reply_to_id == msg.id
    assert out.broadcast_id == sent.broadcast_id
    with get_session() as s:
        row = s.scalars(
            select(InboxMessageRow).where(InboxMessageRow.direction == "in")
        ).one()
    assert row.user_id == uid
    # And it shows in the admin reply feed + broadcast reply count.
    assert [r.id for r in store.list_replies()] == [out.id]
    assert store.list_broadcasts()[0].reply_count == 1


def test_reply_to_foreign_row_returns_none() -> None:
    owner = _make_user()
    other = _make_user()
    _send_all()
    store = get_inbox_store()
    msg = store.list_inbox(owner)[0]
    assert store.reply(other, msg.id, "not mine") is None


def test_read_and_toasted_stamp_once_and_are_idempotent() -> None:
    uid = _make_user()
    _send_all(priority="high")
    store = get_inbox_store()
    msg_id = store.list_inbox(uid)[0].id

    assert store.mark_read(uid, msg_id) is True
    first_read = store.list_inbox(uid)[0].read_at
    assert first_read is not None
    assert store.mark_read(uid, msg_id) is True  # idempotent
    assert store.list_inbox(uid)[0].read_at == first_read  # stamp unchanged

    assert store.mark_toasted(uid, msg_id) is True
    first_toast = store.list_inbox(uid)[0].toasted_at
    assert first_toast is not None
    assert store.mark_toasted(uid, msg_id) is True
    assert store.list_inbox(uid)[0].toasted_at == first_toast

    # Foreign / nonexistent -> False, so the API 404s identically.
    assert store.mark_read(uuid4(), msg_id) is False
    assert store.mark_toasted(uid, uuid4()) is False


def test_singleton_reset_isolation_a() -> None:
    _make_user()
    _send_all()
    assert len(get_inbox_store().list_broadcasts()) == 1


def test_singleton_reset_isolation_b() -> None:
    # Runs after _a in file order; a leaked singleton/db would show its rows.
    assert get_inbox_store().list_broadcasts() == []
