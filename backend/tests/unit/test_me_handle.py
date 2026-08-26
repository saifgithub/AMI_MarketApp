"""CR109 slice 7 — `PATCH /v1/me/handle`, re-homed from `/v1/league/handle`.

The league routes are gone with the reputation league Amendment A retired.
**This one is not, and the distinction is the whole point of the test file
existing separately.** The handle is the player's public name: `games_board.py`
renders `User.handle` on the NEW game's leaderboard and sorts the field by it,
so deleting the only way to change it would have removed a live capability from
the feature CR109 was built to ship — on the strength of the URL prefix it
happened to sit under, not on anything about what it does.

`test_regenerate_handle_once_then_409` below is `test_league_routes.py`'s test,
moved rather than rewritten. The once-ever rule is `users.handle_regenerated_at`
and predates the move; it must survive it.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.me import router as me_router
from app.db import get_session
from app.db.models import User
from app.services.auth_service import AuthService


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(me_router)
    return TestClient(app, raise_server_exceptions=False)


def _make_user_and_token():
    auth = AuthService()
    au, token, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        user = s.execute(select(User).where(User.id == au.id)).scalar_one()
        user.handle = f"Test Handle {str(au.id)[:8]}"
    return au.id, token


def test_regenerate_handle_once_then_409(client: TestClient):
    _, token = _make_user_and_token()
    r1 = client.patch(
        "/v1/me/handle", headers={"Authorization": f"Bearer {token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["handle"]
    r2 = client.patch(
        "/v1/me/handle", headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 409
    assert r2.json()["detail"] == "already_regenerated"


def test_the_new_handle_is_what_the_game_board_would_render(client: TestClient):
    """The reason this route survived, asserted rather than argued.

    `games_board.py` reads `User.handle` straight off the row. A regeneration
    that returned a new string without persisting it would satisfy the test
    above and leave the leaderboard showing the old name forever.
    """
    user_id, token = _make_user_and_token()
    before = client.patch(
        "/v1/me/handle", headers={"Authorization": f"Bearer {token}"},
    ).json()["handle"]
    with get_session() as s:
        stored = s.execute(select(User).where(User.id == user_id)).scalar_one()
        assert stored.handle == before


def test_the_route_requires_auth(client: TestClient):
    assert client.patch("/v1/me/handle").status_code == 401


def test_get_me_returns_the_handle_the_patch_writes():
    """The read and the write must agree, which is the only reason `GET /v1/me`
    exists — Settings renders the name that `PATCH /v1/me/handle` changes."""
    app = FastAPI()
    app.include_router(me_router)
    c = TestClient(app, raise_server_exceptions=False)
    _, token = _make_user_and_token()
    h = {"Authorization": f"Bearer {token}"}
    before = c.get("/v1/me", headers=h).json()["handle"]
    patched = c.patch("/v1/me/handle", headers=h).json()["handle"]
    after = c.get("/v1/me", headers=h).json()["handle"]
    assert patched != before, "regeneration must actually change the name"
    assert after == patched, "the read must reflect the write"


def test_get_me_requires_auth():
    app = FastAPI()
    app.include_router(me_router)
    assert TestClient(app, raise_server_exceptions=False).get(
        "/v1/me",
    ).status_code == 401


def test_the_legacy_league_path_still_works_for_installed_clients():
    """Amendment M's lesson applied to this move instead of re-learned.

    The backend ships by rsync today; the Flutter half calling `/v1/me/handle`
    ships through store review days later. Every installed build in between
    calls `PATCH /v1/league/handle`. Its READS are covered — `_nullOn404` makes
    a removed league read as "nothing to show" — but the regenerate button is
    not: a 404 lands in its generic catch and tells the user their handle could
    not be changed. So the old path is an alias for exactly one release.

    Delete this test with the alias, once the floor is past a build carrying
    `/v1/me/handle`.
    """
    from app.api.me import legacy_handle_router

    app = FastAPI()
    app.include_router(me_router)
    app.include_router(legacy_handle_router)
    c = TestClient(app, raise_server_exceptions=False)
    user_id, token = _make_user_and_token()
    h = {"Authorization": f"Bearer {token}"}

    r = c.patch("/v1/league/handle", headers=h)
    assert r.status_code == 200
    assert c.get("/v1/me", headers=h).json()["handle"] == r.json()["handle"], (
        "the alias must write the same row the new path reads"
    )


def test_the_alias_shares_the_once_ever_rule_it_does_not_reset_it():
    """Two paths, one budget. If the alias had its own counter a client could
    regenerate twice by calling both — the once-ever rule is
    `users.handle_regenerated_at`, and it belongs to the user, not the URL."""
    from app.api.me import legacy_handle_router

    app = FastAPI()
    app.include_router(me_router)
    app.include_router(legacy_handle_router)
    c = TestClient(app, raise_server_exceptions=False)
    _, token = _make_user_and_token()
    h = {"Authorization": f"Bearer {token}"}

    assert c.patch("/v1/league/handle", headers=h).status_code == 200
    assert c.patch("/v1/me/handle", headers=h).status_code == 409

    # BOTH orders. One direction alone is not the guarantee: a legacy handler
    # that resets the budget on its own path passes the sequence above (its
    # reset happens before its own 200, and the /v1/me call is still refused)
    # and fails only when the alias is the SECOND call. Found by the mutation,
    # not by reading.
    _, token2 = _make_user_and_token()
    h2 = {"Authorization": f"Bearer {token2}"}
    assert c.patch("/v1/me/handle", headers=h2).status_code == 200
    assert c.patch("/v1/league/handle", headers=h2).status_code == 409
