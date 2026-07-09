"""AUDITOR pin (CR004 round 1) — blind adversarial probe on the reputation
engine's riskiest dimension: idempotency of streak-milestone CREDIT grants
under the global daily reputation cap.

Self-contained (does NOT rely on backend/tests/conftest.py) so it is provably
independent of the architect's own harness. Sets up its own sqlite tempfile
DB via app.db.reset_for_tests, exactly as the app's own test fixture does.

Hypothesis being tested:
  reputation_service._grant_milestone() grants credits UNCONDITIONALLY once its
  guard passes, but the guard (`_already_awarded`) relies on a reputation_events
  row that award() DECLINES to write when the daily cap is already exhausted
  (`remaining <= 0` returns before the INSERT). streak_7(10)+streak_30(25)+
  streak_100(50) = 85 > the 25/day cap, so on the day all three fire together
  the streak_100 award is clipped to a zero-write, its guard never sets, and
  its 100-credit grant re-fires on EVERY subsequent streak() call
  (GET /v1/league/me is called on every league-screen load).

Run: backend/.venv/bin/python -m pytest audit/handshake/regression/test_streak_milestone_cap_pin.py -q
(from repo root; the editable-installed `app` package resolves via that venv.)
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select


@pytest.fixture(autouse=True)
def _pin_db(tmp_path):
    """Fresh sqlite tempfile DB + reputation-singleton reset — mirrors the
    app's own _isolated_db fixture without importing it."""
    url = f"sqlite:///{tmp_path / 'ami_pin.db'}"
    os.environ["AMI_TEST_DATABASE_URL"] = url
    from app.db import reset_for_tests
    reset_for_tests(url)
    from app.services import reputation_service as _rep
    _rep._service = None
    yield


def _make_user_with_streak(days: int):
    """User with `days` consecutive local-days of activity ending today."""
    from app.db import get_session
    from app.db.models import JournalEntryRow, User
    from app.services.auth_service import AuthService

    au, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    now = datetime.now(timezone.utc)
    with get_session() as s:
        user = s.execute(select(User).where(User.id == au.id)).scalar_one()
        user.timezone = "UTC"
        for d in range(days):
            s.add(JournalEntryRow(
                user_id=user.id, entry_type="trade", title=f"d{d}",
                created_at=now - timedelta(days=d),
            ))
    return au.id


def _snapshot(user_id):
    from app.db import get_session
    from app.db.models import SubscriptionEventRow, User
    with get_session() as s:
        bal = s.execute(select(User.credit_balance).where(User.id == user_id)).scalar_one()
        n_credit_events = len(s.execute(
            select(SubscriptionEventRow.id).where(
                SubscriptionEventRow.user_id == user_id,
                SubscriptionEventRow.event_type == "credits_added",
            )
        ).scalars().all())
    return bal, n_credit_events


def test_streak_milestone_credits_not_regranted_under_cap():
    """Two league-screen loads on the day a user crosses the 100-day streak
    must not re-grant the streak_100 credits. Under the cap-clip bug they do."""
    from app.db import get_session
    from app.services.reputation_service import ReputationService

    user_id = _make_user_with_streak(100)
    svc = ReputationService()

    # First GET /v1/league/me — crosses milestones 7, 30, 100.
    with get_session() as s:
        info = svc.streak(s, user_id)
    assert info.current == 100, f"expected a 100-day streak, got {info.current}"
    bal1, events1 = _snapshot(user_id)

    # Second GET /v1/league/me, same local day — pure idempotency probe.
    with get_session() as s:
        svc.streak(s, user_id)
    bal2, events2 = _snapshot(user_id)

    assert bal2 == bal1, (
        f"streak-milestone credits re-granted on a second streak() call: "
        f"balance {bal1} -> {bal2} (+{bal2 - bal1}). The streak_100 award is "
        f"clipped to a zero-write by the 25/day cap, so its idempotency guard "
        f"row never persists and the 100-credit grant re-fires."
    )
    assert events2 == events1, (
        f"extra credits_added event(s) written on the second call: "
        f"{events1} -> {events2}"
    )
