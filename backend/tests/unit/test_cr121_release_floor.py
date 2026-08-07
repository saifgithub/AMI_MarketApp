"""CR121 — client version gate: floor resolution, the unauthenticated read
endpoint, and server-side 426 enforcement (VersionGateMiddleware).

Admin write-path tests (footgun guard + force override) live in
test_cr121_admin_release_floor.py.
"""

from __future__ import annotations

from uuid import uuid4

import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_session
from app.db.models import ClientReleaseFloorRow
from app.middleware.version_gate import EXEMPT_PATHS, VersionGateMiddleware
from app.services.client_release_floor import (
    build_release_floor_response,
    get_active_floor,
    parse_build_number,
    resolve_action,
    resolve_body,
    resolve_store_url,
)


def _make_floor(
    *,
    min_build: int = 1,
    recommended_build: int | None = None,
    active: bool = True,
    body_ar: str | None = None,
    body_ms: str | None = None,
    headline: str = "Update required",
    body_en: str = "This build is no longer supported.",
) -> ClientReleaseFloorRow:
    with get_session() as s:
        row = ClientReleaseFloorRow(
            id=uuid4(),
            min_build=min_build,
            recommended_build=recommended_build,
            headline=headline,
            body_en=body_en,
            body_ar=body_ar,
            body_ms=body_ms,
            active=active,
        )
        s.add(row)
        s.flush()
        s.refresh(row)
        # Detach a plain snapshot so the caller can read attributes after
        # the session closes (expire_on_commit=False makes this safe, but
        # be explicit about why).
        return row


# ── parse_build_number ───────────────────────────────────────────────────────

def test_parse_build_number_reads_the_pubspec_suffix():
    assert parse_build_number("0.1.0+69") == 69


def test_parse_build_number_accepts_a_bare_integer_string():
    assert parse_build_number("69") == 69


def test_parse_build_number_returns_none_for_missing_or_malformed():
    assert parse_build_number(None) is None
    assert parse_build_number("") is None
    assert parse_build_number("0.1.0") is None
    assert parse_build_number("not-a-version") is None


# ── floor resolution ──────────────────────────────────────────────────────────

def test_empty_table_means_no_floor_and_action_ok():
    with get_session() as s:
        assert get_active_floor(s) is None
    assert resolve_action(build=1, floor=None) == "ok"


def test_highest_active_min_build_wins():
    _make_floor(min_build=50)
    _make_floor(min_build=70)
    _make_floor(min_build=60)
    with get_session() as s:
        active = get_active_floor(s)
        assert active is not None
        assert active.min_build == 70


def test_retracted_row_is_skipped_and_the_previous_floor_governs():
    """Acceptance #6: active=false on the top row restores the previous
    floor. Proved by test, not by convention — the append-only history is
    still queryable (both rows still exist)."""
    _make_floor(min_build=50)
    _make_floor(min_build=90, active=False)
    with get_session() as s:
        active = get_active_floor(s)
        assert active is not None
        assert active.min_build == 50
        # The retracted row is still there — this is a log, not a delete.
        all_rows = s.query(ClientReleaseFloorRow).all()
        assert {r.min_build for r in all_rows} == {50, 90}


def test_resolve_action_below_min_build_blocks():
    floor = _make_floor(min_build=60, recommended_build=65)
    assert resolve_action(59, floor) == "block"


def test_resolve_action_at_min_build_does_not_block():
    floor = _make_floor(min_build=60, recommended_build=65)
    assert resolve_action(60, floor) != "block"


def test_resolve_action_between_min_and_recommended_is_nag():
    floor = _make_floor(min_build=60, recommended_build=65)
    assert resolve_action(62, floor) == "nag"


def test_resolve_action_at_or_above_recommended_is_ok():
    floor = _make_floor(min_build=60, recommended_build=65)
    assert resolve_action(65, floor) == "ok"
    assert resolve_action(99, floor) == "ok"


def test_resolve_action_with_no_recommended_build_is_ok_once_at_floor():
    floor = _make_floor(min_build=60, recommended_build=None)
    assert resolve_action(60, floor) == "ok"


def test_resolve_action_with_unknown_build_never_blocks():
    """A legacy client that predates this CR sends no X-App-Version at all
    — `build` resolves to None. It must never be blocked; the CR's own
    sequencing note is that pre-gate builds are permanently ungateable."""
    floor = _make_floor(min_build=999)
    assert resolve_action(None, floor) == "ok"


# ── locale resolution ─────────────────────────────────────────────────────────

def test_locale_resolves_to_the_matching_translation():
    floor = _make_floor(body_en="EN body", body_ar="AR body", body_ms="MS body")
    assert resolve_body(floor, "ar") == "AR body"
    assert resolve_body(floor, "ms") == "MS body"
    assert resolve_body(floor, "en") == "EN body"


def test_locale_falls_back_to_english_when_translation_is_null():
    floor = _make_floor(body_en="EN body", body_ar=None, body_ms=None)
    assert resolve_body(floor, "ar") == "EN body"
    assert resolve_body(floor, "ms") == "EN body"


def test_unknown_locale_falls_back_to_english():
    floor = _make_floor(body_en="EN body", body_ar="AR body")
    assert resolve_body(floor, "fr") == "EN body"
    assert resolve_body(floor, None) == "EN body"


# ── store URL ─────────────────────────────────────────────────────────────────

def test_android_store_url_is_the_play_store_constant():
    url = resolve_store_url("android")
    assert url.startswith("https://play.google.com/store/apps/details")
    assert "ai.agenticmarketintel.ami_trade" in url


def test_ios_store_url_falls_back_and_logs_when_unconfigured(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "ios_testflight_join_url", "")
    with structlog.testing.capture_logs() as captured:
        url = resolve_store_url("ios")
    assert url == "https://testflight.apple.com/"
    assert any(
        e["event"] == "release_floor_ios_store_url_unconfigured" for e in captured
    )


def test_ios_store_url_uses_the_configured_join_link(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "ios_testflight_join_url", "https://testflight.apple.com/join/ABC123"
    )
    assert resolve_store_url("ios") == "https://testflight.apple.com/join/ABC123"


def test_build_release_floor_response_with_no_floor_is_ok_and_bare():
    with get_session() as s:
        resp = build_release_floor_response(s, build=1, locale="en", platform="ios")
    assert resp.action == "ok"
    assert resp.min_build is None
    assert resp.headline is None


# ── GET /v1/client/release-floor — unauthenticated read endpoint ──────────────

def test_a_negative_or_unparseable_build_is_refused_at_the_boundary():
    """CR121 audit MINOR. Round 1 claimed every degenerate `build` resolves to
    `ok`, never `block`. True for the header path — `parse_build_number` never
    raises and never returns a negative — but the read endpoint took a bare
    `int | None` query param that never went through it, so `?build=` garbage
    produced a 422 (a third outcome the claim didn't name) and, against a
    hand-written `min_build=0` row, `?build=-5` resolved to `block`.

    Neither is reachable by a real client (`DeviceContext.buildNumber` is
    `int?` in Dart; the admin write path is `Field(gt=0)`), so nothing was ever
    at risk. Pinned anyway: `ge=0` is one character, and "unreachable today"
    is a property of the callers, not of this endpoint."""
    from app.main import app

    client = TestClient(app)
    assert client.get("/v1/client/release-floor?build=not-a-number").status_code == 422
    assert client.get("/v1/client/release-floor?build=-5").status_code == 422
    # The legitimate shapes still work, including the omitted param.
    assert client.get("/v1/client/release-floor").status_code == 200
    assert client.get("/v1/client/release-floor?build=0").status_code == 200


def test_read_endpoint_is_reachable_with_no_authorization_header():
    from app.main import app

    client = TestClient(app)
    r = client.get("/v1/client/release-floor", params={"build": 1})
    assert r.status_code == 200
    assert r.json()["action"] == "ok"


def test_read_endpoint_returns_block_below_the_floor():
    _make_floor(min_build=500, headline="Please update", body_en="Old build.")
    from app.main import app

    client = TestClient(app)
    r = client.get("/v1/client/release-floor", params={"build": 1, "locale": "en"})
    assert r.status_code == 200
    body = r.json()
    assert body["action"] == "block"
    assert body["headline"] == "Please update"
    assert body["body"] == "Old build."


def test_read_endpoint_returns_ok_at_or_above_the_floor():
    _make_floor(min_build=500)
    from app.main import app

    client = TestClient(app)
    r = client.get("/v1/client/release-floor", params={"build": 500})
    assert r.json()["action"] == "ok"


# ── VersionGateMiddleware — 426 server-side enforcement ────────────────────────

def _gated_app() -> FastAPI:
    """A tiny app wired exactly like main.py's exempt-path contract: three
    dummy handlers at the real exempt paths, plus one ordinary protected
    route, all behind VersionGateMiddleware."""
    app = FastAPI()
    app.add_middleware(VersionGateMiddleware)

    @app.get("/v1/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/client/release-floor")
    def floor():
        return {"action": "ok"}

    @app.post("/v1/feedback/bug")
    def feedback():
        return {"ok": True}

    @app.get("/v1/sim/portfolio/x")
    def protected():
        return {"ok": True}

    return app


def test_426_fires_below_the_floor_on_a_non_exempt_route():
    _make_floor(min_build=100, headline="Update now", body_en="Below floor.")
    client = TestClient(_gated_app())
    r = client.get("/v1/sim/portfolio/x", headers={"X-App-Version": "0.1.0+50"})
    assert r.status_code == 426
    assert r.json()["detail"]["action"] == "block"
    assert r.json()["detail"]["headline"] == "Update now"


def test_a_block_is_logged_with_the_numbers_an_operator_needs():
    """CR121 audit MAJOR. `VersionGateMiddleware` sits OUTSIDE
    `HTTPAuditMiddleware`, so a 426 short-circuits before the audit log ever
    sees it. Without this event, raising the floor produces no signal
    anywhere about how many clients it just cut off — and the fix for that
    was itself unpinned, so deleting the six-line `logger.warning` block left
    all 2654 tests green. That is DEF038/DEF063's shape recurring one layer
    up: a fix for a silent failure, silently removable.

    Asserts the fields, not just the event name — an operator needs to know
    WHICH build got blocked by WHICH floor, and an event that fired with the
    wrong numbers would be no more useful than no event."""
    _make_floor(min_build=100, headline="Update now", body_en="Below floor.")
    client = TestClient(_gated_app())

    with structlog.testing.capture_logs() as captured:
        r = client.get("/v1/sim/portfolio/x", headers={"X-App-Version": "0.1.0+50"})

    assert r.status_code == 426
    blocked = [e for e in captured if e["event"] == "version_gate_blocked_request"]
    assert len(blocked) == 1, captured
    assert blocked[0]["path"] == "/v1/sim/portfolio/x"
    assert blocked[0]["client_build"] == 50
    assert blocked[0]["min_build"] == 100


def test_an_allowed_request_logs_no_block_event():
    """The other half: an event that fired on every request would be noise an
    operator learns to ignore, which is the same outcome as no event."""
    _make_floor(min_build=100)
    client = TestClient(_gated_app())

    with structlog.testing.capture_logs() as captured:
        r = client.get("/v1/sim/portfolio/x", headers={"X-App-Version": "0.1.0+100"})

    assert r.status_code == 200
    assert not [e for e in captured if e["event"] == "version_gate_blocked_request"]


def test_no_426_at_or_above_the_floor():
    _make_floor(min_build=100)
    client = TestClient(_gated_app())
    r = client.get("/v1/sim/portfolio/x", headers={"X-App-Version": "0.1.0+100"})
    assert r.status_code == 200
    r2 = client.get("/v1/sim/portfolio/x", headers={"X-App-Version": "0.1.0+9999"})
    assert r2.status_code == 200


def test_no_426_when_no_version_header_present():
    _make_floor(min_build=100)
    client = TestClient(_gated_app())
    r = client.get("/v1/sim/portfolio/x")
    assert r.status_code == 200


def test_exempt_routes_still_answer_below_the_floor():
    _make_floor(min_build=100)
    client = TestClient(_gated_app())
    headers = {"X-App-Version": "0.1.0+1"}
    assert client.get("/v1/health", headers=headers).status_code == 200
    assert client.get("/v1/client/release-floor", headers=headers).status_code == 200
    assert client.post("/v1/feedback/bug", headers=headers).status_code == 200


def test_exempt_paths_set_matches_the_documented_three():
    assert EXEMPT_PATHS == {
        "/v1/health",
        "/v1/client/release-floor",
        "/v1/feedback/bug",
    }


# ── fails open ──────────────────────────────────────────────────────────────

def test_middleware_fails_open_when_the_floor_lookup_raises(monkeypatch):
    """If the DB lookup inside the middleware blows up, the request must
    still proceed — never a 5xx storm across the whole app because one
    lookup failed — and the failure must be logged, not swallowed."""
    _make_floor(min_build=100)

    def _boom(_session):
        raise RuntimeError("db unreachable")

    monkeypatch.setattr(
        "app.middleware.version_gate.get_active_floor", _boom,
    )

    client = TestClient(_gated_app())
    with structlog.testing.capture_logs() as captured:
        r = client.get("/v1/sim/portfolio/x", headers={"X-App-Version": "0.1.0+1"})

    assert r.status_code == 200
    assert any(
        e["event"] == "version_gate_middleware_check_failed" for e in captured
    )
