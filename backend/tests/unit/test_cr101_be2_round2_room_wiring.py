"""CR101-BE2 round 2 — regression tests driven THROUGH the Room path, not by
calling `check_mandate_compliance` directly with context hand-populated.

Round 1's own acceptance tests (`test_cr101_be2_new_risk_limits.py`) all drove the
floor directly, so all four mutations went RED correctly — but nothing exercised
`room_runner`'s own call sites, so nothing measured the silent-skip default those
call sites actually hit. The architect's round-1 finding: `room_runner.py`'s
scripted-path check (`_assemble_verdict`) and the LLM-override wrapper
(`enforce_safety_floor`, called from the live-PM path) supplied NONE of the
post-loss cooldown / over-trading / open-risk context `sim_engine.py` builds for
its own `check_mandate_compliance` calls — three of the four new limits were
silently unenforced on the path the user actually watches.

These tests build real `sim_trades` rows via the DB (the same table
`SimEngine._risk_limit_context` reads) and go through `_build_room_risk_limit_context`
+ `_assemble_verdict` (scripted path) or a full `RoomRunner.run()` (live-PM path) —
never a direct `check_mandate_compliance(..., last_loss_closed_at=...)` call. Each
would fail against round-1's code (which passed none of this context at either
site) and each mutation below is reverted immediately after being shown RED.
"""

from __future__ import annotations

import app.agents.safety_floor as safety_floor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.db import get_session
from app.db.models import SimTradeRow
from app.schemas import Mandate
from app.schemas.room import VerdictAction
from app.schemas.trade import ProposedTrade
from app.services.classification_universe import default_classification_universe
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import (
    RoomRunner,
    _assemble_verdict,
    _build_room_risk_limit_context,
    _RoomContext,
)
from app.services.sharia_universe import default_halal_universe
from app.services.sim_engine import get_sim_engine

# SQLite (this suite's fixture DB) drops tzinfo on datetime round-trip — Postgres
# (Alpha/prod) does not, so this is a test-environment-only mismatch, never a
# production one. `check_mandate_compliance`'s default clock is
# `datetime.now(timezone.utc)` (aware); a trade's `opened_at`/`closed_at` read back
# from this fixture DB is naive — comparing the two raises TypeError. These tests
# freeze `safety_floor`'s clock to a naive value matching the fixture round-trip,
# rather than touching production datetime handling (out of this lane's scope).
_FIXED_NOW = datetime(2026, 7, 30, 12, 0)


class _FrozenClock(datetime):
    @classmethod
    def now(cls, tz=None):  # noqa: D102 — matches datetime.now's own signature
        return _FIXED_NOW


def _insert_trade(
    user_id,
    *,
    ticker: str = "AAPL",
    status: str = "open",
    opened_at: datetime,
    closed_at: datetime | None = None,
    quantity: float = 1.0,
    entry_price: float = 100.0,
    stop: float | None = None,
) -> None:
    """Writes a real `sim_trades` row — the same table `SimEngine.list_trades` /
    `_risk_limit_context` read. Not a fixture double: this is what makes these
    tests exercise the Room's OWN wiring rather than a hand-populated context."""
    sim = get_sim_engine()
    portfolio = sim.ensure_portfolio(user_id)
    with get_session() as s:
        s.add(SimTradeRow(
            user_id=user_id,
            portfolio_id=portfolio.id,
            ticker=ticker,
            side="buy",
            quantity=quantity,
            entry_price=entry_price,
            stop=stop,
            opened_at=opened_at,
            closed_at=closed_at,
            status=status,
        ))
        s.commit()


def _ctx_for(
    user_id, mandate: Mandate, *, ticker: str = "MSFT", portfolio_value: float = 10_000.0,
) -> _RoomContext:
    """Builds a `_RoomContext` the SAME way `room_runner.run()` does: through
    `_build_room_risk_limit_context`, not by hand-setting `ctx.risk_*` fields."""
    last_loss, trade_ts, open_risk = _build_room_risk_limit_context(
        user_id, portfolio_value=portfolio_value, quotes={},
    )
    return _RoomContext(
        ticker=ticker,
        mandate=mandate,
        portfolio_value=portfolio_value,
        current_drawdown_pct=0.0,
        halal_universe=default_halal_universe(),
        classification_universe=default_classification_universe(),
        locale_allowed_universe=None,
        user_id=user_id,
        risk_last_loss_closed_at=last_loss,
        risk_trade_open_timestamps=trade_ts,
        risk_existing_open_risk_pct=open_risk,
    )


# ── scripted path (room_runner.py:_assemble_verdict) ───────────────────────


def test_room_scripted_path_blocks_a_buy_during_post_loss_cooldown(
    base_mandate: Mandate, monkeypatch: pytest.MonkeyPatch,
):
    """A stop-out 1 minute ago against a 24h cooldown must reject the next
    scripted-path BUY. Round-1 code never passed `last_loss_closed_at` here —
    this would come back APPROVE against it."""
    monkeypatch.setattr(safety_floor, "datetime", _FrozenClock)
    user_id = uuid4()
    mandate = base_mandate.model_copy(update={"post_loss_cooldown_hours": 24.0})
    _insert_trade(
        user_id, ticker="TSLA", status="lost",
        opened_at=_FIXED_NOW - timedelta(days=2), closed_at=_FIXED_NOW - timedelta(minutes=1),
    )
    ctx = _ctx_for(user_id, mandate)
    verdict = _assemble_verdict(ctx, profile={})
    assert verdict.action == VerdictAction.REJECT
    assert any("cooldown" in v.lower() for v in verdict.violations)


def test_room_scripted_path_blocks_over_trading_per_day(
    base_mandate: Mandate, monkeypatch: pytest.MonkeyPatch,
):
    """A cap of 1 trade/day, one already opened today, must reject the next
    scripted-path BUY. Round-1 code never passed `trade_open_timestamps` here —
    this would come back APPROVE against it."""
    monkeypatch.setattr(safety_floor, "datetime", _FrozenClock)
    user_id = uuid4()
    mandate = base_mandate.model_copy(update={"max_trades_per_day": 1})
    _insert_trade(user_id, ticker="AAPL", status="open", opened_at=_FIXED_NOW)
    ctx = _ctx_for(user_id, mandate)
    verdict = _assemble_verdict(ctx, profile={})
    assert verdict.action == VerdictAction.REJECT
    assert any("max trades per day" in v.lower() for v in verdict.violations)


def test_room_scripted_path_blocks_a_buy_over_the_open_risk_cap(base_mandate: Mandate):
    """An existing open position sized/stopped to carry 5.0 open-risk points
    against a 1.0 cap must reject the next scripted-path BUY. Round-1 code never
    passed `existing_open_risk_pct` here — this would come back APPROVE against
    it (the sum collapses to 0.0)."""
    user_id = uuid4()
    mandate = base_mandate.model_copy(update={"max_open_risk_pct": 1.0})
    # 50% of a $10k book at entry 100 / stop 90 (10% stop distance) = 5.0 open-risk
    # points — see trading_math.risk_limits.position_risk_contribution.
    _insert_trade(
        user_id, ticker="NVDA", status="open", opened_at=datetime.now(timezone.utc),
        quantity=50.0, entry_price=100.0, stop=90.0,
    )
    ctx = _ctx_for(user_id, mandate)
    verdict = _assemble_verdict(ctx, profile={})
    assert verdict.action == VerdictAction.REJECT
    assert any("open risk" in v.lower() for v in verdict.violations)


# ── live-PM path (room_runner.py -> enforce_safety_floor) ──────────────────


class _LiberalPmGateway:
    """A fake LLMGateway whose PM always APPROVEs — used to prove the
    deterministic safety floor (not the LLM) vetoes the trade via
    `enforce_safety_floor`, the LLM-override wrapper named in the round-1 finding."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                           locale="en", max_tokens=1024, **_audit):
        if "speak as the portfolio manager" in system_prompt.lower():
            text = (
                '{"action": "APPROVE", "size_pct": 3.0, "entry": 100, '
                '"stop": 94, "target": 113, "horizon_days": 42, '
                '"narration": "PM: APPROVE."}'
            )
        else:
            text = "Agent reply."
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


def _collect(coro_gen) -> list:
    import asyncio

    async def run():
        events = []
        async for ev in coro_gen:
            events.append(ev)
        return events
    return asyncio.run(run())


def test_room_live_pm_enforce_safety_floor_rejects_a_post_loss_cooldown_approve(
    monkeypatch: pytest.MonkeyPatch,
):
    """The live-PM path's `enforce_safety_floor` call must veto a PM APPROVE made
    during an active post-loss cooldown. Round-1 code never passed
    `last_loss_closed_at` at this call site either — this would come back the
    PM's raw APPROVE against it."""
    monkeypatch.setattr(safety_floor, "datetime", _FrozenClock)
    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3}).model_copy(
        update={"post_loss_cooldown_hours": 24.0}
    )
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)
    _insert_trade(
        user_id, ticker="TSLA", status="lost",
        opened_at=_FIXED_NOW - timedelta(days=2), closed_at=_FIXED_NOW - timedelta(minutes=1),
    )
    portfolio_value = sim.total_value(user_id)
    runner = RoomRunner(llm=_LiberalPmGateway())  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=portfolio_value,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.REJECT.value
    assert v.overridden_from_llm is True
    # Auditor M4: asserting only `"cooldown" in vio` cannot tell a REAL cooldown veto
    # from the loud missing-context veto, because the fallback text
    # ("post-loss cooldown is set on the mandate but the caller did not supply …")
    # contains that substring too. The auditor proved it: dropping all five kwargs at
    # this call site left the suite GREEN. Pin the veto that only the WIRED path can
    # produce — the computed lift time — and explicitly refuse the fallback wording.
    assert any("active until" in vio.lower() for vio in v.violations), v.violations
    assert not any("did not supply" in vio.lower() for vio in v.violations), (
        "the live-PM call site stopped supplying its risk-limit context: this is the "
        "loud missing-context veto, not a real cooldown veto"
    )


def test_room_risk_limit_context_degrades_loudly_when_the_db_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    """Auditor M5. `_build_room_risk_limit_context`'s outage branch must return the
    sentinel, NOT plausible-looking real values.

    The auditor flipped that branch's return from `(CONTEXT_NOT_SUPPLIED, None, None)`
    to `(None, [], 0.0)` and the whole suite stayed GREEN — nothing pinned it. That
    tuple is the dangerous one precisely because every element reads as a legitimate
    measurement: "no prior loss", "no trades today", "zero open risk". Under it, a
    database outage would silently disable every risk limit the user explicitly set,
    on exactly the Room path the round-1 BLOCKER was about, and the floor would report
    a clean pass. Losing enforcement during an outage is survivable; not being able to
    tell that it happened is not (CR040).
    """
    from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED

    def _boom(*_a, **_k):
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr("app.services.room_runner.get_sim_engine", _boom)

    last_loss, timestamps, open_risk = _build_room_risk_limit_context(
        uuid4(), portfolio_value=100_000.0, quotes={},
    )

    assert last_loss is CONTEXT_NOT_SUPPLIED, (
        "an outage must be distinguishable from 'this user has never had a loss' — "
        "a real None here is a legitimate value and would silently pass the cooldown"
    )
    assert timestamps is None, "None means 'not supplied'; [] would read as 'no trades'"
    assert open_risk is None, "None means 'not supplied'; 0.0 would read as 'no risk'"


def test_a_set_limit_blocks_loudly_when_the_room_context_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    """The other half of M5: prove the sentinel actually reaches the floor and blocks.

    Asserting the tuple's shape only pins the helper. This pins the CONSEQUENCE — that
    a user with a cooldown set is not silently waved through during an outage.
    """
    monkeypatch.setattr(safety_floor, "datetime", _FrozenClock)

    def _boom(*_a, **_k):
        raise RuntimeError("simulated database outage")

    monkeypatch.setattr("app.services.room_runner.get_sim_engine", _boom)

    last_loss, timestamps, open_risk = _build_room_risk_limit_context(
        uuid4(), portfolio_value=100_000.0, quotes={},
    )
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3}).model_copy(
        update={"post_loss_cooldown_hours": 24.0}
    )
    result = safety_floor.check_mandate_compliance(
        ProposedTrade(ticker="AAPL", side="buy", quantity=10.0),
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
        last_loss_closed_at=last_loss,
        trade_open_timestamps=timestamps,
        existing_open_risk_pct=open_risk,
    )

    assert result.passed is False, (
        "an outage silently disabled a limit the user explicitly set — this is the "
        "round-1 BLOCKER's failure mode arriving by a different route"
    )
    assert any("did not supply" in v.lower() for v in result.violations), result.violations
