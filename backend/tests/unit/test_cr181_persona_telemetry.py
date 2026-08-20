"""CR181 — persona telemetry: the four segments, actually measured.

What must hold, per the CR doc's own fences:
  - segments are deterministic predicates over recorded events (CR038) —
    every boundary of bounce/convene/depth/locale is pinned here;
  - ingest is idempotent per (user_id, event_id): a replayed batch inserts
    nothing and says so (`duplicates`), never silently absorbs (CR040);
  - user_id comes from the token only — a payload cannot write, or be
    counted, under another user;
  - a client-side drop is countable (`client_drop` marker rows), and the
    marker itself never reads as engagement;
  - the §2 answering query (segment counts over a window) ships here, with
    [since, until) window edges pinned;
  - retention (400 days) is enforced on the ingest path itself.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.telemetry import router as telemetry_router
from app.core.config import settings
from app.db import get_session
from app.db.models import PersonaEventRow, User
from app.schemas.telemetry import TELEMETRY_EVENT_TYPES
from app.services import persona_telemetry
from app.services.auth_service import _scaffold_token
from app.services.persona_telemetry import (
    PersonaSegments,
    _segments_from_rows,
    derive_segments,
    segment_counts,
)

_T0 = datetime(2026, 8, 1, 12, 0, 0, tzinfo=timezone.utc)
_SINCE = datetime(2026, 8, 1, 0, 0, 0, tzinfo=timezone.utc)
_UNTIL = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
_ADMIN_SECRET = "test-admin-secret-cr181"


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(telemetry_router)
    return TestClient(app)


@pytest.fixture
def admin_headers(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.setattr(settings, "admin_secret", _ADMIN_SECRET)
    return {"Authorization": f"Bearer {_ADMIN_SECRET}"}


def _auth(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {_scaffold_token(user_id, token_version=1)}"}


def _make_user() -> UUID:
    uid = uuid4()
    with get_session() as s:
        s.add(User(id=uid, device_model="iPhone18,1", last_app_version="0.1.0+54"))
    return uid


def _event(
    event_type: str,
    minute: int = 0,
    locale: str | None = None,
    count: int = 1,
    event_id: UUID | None = None,
) -> dict:
    return {
        "event_id": str(event_id or uuid4()),
        "event_type": event_type,
        "occurred_at": (_T0 + timedelta(minutes=minute)).isoformat(),
        "locale": locale,
        "count": count,
    }


def _post(client: TestClient, uid: UUID, events: list[dict]):
    return client.post(
        "/v1/telemetry/events", json={"events": events}, headers=_auth(uid)
    )


def _row_count(uid: UUID) -> int:
    with get_session() as s:
        return (
            s.query(PersonaEventRow)
            .filter(PersonaEventRow.user_id == uid)
            .count()
        )


# ── Segment predicates — every boundary of the four segments ─────────────────


def test_only_app_open_is_bounce() -> None:
    seg = _segments_from_rows([("app_open", None)])
    assert seg == PersonaSegments(bounce=True, convene=False, depth=False, locale=None)


def test_convene_kills_bounce() -> None:
    seg = _segments_from_rows([("app_open", None), ("room_convene", None)])
    assert seg.bounce is False
    assert seg.convene is True
    assert seg.depth is False


def test_convene_without_app_open_is_not_bounce() -> None:
    seg = _segments_from_rows([("room_convene", None)])
    assert seg.bounce is False
    assert seg.convene is True


def test_no_events_is_nothing() -> None:
    seg = _segments_from_rows([])
    assert seg == PersonaSegments(bounce=False, convene=False, depth=False, locale=None)


@pytest.mark.parametrize("depth_type", ["one_on_one_open", "firm_open", "lesson_open"])
def test_each_depth_type_sets_depth_and_kills_bounce(depth_type: str) -> None:
    seg = _segments_from_rows([("app_open", None), (depth_type, None)])
    assert seg.depth is True
    assert seg.bounce is False
    assert seg.convene is False


@pytest.mark.parametrize("core_type", ["trade_place", "challenge_attempt", "brief_edit"])
def test_non_depth_core_actions_kill_bounce_without_depth(core_type: str) -> None:
    seg = _segments_from_rows([("app_open", None), (core_type, None)])
    assert seg.bounce is False
    assert seg.depth is False
    assert seg.convene is False


def test_client_drop_is_not_engagement() -> None:
    seg = _segments_from_rows([("app_open", None), ("client_drop", None)])
    assert seg.bounce is True
    assert seg.depth is False
    assert seg.convene is False


def test_locale_latest_nonnull_wins() -> None:
    seg = _segments_from_rows([
        ("app_open", "en"),
        ("lesson_open", "ar"),
        ("app_open", None),
    ])
    assert seg.locale == "ar"


# ── Ingest: idempotency, isolation, vocabulary, auth ─────────────────────────


def test_ingest_accepts_batch(client: TestClient) -> None:
    uid = _make_user()
    r = _post(client, uid, [
        _event("app_open", 0, locale="en"),
        _event("room_convene", 5),
        _event("lesson_open", 9),
    ])
    assert r.status_code == 200
    assert r.json() == {"accepted": 3, "duplicates": 0}
    assert _row_count(uid) == 3


def test_replayed_batch_is_noop_and_says_so(client: TestClient) -> None:
    uid = _make_user()
    batch = [_event("app_open", 0), _event("room_convene", 5)]
    assert _post(client, uid, batch).json() == {"accepted": 2, "duplicates": 0}
    assert _post(client, uid, batch).json() == {"accepted": 0, "duplicates": 2}
    assert _row_count(uid) == 2
    seg = derive_segments(uid, _SINCE, _UNTIL)
    assert seg.convene is True and seg.bounce is False


def test_partial_overlap_inserts_only_the_new(client: TestClient) -> None:
    uid = _make_user()
    old = [_event("app_open", 0), _event("lesson_open", 3)]
    _post(client, uid, old)
    r = _post(client, uid, old + [_event("trade_place", 7)])
    assert r.json() == {"accepted": 1, "duplicates": 2}
    assert _row_count(uid) == 3


def test_same_event_id_twice_in_one_batch_dedupes(client: TestClient) -> None:
    uid = _make_user()
    eid = uuid4()
    r = _post(client, uid, [
        _event("app_open", 0, event_id=eid),
        _event("app_open", 1, event_id=eid),
    ])
    assert r.json() == {"accepted": 1, "duplicates": 1}
    assert _row_count(uid) == 1


def test_unknown_event_type_is_422_and_names_the_vocabulary(
    client: TestClient,
) -> None:
    uid = _make_user()
    r = _post(client, uid, [_event("mystery_tap", 0)])
    assert r.status_code == 422
    detail = str(r.json())
    assert "mystery_tap" in detail
    for t in TELEMETRY_EVENT_TYPES:
        assert t in detail


def test_missing_token_is_401(client: TestClient) -> None:
    r = client.post(
        "/v1/telemetry/events", json={"events": [_event("app_open", 0)]}
    )
    assert r.status_code == 401


def test_payload_user_id_is_ignored_rows_land_under_token_user(
    client: TestClient,
) -> None:
    me = _make_user()
    victim = _make_user()
    ev = _event("room_convene", 0)
    ev["user_id"] = str(victim)
    r = client.post(
        "/v1/telemetry/events",
        json={"events": [ev], "user_id": str(victim)},
        headers=_auth(me),
    )
    assert r.status_code == 200
    assert _row_count(me) == 1
    assert _row_count(victim) == 0


def test_cross_user_isolation_in_derivation(client: TestClient) -> None:
    convener = _make_user()
    bouncer = _make_user()
    _post(client, convener, [_event("app_open", 0), _event("room_convene", 1)])
    _post(client, bouncer, [_event("app_open", 0)])

    assert derive_segments(convener, _SINCE, _UNTIL).convene is True
    b = derive_segments(bouncer, _SINCE, _UNTIL)
    assert b.convene is False
    assert b.bounce is True

    # The same event_id under two users lands twice — the constraint is
    # per user, so one client can never burn another user's ids.
    shared = uuid4()
    assert _post(client, convener, [_event("lesson_open", 2, event_id=shared)]).json()["accepted"] == 1
    assert _post(client, bouncer, [_event("lesson_open", 2, event_id=shared)]).json()["accepted"] == 1


# ── The answering query: counts, drops, window edges, admin gate ─────────────


def test_segment_counts_cohorts(client: TestClient) -> None:
    bouncer = _make_user()
    convener = _make_user()
    depth_user = _make_user()
    _post(client, bouncer, [_event("app_open", 0, locale="en")])
    _post(client, convener, [
        _event("app_open", 0, locale="ar"),
        _event("room_convene", 5, locale="ar"),
    ])
    _post(client, depth_user, [
        _event("app_open", 0, locale="en"),
        _event("firm_open", 2, locale="ms"),
    ])

    counts = segment_counts(_SINCE, _UNTIL)
    assert counts["users"] == 3
    assert counts["bounce"] == 1
    assert counts["convene"] == 1
    assert counts["depth"] == 1
    assert counts["locales"] == {"en": 1, "ar": 1, "ms": 1}
    assert counts["dropped_events"] == 0


def test_dropped_events_are_countable(client: TestClient) -> None:
    uid = _make_user()
    _post(client, uid, [
        _event("app_open", 0),
        _event("client_drop", 1, count=7),
        _event("client_drop", 2, count=2),
    ])
    counts = segment_counts(_SINCE, _UNTIL)
    assert counts["dropped_events"] == 9
    assert counts["bounce"] == 1  # drop markers never read as engagement


def test_window_is_half_open(client: TestClient) -> None:
    uid = _make_user()
    at_since = {**_event("room_convene"), "occurred_at": _SINCE.isoformat()}
    at_until = {**_event("firm_open"), "occurred_at": _UNTIL.isoformat()}
    _post(client, uid, [at_since, at_until])

    counts = segment_counts(_SINCE, _UNTIL)
    assert counts["users"] == 1
    assert counts["convene"] == 1
    assert counts["depth"] == 0  # the firm_open at `until` is OUT of this window

    seg = derive_segments(uid, _SINCE, _UNTIL)
    assert seg.convene is True   # event exactly at `since` is IN
    assert seg.depth is False    # event exactly at `until` is OUT

    later = segment_counts(_UNTIL, _UNTIL + timedelta(days=30))
    assert later["users"] == 1   # event at `until` belongs to the NEXT window
    assert later["depth"] == 1
    assert later["convene"] == 0  # the at-`since` event stayed in window one


def test_segments_route_is_admin_gated(
    client: TestClient, admin_headers: dict[str, str],
) -> None:
    uid = _make_user()
    _post(client, uid, [_event("app_open", 0, locale="en")])

    window = {"since": _SINCE.isoformat(), "until": _UNTIL.isoformat()}
    assert client.get("/v1/telemetry/segments", params=window).status_code == 403
    assert (
        client.get(
            "/v1/telemetry/segments", params=window, headers=_auth(uid)
        ).status_code
        == 403
    )

    r = client.get("/v1/telemetry/segments", params=window, headers=admin_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["users"] == 1
    assert body["bounce"] == 1

    bad = client.get(
        "/v1/telemetry/segments",
        params={"since": _UNTIL.isoformat(), "until": _SINCE.isoformat()},
        headers=admin_headers,
    )
    assert bad.status_code == 422


# ── Retention rides the ingest path ──────────────────────────────────────────


def test_retention_sweeps_only_this_users_expired_rows(client: TestClient) -> None:
    uid = _make_user()
    other = _make_user()
    ancient = datetime.now(timezone.utc) - timedelta(
        days=persona_telemetry.RETENTION_DAYS + 5
    )
    with get_session() as s:
        for owner in (uid, other):
            s.add(PersonaEventRow(
                user_id=owner, event_id=uuid4(), event_type="app_open",
                occurred_at=ancient, count=1,
            ))
    assert _row_count(uid) == 1 and _row_count(other) == 1

    _post(client, uid, [_event("room_convene", 0)])
    assert _row_count(uid) == 1        # expired row swept, fresh row kept
    assert _row_count(other) == 1      # another user's rows are not mine to sweep
    with get_session() as s:
        kept = s.query(PersonaEventRow).filter(
            PersonaEventRow.user_id == uid
        ).one()
        assert kept.event_type == "room_convene"
