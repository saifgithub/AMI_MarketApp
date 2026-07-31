"""CR128 — ticker existence validation + closest-match suggestion.

None of the three ticker-entry points (Convene the Room, Start Trade, Add to
Watchlist) validated that a typed ticker actually existed. Verified before
building this: the trade path fabricates a mock quote for any string via
`MockWalkProvider`, and Room convene charges credits + paid feed quota before
any agent speaks — a garbage ticker ran a full fake debate and spent real
money on nothing.

Covers the service layer (parsing, refresh idempotency/soft-delete,
lookup/suggest) against real NASDAQ Trader sample data, the new
`GET /v1/tickers/validate` endpoint, and the server-side guard now inside all
three action endpoints — including the Room acceptance criterion that a
rejected ticker spends zero credits and never reaches `start_run`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.room import get_room_runner
from app.api.room import router as room_router
from app.api.sim import router as sim_router
from app.api.tickers import router as tickers_router
from app.api.watchlist import router as watchlist_router
from app.db import get_session
from app.db.models import TickerReferenceRow
from app.services.auth_service import AuthService
from app.services.credit_service import balance_for
from app.services.watchlist_store import get_watchlist_store
from app.services.ticker_reference import (
    TickerNotFoundError,
    TickerReferenceSourceError,
    parse_nasdaq_listed,
    parse_nasdaq_other,
    require_ticker_exists,
    run_ticker_reference_refresh_tick,
    suggest_closest,
    upsert_reference,
)

# ── Fixture data — a tiny slice of the real files, same column shapes as the
# live NASDAQ Trader pull verified 2026-07-31 ────────────────────────────────

_LISTED_SAMPLE = (
    "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
    "Round Lot Size|ETF|NextShares\n"
    "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
    "MSFT|Microsoft Corporation - Common Stock|Q|N|N|100|N|N\n"
    "ZWZZT|Test Company Symbol|G|Y|N|100|N|N\n"
    "File Creation Time: 0731202603:03|||||||\n"
)

_OTHER_SAMPLE = (
    "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
    "Test Issue|NASDAQ Symbol\n"
    "A|Agilent Technologies, Inc. Common Stock|N|A|N|100|N|A\n"
    "AAA|Alternative Access First Priority CLO Bond ETF|P|AAA|Y|100|N|AAA\n"
    "ZXIET|IEX Test Symbol|V|ZXIET|N|100|Y|ZXIET\n"
    "File Creation Time: 0731202603:03||||||\n"
)


def _fake_fetch() -> list[dict]:
    return parse_nasdaq_listed(_LISTED_SAMPLE) + parse_nasdaq_other(_OTHER_SAMPLE)


# ── Parsing ───────────────────────────────────────────────────────────────


def test_parse_nasdaq_listed_drops_test_issues():
    records = parse_nasdaq_listed(_LISTED_SAMPLE)
    symbols = {r["symbol"] for r in records}
    assert symbols == {"AAPL", "MSFT"}
    assert "ZWZZT" not in symbols  # Test Issue = Y


def test_parse_nasdaq_other_maps_exchange_codes_and_drops_test_issues():
    records = {r["symbol"]: r for r in parse_nasdaq_other(_OTHER_SAMPLE)}
    assert set(records) == {"A", "AAA"}
    assert records["A"]["exchange"] == "NYSE"
    assert records["AAA"]["exchange"] == "NYSE Arca"
    assert records["AAA"]["is_etf"] is True


def test_parse_nasdaq_listed_raises_on_missing_columns():
    with pytest.raises(TickerReferenceSourceError):
        parse_nasdaq_listed("Symbol|Security Name\nAAPL|Apple\n")


# ── Refresh: idempotency + soft-delete ──────────────────────────────────────


def test_refresh_stores_then_skips_fresh_then_reruns_on_force():
    now = datetime.now(timezone.utc)
    # conftest's autouse fixture already seeded a "just refreshed" table (the
    # common test tickers, `last_seen_at=now`) — force=True here proves the
    # fetch + upsert genuinely ran and overwrote it with this test's own data,
    # rather than the assertion passing by accident of the pre-seed.
    assert (
        run_ticker_reference_refresh_tick(fetcher=_fake_fetch, now=now, force=True) == "stored"
    )
    assert (
        run_ticker_reference_refresh_tick(fetcher=_fake_fetch, now=now + timedelta(minutes=1))
        == "skipped_fresh"
    )
    assert (
        run_ticker_reference_refresh_tick(fetcher=_fake_fetch, now=now, force=True) == "stored"
    )


def test_refresh_failure_leaves_held_table_untouched():
    now = datetime.now(timezone.utc)
    run_ticker_reference_refresh_tick(fetcher=_fake_fetch, now=now, force=True)

    def _boom():
        raise TickerReferenceSourceError("source down")

    status = run_ticker_reference_refresh_tick(fetcher=_boom, now=now, force=True)
    assert status == "fetch_failed"
    with get_session() as s:
        assert require_ticker_exists(s, "AAPL") is None  # still there, unaffected


def test_symbol_missing_from_a_fresh_fetch_is_soft_deleted_not_dropped():
    now = datetime.now(timezone.utc)
    run_ticker_reference_refresh_tick(fetcher=_fake_fetch, now=now, force=True)

    def _fetch_without_aapl():
        return [r for r in _fake_fetch() if r["symbol"] != "AAPL"]

    run_ticker_reference_refresh_tick(fetcher=_fetch_without_aapl, now=now, force=True)
    with get_session() as s:
        with pytest.raises(TickerNotFoundError):
            require_ticker_exists(s, "AAPL")
        row = s.get(TickerReferenceRow, "AAPL")
        assert row is not None  # soft-deleted, never hard-deleted
        assert row.is_active is False


# ── Lookup + suggest ─────────────────────────────────────────────────────


def test_lookup_and_suggest_against_the_seeded_common_set():
    # conftest's autouse fixture already seeds AAPL/MSFT/GOOGL/META/TSLA/AMZN/NVDA
    # (plus a few DEF094/DEF112 test fixtures) — no AAPE here, so the nearest
    # edit-distance-1 candidate to "AAPLE" is deterministically AAPL.
    with get_session() as s:
        assert require_ticker_exists(s, "aapl") is None  # case-insensitive, no raise
        match = suggest_closest(s, "AAPLE", limit=1)
        assert len(match) == 1
        assert match[0].symbol == "AAPL"
        assert suggest_closest(s, "ZZZZZQQQQQ", limit=1) == []


def test_company_name_resolves_to_its_ticker():
    """DEF207 — the case CR128 shipped broken. Users type company NAMES, and
    symbol edit-distance alone answered NETFLIX with nothing (distance to
    NFLX is 3) and TESLA with ESLA (Estrella Immunopharma), both verified
    against the live 13k-row table. conftest seeds "Netflix, Inc." etc., so
    the same tiering is exercised here on a small fixture."""
    with get_session() as s:
        for typed, expected in [
            ("NETFLIX", "NFLX"),
            ("TESLA", "TSLA"),
            ("APPLE", "AAPL"),
            ("MICROSOFT", "MSFT"),
        ]:
            match = suggest_closest(s, typed, limit=1)
            assert match, f"{typed} produced no suggestion"
            assert match[0].symbol == expected, f"{typed} -> {match[0].symbol}"


def test_a_name_hit_outranks_a_coincidental_symbol_typo():
    """DEF207's sharpest case: TESLA is one edit from ESLA-shaped junk, so a
    pure edit-distance ranking prefers a random microcap over Tesla. The name
    tier must win — a wrong-company suggestion is worse than none."""
    now = datetime.now(timezone.utc)
    with get_session() as s:
        s.add(TickerReferenceRow(
            symbol="ESLA", company_name="Estrella Immunopharma, Inc.",
            exchange="NASDAQ", is_etf=False, is_active=True, last_seen_at=now,
        ))
    from app.services.ticker_reference import _invalidate_active_symbol_cache
    _invalidate_active_symbol_cache()
    with get_session() as s:
        match = suggest_closest(s, "TESLA", limit=1)
        assert match[0].symbol == "TSLA", (
            f"a one-edit junk symbol outranked the named company: {match[0].symbol}"
        )


def test_require_ticker_exists_raises_with_suggestion_attached():
    with get_session() as s:
        with pytest.raises(TickerNotFoundError) as exc_info:
            require_ticker_exists(s, "AAPLE")
        assert exc_info.value.ticker == "AAPLE"
        assert exc_info.value.suggestion is not None
        assert exc_info.value.suggestion.ticker == "AAPL"


def test_require_ticker_exists_no_suggestion_when_nothing_close():
    with get_session() as s:
        with pytest.raises(TickerNotFoundError) as exc_info:
            require_ticker_exists(s, "ZZZZZQQQQQ")
        assert exc_info.value.suggestion is None


# ── GET /v1/tickers/validate ─────────────────────────────────────────────


@pytest.fixture
def tickers_client() -> TestClient:
    app = FastAPI()
    app.include_router(tickers_router)
    return TestClient(app)


def test_validate_exact_match(tickers_client: TestClient):
    r = tickers_client.get("/v1/tickers/validate", params={"ticker": "aapl"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body == {
        "ticker": "AAPL",
        "exists": True,
        "company_name": "Apple Inc.",
        "exchange": "NASDAQ",
        "suggestion": None,
    }


def test_validate_fuzzy_match_returns_suggestion(tickers_client: TestClient):
    r = tickers_client.get("/v1/tickers/validate", params={"ticker": "AAPLE"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["exists"] is False
    assert body["suggestion"] == {
        "ticker": "AAPL", "company_name": "Apple Inc.", "exchange": "NASDAQ",
    }


def test_validate_no_match_returns_null_suggestion(tickers_client: TestClient):
    r = tickers_client.get("/v1/tickers/validate", params={"ticker": "ZZZZZQQQQQ"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["exists"] is False
    assert body["suggestion"] is None


# ── Server-side guard: watchlist ─────────────────────────────────────────


@pytest.fixture
def watchlist_client() -> TestClient:
    app = FastAPI()
    app.include_router(watchlist_router)
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


def test_watchlist_add_rejects_nonexistent_ticker(watchlist_client: TestClient):
    user_id, token = _new_user()
    r = watchlist_client.post(
        f"/v1/watchlist/{user_id}",
        json={"ticker": "ZZZZZQQQQQ"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["exists"] is False
    assert get_watchlist_store().list_for_user(user_id) == []


def test_watchlist_store_add_raises_ticker_not_found_directly():
    with pytest.raises(TickerNotFoundError):
        get_watchlist_store().add(uuid4(), "ZZZZZQQQQQ")


# ── Server-side guard: trade preview/submit ──────────────────────────────


@pytest.fixture
def sim_client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app)


def test_preview_trade_rejects_nonexistent_ticker(sim_client: TestClient):
    user_id, token = _new_user()
    r = sim_client.post(
        "/v1/sim/preview",
        json={"user_id": str(user_id), "ticker": "ZZZZZQQQQQ", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["exists"] is False


def test_submit_trade_rejects_nonexistent_ticker(sim_client: TestClient):
    user_id, token = _new_user()
    r = sim_client.post(
        "/v1/sim/submit",
        json={"user_id": str(user_id), "ticker": "ZZZZZQQQQQ", "quantity": 1},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["exists"] is False


# ── Server-side guard: Room convene — the acceptance-critical one ────────


class _MustNotRunRunner:
    """If `start_run` is ever reached, the CR128 guard did not fire strictly
    before it — the negative-space half of "zero credits/feed-quota spent on
    a rejected ticker" (the credit charge lives inside `start_run`)."""

    async def start_run(self, **_kwargs):
        raise AssertionError("start_run called — CR128 guard did not block before it")

    def is_active(self, run_id) -> bool:
        return False

    def get_run(self, run_id):
        return None


@pytest.fixture
def room_app() -> FastAPI:
    a = FastAPI()
    a.include_router(room_router)
    a.dependency_overrides[get_room_runner] = lambda: _MustNotRunRunner()
    return a


@pytest.fixture
def room_client(room_app: FastAPI) -> TestClient:
    return TestClient(room_app)


def test_room_stream_rejects_nonexistent_ticker_before_any_spend(room_client: TestClient):
    user_id, token = _new_user()
    balance_before, _, _ = balance_for(user_id)

    r = room_client.post(
        "/v1/room/stream",
        json={"user_id": str(user_id), "ticker": "ZZZZZQQQQQ", "locale": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert r.status_code == 422, r.text
    assert r.json()["detail"]["exists"] is False
    balance_after, _, _ = balance_for(user_id)
    assert balance_after == balance_before  # zero credits spent


def test_room_stream_proceeds_past_the_guard_for_a_known_ticker(room_client: TestClient):
    """Sanity check the guard isn't over-broad: a seeded ticker must reach
    `start_run`, not get rejected. `_MustNotRunRunner.start_run` raises on
    purpose to prove exactly that — TestClient's default
    `raise_server_exceptions=True` re-raises it here rather than turning it
    into a 500 response, so this asserts on the exception directly."""
    user_id, token = _new_user()
    with pytest.raises(AssertionError, match="start_run called"):
        room_client.post(
            "/v1/room/stream",
            json={"user_id": str(user_id), "ticker": "AAPL", "locale": "en"},
            headers={"Authorization": f"Bearer {token}"},
        )
