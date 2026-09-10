"""CR102 — resolve_audience: the base real-tester filter + the four modes.

The base filter (suspended, house desks, CR035 room-benchmark synthetics,
the 2026-05-24 seed-burst shape, and the 12 by-id exclusions from
memory/feedback_user_report_exclusions.md) must hold on EVERY mode,
including explicit mode=user ids — a blast can never reach a non-tester.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app.db import get_session
from app.db.models import User, UserDeviceRow
from app.schemas.messages import Audience
from app.services.admin_analytics import _EXCLUDED_USER_IDS as EXCLUDED_USER_IDS
from app.services.inbox_store import resolve_audience


def _make_user(
    *,
    created_at: datetime | None = None,
    device_model: str | None = "iPhone18,1",
    last_app_version: str | None = "0.1.0+54",
    suspended: bool = False,
    is_desk: bool = False,
    user_id: UUID | None = None,
) -> UUID:
    uid = user_id or uuid4()
    now = datetime.now(timezone.utc)
    with get_session() as s:
        s.add(User(
            id=uid,
            created_at=created_at or now,
            device_model=device_model,
            last_app_version=last_app_version,
            suspended_at=now if suspended else None,
            is_desk=is_desk,
            desk_key=f"desk-{uid.hex[:8]}" if is_desk else None,
        ))
    return uid


def _add_device(user_id: UUID, *, app_version: str | None, last_seen_at: datetime) -> None:
    with get_session() as s:
        s.add(UserDeviceRow(
            user_id=user_id,
            device_install_id=uuid4(),
            app_version=app_version,
            first_seen_at=last_seen_at,
            last_seen_at=last_seen_at,
        ))


def test_mode_all_excludes_every_non_tester_cohort() -> None:
    real = _make_user()
    _make_user(last_app_version="room-benchmark")            # CR035 synthetic
    _make_user(                                              # seed-burst shape
        created_at=datetime(2026, 5, 24, 5, 10, 30, tzinfo=timezone.utc),
        device_model=None, last_app_version=None,
    )
    _make_user(user_id=sorted(EXCLUDED_USER_IDS, key=str)[0])  # by-id exclusion
    _make_user(is_desk=True)                                 # CR109 house desk
    _make_user(suspended=True)

    with get_session() as s:
        got = resolve_audience(s, Audience(mode="all"))
    assert got == [real]


def test_seed_shape_requires_all_three_conditions() -> None:
    # In the window but WITH a device model — a real user, not a seed row.
    real = _make_user(
        created_at=datetime(2026, 5, 24, 5, 10, 30, tzinfo=timezone.utc),
        last_app_version=None,
    )
    with get_session() as s:
        got = resolve_audience(s, Audience(mode="all"))
    assert got == [real]


def test_mode_build_int_compare_on_build_suffix() -> None:
    older = _make_user()
    newer = _make_user()
    unknown = _make_user()
    _add_device(older, app_version="0.1.0+54",
                last_seen_at=datetime.now(timezone.utc))
    _add_device(newer, app_version="0.1.0+55",
                last_seen_at=datetime.now(timezone.utc))
    # No parseable build -> excluded (absent over fabricated, CR040).
    _add_device(unknown, app_version=None,
                last_seen_at=datetime.now(timezone.utc))

    with get_session() as s:
        got = resolve_audience(
            s, Audience(mode="build", app_version_lt="0.1.0+55")
        )
    assert got == [older]


def test_mode_build_newest_device_wins() -> None:
    upgraded = _make_user()
    now = datetime.now(timezone.utc)
    _add_device(upgraded, app_version="0.1.0+40", last_seen_at=now)
    _add_device(upgraded, app_version="0.1.0+60", last_seen_at=now)
    with get_session() as s:
        got = resolve_audience(
            s, Audience(mode="build", app_version_lt="0.1.0+55")
        )
    assert got == []  # their newest install is already past the floor


def test_mode_activity_windows() -> None:
    now = datetime.now(timezone.utc)
    fresh = _make_user()
    stale = _make_user()
    deviceless = _make_user()
    _add_device(fresh, app_version="0.1.0+54", last_seen_at=now - timedelta(days=2))
    _add_device(stale, app_version="0.1.0+54", last_seen_at=now - timedelta(days=30))

    with get_session() as s:
        active = resolve_audience(s, Audience(mode="activity", active_within_days=7))
        dormant = resolve_audience(s, Audience(mode="activity", dormant_beyond_days=14))
    assert active == [fresh]
    assert dormant == [stale]
    # No device row -> no last_seen fact -> in neither window.
    assert deviceless not in active + dormant


def test_mode_user_applies_base_filter_even_on_explicit_ids() -> None:
    real = _make_user()
    suspended = _make_user(suspended=True)
    desk = _make_user(is_desk=True)
    excluded_id = sorted(EXCLUDED_USER_IDS, key=str)[1]
    _make_user(user_id=excluded_id)

    with get_session() as s:
        got = resolve_audience(
            s,
            Audience(mode="user", user_ids=[real, suspended, desk, excluded_id]),
        )
    assert got == [real]


def test_excluded_ids_match_memory_file_count() -> None:
    assert len(EXCLUDED_USER_IDS) == 12
