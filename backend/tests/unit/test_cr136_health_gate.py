"""CR136 M07 — gate semantics (trial window/budget/daily cap/modes), route guards, API shapes; tiles are never gated.

Journal rows are the counter, so the tests seed real `JournalEntryRow`s through
the store and backdate them, rather than mocking the counting read: the whole
point of the design is that the thing being counted is the thing the user can
see and delete, and a mocked counter would not exercise that.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.api.portfolio import router as portfolio_router
from app.core.config import settings
from app.db import get_session
from app.db.models import JournalEntryRow, User
from app.schemas import Plan
from app.schemas.journal import EntryType
from app.services import portfolio_finding
from app.services.health_gate import (
    DAILY_CAP_CODE,
    GATE_CLOSED_CODE,
    PORTFOLIO_HEALTH_ENTRY_TYPE,
    evaluate_gate,
)
from app.services.journal_store import get_journal_store
from app.services.rate_limit import portfolio_health_finding_rate_limit
from app.services.sim_engine import SimEngine, get_sim_engine


@dataclass
class _U:
    id: UUID


class _Portfolio:
    def __init__(self, portfolio_id: UUID) -> None:
        self.id = portfolio_id


class _Sim:
    def __init__(self, portfolio_id: UUID) -> None:
        self._p = _Portfolio(portfolio_id)

    def ensure_portfolio(self, user_id: UUID):
        return self._p


_OK_CONTEXT = {
    "status": "ok",
    "as_of": "2026-08-02",
    "generated_at": "2026-08-02T09:00:00+00:00",
    "engine_version": "cr136.v1",
    "blocks": {"portfolio_volatility": {"metric": "portfolio_volatility",
                                        "sufficient": True, "value": 0.19}},
    "holdings": [],
    "cash_fraction": 0.0,
    "contains_etfs": False,
    "context": {"correlation_pairs": []},
}


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch):
    get_journal_store().clear()
    portfolio_health_finding_rate_limit.reset()
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "trial")
    monkeypatch.setattr(settings, "portfolio_health_trial_days", 14)
    monkeypatch.setattr(settings, "portfolio_health_trial_findings", 7)
    monkeypatch.setattr(settings, "portfolio_health_daily_cap", 2)
    monkeypatch.setattr(settings, "portfolio_health_plans", ["trader", "floor_manager"])
    yield
    get_journal_store().clear()


def _seed_user(plan: Plan = Plan.FLOOR_PASS, trial_expires_at=None) -> UUID:
    user_id = uuid4()
    with get_session() as s:
        s.add(User(id=user_id, plan=plan.value, trial_expires_at=trial_expires_at))
    return user_id


def _today_utc(offset: timedelta = timedelta()) -> datetime:
    """A timestamp guaranteed to fall on TODAY in UTC.

    `now - timedelta(minutes=10)` is not: run it in the first ten minutes after
    UTC midnight and the row lands on yesterday, `daily_used` reads 0, and the
    cap tests fail for eleven minutes a day. Measured by the M11 audit — the
    suite really was green at the SHA it was measured at, and really would not
    have been at 00:05 UTC. Clamping to the start of the UTC day makes the
    fixture say what it means: "earlier today".
    """
    now = datetime.now(timezone.utc)
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return max(now + offset, day_start)


def _seed_finding(
    user_id: UUID, portfolio_id: UUID, *, as_of: str, created_at: datetime,
    deleted: bool = False,
) -> UUID:
    """Insert the row directly — the store's `append` stamps `created_at` from
    the clock, and every trial/cap boundary in this file is a statement about
    WHEN a Finding was written."""
    entry_id = uuid4()
    with get_session() as s:
        s.add(JournalEntryRow(
            id=entry_id,
            user_id=user_id,
            entry_type=EntryType.PORTFOLIO_HEALTH_ANALYSIS.value,
            reference_id=portfolio_id,
            title=f"Portfolio Health — Finding {as_of}",
            payload={"as_of": as_of, "portfolio_id": str(portfolio_id),
                     "sections": {"head": "h", "f1": "a", "f2": "b",
                                  "f3": "c", "f4": "d", "f5": "e"},
                     "rule_states": {}},
            created_at=created_at,
            deleted_at=created_at if deleted else None,
        ))
    return entry_id


def _app(user_id: UUID, portfolio_id: UUID) -> FastAPI:
    app = FastAPI()
    app.include_router(portfolio_router)
    app.dependency_overrides[get_sim_engine] = lambda: _Sim(portfolio_id)
    app.dependency_overrides[get_current_user] = lambda: _U(id=user_id)
    return app


@pytest.fixture
def wired(monkeypatch: pytest.MonkeyPatch):
    """Both engine seams stubbed: this module gates and routes, it does not
    compute metrics or render prose."""
    user_id = _seed_user()
    portfolio_id = uuid4()
    generated: list = []

    monkeypatch.setattr(
        "app.api.portfolio.build_health_context", lambda uid: dict(_OK_CONTEXT),
    )
    monkeypatch.setattr(
        "app.api.portfolio.evaluate_rules_for_context",
        lambda context, mandate, prior_states: ([], {}),
    )

    async def _fake_generate(**kwargs):
        generated.append(kwargs)
        entry_id = _seed_finding(
            kwargs["user_id"], kwargs["portfolio_id"], as_of=kwargs["as_of"],
            created_at=datetime.now(timezone.utc),
        )
        entry = get_journal_store().latest_portfolio_health_entry(
            kwargs["user_id"], kwargs["portfolio_id"],
        )
        assert entry is not None and entry.id == entry_id
        return portfolio_finding.FindingResult(
            entry=entry, created=True, llm_used=False, llm_rejected_reason=None,
        )

    monkeypatch.setattr(
        "app.api.portfolio.generate_and_persist_finding", _fake_generate,
    )
    monkeypatch.setattr("app.api.portfolio.resolve_mandate", lambda uid, v: None,
                        raising=False)
    client = TestClient(_app(user_id, portfolio_id), raise_server_exceptions=False)
    return client, user_id, portfolio_id, generated


# ── Ownership ───────────────────────────────────────────────────────────────


def test_another_users_book_is_403_on_both_routes(wired) -> None:
    client, _user_id, _portfolio_id, _gen = wired
    stranger = uuid4()
    assert client.get(f"/v1/portfolio/health/{stranger}").status_code == 403
    assert client.post(f"/v1/portfolio/health/{stranger}/finding").status_code == 403


# ── Tiles are never gated ───────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["open", "trial", "plan"])
def test_tiles_are_free_in_every_mode_even_fully_exhausted(
    wired, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    """The one guarantee that has to hold unconditionally: a measurement of the
    user's own book is not a paid surface."""
    client, user_id, portfolio_id, _gen = wired
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", mode)
    now = datetime.now(timezone.utc)
    for i in range(7):
        _seed_finding(user_id, portfolio_id, as_of=f"2026-07-0{i + 1}",
                      created_at=now - timedelta(days=30 - i))

    r = client.get(f"/v1/portfolio/health/{user_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["metrics"]["blocks"]["portfolio_volatility"]["value"] == 0.19
    assert body["gate"]["trial_active"] is False
    assert body["gate"]["plan_has_access"] is False


def test_the_tiles_route_never_calls_enforce_gate() -> None:
    """Structural, not behavioural: the free surface must be incapable of
    gating, not merely observed not to."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path("app/api/portfolio.py").read_text())
    fn = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == "portfolio_health"
    )
    # Every NAME the body mentions, not just direct calls: both gate functions
    # reach the thread pool as `asyncio.to_thread(fn, ...)` arguments, so a
    # call-node check would report neither and pass vacuously.
    names = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    assert "enforce_gate" not in names, names
    assert "evaluate_gate" in names, names


# ── Trial: window and budget, whichever exhausts sooner ─────────────────────


def test_trial_by_days_at_the_boundary(wired) -> None:
    client, user_id, portfolio_id, _gen = wired
    now = datetime.now(timezone.utc)
    _seed_finding(user_id, portfolio_id, as_of="2026-07-01",
                  created_at=now - timedelta(days=13, hours=23))

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, r.text

    get_journal_store().clear()
    _seed_finding(user_id, portfolio_id, as_of="2026-07-01",
                  created_at=now - timedelta(days=14))
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 402
    assert r.json()["detail"]["code"] == GATE_CLOSED_CODE
    assert r.json()["detail"]["gate"]["trial_days_left"] == 0


def test_trial_by_findings_counts_soft_deleted_rows(wired) -> None:
    """Deleting yesterday's Finding must not mint budget — the counter is the
    row, and the row survives the delete."""
    client, user_id, portfolio_id, _gen = wired
    now = datetime.now(timezone.utc)
    for i in range(6):
        _seed_finding(user_id, portfolio_id, as_of=f"2026-07-0{i + 1}",
                      created_at=now - timedelta(days=6 - i), deleted=i == 0)

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, "the 7th is inside a 7-Finding budget"

    get_journal_store().clear()
    for i in range(7):
        _seed_finding(user_id, portfolio_id, as_of=f"2026-07-0{i + 1}",
                      created_at=now - timedelta(days=7 - i), deleted=i < 2)
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 402
    assert r.json()["detail"]["gate"]["trial_findings_used"] == 7


def test_whichever_exhausts_sooner_wins(wired) -> None:
    client, user_id, portfolio_id, _gen = wired
    now = datetime.now(timezone.utc)

    for i in range(7):
        _seed_finding(user_id, portfolio_id, as_of=f"2026-07-0{i + 1}",
                      created_at=now - timedelta(days=3))
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 402
    assert r.json()["detail"]["gate"]["trial_days_left"] > 0, "budget ran out first"

    get_journal_store().clear()
    _seed_finding(user_id, portfolio_id, as_of="2026-07-01",
                  created_at=now - timedelta(days=15))
    _seed_finding(user_id, portfolio_id, as_of="2026-07-02",
                  created_at=now - timedelta(days=14))
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 402
    gate = r.json()["detail"]["gate"]
    assert gate["trial_findings_used"] < 7, "the window ran out first"
    assert gate["trial_days_left"] == 0


def test_an_untouched_trial_has_not_started_ticking(wired) -> None:
    """No Finding yet means the window has not begun — a user who installs and
    waits a month still gets the full trial when they first ask."""
    _client, user_id, portfolio_id, _gen = wired
    gate = evaluate_gate(user_id, portfolio_id)
    assert gate.trial_active is True
    assert gate.trial_days_left == 14
    assert gate.trial_findings_used == 0


# ── Daily cap ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["open", "trial", "plan"])
def test_the_daily_cap_applies_in_every_mode(
    wired, monkeypatch: pytest.MonkeyPatch, mode: str,
) -> None:
    client, user_id, portfolio_id, _gen = wired
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", mode)
    if mode == "plan":
        monkeypatch.setattr(settings, "portfolio_health_plans", ["floor_pass"])
    now = datetime.now(timezone.utc)
    for i in range(2):
        _seed_finding(user_id, portfolio_id, as_of=f"2026-07-0{i + 1}",
                      created_at=_today_utc(timedelta(minutes=-(10 + i))))

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 429, r.text
    assert r.json()["detail"]["code"] == DAILY_CAP_CODE


def test_one_finding_today_still_leaves_the_second(wired) -> None:
    client, user_id, portfolio_id, _gen = wired
    _seed_finding(user_id, portfolio_id, as_of="2026-07-01",
                  created_at=_today_utc(timedelta(minutes=-5)))
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, r.text
    assert r.json()["gate"]["daily_used"] == 2, "re-evaluated to include the new row"


def test_the_daily_boundary_is_utc_midnight(wired) -> None:
    _client, user_id, portfolio_id, _gen = wired
    now = datetime(2026, 8, 2, 0, 30, tzinfo=timezone.utc)
    _seed_finding(user_id, portfolio_id, as_of="2026-08-01",
                  created_at=now - timedelta(hours=1))     # 23:30 yesterday
    _seed_finding(user_id, portfolio_id, as_of="2026-08-02",
                  created_at=now - timedelta(minutes=10))  # 00:20 today

    gate = evaluate_gate(user_id, portfolio_id, now=now)
    assert gate.daily_used == 1
    assert gate.trial_findings_used == 2


def test_the_daily_counter_is_per_portfolio_the_trial_is_per_user(wired) -> None:
    """`reset_portfolio` destroys and recreates the book, so a per-portfolio
    trial would reset itself on every reset."""
    _client, user_id, portfolio_id, _gen = wired
    other_portfolio = uuid4()
    now = datetime.now(timezone.utc)
    _seed_finding(user_id, other_portfolio, as_of="2026-08-02", created_at=now)
    _seed_finding(user_id, other_portfolio, as_of="2026-08-02", created_at=now)

    gate = evaluate_gate(user_id, portfolio_id, now=now)
    assert gate.daily_used == 0, "another portfolio's Findings are not this cap"
    assert gate.trial_findings_used == 2, "...but they are the same user's trial"


# ── Modes ───────────────────────────────────────────────────────────────────


def test_open_mode_bypasses_an_exhausted_trial(
    wired, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, user_id, portfolio_id, _gen = wired
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "open")
    now = datetime.now(timezone.utc)
    for i in range(7):
        _seed_finding(user_id, portfolio_id, as_of=f"2026-07-0{i + 1}",
                      created_at=now - timedelta(days=20 - i))

    assert client.post(f"/v1/portfolio/health/{user_id}/finding").status_code == 200


def test_plan_mode_gates_from_day_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "plan")
    monkeypatch.setattr(settings, "portfolio_health_plans", ["trader", "floor_manager"])
    portfolio_id = uuid4()

    floor_pass = _seed_user(Plan.FLOOR_PASS)
    assert evaluate_gate(floor_pass, portfolio_id).has_access is False

    trader = _seed_user(Plan.TRADER)
    assert evaluate_gate(trader, portfolio_id).has_access is True

    expired = _seed_user(
        Plan.TRIAL_TRADER,
        trial_expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    assert evaluate_gate(expired, portfolio_id).has_access is False, (
        "an expired account trial resolves to FLOOR_PASS through entitlements"
    )


def test_the_plan_list_parses_rev4s_own_spelling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "plan")
    monkeypatch.setattr(settings, "portfolio_health_plans", ["TRADER", " floor_manager"])
    trader = _seed_user(Plan.TRADER)
    assert evaluate_gate(trader, uuid4()).plan_has_access is True

    monkeypatch.setattr(settings, "portfolio_health_plans", [])
    assert evaluate_gate(trader, uuid4()).plan_has_access is False, (
        "an empty list hard-closes plan mode — loud and documented, not a default-open"
    )


# ── Idempotency ─────────────────────────────────────────────────────────────


def test_same_day_regeneration_returns_the_existing_entry_ungated(
    wired, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unconditional: the entry is already in the user's journal, so re-reading
    it must not cost budget or be refusable."""
    client, user_id, portfolio_id, generated = wired
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "plan")
    monkeypatch.setattr(settings, "portfolio_health_plans", ["floor_manager"])
    entry_id = _seed_finding(user_id, portfolio_id, as_of=_OK_CONTEXT["as_of"],
                             created_at=datetime.now(timezone.utc))

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, "gated user, but nothing is being generated"
    body = r.json()
    assert body["created"] is False
    assert body["journal_entry_id"] == str(entry_id)
    assert set(body["sections"]) == {"head", "f1", "f2", "f3", "f4", "f5"}
    assert generated == [], "no generation, so no LLM call and no write"


def test_a_deleted_prior_entry_is_not_replayed_to_the_client(wired) -> None:
    """It still counts against the budget — but handing back a journal id the
    user cannot open would answer "regenerate" with a dead link."""
    client, user_id, portfolio_id, generated = wired
    _seed_finding(user_id, portfolio_id, as_of=_OK_CONTEXT["as_of"],
                  created_at=datetime.now(timezone.utc), deleted=True)

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True
    assert len(generated) == 1


def test_the_hysteresis_state_survives_a_delete(wired) -> None:
    """The counters and the rule memory read the same row for the same reason:
    a deleted Finding is still something that happened."""
    _client, user_id, portfolio_id, _gen = wired
    _seed_finding(user_id, portfolio_id, as_of="2026-08-01",
                  created_at=datetime.now(timezone.utc), deleted=True)
    prior = get_journal_store().latest_portfolio_health_entry(user_id, portfolio_id)
    assert prior is not None and prior.deleted_at is not None


# ── Shapes + limiter + engine refusal ───────────────────────────────────────


def test_the_gate_dict_is_exactly_the_eight_pinned_keys(wired) -> None:
    client, user_id, _portfolio_id, _gen = wired
    expected = {
        "mode", "trial_active", "trial_findings_used", "trial_findings_budget",
        "trial_days_left", "daily_used", "daily_cap", "plan_has_access",
    }
    tiles = client.get(f"/v1/portfolio/health/{user_id}").json()
    assert set(tiles["gate"]) == expected
    finding = client.post(f"/v1/portfolio/health/{user_id}/finding").json()
    assert set(finding["gate"]) == expected
    assert set(finding) == {"journal_entry_id", "created", "as_of", "sections", "gate"}


def test_the_sixth_post_in_a_minute_is_rate_limited(wired) -> None:
    client, user_id, _portfolio_id, _gen = wired
    for _ in range(5):
        client.post(f"/v1/portfolio/health/{user_id}/finding")
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 429
    assert r.json()["detail"] == "rate_limit_exceeded: portfolio_health_finding"


def test_an_engine_refusal_is_409_on_post_and_200_on_get(
    wired, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Finding narrated over mock-walk prices would read exactly like a real
    one and mean nothing; the tiles still render, carrying the refusal."""
    client, user_id, _portfolio_id, _gen = wired
    refusal = {"status": "refused_mock_data", "reason": "use_real_market_data=false",
               "engine_version": "cr136.v1", "generated_at": "2026-08-02T09:00:00+00:00"}
    monkeypatch.setattr(
        "app.api.portfolio.build_health_context", lambda uid: dict(refusal),
    )

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "portfolio_health_unavailable"

    tiles = client.get(f"/v1/portfolio/health/{user_id}")
    assert tiles.status_code == 200
    assert tiles.json()["status"] == "refused_mock_data"


# ── The whole pipeline, unstubbed ───────────────────────────────────────────


def test_the_route_composes_the_real_engine_rules_and_renderer(
    monkeypatch: pytest.MonkeyPatch, base_mandate,
) -> None:
    """Nothing stubbed below the route: real M04 context → real M05 rules → real
    M06 render/validate/persist. Every other test here stubs both seams, so
    without this one a signature drift anywhere along the chain — the exact
    class of defect the M06 audit found twice — would leave the suite green.
    """
    from tests.unit.test_cr136_metrics_engine import _book

    from app.services.portfolio_health import compute_health

    user_id = _seed_user(Plan.TRADER)
    portfolio_id = uuid4()
    context = compute_health(**_book())
    monkeypatch.setattr(
        "app.api.portfolio.build_health_context", lambda uid: context,
    )
    monkeypatch.setattr(
        "app.api.portfolio.resolve_mandate", lambda uid, v: base_mandate,
    )
    # No LLM in a unit test — the deterministic rendering is the complete
    # report, which is the whole point of M06's fallback design.
    monkeypatch.setattr(settings, "portfolio_health_llm_enabled", False)
    monkeypatch.setattr("app.api.portfolio.get_llm_gateway", lambda: None)

    client = TestClient(_app(user_id, portfolio_id), raise_server_exceptions=False)
    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] is True
    assert body["as_of"] == context["as_of"]
    assert set(body["sections"]) == {"head", "f1", "f2", "f3", "f4", "f5"}
    assert "Not investment advice" in body["sections"]["head"]
    assert body["gate"]["daily_used"] == 1

    stored = get_journal_store().latest_portfolio_health_entry(user_id, portfolio_id)
    assert stored is not None
    assert stored.payload["rule_states"].keys() == {
        "R0", "R1", "R2", "R2b", "R3", "R4", "R5",
    }

    replay = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert replay.status_code == 200
    assert replay.json()["created"] is False
    assert replay.json()["journal_entry_id"] == body["journal_entry_id"]


def test_concurrent_posts_write_exactly_one_finding(
    monkeypatch: pytest.MonkeyPatch, base_mandate,
) -> None:
    """Measured before the unique constraint existed: five concurrent POSTs
    produced five Findings against a daily cap of two, and five LLM bills for
    one logical action. A double-tap, or a client retrying a slow response, is
    enough — no attacker required.

    An application re-read cannot fix this. There is no point in the sequence
    where reading again is safe, because the competing INSERT may land right
    after it, so the check has to be one the database makes.
    """
    import asyncio as _asyncio

    import httpx

    from tests.unit.test_cr136_metrics_engine import _book

    from app.services.portfolio_health import compute_health

    user_id = _seed_user(Plan.TRADER)
    portfolio_id = uuid4()
    context = compute_health(**_book())
    llm_calls: list[int] = []

    monkeypatch.setattr("app.api.portfolio.build_health_context", lambda uid: context)
    monkeypatch.setattr("app.api.portfolio.resolve_mandate", lambda uid, v: base_mandate)
    monkeypatch.setattr(settings, "portfolio_health_llm_enabled", True)

    class _SlowGateway:
        def has_real_provider(self) -> bool:
            return True

        def stream_chat(self, **kwargs):
            llm_calls.append(1)

            async def _gen():
                # Wide enough for every request to clear the idempotency read
                # before any of them writes — the window the defect lives in.
                await _asyncio.sleep(0.05)
                yield '{"f1": ["Calm."], "f2": "x", "f3": "y", "f4": "z", "f5": "w"}'

            return _gen()

    monkeypatch.setattr("app.api.portfolio.get_llm_gateway", lambda: _SlowGateway())

    async def _fire(n: int):
        app = _app(user_id, portfolio_id)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test",
        ) as client:
            return await _asyncio.gather(*(
                client.post(f"/v1/portfolio/health/{user_id}/finding")
                for _ in range(n)
            ))

    responses = _asyncio.run(_fire(5))

    assert all(r.status_code == 200 for r in responses), [r.status_code for r in responses]
    ids = {r.json()["journal_entry_id"] for r in responses}
    assert len(ids) == 1, f"five concurrent POSTs minted {len(ids)} Findings"
    assert sum(1 for r in responses if r.json()["created"]) == 1

    _used, _first, daily = get_journal_store().portfolio_health_stats(
        user_id, portfolio_id, now=datetime.now(timezone.utc),
    )
    assert daily == 1, f"daily counter says {daily} — the cap was bypassed"


def test_a_refused_user_over_the_cap_is_told_to_upgrade_not_to_come_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both conditions true at once. Order is load-bearing and was asserted only
    by the code's own docstring: a 429 tells a user who can never generate to
    try again tomorrow, which will be just as false tomorrow."""
    from app.services.health_gate import GateStatus, enforce_gate

    both = GateStatus(
        mode="plan", trial_active=False, trial_findings_used=9,
        trial_findings_budget=7, trial_days_left=0, daily_used=2, daily_cap=2,
        plan_has_access=False,
    )
    assert both.has_access is False and both.daily_cap_reached is True
    with pytest.raises(Exception) as exc:
        enforce_gate(both)
    assert exc.value.status_code == 402
    assert exc.value.detail["code"] == GATE_CLOSED_CODE


def test_plan_mode_generates_end_to_end_for_an_entitled_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doc case 9's generate half, through the route rather than asserted on the
    gate object — `has_access is True` proves the gate would allow it, not that
    a POST returns a Finding."""
    monkeypatch.setattr(settings, "portfolio_health_gate_mode", "plan")
    user_id = _seed_user(Plan.TRADER)
    portfolio_id = uuid4()
    generated: list = []

    monkeypatch.setattr(
        "app.api.portfolio.build_health_context", lambda uid: dict(_OK_CONTEXT),
    )
    monkeypatch.setattr(
        "app.api.portfolio.evaluate_rules_for_context",
        lambda context, mandate, prior_states: ([], {}),
    )
    monkeypatch.setattr("app.api.portfolio.resolve_mandate", lambda uid, v: None)

    async def _fake_generate(**kwargs):
        generated.append(kwargs)
        _seed_finding(kwargs["user_id"], kwargs["portfolio_id"],
                      as_of=kwargs["as_of"], created_at=datetime.now(timezone.utc))
        entry = get_journal_store().latest_portfolio_health_entry(
            kwargs["user_id"], kwargs["portfolio_id"],
        )
        return portfolio_finding.FindingResult(
            entry=entry, created=True, llm_used=False, llm_rejected_reason=None,
        )

    monkeypatch.setattr("app.api.portfolio.generate_and_persist_finding", _fake_generate)
    client = TestClient(_app(user_id, portfolio_id), raise_server_exceptions=False)

    r = client.post(f"/v1/portfolio/health/{user_id}/finding")
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True
    assert len(generated) == 1


def test_a_naive_now_is_read_as_utc_not_as_server_local_time() -> None:
    """`astimezone()` on a naive datetime reinterprets it as LOCAL time, so the
    daily cap would reset hours early or late depending on where the container
    runs."""
    user_id = _seed_user()
    portfolio_id = uuid4()
    _seed_finding(user_id, portfolio_id, as_of="2026-08-02",
                  created_at=datetime(2026, 8, 2, 3, 0, tzinfo=timezone.utc))

    aware = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    naive = aware.replace(tzinfo=None)
    store = get_journal_store()
    assert (
        store.portfolio_health_stats(user_id, portfolio_id, now=naive)
        == store.portfolio_health_stats(user_id, portfolio_id, now=aware)
    )


def test_the_entry_type_string_matches_the_enum() -> None:
    assert PORTFOLIO_HEALTH_ENTRY_TYPE == "portfolio_health_analysis"
    assert PORTFOLIO_HEALTH_ENTRY_TYPE == EntryType.PORTFOLIO_HEALTH_ANALYSIS.value


def test_the_gate_module_never_imports_the_journal_enum() -> None:
    """M07 reads rows by the string constant so it carries no build-order
    dependency on M08's enum member."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path("app/services/health_gate.py").read_text())
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert "EntryType" not in imported, imported
