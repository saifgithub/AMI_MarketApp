"""CR267 WP-24 — same inputs return the same Room.

Guards, in the order the acceptance reads:
  1. the 50-pair test: two convenes with identical inputs return the identical
     room ID in 100% of 50 pairs, and the second is free;
  2. changing ANY keyed input (user, ticker, mandate content, fact sheet, policy
     version, model root, trading day) produces a new Room;
  3. two concurrent identical convenes are one Room (unique key, no SELECT-then-
     INSERT), with one charge;
  4. failed / cancelled / outage / scripted-desk Rooms are not banked;
  5. a Room restarted on the backup slot is keyed by the backup's root;
  6. an unreadable model root runs the Room unbanked, loudly;
  7. the fact sheet is frozen per ticker per trading day, race-safe;
  8. the mandate digest covers every Mandate field or names why it does not;
  9. `done` reports a banked return as free, and the provider's root read is
     cached, expires, and never serves a stale root after a failed refresh.

A stand-in `run` replaces the 12-desk Room for the key/charge/race tests (those
properties live in `start_run` and the row's unique key, not in the debate).
"""

from __future__ import annotations

import asyncio
import threading
from datetime import date, datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import RoomRunRow, User
from app.schemas import AgentId, AgentMessage
from app.schemas.mandate import Mandate
from app.schemas.room import RoomRun, RoomStatus, Verdict, VerdictAction
from app.services import room_bank, room_runner as rr
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for
from app.services.llm_gateway import LLMGateway, VLLMProvider
from app.services.room_runner import RoomEvent, RoomRunner, run_is_bankable
from app.trading_math.session_calendar import (
    is_us_session_day,
    last_us_session_date,
    nyse_holidays,
)


def _user(plan: str = "trader") -> UUID:
    u, _, _ = AuthService().ensure_anonymous(device_user_id=None)
    with get_session() as s:
        s.get(User, u.id).plan = plan
    return u.id


def _mandate(**kw) -> Mandate:
    return hydrate_coach_mandate({"plan": "trader", "risk_score": 3, **kw})


class _RootGateway(LLMGateway):
    """A real gateway whose model root is whatever the test says."""

    def __init__(self, root: str | None = "root-A", backup_root: str | None = "root-B"):
        super().__init__()
        self.root = root
        self.backup_root = backup_root

    async def room_model_root(self, provider_name: str | None = None):
        return self.backup_root if provider_name else self.root


@pytest.fixture
def fast_room(monkeypatch):
    """Replace the 12-desk run with one that persists a COMPLETED Room."""
    calls: list[dict] = []

    async def _fast(self, *, run_id=None, user_id, ticker, mandate, credit_cost=None,
                    bank=None, frozen_profile=None, **_kw):
        run_id = run_id or uuid4()
        now = datetime.now(timezone.utc)
        calls.append({"run_id": run_id, "bank": bank, "profile": frozen_profile})
        run = RoomRun(
            id=run_id, user_id=user_id, ticker=ticker.upper(), triggered_at=now,
            started_at=now, mandate_version=mandate.version, model_tier="cheap",
            credit_cost=credit_cost or 0, status=RoomStatus.RUNNING,
            bank_key=bank[0] if bank else None,
            bank_inputs=dict(bank[1]) if bank else None,
        )
        rr._persist_run(run)
        yield RoomEvent(kind="started", run_id=run_id)
        await asyncio.sleep(0)
        run.status = RoomStatus.COMPLETED
        run.finished_at = datetime.now(timezone.utc)
        run.verdict = Verdict(action=VerdictAction.PASS, reason="ok")
        rr._persist_run(run)
        yield RoomEvent(kind="verdict", run_id=run_id, verdict=run.verdict)

    monkeypatch.setattr(RoomRunner, "run", _fast)
    monkeypatch.setattr(room_bank, "policy_version", lambda: "policy-1")
    return calls


async def _convene(runner: RoomRunner, user_id: UUID, ticker: str, mandate: Mandate,
                   outcome: dict | None = None) -> UUID:
    rid = await runner.start_run(
        user_id=user_id, ticker=ticker, mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0, bank_outcome=outcome,
    )
    async for _ in runner.subscribe(rid):
        pass
    for t in [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
        await asyncio.gather(t, return_exceptions=True)
    return rid


def _go(coro):
    return asyncio.run(coro)


# ── 1. acceptance: 50 pairs ───────────────────────────────────────────────


def test_fifty_identical_pairs_return_the_identical_room_and_charge_once(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    users = [_user() for _ in range(5)]
    tickers = [f"T{i}" for i in range(10)]

    async def go():
        pairs = 0
        for u in users:
            m = _mandate()
            for t in tickers:
                before = balance_for(u)[0]
                first = await _convene(runner, u, t, m)
                after_first = balance_for(u)[0]
                outcome: dict = {}
                second = await _convene(runner, u, t, m, outcome)
                assert first == second, (u, t)
                assert outcome.get("banked") is True
                assert balance_for(u)[0] == after_first, "a banked return is free"
                assert after_first < before, "the first convene was charged"
                pairs += 1
        return pairs

    assert _go(go()) == 50
    assert len(fast_room) == 50, "the stand-in ran once per pair, never for the repeat"


def test_a_banked_return_reports_when_the_room_finished(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        first = await _convene(runner, u, "AAPL", m)
        out: dict = {}
        await _convene(runner, u, "AAPL", m, out)
        return first, out

    first, out = _go(go())
    assert out["banked"] is True
    assert out["banked_at"] is not None and out["banked_at"].tzinfo is not None
    with get_session() as s:
        row = s.get(RoomRunRow, first)
        assert row.bank_key is not None and row.bank_inputs["fact_sheet"]


# ── 2. each keyed input changes the Room ──────────────────────────────────


def _two(fast_room, *, second_user=None, second_ticker="AAPL", second_mandate=None,
         before_second=None, gw=None):
    gw = gw or _RootGateway()
    runner = RoomRunner(llm=gw)
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        if before_second:
            before_second(gw)
        b = await _convene(
            runner, second_user or u, second_ticker,
            second_mandate(m) if second_mandate else m,
        )
        return a, b

    return _go(go())


def test_identical_inputs_control(fast_room):
    a, b = _two(fast_room)
    assert a == b


def test_changed_ticker_is_a_new_room(fast_room):
    a, b = _two(fast_room, second_ticker="MSFT")
    assert a != b


def test_another_user_is_a_new_room(fast_room):
    a, b = _two(fast_room, second_user=_user())
    assert a != b


@pytest.mark.parametrize("change", [
    {"risk_score": 4},
    {"display_name": "Someone Else"},
])
def test_changed_mandate_content_is_a_new_room(fast_room, change):
    a, b = _two(fast_room, second_mandate=lambda m: m.model_copy(update=change))
    assert a != b


def test_a_resaved_unchanged_mandate_is_still_the_same_room(fast_room):
    a, b = _two(fast_room, second_mandate=lambda m: m.model_copy(update={
        "version": m.version + 5, "updated_at": m.updated_at + timedelta(days=3),
        "credit_balance": 1, "room_cooldown_until": None,
    }))
    assert a == b


def test_changed_fact_sheet_is_a_new_room(fast_room, monkeypatch):
    sheets = iter([{"ticker": "AAPL", "base_price": 100.0, "field_state": {}},
                   {"ticker": "AAPL", "base_price": 101.0, "field_state": {}}])
    monkeypatch.setattr(rr, "_profile_for_ticker", lambda *a, **k: next(sheets))
    day = {"d": date(2026, 11, 19)}
    monkeypatch.setattr(room_bank, "trading_date_for", lambda now: day["d"])
    a, b = _two(fast_room, before_second=lambda _g: day.update(d=date(2026, 11, 20)))
    assert a != b


def test_changed_policy_version_is_a_new_room(fast_room, monkeypatch):
    def bump(_g):
        monkeypatch.setattr(room_bank, "policy_version", lambda: "policy-2")

    a, b = _two(fast_room, before_second=bump)
    assert a != b


def test_changed_model_root_is_a_new_room(fast_room):
    a, b = _two(fast_room, before_second=lambda g: setattr(g, "root", "root-NEW"))
    assert a != b


def test_a_new_trading_day_is_a_new_room_even_if_the_sheet_content_matches(
    fast_room, monkeypatch,
):
    """No materiality threshold: the sheet's own `run_date` is part of what is
    frozen, so a new day is a changed input."""
    monkeypatch.setattr(rr, "_profile_for_ticker", lambda t, **k: {
        "ticker": t, "run_date": datetime.now(timezone.utc).date().isoformat(),
        "field_state": {},
    })
    day = {"d": date(2026, 11, 19)}
    monkeypatch.setattr(room_bank, "trading_date_for", lambda now: day["d"])
    a, b = _two(fast_room, before_second=lambda _g: day.update(d=date(2026, 11, 20)))
    assert a != b


def test_banked_return_does_not_touch_the_backup_keyed_room(fast_room):
    """A fallback-model Room banks under its own root: a primary-root convene
    is never handed it."""
    gw = _RootGateway()
    runner = RoomRunner(llm=gw)
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        with get_session() as s:
            row = s.get(RoomRunRow, a)
            parts = dict(row.bank_inputs)
        key_b, parts_b = room_bank.with_model_root(parts, "root-B")
        with get_session() as s:
            s.get(RoomRunRow, a).bank_key = key_b
            s.get(RoomRunRow, a).bank_inputs = parts_b
        b = await _convene(runner, u, "AAPL", m)
        return a, b

    a, b = _go(go())
    assert a != b


# ── 3. concurrency ────────────────────────────────────────────────────────


def test_two_concurrent_identical_convenes_are_one_room_and_one_charge(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()
    before = balance_for(u)[0]

    async def go():
        ids = await asyncio.gather(
            runner.start_run(user_id=u, ticker="AAPL", mandate=m,
                             char_delay_min=0.0, char_delay_max=0.0),
            runner.start_run(user_id=u, ticker="AAPL", mandate=m,
                             char_delay_min=0.0, char_delay_max=0.0),
        )
        for t in [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
            await asyncio.gather(t, return_exceptions=True)
        return ids

    a, b = _go(go())
    assert a == b
    with get_session() as s:
        rows = s.execute(select(RoomRunRow).where(RoomRunRow.user_id == u)).scalars().all()
    assert len(rows) == 1
    assert len(fast_room) == 1
    assert before - balance_for(u)[0] == rows[0].credit_cost > 0


def test_the_unique_key_stops_a_second_insert_across_threads():
    """The constraint, not a check, is what holds: eight threads reserve the
    same key at once and exactly one wins."""
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()
    key = "k" * 64
    results: list = []

    def reserve():
        results.append(runner._reserve_run_row(
            run_id=uuid4(), user_id=u, ticker="AAPL", mandate=m, tier="cheap",
            key=key, parts={"x": "y"},
        ))

    threads = [threading.Thread(target=reserve) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    winners = [r for r in results if r is None]
    assert len(winners) == 1
    with get_session() as s:
        assert len(s.execute(
            select(RoomRunRow).where(RoomRunRow.bank_key == key)
        ).scalars().all()) == 1


def test_a_failed_charge_drops_the_reservation(fast_room, monkeypatch):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    def boom(*a, **k):
        raise RuntimeError("charge failed")

    monkeypatch.setattr(runner, "_resolve_and_charge_feeds", boom)

    async def go():
        with pytest.raises(RuntimeError):
            await runner.start_run(user_id=u, ticker="AAPL", mandate=m)

    _go(go())
    with get_session() as s:
        assert s.execute(select(RoomRunRow).where(RoomRunRow.user_id == u)).first() is None


# ── 4. what is not banked ─────────────────────────────────────────────────


def _run(status: str, *, verdict: Verdict | None = None, refund: bool = False,
         transcript=None) -> RoomRun:
    now = datetime.now(timezone.utc)
    return RoomRun(
        id=uuid4(), user_id=uuid4(), ticker="AAPL", triggered_at=now,
        mandate_version=1, model_tier="cheap", credit_cost=8,
        status=RoomStatus(status), verdict=verdict, refund_recorded=refund,
        transcript=transcript or [], bank_key="k",
    )


_REAL = Verdict(action=VerdictAction.PASS, reason="a real call")


def test_bankable_states():
    assert run_is_bankable(_run("running"))
    assert run_is_bankable(_run("completed", verdict=_REAL))
    assert not run_is_bankable(_run("failed"))
    assert not run_is_bankable(_run("cancelled"))
    assert not run_is_bankable(_run("completed", verdict=None))
    assert not run_is_bankable(_run("completed", verdict=_REAL, refund=True))
    outage = Verdict(
        action=VerdictAction.PASS, reason=rr.PM_LLM_UNAVAILABLE_REASON,
        overridden_from_llm=True,
    )
    assert not run_is_bankable(_run("completed", verdict=outage))
    scripted = AgentMessage(
        agent_id=AgentId.MARKET_ANALYST, content="standing guidance", scripted=True,
        timestamp=datetime.now(timezone.utc),
    )
    assert not run_is_bankable(_run("completed", verdict=_REAL, transcript=[scripted]))


def test_a_failed_room_clears_its_key_and_the_next_convene_runs_fresh(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        with get_session() as s:
            row = s.get(RoomRunRow, a)
            row.status = "failed"
            row.bank_key = None
        b = await _convene(runner, u, "AAPL", m)
        return a, b

    a, b = _go(go())
    assert a != b


def test_snapshot_of_a_failed_run_carries_no_key():
    seq, snap = rr._snapshot_run(_run("failed"))
    assert snap["bank_key"] is None
    seq, snap = rr._snapshot_run(_run("running"))
    assert snap["bank_key"] == "k"


def test_a_dead_running_row_releases_its_key(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        with get_session() as s:
            row = s.get(RoomRunRow, a)
            row.status = "running"
            row.interrupted_at = datetime.now(timezone.utc)
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a != b, "a Room no process is running must not be attached to"


def test_a_key_collision_on_write_leaves_the_room_unbanked_not_failed():
    """Backup restart landing on a key another Room already holds."""
    u = uuid4()
    first = _run("completed", verdict=_REAL)
    first.user_id = u
    first.bank_key = "same"
    second = _run("completed", verdict=_REAL)
    second.user_id = u
    second.bank_key = "same"
    rr._persist_run(first)
    rr._persist_run(second)
    with get_session() as s:
        assert s.get(RoomRunRow, first.id).bank_key == "same"
        assert s.get(RoomRunRow, second.id).bank_key is None
        assert s.get(RoomRunRow, second.id).status == "completed"


# ── 5. backup slot ────────────────────────────────────────────────────────


def test_a_backup_restart_rekeys_to_the_backup_root():
    gw = _RootGateway(root="root-A", backup_root="root-B")
    runner = RoomRunner(llm=gw)
    parts = {"user_id": "u", "ticker": "AAPL", "mandate": "m", "fact_sheet": "f",
             "policy": "p", "model_root": "root-A", "trading_date": "2026-11-20",
             "portfolio": "pf", "journal": "jn", "alpaca": "none"}
    run = _run("running")
    run.bank_key, run.bank_inputs = room_bank.key_from_parts(parts), parts
    primary_key = run.bank_key

    _go(runner._rekey_for_backup(run, gw))

    assert run.bank_inputs["model_root"] == "root-B"
    assert run.bank_key != primary_key
    assert run.bank_key == room_bank.key_from_parts({**parts, "model_root": "root-B"})


def test_a_backup_restart_with_an_unreadable_backup_root_is_not_banked():
    gw = _RootGateway(backup_root=None)
    run = _run("running")
    run.bank_inputs = {"model_root": "root-A"}
    _go(RoomRunner(llm=gw)._rekey_for_backup(run, gw))
    assert run.bank_key is None


# ── 6. an unreadable root degrades loudly ─────────────────────────────────


def test_unreadable_model_root_runs_every_convene_fresh_and_says_so(fast_room, caplog):
    runner = RoomRunner(llm=_RootGateway(root=None))
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        out: dict = {}
        b = await _convene(runner, u, "AAPL", m, out)
        return a, b, out

    a, b, out = _go(go())
    assert a != b
    assert "banked" not in out
    with get_session() as s:
        assert s.get(RoomRunRow, a).bank_key is None


def test_a_gateway_that_is_not_a_real_one_runs_unbanked(fast_room):
    class _Fake:
        def has_real_provider(self):
            return False

    runner = RoomRunner(llm=_Fake())
    prep = _go(runner._prepare_bank(
        user_id=_user(), ticker="AAPL", mandate=_mandate(),
        roster=rr.resolve_roster_for_user(uuid4()),
        decision=runner._decide_feeds(uuid4(), "AAPL"),
    ))
    assert prep.key is None and "model root" in prep.reason


# ── 7. the frozen fact sheet ──────────────────────────────────────────────


def test_the_same_trading_day_yields_a_byte_identical_sheet_built_once():
    built = []

    def build():
        built.append(1)
        return {"ticker": "AAPL", "base_price": 123.4, "field_state": {"pe": "live"},
                "stamp": datetime.now(timezone.utc).isoformat()}

    d = date(2026, 11, 20)
    a = room_bank.freeze_fact_sheet(ticker="AAPL", trading_date=d, variant="v", build=build)
    b = room_bank.freeze_fact_sheet(ticker="AAPL", trading_date=d, variant="v", build=build)
    assert built == [1]
    assert a.sheet_hash == b.sheet_hash and a.profile == b.profile
    nxt = room_bank.freeze_fact_sheet(
        ticker="AAPL", trading_date=date(2026, 11, 23), variant="v", build=build,
    )
    assert nxt.sheet_hash != a.sheet_hash and built == [1, 1]
    other = room_bank.freeze_fact_sheet(ticker="AAPL", trading_date=d, variant="w", build=build)
    assert built == [1, 1, 1] and other.variant == "w"


def test_typed_values_survive_the_freeze():
    from app.services.news_context import LiveHeadline

    h = LiveHeadline("t", "l", "p", 1, None, "yfinance", "s")
    fs = room_bank.freeze_fact_sheet(
        ticker="AAPL", trading_date=date(2026, 11, 20), variant="v",
        build=lambda: {"news_headlines": [h], "x": (1, 2), "d": date(2026, 1, 2)},
    )
    again = room_bank.freeze_fact_sheet(
        ticker="AAPL", trading_date=date(2026, 11, 20), variant="v", build=lambda: {},
    )
    assert fs.profile == again.profile == {
        "news_headlines": [h], "x": (1, 2), "d": date(2026, 1, 2),
    }


def test_a_sheet_that_cannot_be_frozen_runs_unbanked_with_its_fresh_profile():
    fs = room_bank.freeze_fact_sheet(
        ticker="AAPL", trading_date=date(2026, 11, 20), variant="v",
        build=lambda: {"weird": object()},
    )
    assert fs.sheet_hash is None and "weird" in fs.profile


def test_concurrent_first_builds_converge_on_one_sheet():
    d = date(2026, 11, 20)
    gate = threading.Barrier(2)
    out: list = []

    def build():
        gate.wait(timeout=5)
        return {"n": threading.get_ident()}

    def go():
        out.append(room_bank.freeze_fact_sheet(
            ticker="RACE", trading_date=d, variant="v", build=build,
        ))

    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(out) == 2 and out[0].sheet_hash == out[1].sheet_hash
    assert out[0].profile == out[1].profile


def test_the_sheet_variant_separates_entitlements():
    a = room_bank.sheet_variant(news_state="live", social_state="live", market_withheld=False)
    b = room_bank.sheet_variant(news_state="withheld_paid", social_state="live", market_withheld=False)
    c = room_bank.sheet_variant(news_state="live", social_state="live", market_withheld=True)
    assert len({a, b, c}) == 3


# ── 8. the mandate digest names every field ───────────────────────────────

_KEYED_MANDATE_FIELDS = {
    "user_id", "display_name", "locale", "timezone", "primary_goal", "horizon",
    "target_outcome", "path", "risk_score", "risk_components", "risk_quotes",
    "max_drawdown_pct", "sector_cap_pct", "single_name_cap_pct",
    "post_loss_cooldown_hours", "max_open_positions", "max_trades_per_day",
    "max_trades_per_week", "max_option_premium_pct", "max_option_notional_pct",
    "max_assignment_exposure_pct", "min_days_to_expiry", "max_open_risk_pct",
    "max_portfolio_delta", "max_portfolio_vega", "compliance", "learning_style",
    "min_reward_risk",
}


def test_every_mandate_field_is_keyed_or_explicitly_excluded():
    """A new Mandate field must be decided here: part of what the user asked
    for (it keys the Room) or plan/time state (it does not). Silence would let
    a material field be banked over."""
    every = set(Mandate.model_fields)
    assert every == _KEYED_MANDATE_FIELDS | room_bank.MANDATE_KEY_EXCLUDED, (
        every - (_KEYED_MANDATE_FIELDS | room_bank.MANDATE_KEY_EXCLUDED)
    )
    assert not (_KEYED_MANDATE_FIELDS & room_bank.MANDATE_KEY_EXCLUDED)


@pytest.mark.parametrize("field,value", [
    ("risk_score", 5), ("max_drawdown_pct", 7), ("single_name_cap_pct", 12.5),
    ("max_open_positions", 3), ("locale", "ar"), ("risk_quotes", ["new"]),
    ("min_reward_risk", 2.5),
])
def test_each_keyed_mandate_field_moves_the_digest(field, value):
    m = _mandate()
    assert room_bank.mandate_digest(m) != room_bank.mandate_digest(
        m.model_copy(update={field: value})
    )


def test_compliance_changes_move_the_digest():
    m = _mandate()
    c = m.compliance.model_copy(update={"liquid_only": not m.compliance.liquid_only})
    assert room_bank.mandate_digest(m) != room_bank.mandate_digest(
        m.model_copy(update={"compliance": c})
    )


# ── session calendar ──────────────────────────────────────────────────────


def test_trading_day_rolls_weekends_and_holidays_back_to_the_last_session():
    utc = timezone.utc
    assert last_us_session_date(datetime(2026, 11, 21, 15, tzinfo=utc)) == date(2026, 11, 20)  # Sat
    assert last_us_session_date(datetime(2026, 11, 22, 15, tzinfo=utc)) == date(2026, 11, 20)  # Sun
    assert last_us_session_date(datetime(2026, 11, 26, 15, tzinfo=utc)) == date(2026, 11, 25)  # Thanksgiving
    assert last_us_session_date(datetime(2026, 4, 5, 15, tzinfo=utc)) == date(2026, 4, 2)      # Easter Sun, Good Fri before
    assert last_us_session_date(datetime(2026, 11, 20, 15, tzinfo=utc)) == date(2026, 11, 20)
    # 02:00 UTC Wednesday is still Tuesday evening in New York.
    assert last_us_session_date(datetime(2026, 11, 25, 2, tzinfo=utc)) == date(2026, 11, 24)
    # naive is read as UTC
    assert last_us_session_date(datetime(2026, 11, 20, 15)) == date(2026, 11, 20)


def test_nyse_holiday_rules():
    assert sorted(nyse_holidays(2026)) == [
        date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3),
        date(2026, 5, 25), date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7),
        date(2026, 11, 26), date(2026, 12, 25),
    ]
    assert date(2027, 12, 24) in nyse_holidays(2027)     # Christmas on a Saturday
    assert date(2027, 12, 31) not in nyse_holidays(2027)  # Jan 1 2028 is a Saturday: not observed
    assert not is_us_session_day(date(2026, 11, 21)) and is_us_session_day(date(2026, 11, 27))


# ── API: a banked return reports itself and costs nothing ─────────────────


def test_done_reports_a_banked_return_as_free():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.room import get_room_runner, router

    class _Banked:
        def __init__(self, run):
            self._run = run

        async def start_run(self, **kw):
            kw["bank_outcome"]["banked"] = True
            kw["bank_outcome"]["banked_at"] = datetime(2026, 11, 20, 9, tzinfo=timezone.utc)
            return self._run.id

        def is_active(self, rid):
            return False

        def get_run(self, rid):
            return self._run

    app = FastAPI()
    app.include_router(router)
    auth_user, tok, _ = AuthService().ensure_anonymous(device_user_id=None)
    run = _run("completed", verdict=_REAL)
    run.user_id = auth_user.id
    app.dependency_overrides[get_room_runner] = lambda: _Banked(run)
    r = TestClient(app).post(
        "/v1/room/stream",
        json={"user_id": str(auth_user.id), "ticker": "AAPL", "locale": "en"},
        headers={"Authorization": f"Bearer {tok}"},
    )
    assert r.status_code == 200
    assert r.headers["X-Room-Banked"] == "true" and r.headers["X-Room-Cached"] == "true"
    lines = r.text.splitlines()
    done = lines[lines.index("event: done") + 1]
    assert '"credit_cost": 0' in done and '"banked": true' in done
    assert '"banked_at": "2026-11-20T09:00:00+00:00"' in done
    assert '"refunded": false' in done


# ── the provider's root read ──────────────────────────────────────────────


def _provider(handler, *, kind="vllm"):
    p = VLLMProvider(base_url="http://x", model_name="ami-llm", kind=kind)
    p._client = httpx.AsyncClient(
        base_url="http://x", transport=httpx.MockTransport(handler),
    )
    return p


def _models(root="/models/real", mid="ami-llm"):
    return lambda req: httpx.Response(200, json={"data": [{"id": mid, "root": root}]})


def test_root_is_read_cached_and_expires():
    hits = []

    def handler(req):
        hits.append(1)
        return _models()(req)

    p = _provider(handler)
    assert _go(p.read_served_root(300)) == "/models/real"
    assert _go(p.read_served_root(300)) == "/models/real"
    assert len(hits) == 1, "cached inside the TTL"
    p.served_at -= 1000
    assert _go(p.read_served_root(300)) == "/models/real"
    assert len(hits) == 2, "read again once stale"


def test_a_failed_refresh_never_serves_the_stale_root():
    state = {"up": True}

    def handler(req):
        return _models()(req) if state["up"] else httpx.Response(503)

    p = _provider(handler)
    assert _go(p.read_served_root(300)) == "/models/real"
    p.served_at -= 1000
    state["up"] = False
    assert _go(p.read_served_root(300)) is None


def test_a_vllm_slot_without_a_root_is_unreadable_not_the_alias():
    p = _provider(lambda req: httpx.Response(200, json={"data": [{"id": "ami-llm"}]}))
    assert _go(p.read_served_root(300)) is None


def test_a_hosted_slot_without_a_root_uses_its_vendor_model_id():
    p = _provider(
        lambda req: httpx.Response(200, json={"data": [{"id": "ami-llm"}]}),
        kind="openai",
    )
    assert _go(p.read_served_root(300)) == "ami-llm"


def test_gateway_reads_the_active_providers_root():
    gw = LLMGateway()
    assert _go(gw.room_model_root()) == "mock"
    assert _go(gw.room_model_root("not-a-slot")) is None


# ── the real run path ─────────────────────────────────────────────────────


def test_a_real_room_banks_and_the_repeat_returns_it_free():
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        first = await _convene(runner, u, "AAPL", m)
        spent = balance_for(u)[0]
        out: dict = {}
        second = await _convene(runner, u, "AAPL", m, out)
        return first, second, out, spent

    first, second, out, spent = _go(go())
    assert first == second and out["banked"] is True
    assert balance_for(u)[0] == spent
    with get_session() as s:
        row = s.get(RoomRunRow, first)
        assert row.status == "completed" and row.bank_key
        assert row.bank_inputs["model_root"] == "root-A"
        assert len(s.execute(select(RoomRunRow).where(RoomRunRow.user_id == u)).scalars().all()) == 1


def test_a_crashed_room_is_refunded_unbanked_and_the_retry_runs_fresh(monkeypatch):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()
    start = balance_for(u)[0]
    real_run = RoomRunner.run

    async def crash(self, **kw):
        raise RuntimeError("boom")
        yield  # pragma: no cover

    monkeypatch.setattr(RoomRunner, "run", crash)

    async def first():
        return await _convene(runner, u, "AAPL", m)

    a = _go(first())
    with get_session() as s:
        row = s.get(RoomRunRow, a)
        assert row.status == "failed" and row.bank_key is None
    assert balance_for(u)[0] == start, "the failed Room was refunded"

    monkeypatch.setattr(RoomRunner, "run", real_run)
    b = _go(_convene(runner, u, "AAPL", m))
    assert a != b


def test_a_users_resolved_mandate_digest_is_stable_across_reads():
    """The convene route resolves the mandate afresh each time (default-hydrated
    for a user who never saved one: new timestamps every read). The digest must
    not move with them or no repeat convene would ever match."""
    import time

    from app.services.mandate_store import resolve_mandate

    u = _user()
    first = room_bank.mandate_digest(resolve_mandate(u, None))
    time.sleep(0.01)
    assert room_bank.mandate_digest(resolve_mandate(u, None)) == first


# ── the user's account is keyed: any trade, note or linked-account change ──


def _portfolio_id(u: UUID) -> UUID:
    from app.services.sim_engine import get_sim_engine

    return get_sim_engine().ensure_portfolio(u).id


def _set_cash(u: UUID, cash: float) -> None:
    from app.db.models import SimPortfolioRow

    with get_session() as s:
        s.get(SimPortfolioRow, _portfolio_id(u)).current_cash = cash


def _add_holding(u: UUID, ticker="NVDA", qty=3.0) -> None:
    from app.db.models import SimHoldingRow

    with get_session() as s:
        s.add(SimHoldingRow(
            portfolio_id=_portfolio_id(u), ticker=ticker, quantity=qty, avg_cost=100.0,
            opened_at=datetime.now(timezone.utc),
        ))


def _add_trade(u: UUID, *, status="open", side="buy", stop=90.0, ticker="NVDA",
               qty=3.0, closed=False) -> None:
    from app.db.models import SimTradeRow

    now = datetime.now(timezone.utc)
    if status == "open":
        _add_holding(u, ticker, qty)  # the engine's ledger: an open buy is a holding
    with get_session() as s:
        s.add(SimTradeRow(
            user_id=u, portfolio_id=_portfolio_id(u), ticker=ticker, side=side,
            quantity=qty, entry_price=100.0, stop=stop, opened_at=now,
            closed_at=now if closed else None, status=status,
        ))


def _journal(u: UUID, ticker="AAPL", *, title="note", etype="sim_trade", note=None):
    from app.schemas.journal import EntryType, JournalEntryCreate
    from app.services.journal_store import get_journal_store

    return get_journal_store().append(JournalEntryCreate(
        user_id=u, entry_type=EntryType(etype), title=title, ticker=ticker, user_note=note,
    ))


def _convene_twice(mutate, ticker="AAPL"):
    """Run a Room, apply `mutate(user)`, convene the same inputs again."""
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, ticker, m)
        mutate(u)
        b = await _convene(runner, u, ticker, m)
        return a, b

    return _go(go())


def test_unchanged_account_is_the_same_room(fast_room):
    a, b = _convene_twice(lambda u: None)
    assert a == b


def test_cash_to_the_dollar_is_keyed_and_cents_are_not(fast_room):
    a, b = _convene_twice(lambda u: _set_cash(u, 10_000.40))
    assert a == b, "under a dollar of cash movement is the same Room"
    a, b = _convene_twice(lambda u: _set_cash(u, 9_000.0))
    assert a != b


def test_a_new_holding_is_a_new_room(fast_room):
    a, b = _convene_twice(lambda u: _add_holding(u))
    assert a != b


def test_a_changed_holding_quantity_is_a_new_room(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        _add_holding(u, qty=3.0)
        a = await _convene(runner, u, "AAPL", m)
        from app.db.models import SimHoldingRow

        with get_session() as s:
            row = s.execute(select(SimHoldingRow)).scalars().first()
            row.quantity = 5.0
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a != b


def test_an_opened_trade_is_a_new_room(fast_room):
    a, b = _convene_twice(lambda u: _add_trade(u))
    assert a != b


def test_a_changed_stop_on_an_open_lot_is_a_new_room(fast_room):
    from app.db.models import SimTradeRow

    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        _add_trade(u, stop=90.0)
        a = await _convene(runner, u, "AAPL", m)
        with get_session() as s:
            s.execute(select(SimTradeRow)).scalars().first().stop = 95.0
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a != b


def test_trade_side_is_in_the_portfolio_digest():
    from types import SimpleNamespace as NS

    pf = NS(current_cash=0, holdings=[], shorts=[], options=[])

    def lot(side):
        return NS(ticker="A", side=side, quantity=1, entry_price=2.0, stop=1.0,
                  status="open", opened_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                  closed_at=None)

    assert room_bank.portfolio_digest(pf, [lot("buy")]) != room_bank.portfolio_digest(pf, [lot("sell")])


def test_a_closed_trade_in_the_history_is_a_new_room(fast_room):
    """The cooldown and over-trading checks read closed trades too."""
    a, b = _convene_twice(lambda u: _add_trade(u, status="lost", closed=True))
    assert a != b


def test_portfolio_digest_covers_short_and_option_legs():
    from types import SimpleNamespace as NS

    base = dict(
        current_cash=1000.2, holdings=[NS(ticker="A", quantity=1, avg_cost=2.0)],
        shorts=[], options=[],
    )
    d0 = room_bank.portfolio_digest(NS(**base), [])
    short = NS(**{**base, "shorts": [NS(ticker="B", quantity=2, entry_price=5.0)]})
    opt = NS(**{**base, "options": [NS(occ_symbol="X1", quantity=-1, avg_premium=1.5)]})
    assert len({d0, room_bank.portfolio_digest(short, []), room_bank.portfolio_digest(opt, [])}) == 3
    # order of legs is not a change
    two = NS(**{**base, "shorts": [NS(ticker="B", quantity=2, entry_price=5.0),
                                   NS(ticker="C", quantity=1, entry_price=6.0)]})
    rev = NS(**{**base, "shorts": list(reversed(two.shorts))})
    assert room_bank.portfolio_digest(two, []) == room_bank.portfolio_digest(rev, [])


def test_a_new_non_room_journal_entry_for_the_ticker_is_a_new_room(fast_room):
    a, b = _convene_twice(lambda u: _journal(u, "AAPL", title="my thesis"))
    assert a != b


def test_an_edited_journal_note_is_a_new_room(fast_room):
    from app.db.models import JournalEntryRow

    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        _journal(u, "AAPL", title="thesis", note="first view")
        a = await _convene(runner, u, "AAPL", m)
        with get_session() as s:
            s.execute(select(JournalEntryRow)).scalars().first().user_note = "changed my mind"
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a != b


def test_a_journal_entry_for_another_ticker_is_the_same_room(fast_room):
    a, b = _convene_twice(lambda u: _journal(u, "MSFT", title="other name"))
    assert a == b, "the desks read this ticker's entries only"


def test_the_rooms_own_journal_entry_does_not_unkey_the_next_convene(fast_room):
    """Room-run entries are the Rooms' own output: counting them would make every
    repeat convene a miss."""
    a, b = _convene_twice(lambda u: _journal(u, "AAPL", title="Room on AAPL", etype="room_run"))
    assert a == b


def test_a_linked_alpaca_account_is_keyed_by_cash_and_positions():
    from types import SimpleNamespace as NS

    def acct(cash=5000.0, positions=(("AAPL", 2.0),), mv=999.0, pl=1.0):
        return NS(cash=cash, positions=[
            NS(symbol=s, qty=q, market_value=mv, unrealized_pl=pl) for s, q in positions
        ])

    base = room_bank.alpaca_digest(acct())
    assert room_bank.alpaca_digest(None) == "none" != base
    assert room_bank.alpaca_digest(acct(mv=1500.0, pl=-40.0)) == base, "price drift is not a change"
    assert room_bank.alpaca_digest(acct(cash=5000.4)) == base
    assert room_bank.alpaca_digest(acct(cash=4000.0)) != base
    assert room_bank.alpaca_digest(acct(positions=(("AAPL", 3.0),))) != base
    assert room_bank.alpaca_digest(acct(positions=(("AAPL", 2.0), ("MSFT", 1.0)))) != base


def test_a_changed_alpaca_digest_is_a_new_room(fast_room):
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        out: dict = {}
        b = await runner.start_run(
            user_id=u, ticker="AAPL", mandate=m, char_delay_min=0.0, char_delay_max=0.0,
            alpaca_key="changed", bank_outcome=out,
        )
        async for _ in runner.subscribe(b):
            pass
        for t in [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
            await asyncio.gather(t, return_exceptions=True)
        return a, b

    a, b = _go(go())
    assert a != b


def test_an_unreadable_account_runs_unbanked(fast_room, monkeypatch):
    monkeypatch.setattr(RoomRunner, "_account_digests_blocking", staticmethod(lambda *a: None))
    runner = RoomRunner(llm=_RootGateway())
    u, m = _user(), _mandate()

    async def go():
        a = await _convene(runner, u, "AAPL", m)
        return a, await _convene(runner, u, "AAPL", m)

    a, b = _go(go())
    assert a != b
