"""CR125 — mobile secure session (backend half).

Covers the acceptance criteria from
docs/forward_planning/CR125_mobile_secure_session/CR125_mobile_secure_session.md:

  - an expired or wrong-version token 401s at every guarded route
  - `DELETE /v1/auth/session` then reuse of the old token → 401
  - sign-out bumps `token_version` in the DB (real revocation, not a no-op)
  - a revoked/expired bearer no longer proves device-ownership on
    `/v1/auth/anon` (would otherwise re-mint a fresh valid token, undoing
    the sign-out — see the CR125 comment in `api/auth.py::anon_session`)
  - issue/parse round-trip carries the token_version through
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.api.mandate import router as mandate_router
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService, _scaffold_token


@pytest.fixture
def app() -> FastAPI:
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(mandate_router)
    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


def _current_version(user_id: UUID) -> int:
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one()
        return row.token_version


# ── expiry ──────────────────────────────────────────────────────────────


def test_token_accepted_before_expiry(client: TestClient):
    user_id, _ = _new_user()
    token = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=30)
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_token_rejected_after_expiry(client: TestClient):
    user_id, _ = _new_user()
    token = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=-1)
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_whoami_rejects_expired_token(client: TestClient):
    user_id, _ = _new_user()
    token = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=-1)
    r = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ── token_version revocation ───────────────────────────────────────────


def test_stale_token_version_returns_401(client: TestClient):
    """A token minted before a version bump (e.g. from another sign-in on
    the same account) 401s once the version has moved on."""
    user_id, token = _new_user()
    with get_session() as s:
        row = s.execute(select(User).where(User.id == user_id)).scalar_one()
        row.token_version += 1
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_sign_out_bumps_token_version_in_db(client: TestClient):
    user_id, token = _new_user()
    before = _current_version(user_id)
    r = client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"signed_out": True}
    assert _current_version(user_id) == before + 1


def test_sign_out_then_replay_old_bearer_returns_401(client: TestClient):
    user_id, token = _new_user()
    r = client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    replay = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert replay.status_code == 401


def test_sign_out_then_replay_on_guarded_route_returns_401(client: TestClient):
    """Same as above, exercised against a non-auth guarded route (mandate),
    proving the revocation isn't special-cased to the auth router."""
    user_id, token = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    r = client.get(f"/v1/mandate/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_sign_out_does_not_affect_other_users(client: TestClient):
    user_a, token_a = _new_user()
    user_b, token_b = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token_a}"})
    r = client.get(f"/v1/mandate/{user_b}", headers={"Authorization": f"Bearer {token_b}"})
    assert r.status_code == 200


def test_fresh_token_after_reauth_works_again(client: TestClient):
    """Sign out, then re-bootstrap (no bearer, as the client does after
    clearing its local copy) — the resulting fresh token is valid."""
    user_id, token = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    r = client.post("/v1/auth/anon", json={"device_user_id": None})
    assert r.status_code == 200
    new_token = r.json()["token"]
    check = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert check.status_code == 200


# ── revoked bearer must not re-prove device ownership on /v1/auth/anon ──


def test_revoked_token_no_longer_proves_ownership_on_anon(client: TestClient):
    """Before CR125's anon_session fix, a signed-out-but-not-yet-expired
    token still satisfied the `device_user_id == authenticated_user_id`
    trust check, so /v1/auth/anon would happily re-mint a brand-new valid
    token for the "revoked" user — silently undoing the sign-out. Now the
    revoked bearer proves nothing, so the call mints a fresh user instead of
    reusing the original."""
    user_id, token = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    returned_id = UUID(r.json()["user"]["id"])
    assert returned_id != user_id, "revoked bearer must not prove ownership"


def test_an_expired_token_still_proves_ownership_on_anon(client: TestClient):
    """Expiry bounds a session; it must not destroy an identity.

    This app is anonymous-first: most users hold no Apple/Google/email
    credential to sign back in with. `ensure_anonymous` reuses an existing
    row only when the caller proves possession of a token for that same user
    (audit finding A2). If an expired token proved nothing, then on day 31
    every anonymous user would be handed a brand-new user_id and their
    portfolio, journal, streaks and credits would be orphaned — with no
    error, the app simply looking new. Nothing about that is a security
    property; it is data loss on a timer.

    So `/v1/auth/anon` — and only `/v1/auth/anon` — accepts an expired
    token as proof of ownership. The signature and `token_version` are still
    enforced (see the two tests below), and the expired token still
    authenticates no ordinary request (`test_token_rejected_after_expiry`)."""
    user_id, _ = _new_user()
    expired = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=-1)
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {expired}"},
    )
    assert r.status_code == 200
    assert UUID(r.json()["user"]["id"]) == user_id, (
        "an anonymous user was handed a fresh identity when their token "
        "expired — their entire account is now orphaned"
    )
    assert r.json()["is_new"] is False


def test_an_expired_token_that_was_also_revoked_proves_nothing(client: TestClient):
    """The security leg. Relaxing `exp` on this one route must not weaken
    revocation: sign-out bumps `token_version`, and a token failing THAT
    check is still worthless here no matter how the expiry lands."""
    user_id, token = _new_user()
    client.delete("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    stale_version = _current_version(user_id) - 1
    expired_and_revoked = _scaffold_token(
        user_id, token_version=stale_version, ttl_days=-1,
    )
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {expired_and_revoked}"},
    )
    assert r.status_code == 200
    assert UUID(r.json()["user"]["id"]) != user_id


def test_a_forged_expired_token_proves_nothing(client: TestClient):
    """The other security leg. `allow_expired` skips ONLY the `exp` check —
    the HMAC is still required, so an attacker cannot hand-write a token for
    a user_id they do not own and claim their account."""
    victim_id, _ = _new_user()
    forged = f"scaffold:{victim_id.hex}:1:1:deadbeef"
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(victim_id)},
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert r.status_code == 200
    assert UUID(r.json()["user"]["id"]) != victim_id


def test_an_expired_token_still_authenticates_nothing_else(client: TestClient):
    """Non-vacuity for the whole relaxation: the flag is scoped to the
    re-bootstrap decision. If it leaked into ordinary auth, expiry would be
    decorative."""
    user_id, _ = _new_user()
    expired = _scaffold_token(user_id, token_version=_current_version(user_id), ttl_days=-1)
    headers = {"Authorization": f"Bearer {expired}"}
    assert client.get(f"/v1/mandate/{user_id}", headers=headers).status_code == 401
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


# ── issue/parse round trip carries the version ───────────────────────────


def test_issued_token_carries_current_version(client: TestClient):
    user_id, token = _new_user()
    from app.services.auth_service import parse_scaffold_token

    parsed = parse_scaffold_token(token)
    assert parsed is not None
    assert parsed.user_id == user_id
    assert parsed.token_version == _current_version(user_id) == 1


# ── the upgrade path: a PRE-CR125 token must still prove ownership ──────


def _legacy_token(user_id: UUID) -> str:
    """A token in the exact pre-CR125 shape: scaffold:<hex>:<sig>, HMAC over
    the hex id alone. This is what every installed device is holding on the
    day CR125 ships."""
    import hmac as _hmac

    from app.core.config import settings as _s

    sig = _hmac.new(
        _s.secret_key.encode("utf-8"), user_id.hex.encode("utf-8"), "sha256",
    ).hexdigest()
    return f"scaffold:{user_id.hex}:{sig}"


def test_a_pre_cr125_token_still_proves_ownership_on_anon(client: TestClient):
    """CR125 audit BLOCKER, and the one the 30-day fix did not cover.

    Every installed token is in the old format the day this ships. If the old
    format proves nothing, then on the FIRST call after the update every
    returning user looks like a brand-new install and gets a fresh identity —
    100% of the alpha cohort, on day zero, not day 31. The expiry fix does not
    help: the token never gets the chance to expire."""
    user_id, _ = _new_user()
    legacy = _legacy_token(user_id)

    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {legacy}"},
    )
    assert r.status_code == 200
    assert UUID(r.json()["user"]["id"]) == user_id, (
        "every existing account was orphaned by the token-format change itself"
    )
    assert r.json()["is_new"] is False


def test_a_pre_cr125_token_authenticates_nothing_else(client: TestClient):
    """The legacy format is ownership proof on ONE route, not a credential.
    It carries no version field, so it cannot be revoked — which is precisely
    why it must not authenticate anything."""
    user_id, _ = _new_user()
    headers = {"Authorization": f"Bearer {_legacy_token(user_id)}"}
    assert client.get(f"/v1/mandate/{user_id}", headers=headers).status_code == 401
    assert client.get("/v1/auth/me", headers=headers).status_code == 401


def test_a_forged_legacy_token_proves_nothing(client: TestClient):
    victim_id, _ = _new_user()
    forged = f"scaffold:{victim_id.hex}:deadbeef"
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(victim_id)},
        headers={"Authorization": f"Bearer {forged}"},
    )
    assert r.status_code == 200
    assert UUID(r.json()["user"]["id"]) != victim_id


def test_legacy_proof_stops_once_the_migration_window_closes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    """The widening is bounded. A legacy token cannot be revoked, so it must
    not be honoured forever — an empty/past window closes it."""
    from app.core.config import settings

    user_id, _ = _new_user()
    monkeypatch.setattr(settings, "auth_legacy_rebootstrap_until", "2020-01-01")
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {_legacy_token(user_id)}"},
    )
    assert UUID(r.json()["user"]["id"]) != user_id


def test_a_malformed_window_refuses_rather_than_accepting_forever(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    """CR040: a typo'd date must not silently mean "accept legacy forever"."""
    from app.core.config import settings

    user_id, _ = _new_user()
    monkeypatch.setattr(settings, "auth_legacy_rebootstrap_until", "not-a-date")
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {_legacy_token(user_id)}"},
    )
    assert UUID(r.json()["user"]["id"]) != user_id


def test_an_expired_token_past_the_grace_window_proves_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    """CR125 audit MAJOR. `allow_expired` never looked at `exp` at all, so a
    stolen expired token could resurrect its account forever — strictly worse
    than a stolen unexpired one, which dies on its own. Now bounded."""
    from app.core.config import settings

    user_id, _ = _new_user()
    monkeypatch.setattr(settings, "auth_rebootstrap_grace_days", 30)
    long_dead = _scaffold_token(
        user_id, token_version=_current_version(user_id), ttl_days=-400,
    )
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {long_dead}"},
    )
    assert UUID(r.json()["user"]["id"]) != user_id


def test_an_expired_token_inside_the_grace_window_still_proves_ownership(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    """The non-vacuity leg: a grace window that rejected everything would pass
    the test above and re-open the day-31 orphaning it exists to prevent."""
    from app.core.config import settings

    user_id, _ = _new_user()
    monkeypatch.setattr(settings, "auth_rebootstrap_grace_days", 180)
    recently_dead = _scaffold_token(
        user_id, token_version=_current_version(user_id), ttl_days=-5,
    )
    r = client.post(
        "/v1/auth/anon",
        json={"device_user_id": str(user_id)},
        headers={"Authorization": f"Bearer {recently_dead}"},
    )
    assert UUID(r.json()["user"]["id"]) == user_id
