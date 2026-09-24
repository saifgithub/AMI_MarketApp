"""DEF416 — apple_id/google_id concurrent first-sign-in race.

`sign_in_with_apple` / `sign_in_with_google` SELECT by the provider sub, find
nothing, and INSERT a fresh `User` row. Before this fix, `apple_id`/
`google_id` carried no DB constraint at all — the ISS001 dilemma's own
correction (`docs/dilemmas/ISS001_DB_INSERT_RACE/ISS001_problem_statement.md`
§3.1) found that two concurrent first-time sign-ins with the same OIDC `sub`
silently wrote two `User` rows, with no `IntegrityError` to even catch.

Migration `def416a0oidc0uq` adds `uq_users_apple_id` / `uq_users_google_id`
(partial, `WHERE ... IS NOT NULL`), and `auth_service.py` gets the same
begin_nested()/catch-IntegrityError/re-SELECT-and-return-the-winner recovery
DEF401 shipped for `bank_verdict_outcome` (`verdict_outcomes.py:286-312`).

Race reproduced deterministically, matching
`test_cr219_verdict_outcome_ledger.py::test_a_lost_bank_race_on_a_fresh_run_also_returns_the_winners_row`
and `test_def220_check_then_insert_outcomes.py`'s `_BlindOnce`: the winner's
row is committed through a separate, already-closed session first, then the
loser's own pre-check SELECT is blinded once so it takes the INSERT branch
and meets the real constraint — no threads, no flakiness.
"""

from __future__ import annotations

import base64
import contextlib
import json
from uuid import uuid4

from sqlalchemy import select

import app.services.auth_service as auth_mod
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService
from app.services.oidc_verifier import OIDCVerificationError


def _apple_jwt(sub: str, *, email: str | None = None) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"abc"}').rstrip(b"=").decode()
    payload: dict = {"sub": sub}
    if email is not None:
        payload["email"] = email
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


def _google_jwt(sub: str, *, email: str | None = None, email_verified: bool = True) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"abc"}').rstrip(b"=").decode()
    payload: dict = {"sub": sub, "email_verified": email_verified}
    if email is not None:
        payload["email"] = email
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    sig = base64.urlsafe_b64encode(b"sig").rstrip(b"=").decode()
    return f"{header}.{body}.{sig}"


class _FakeVerifier:
    """Body-only OIDC reader — no signature/iss/aud checks. Same double the
    existing Apple/Google auth tests use."""

    def verify(self, identity_token: str) -> dict:
        if not identity_token or identity_token.count(".") != 2:
            raise OIDCVerificationError("malformed identity token")
        try:
            _hdr, body, _sig = identity_token.split(".")
            padding = "=" * (-len(body) % 4)
            payload = json.loads(base64.urlsafe_b64decode(body + padding).decode())
        except Exception as e:
            raise OIDCVerificationError(f"undecodable body: {e}") from e
        return payload


class _BlindSelectOnce:
    """Session proxy that misses the FIRST SELECT against `users`, so a
    caller's own pre-check reads "no row" even though the winner already
    committed one — forcing the INSERT branch to run and meet the real
    UNIQUE constraint. Mirrors `test_cr219_verdict_outcome_ledger.py`'s
    `_BlindSelectOnce`.
    """

    def __init__(self, session):
        self._s = session
        self._blinded = False

    def execute(self, stmt, *a, **k):
        if not self._blinded and "users" in str(stmt) and "SELECT" in str(stmt):
            self._blinded = True

            class _Empty:
                def scalar_one_or_none(self):
                    return None

            return _Empty()
        return self._s.execute(stmt, *a, **k)

    def __getattr__(self, name):
        return getattr(self._s, name)


def _users_with(**kw) -> list[User]:
    with get_session() as s:
        stmt = select(User)
        for k, v in kw.items():
            stmt = stmt.where(getattr(User, k) == v)
        return list(s.execute(stmt).scalars())


def test_apple_sign_in_race_lands_one_user_row_both_callers_agree():
    """Two concurrent first-time Apple sign-ins with the same `sub`: the
    loser must not fork a second User row, and must return the winner's id
    rather than raising."""
    auth = AuthService(apple_verifier=_FakeVerifier())
    sub = "apple-sub-race-1"

    winner_uid = uuid4()
    with get_session() as s:  # the winner, committed before we run
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        s.add(User(
            id=winner_uid, apple_id=sub, email="race@example.com",
            is_anonymous=False, claimed_at=now, trial_started_at=now,
            trial_expires_at=now + timedelta(days=7),
        ))

    real_get_session = auth_mod.get_session

    @contextlib.contextmanager
    def _blinded_session():
        with real_get_session() as s:
            yield _BlindSelectOnce(s)

    orig = auth_mod.get_session
    auth_mod.get_session = _blinded_session
    try:
        user, _token, adopted = auth.sign_in_with_apple(
            identity_token=_apple_jwt(sub), user_id=uuid4(),
        )
    finally:
        auth_mod.get_session = orig

    assert user.id == winner_uid, "the loser must sign into the winner's account"
    assert adopted is None

    rows = _users_with(apple_id=sub)
    assert len(rows) == 1, f"expected exactly one row for apple_id={sub!r}, got {len(rows)}"
    assert rows[0].id == winner_uid


def test_google_sign_in_race_lands_one_user_row_both_callers_agree():
    """Mirrors the Apple case for `uq_users_google_id`."""
    auth = AuthService(google_verifier=_FakeVerifier())
    sub = "google-sub-race-1"

    winner_uid = uuid4()
    with get_session() as s:  # the winner, committed before we run
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        s.add(User(
            id=winner_uid, google_id=sub, email="race2@example.com",
            is_anonymous=False, claimed_at=now, trial_started_at=now,
            trial_expires_at=now + timedelta(days=7),
        ))

    real_get_session = auth_mod.get_session

    @contextlib.contextmanager
    def _blinded_session():
        with real_get_session() as s:
            yield _BlindSelectOnce(s)

    orig = auth_mod.get_session
    auth_mod.get_session = _blinded_session
    try:
        user, _token, adopted = auth.sign_in_with_google(
            identity_token=_google_jwt(sub), user_id=uuid4(),
        )
    finally:
        auth_mod.get_session = orig

    assert user.id == winner_uid, "the loser must sign into the winner's account"
    assert adopted is None

    rows = _users_with(google_id=sub)
    assert len(rows) == 1, f"expected exactly one row for google_id={sub!r}, got {len(rows)}"
    assert rows[0].id == winner_uid


def test_apple_id_unique_index_rejects_duplicate_outside_the_recovery_path():
    """Structural check that the constraint itself exists and holds, bypassing
    `auth_service` entirely — a direct INSERT of a second row with the same
    `apple_id` must fail, so the recovery path in `sign_in_with_apple` has
    something to catch."""
    import pytest
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    sub = "apple-sub-direct-dup"
    with get_session() as s:
        s.add(User(id=uuid4(), apple_id=sub))

    with pytest.raises(SAIntegrityError):
        with get_session() as s:
            s.add(User(id=uuid4(), apple_id=sub))


def test_google_id_unique_index_rejects_duplicate_outside_the_recovery_path():
    import pytest
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    sub = "google-sub-direct-dup"
    with get_session() as s:
        s.add(User(id=uuid4(), google_id=sub))

    with pytest.raises(SAIntegrityError):
        with get_session() as s:
            s.add(User(id=uuid4(), google_id=sub))


def test_multiple_users_with_null_apple_id_do_not_collide():
    """The partial index must not turn "never linked Apple" into a
    one-user-only state — NULL apple_id is the common case for every
    magic-link-only / anonymous user."""
    with get_session() as s:
        s.add(User(id=uuid4(), email="a1@example.com"))
        s.add(User(id=uuid4(), email="a2@example.com"))
    # No exception on commit above is the assertion — both rows have
    # apple_id NULL and must coexist.


def test_hms_unionid_unique_index_rejects_duplicate():
    """`hms_unionid` is unwritten today (no Huawei flow yet), but the
    migration closes it alongside apple_id/google_id — same column shape,
    same class of bug, don't leave it as the next instance."""
    import pytest
    from sqlalchemy.exc import IntegrityError as SAIntegrityError

    uid_val = "hms-union-dup"
    with get_session() as s:
        s.add(User(id=uuid4(), hms_unionid=uid_val))

    with pytest.raises(SAIntegrityError):
        with get_session() as s:
            s.add(User(id=uuid4(), hms_unionid=uid_val))
