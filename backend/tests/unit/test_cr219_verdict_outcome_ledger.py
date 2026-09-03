"""CR219 R55 — the verdict-outcome ledger: writer, scorer, exclusions, endpoint.

The ledger is an internal calibration *sanity floor* ("APPROVEs are not
systematically worse than PASSes"; "high conviction means something"), never a
performance claim — these tests assert the mechanics that keep it honest:

  * migration up/down applies cleanly on the sqlite fixture;
  * a COMPLETED APPROVE/PASS banks exactly one `pending` row, and re-banking the
    same run updates rather than duplicating;
  * an abstain (`NO_VERDICT`, DEF376/R51) banks NOTHING — there is no call to
    score;
  * a run with no reference price banks `unscorable`, never a guessed price;
  * an excluded synthetic user banks `unscorable` with a reason, never a silent
    drop;
  * the scorer scores past-horizon rows only, is idempotent on re-run, and marks
    a `mock_walk`-only ticker `unscorable` rather than scoring the Room against
    a random walk (CR040 degrade-loudly);
  * the aggregates endpoint is 403 bare / 200 with the admin bearer.

Paths derive from `__file__`, so the file passes from the repo root and from
`backend/` alike.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text

from app.api.admin_verdict_outcomes import router as vo_router
from app.core.config import settings
from app.db import get_session, init_schema
from app.db.models import PriceHistoryDailyRow, RoomRunRow, User, VerdictOutcomeRow
from app.schemas.room import Verdict, VerdictAction
from app.services import verdict_outcomes as vo

_SECRET = "test-admin-secret-cr219"
_HDR = {"Authorization": f"Bearer {_SECRET}"}

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION = _BACKEND / "alembic" / "versions" / "cr219a0b0c0d3_verdict_outcomes.py"


@pytest.fixture(autouse=True)
def _admin_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "admin_secret", _SECRET)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _mk_user(*, last_app_version: str | None = "0.1.0+70") -> UUID:
    init_schema()
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            last_app_version=last_app_version,
            created_at=datetime.now(timezone.utc),
        ))
    return uid


def _mk_run(user_id: UUID, ticker: str = "AAPL") -> UUID:
    rid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=rid, user_id=user_id, ticker=ticker,
            started_at=datetime.now(timezone.utc),
            mandate_version=1, model_tier="mid", status="completed",
        ))
    return rid


def _verdict(
    action: VerdictAction = VerdictAction.APPROVE,
    *,
    approve_votes: int | None = None,
    samples: int | None = None,
    time_horizon_days: int | None = None,
) -> Verdict:
    return Verdict(
        action=action, reason="fixture", size_pct=2.0,
        approve_votes=approve_votes, samples=samples,
        time_horizon_days=time_horizon_days,
    )


def _bank(user_id: UUID, run_id: UUID, verdict: Verdict, price: float | None = 100.0,
          ref_at: datetime | None = None, horizon: str | None = "medium") -> UUID | None:
    return vo.bank_verdict_outcome(
        room_run_id=run_id, user_id=user_id, ticker="AAPL", verdict=verdict,
        reference_price=price, reference_at=ref_at, mandate_horizon=horizon,
    )


def _rows() -> list[VerdictOutcomeRow]:
    with get_session() as s:
        rows = list(s.execute(select(VerdictOutcomeRow)).scalars().all())
        for r in rows:
            s.expunge(r)
        return rows


def _bar(ticker: str, d: date, close: float, source: str = "yfinance") -> None:
    with get_session() as s:
        s.add(PriceHistoryDailyRow(
            ticker=ticker, date=d, close=close, adj_close=close, source=source,
            fetched_at=datetime.now(timezone.utc),
        ))


# ── 1. Migration up/down ────────────────────────────────────────────────────

def test_migration_applies_and_reverses_on_sqlite(tmp_path: Path) -> None:
    """The CR219 migration's upgrade() and downgrade() both run clean.

    Applied against a bare sqlite DB carrying only the `room_runs` FK target —
    the whole chain is not replayable here (DEF278 records why: it contains
    Postgres-only DDL), so this exercises exactly this revision's DDL, which is
    the part this lane owns.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("cr219_mig", _MIGRATION)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.revision == "cr219a0b0c0d3"
    assert mod.down_revision == "def335a0b0c0d2"

    engine = create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE room_runs (id CHAR(32) NOT NULL PRIMARY KEY)"
        ))

    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    with engine.begin() as conn:
        ops = Operations(MigrationContext.configure(conn))
        mod.op = ops  # the module-level `op` proxy needs a bound context
        mod.upgrade()
        names = set(inspect(conn).get_table_names())
        assert "verdict_outcomes" in names
        cols = {c["name"] for c in inspect(conn).get_columns("verdict_outcomes")}
        assert {
            "room_run_id", "user_id", "ticker", "verdict_action", "conviction",
            "size_pct", "reference_price", "reference_at", "horizon_days",
            "status", "outcome_price", "forward_return", "scored_at",
            "exclusion_reason",
        } <= cols
        idx = {i["name"] for i in inspect(conn).get_indexes("verdict_outcomes")}
        assert "ix_verdict_outcomes_status" in idx

        mod.downgrade()
        assert "verdict_outcomes" not in set(inspect(conn).get_table_names())


def test_migration_is_the_only_new_head() -> None:
    """No sibling revision also claims `def335a0b0c0d2` as its parent.

    A second child would be a second alembic head — the lane rule this WP owns.
    Static check over the versions directory, so it runs anywhere.
    """
    versions = _BACKEND / "alembic" / "versions"
    children = [
        p.name for p in versions.glob("*.py")
        if 'down_revision: Union[str, Sequence[str], None] = "def335a0b0c0d2"'
        in p.read_text()
    ]
    assert children == ["cr219a0b0c0d3_verdict_outcomes.py"], children


# ── 2. Writer hook semantics ────────────────────────────────────────────────

def test_completed_approve_banks_one_pending_row() -> None:
    uid = _mk_user()
    rid = _mk_run(uid)
    assert _bank(uid, rid, _verdict()) is not None

    rows = _rows()
    assert len(rows) == 1
    r = rows[0]
    assert r.room_run_id == rid
    assert r.verdict_action == VerdictAction.APPROVE.value
    assert r.status == vo.STATUS_PENDING
    assert r.exclusion_reason is None
    assert float(r.reference_price) == 100.0
    assert r.horizon_days == vo.HORIZON_DAYS["medium"]


def test_pass_is_banked_too() -> None:
    """A PASS is half the floor's comparison — it must be in the ledger."""
    uid = _mk_user()
    assert _bank(uid, _mk_run(uid), _verdict(VerdictAction.PASS)) is not None
    assert _rows()[0].verdict_action == VerdictAction.PASS.value


def test_abstain_banks_nothing() -> None:
    """DEF376/R51: NO_VERDICT is an abstain — there is no call to score."""
    uid = _mk_user()
    assert _bank(uid, _mk_run(uid), _verdict(VerdictAction.NO_VERDICT)) is None
    assert _rows() == []


@pytest.mark.parametrize("action", [VerdictAction.REJECT, VerdictAction.MODIFY])
def test_non_bankable_actions_are_skipped(action: VerdictAction) -> None:
    uid = _mk_user()
    assert _bank(uid, _mk_run(uid), _verdict(action)) is None
    assert _rows() == []


def test_missing_reference_price_banks_unscorable() -> None:
    """No price the Room saw ⇒ unscorable with a reason, never a guessed price.

    The row still exists: how often the Room decides without a live price is
    itself worth counting.
    """
    uid = _mk_user()
    assert _bank(uid, _mk_run(uid), _verdict(), price=None) is not None
    r = _rows()[0]
    assert r.status == vo.STATUS_UNSCORABLE
    assert r.exclusion_reason == vo.REASON_NO_REFERENCE_PRICE


def test_rebank_same_run_updates_not_duplicates() -> None:
    uid = _mk_user()
    rid = _mk_run(uid)
    first = _bank(uid, rid, _verdict())
    second = _bank(uid, rid, _verdict(VerdictAction.PASS))
    assert first == second
    rows = _rows()
    assert len(rows) == 1
    assert rows[0].verdict_action == VerdictAction.PASS.value


def test_held_back_hook_expression_is_valid_verbatim() -> None:
    """The room_runner hook's exact call, proven before it is applied.

    The hook itself is HELD BACK — WP13 owns `room_runner.py` this wave, and
    two lanes co-editing one file is the sweep that has bitten this project
    three times. But the call it will make can be proven here: this is the
    verbatim expression, including `_reference_close(profile)` (the price the
    Room was actually shown, imported from room_runner without editing it) and
    `Horizon.LONG.value` — the mandate horizon is an enum, so `.value` is
    required and a bare `ctx.mandate.horizon` would silently fall through to
    the medium default.
    """
    from app.schemas.mandate import Horizon
    from app.services.room_runner import _reference_close

    uid = _mk_user()
    rid = _mk_run(uid)

    # A LIVE-technicals profile, the shape `_reference_close` gates on.
    profile = {"field_state": {"technicals": "live"}, "last_close": 231.5}

    vo.bank_verdict_outcome(
        room_run_id=rid, user_id=uid, ticker="AAPL",
        verdict=_verdict(approve_votes=4, samples=5),
        reference_price=_reference_close(profile),
        reference_at=datetime.now(timezone.utc),
        mandate_horizon=Horizon.LONG.value,
    )

    r = _rows()[0]
    assert r.status == vo.STATUS_PENDING
    assert float(r.reference_price) == 231.5
    assert r.horizon_days == vo.HORIZON_DAYS["long"] == 126
    assert r.conviction == vo.CONVICTION_HIGH  # 4/5 = 0.8, the high threshold


def test_hook_banks_unscorable_when_technicals_are_not_live() -> None:
    """`_reference_close` yields None without LIVE provenance (CR104).

    That is not a hook bug to route around — it is the honest path: the run
    goes into the ledger `unscorable`, so how often the Room decides without a
    live price stays countable.
    """
    from app.services.room_runner import _reference_close

    uid = _mk_user()
    profile = {"field_state": {"technicals": "unavailable"}, "last_close": 231.5}
    assert _reference_close(profile) is None

    vo.bank_verdict_outcome(
        room_run_id=_mk_run(uid), user_id=uid, ticker="AAPL", verdict=_verdict(),
        reference_price=_reference_close(profile),
        reference_at=datetime.now(timezone.utc), mandate_horizon="medium",
    )
    r = _rows()[0]
    assert r.status == vo.STATUS_UNSCORABLE
    assert r.exclusion_reason == vo.REASON_NO_REFERENCE_PRICE


def test_verdict_horizon_overrides_mandate_horizon() -> None:
    uid = _mk_user()
    _bank(uid, _mk_run(uid), _verdict(time_horizon_days=10), horizon="long")
    assert _rows()[0].horizon_days == 10


def test_mandate_horizon_maps_to_days() -> None:
    for horizon, days in vo.HORIZON_DAYS.items():
        assert vo.horizon_days_for(horizon, None) == days
    assert vo.horizon_days_for("nonsense", None) == vo.HORIZON_DAYS["medium"]


def test_conviction_buckets_from_cr214_votes() -> None:
    assert vo.conviction_bucket(5, 5) == vo.CONVICTION_HIGH
    assert vo.conviction_bucket(4, 5) == vo.CONVICTION_HIGH  # 0.8 is inclusive
    assert vo.conviction_bucket(3, 5) == vo.CONVICTION_MEDIUM
    assert vo.conviction_bucket(2, 5) == vo.CONVICTION_MEDIUM  # 0.4 is inclusive
    assert vo.conviction_bucket(1, 5) == vo.CONVICTION_LOW
    assert vo.conviction_bucket(0, 5) == vo.CONVICTION_LOW
    # Absence is absence — self-consistency off, or a pre-CR214 run.
    assert vo.conviction_bucket(None, None) is None
    assert vo.conviction_bucket(3, 0) is None


def test_conviction_is_persisted_from_votes() -> None:
    uid = _mk_user()
    _bank(uid, _mk_run(uid), _verdict(approve_votes=5, samples=5))
    assert _rows()[0].conviction == vo.CONVICTION_HIGH


# ── 3. Exclusion filter ─────────────────────────────────────────────────────

def test_room_benchmark_synthetic_is_excluded() -> None:
    """CR035's 13 synthetics carry `last_app_version='room-benchmark'`."""
    uid = _mk_user(last_app_version="room-benchmark")
    assert vo.is_excluded_user(uid) is True
    assert _bank(uid, _mk_run(uid), _verdict()) is not None
    r = _rows()[0]
    assert r.status == vo.STATUS_UNSCORABLE
    assert r.exclusion_reason == vo.REASON_EXCLUDED_USER


def test_seed_burst_row_is_excluded() -> None:
    """The 10 seed fixtures: the 2026-05-24 05:10 burst shape, all conjuncts."""
    init_schema()
    uid = uuid4()
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            device_model=None, last_app_version=None,
            created_at=datetime(2026, 5, 24, 5, 10, 30, tzinfo=timezone.utc),
        ))
    assert vo.is_excluded_user(uid) is True
    assert uid in vo.excluded_user_ids()


def test_probe_user_excluded_by_id() -> None:
    """The CR125/DEF227-229 probes are shape-indistinguishable — excluded by id."""
    from app.services.admin_analytics import _EXCLUDED_USER_IDS

    init_schema()
    uid = _EXCLUDED_USER_IDS[0]
    with get_session() as s:
        s.add(User(
            id=uid, plan="floor_pass", credit_balance=8, is_anonymous=True,
            created_at=datetime.now(timezone.utc),
        ))
    assert vo.is_excluded_user(uid) is True


def test_real_user_is_not_excluded() -> None:
    uid = _mk_user()
    assert vo.is_excluded_user(uid) is False
    assert uid not in vo.excluded_user_ids()


# ── 4. Scorer ───────────────────────────────────────────────────────────────

def test_scorer_scores_only_past_horizon() -> None:
    uid = _mk_user()
    now = datetime.now(timezone.utc)

    # Due: banked 100 days ago on a 63-day horizon.
    due_ref = now - timedelta(days=100)
    _bank(uid, _mk_run(uid), _verdict(), price=100.0, ref_at=due_ref)
    _bar("AAPL", (due_ref + timedelta(days=63)).date(), 110.0)

    # Not due: banked yesterday.
    _bank(uid, _mk_run(uid), _verdict(), price=100.0, ref_at=now - timedelta(days=1))

    counts = vo.score_pending(now=now)
    assert counts["scored"] == 1
    assert counts["not_due"] == 1

    scored = [r for r in _rows() if r.status == vo.STATUS_SCORED]
    assert len(scored) == 1
    assert float(scored[0].outcome_price) == 110.0
    assert scored[0].forward_return == pytest.approx(0.10)


def test_scorer_is_idempotent() -> None:
    uid = _mk_user()
    now = datetime.now(timezone.utc)
    ref = now - timedelta(days=100)
    _bank(uid, _mk_run(uid), _verdict(), price=100.0, ref_at=ref)
    _bar("AAPL", (ref + timedelta(days=63)).date(), 110.0)

    first = vo.score_pending(now=now)
    second = vo.score_pending(now=now)
    assert first["scored"] == 1
    assert second["scored"] == 0  # nothing pending left to re-score

    rows = _rows()
    assert len(rows) == 1
    assert rows[0].forward_return == pytest.approx(0.10)


def test_mock_walk_price_marks_unscorable_never_scores() -> None:
    """CR040 applied: a fabricated bar must never become a calibration number."""
    uid = _mk_user()
    now = datetime.now(timezone.utc)
    ref = now - timedelta(days=100)
    _bank(uid, _mk_run(uid), _verdict(), price=100.0, ref_at=ref)
    _bar("AAPL", (ref + timedelta(days=63)).date(), 110.0, source="mock_walk")

    counts = vo.score_pending(now=now)
    assert counts["scored"] == 0
    assert counts["unscorable_mock"] == 1

    r = _rows()[0]
    assert r.status == vo.STATUS_UNSCORABLE
    assert r.exclusion_reason == vo.REASON_MOCK_PRICE
    assert r.forward_return is None
    assert r.outcome_price is None


def test_no_stored_bar_marks_unscorable_with_its_own_reason() -> None:
    """Distinct from the mock case: no data at all, not fabricated data."""
    uid = _mk_user()
    now = datetime.now(timezone.utc)
    _bank(uid, _mk_run(uid), _verdict(), price=100.0, ref_at=now - timedelta(days=100))

    counts = vo.score_pending(now=now)
    assert counts["scored"] == 0
    assert counts["unscorable_no_bar"] == 1
    assert _rows()[0].exclusion_reason == vo.REASON_NO_HORIZON_BAR


def test_unscorable_reasons_are_counted_separately() -> None:
    """Three distinct unscorable causes, three distinct counters.

    A lumped counter would hide which one is growing: "no bar yet" is transient,
    "all bars fabricated" never resolves, and "the Room decided without a live
    price" is a fact about the Room rather than the feed.
    """
    uid = _mk_user()
    now = datetime.now(timezone.utc)
    ref = now - timedelta(days=100)
    outcome_day = (ref + timedelta(days=63)).date()

    # no bar at all
    _bank(uid, _mk_run(uid, "AAPL"), _verdict(), 100.0, ref)
    # mock-only bars
    vo.bank_verdict_outcome(
        room_run_id=_mk_run(uid, "MSFT"), user_id=uid, ticker="MSFT",
        verdict=_verdict(), reference_price=100.0, reference_at=ref,
        mandate_horizon="medium",
    )
    _bar("MSFT", outcome_day, 110.0, source="mock_walk")

    counts = vo.score_pending(now=now)
    assert counts["unscorable_no_bar"] == 1
    assert counts["unscorable_mock"] == 1
    assert counts["unscorable_no_reference"] == 0
    assert counts["scored"] == 0

    reasons = {r.exclusion_reason for r in _rows()}
    assert reasons == {vo.REASON_NO_HORIZON_BAR, vo.REASON_MOCK_PRICE}


# ── 5. Aggregates + endpoint ────────────────────────────────────────────────

def _client() -> TestClient:
    app = FastAPI()
    app.include_router(vo_router)
    return TestClient(app)


def test_aggregates_endpoint_requires_admin() -> None:
    c = _client()
    assert c.get("/v1/admin/verdict-outcomes/aggregates").status_code == 403
    assert c.get(
        "/v1/admin/verdict-outcomes/aggregates",
        headers={"Authorization": "Bearer wrong"},
    ).status_code == 403


def test_aggregates_endpoint_200_with_admin_bearer() -> None:
    init_schema()
    r = _client().get("/v1/admin/verdict-outcomes/aggregates", headers=_HDR)
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {
        "by_status", "exclusion_reasons", "by_action", "conviction",
        "interpretation",
    }


def test_aggregates_separate_approve_and_pass() -> None:
    uid = _mk_user()
    now = datetime.now(timezone.utc)
    ref = now - timedelta(days=100)
    outcome_day = (ref + timedelta(days=63)).date()

    _bar("AAPL", outcome_day, 110.0)
    _bar("MSFT", outcome_day, 90.0)

    _bank(uid, _mk_run(uid, "AAPL"), _verdict(VerdictAction.APPROVE), 100.0, ref)
    vo.bank_verdict_outcome(
        room_run_id=_mk_run(uid, "MSFT"), user_id=uid, ticker="MSFT",
        verdict=_verdict(VerdictAction.PASS), reference_price=100.0,
        reference_at=ref, mandate_horizon="medium",
    )
    vo.score_pending(now=now)

    agg = vo.aggregates()
    assert agg["by_action"]["APPROVE"]["n"] == 1
    assert agg["by_action"]["APPROVE"]["mean"] == pytest.approx(0.10)
    assert agg["by_action"]["PASS"]["n"] == 1
    assert agg["by_action"]["PASS"]["mean"] == pytest.approx(-0.10)
    assert agg["by_status"][vo.STATUS_SCORED] == 2


def test_aggregates_conviction_hit_rate_is_approve_only() -> None:
    uid = _mk_user()
    now = datetime.now(timezone.utc)
    ref = now - timedelta(days=100)
    _bar("AAPL", (ref + timedelta(days=63)).date(), 110.0)
    _bank(
        uid, _mk_run(uid),
        _verdict(VerdictAction.APPROVE, approve_votes=5, samples=5), 100.0, ref,
    )
    vo.score_pending(now=now)

    conv = vo.aggregates()["conviction"]
    assert conv[vo.CONVICTION_HIGH]["n"] == 1
    assert conv[vo.CONVICTION_HIGH]["hit_rate"] == pytest.approx(1.0)


def test_aggregates_carry_the_framing_disclaimer() -> None:
    """The payload must say what it is NOT — a reader may never see the module."""
    init_schema()
    text_ = vo.aggregates()["interpretation"].lower()
    assert "not a performance claim" in text_
    assert "simulation-only" in text_
    # The AI is named AMI wherever a string could reach a person.
    assert "the ai" not in text_
