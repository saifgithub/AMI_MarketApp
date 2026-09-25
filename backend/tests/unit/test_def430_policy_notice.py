"""DEF430 — the one-time Privacy Policy v2.1 notice.

`app.services.policy_notice.notify_policy_update_v2_1` is the whole feature
under test: every user with `alpaca_linked_at` set gets exactly one
`policy_update` notification row, ever, no matter how many times the sweep
runs — the idempotency the boot-time lifespan hook relies on to be safe on
every restart. No network: goes through the REAL `notification_service.notify()`
(so the durable-row write and the `uq_notifications_dedupe` constraint it
relies on behave exactly as production), same style as
`test_cr095_daily_reminder.py`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select

from app.db import get_session
from app.db.models import NotificationRow, User
from app.services import policy_notice


def _make_user(*, alpaca_linked_at: datetime | None) -> User:
    user_id = uuid4()
    with get_session() as s:
        s.add(User(
            id=user_id, plan="floor_pass", is_anonymous=True,
            alpaca_linked_at=alpaca_linked_at,
        ))
    with get_session() as s:
        return s.execute(select(User).where(User.id == user_id)).scalar_one()


def _policy_rows_for(user_id) -> list[NotificationRow]:
    with get_session() as s:
        return s.execute(
            select(NotificationRow).where(
                NotificationRow.user_id == user_id,
                NotificationRow.type == "policy_update",
            )
        ).scalars().all()


def test_only_alpaca_linked_users_are_notified():
    linked = _make_user(alpaca_linked_at=datetime(2026, 8, 1, tzinfo=timezone.utc))
    unlinked = _make_user(alpaca_linked_at=None)

    stats = policy_notice.notify_policy_update_v2_1()

    assert len(_policy_rows_for(linked.id)) == 1
    assert _policy_rows_for(unlinked.id) == []
    assert stats["eligible"] >= 1
    assert stats["notified"] >= 1


def test_row_shape_names_the_privacy_policy():
    user = _make_user(alpaca_linked_at=datetime(2026, 8, 1, tzinfo=timezone.utc))

    policy_notice.notify_policy_update_v2_1()

    rows = _policy_rows_for(user.id)
    assert len(rows) == 1
    row = rows[0]
    assert "v2.1" in row.title
    assert row.deep_link["route"] == "open_privacy_policy"
    assert "privacy" in row.deep_link["params"]["url"]


def test_a_second_run_never_creates_a_second_row_for_the_same_user():
    user = _make_user(alpaca_linked_at=datetime(2026, 8, 1, tzinfo=timezone.utc))

    first = policy_notice.notify_policy_update_v2_1()
    second = policy_notice.notify_policy_update_v2_1()

    assert len(_policy_rows_for(user.id)) == 1, (
        "DEF430: at most one policy_update row per user, ever — a second "
        "sweep (e.g. every container restart) must be a no-op"
    )
    assert first["notified"] == 1
    assert second["notified"] == 0
    assert second["already_notified"] == 1


def test_a_user_who_links_after_the_sweep_is_not_retroactively_notified():
    # Not linked at sweep time.
    user = _make_user(alpaca_linked_at=None)
    policy_notice.notify_policy_update_v2_1()
    assert _policy_rows_for(user.id) == []

    # Links afterwards — DEF430's mobile link-screen disclosure is that
    # user's consent-at-collection moment; a backend notice for them would
    # be redundant, not missing, so a later sweep must still skip them
    # unless this module is deliberately re-run with a different intent.
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user.id)).scalar_one()
        row.alpaca_linked_at = datetime(2026, 9, 26, tzinfo=timezone.utc)

    stats = policy_notice.notify_policy_update_v2_1()

    assert len(_policy_rows_for(user.id)) == 1
    assert stats["notified"] == 1


def test_no_users_at_all_is_not_an_error():
    stats = policy_notice.notify_policy_update_v2_1()
    assert stats["errors"] == 0
