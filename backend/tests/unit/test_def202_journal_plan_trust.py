"""DEF202 — `GET /v1/journal/{user_id}`'s retention must come from the
authenticated user's own entitlement, never from a client-supplied `plan`
query parameter.

Before the fix, `plan` was an input with a `trial_trader` default: a Floor
Pass user could ask for `?plan=floor_manager` and be served unlimited
retention, and any caller who omitted the parameter got `trial_trader`'s
regardless of what they actually pay for. `_own()` already stops a caller
reading someone else's journal, so the exposure was never cross-user — it
was a caller seeing more of their *own* history than their tier allows,
plus a retention caveat that misstates their plan.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import get_current_user
from app.api.journal import router as journal_router
from app.db import get_session
from app.db.models import User
from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.auth_service import AuthService
from app.services.journal_store import JournalStore, get_journal_store


def _make_user() -> User:
    auth = AuthService()
    u, _, _ = auth.ensure_anonymous(device_user_id=None)
    return u


def _set_plan(user_id, plan: str) -> None:
    with get_session() as s:
        u = s.execute(select(User).where(User.id == user_id)).scalar_one()
        u.plan = plan


def _client(user: User, store: JournalStore) -> TestClient:
    app = FastAPI()
    app.include_router(journal_router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_journal_store] = lambda: store
    return TestClient(app, raise_server_exceptions=False)


def _seed_old_and_new_entry(store: JournalStore, user_id) -> None:
    """One entry 31 days old (out of Floor Pass's 30-day window), one fresh."""
    old = store.append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ONE_ON_ONE, title="old",
    ))
    store._backdate_for_test(
        user_id, old.id, datetime.now(timezone.utc) - timedelta(days=31),
    )
    store.append(JournalEntryCreate(
        user_id=user_id, entry_type=EntryType.ONE_ON_ONE, title="new",
    ))


def test_plan_query_param_cannot_upgrade_a_floor_pass_users_retention():
    """A Floor Pass user asking for `?plan=floor_manager` still gets Floor
    Pass's 30-day retention and the truncated entry list that goes with it —
    the server derives the plan from the authenticated user, not the query
    string."""
    user = _make_user()
    _set_plan(user.id, "floor_pass")
    store = JournalStore()
    _seed_old_and_new_entry(store, user.id)

    client = _client(user, store)
    r = client.get(f"/v1/journal/{user.id}", params={"plan": "floor_manager"})

    assert r.status_code == 200
    body = r.json()
    assert body["retention_days"] == 30, (
        "a client-supplied `plan=floor_manager` must not upgrade this "
        "Floor Pass user's retention window"
    )
    assert {e["title"] for e in body["entries"]} == {"new"}, (
        "the 31-day-old entry must stay excluded regardless of the "
        "requested `plan`"
    )


def test_omitting_plan_no_longer_silently_yields_trial_trader():
    """A Floor Pass user who omits `plan` entirely must still be served
    THEIR 30-day retention. The old default (`trial_trader`, unlimited)
    would have silently handed this user MORE history than their tier
    allows — the exact exposure the row describes — rather than less, which
    is why this case, not a paid-tier one, is the one that actually proves
    the fix: trial_trader and floor_manager both resolve to `None`
    (unlimited), so a paid-tier check alone can't tell the old default
    apart from a correct read.
    """
    user = _make_user()
    _set_plan(user.id, "floor_pass")
    store = JournalStore()
    _seed_old_and_new_entry(store, user.id)

    client = _client(user, store)
    r = client.get(f"/v1/journal/{user.id}")

    assert r.status_code == 200
    body = r.json()
    assert body["retention_days"] == 30, (
        "omitting `plan` must not fall back to trial_trader's unlimited "
        "retention for a Floor Pass user"
    )
    assert {e["title"] for e in body["entries"]} == {"new"}
