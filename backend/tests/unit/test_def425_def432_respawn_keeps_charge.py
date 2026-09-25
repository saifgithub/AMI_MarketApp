"""DEF425 round 4 / DEF432 round 2 — the respawn drops the real charge.

One root, found by the auditor across both lanes' round-3/round-1 reviews:
`_respawn_run_from_row` called `self.run(...)` without `credit_cost`
(`room_runner.py`). `_PendingRetry` had no field to carry it. So `run()` fell
back to `room_cost_for_plan(plan)` (base price only), and `_persist_run`
overwrote `row.credit_cost` with that lower figure — losing whatever CR090
live-data surcharge the ORIGINAL `start_run()` had actually charged, before
any refund ever reads the row.

Measured (auditor u66, DEF425 round 3): a Trader user charged base 8 +
surcharge 4 = 12, respawned once, then refunded on retry-exhaustion, got back
only 8 — down 4 credits net, on the exact restart-mid-Room scenario DEF425
exists to make whole. The same overwritten figure is what DEF432's outage
refund reads too (`room_runner.py`'s `run_was_refunded` branch), so a
respawned Room that dies to an outage NO_VERDICT gives back the same short
amount.

Fix: `_PendingRetry` gained a `credit_cost: int` field, filled from
`row.credit_cost` at claim time in `_sweep_stuck_runs`, and threaded through
as `credit_cost=p.credit_cost` into the respawn's `self.run(...)` call in
`_respawn_run_from_row`. `run()` then never falls back to base pricing for a
respawned row, so `_persist_run` never overwrites the real charge, and every
refund path that reads `row.credit_cost` afterwards (this sweep's own
retry-exhausted refund, CR039's failed-run refund, DEF432's outage refund)
gives back the full amount.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.config import settings as real_settings
from app.db import get_session
from app.db.models import RoomRunRow
from app.services import room_runner as room_runner_mod
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import balance_for, spend
from app.services.mandate_store import get_mandate_store
from app.services.room_runner import MAX_AUTO_RETRIES, RoomRunner
from tests.unit.test_def425_shutdown_cancel_no_refund_gap import _billed_user, _row

pytestmark = pytest.mark.allow_ledger_drift

SURCHARGED_COST = 12  # base 8 + CR090 live-data surcharge 4


class _PartialOutageGateway:
    """Same fixture `test_def432_room_outage_refund.py` uses: answers the
    CIO properly, starves the first `fail_n` other desks (empty stream ->
    scripted fallback turn) so the Room ends CR219 R51's outage NO_VERDICT."""

    def __init__(self, fail_n: int):
        self.fail_n = fail_n
        self.failed = 0

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the chief investment officer" in system_prompt.lower():
            yield (
                '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, '
                '"stop": 141, "target": 172, "horizon_days": 42, '
                '"narration": "Synthesis defended; the mandate clears at '
                'this size."}'
            )
            return
        if self.failed < self.fail_n:
            self.failed += 1
            return  # empty stream -> scripted fallback
        yield "AMI agent live reply with a real contribution."


def _seed_surcharged_stuck_row(user_id, credit_cost=SURCHARGED_COST, retry_count=0):
    run_id = uuid4()
    started_at = datetime.now(timezone.utc) - timedelta(hours=1)
    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id,
            user_id=user_id,
            ticker="AAPL",
            triggered_at=started_at,
            started_at=started_at,
            mandate_version=1,
            model_tier="mid",
            rounds=1,
            transcript=[],
            verdict=None,
            credit_cost=credit_cost,
            status="running",
            retry_count=retry_count,
        ))
    return run_id


# ── 1: after a respawn, row.credit_cost still holds the real charge ──────


def test_respawn_keeps_the_surcharged_credit_cost_on_the_row():
    user_id = _billed_user()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    run_id = _seed_surcharged_stuck_row(user_id, credit_cost=SURCHARGED_COST)
    spend(user_id, SURCHARGED_COST, reason=f"room:AAPL:{run_id}")

    runner = RoomRunner()  # __init__ sweep claims the stuck row
    assert len(runner._pending_retry) == 1
    assert runner._pending_retry[0].credit_cost == SURCHARGED_COST

    asyncio.run(runner.resume_pending_retries())

    async def _drain():
        async for _ in runner.subscribe(run_id):
            pass

    asyncio.run(_drain())

    row = _row(run_id)
    assert row.credit_cost == SURCHARGED_COST, (
        "the respawn must not overwrite the row's real charge with the "
        "plan's base price — this is the root DEF425/DEF432 share"
    )


# ── 2: a retry-exhausted sweep refund returns the FULL surcharged amount ──


def test_retry_exhausted_respawn_refunds_the_full_surcharge_net_zero():
    user_id = _billed_user()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    # retry_count already at MAX_AUTO_RETRIES - 1 so ONE more claim (this
    # respawn) plus its own later sweep exhausts it in this same test's
    # second RoomRunner() boot.
    run_id = _seed_surcharged_stuck_row(
        user_id, credit_cost=SURCHARGED_COST, retry_count=MAX_AUTO_RETRIES - 1,
    )
    spend(user_id, SURCHARGED_COST, reason=f"room:AAPL:{run_id}")
    before = balance_for(user_id)[0]

    # Boot 1: claim + respawn. The respawn's own gateway is irrelevant here —
    # simulate a SECOND shutdown landing mid-retry by never letting it finish;
    # instead re-seed status=running (as a stuck respawn would be found) and
    # let boot 2's sweep see retry_count now at MAX_AUTO_RETRIES.
    runner = RoomRunner()
    assert len(runner._pending_retry) == 1
    assert runner._pending_retry[0].credit_cost == SURCHARGED_COST

    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one()
        assert row.retry_count == MAX_AUTO_RETRIES
        assert row.credit_cost == SURCHARGED_COST, (
            "the sweep's own claim must not touch credit_cost"
        )

    # Boot 2: this row is now at MAX_AUTO_RETRIES and still "running" (it was
    # never actually respawned in this test — standing in for a SECOND
    # shutdown landing mid-retry). Mark it `interrupted_at` the way the real
    # shutdown branch would, so the sweep claims it at ANY age rather than
    # needing the 30-minute cutoff — the next sweep exhausts it and refunds
    # off row.credit_cost.
    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one()
        row.interrupted_at = datetime.now(timezone.utc)

    RoomRunner()

    with get_session() as s:
        row = s.execute(
            select(RoomRunRow).where(RoomRunRow.id == run_id)
        ).scalar_one()
        assert row.status == "failed"

    assert balance_for(user_id)[0] == before + SURCHARGED_COST, (
        "the retry-exhausted refund must return the FULL surcharged charge "
        "the row actually held, not the plan's base price"
    )


# ── 3: a respawned Room that ends in the outage NO_VERDICT refunds in full ─


def test_respawned_room_ending_in_outage_no_verdict_refunds_in_full():
    """Reuses the DEF432 down-gateway fixture, driven through the RESPAWN
    path (`_respawn_run_from_row`, not a direct `run()` call) so the
    `credit_cost` thread-through is what's under test, not the outage
    detection itself (already covered by DEF432's own suite)."""
    user_id = _billed_user()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    before = balance_for(user_id)[0]
    run_id = _seed_surcharged_stuck_row(user_id, credit_cost=SURCHARGED_COST)
    spend(user_id, SURCHARGED_COST, reason=f"room:AAPL:{run_id}")
    assert balance_for(user_id)[0] == before - SURCHARGED_COST

    runner = RoomRunner(llm=_PartialOutageGateway(fail_n=4))  # type: ignore[arg-type]

    async def _go():
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(real_settings, "room_max_scripted_turns", 4)
            mp.setattr(room_runner_mod.settings, "room_max_scripted_turns", 4)
            await runner.resume_pending_retries()
            async for _ in runner.subscribe(run_id):
                pass

    asyncio.run(_go())

    row = _row(run_id)
    assert row.status == "completed"
    assert row.credit_cost == SURCHARGED_COST, (
        "the outage refund reads row.credit_cost — it must still hold the "
        "real surcharged figure, not the base price the pre-fix respawn "
        "would have overwritten it with"
    )
    assert room_runner_mod.room_verdict_is_incomplete(row.verdict)
    assert balance_for(user_id)[0] == before, (
        "a respawned Room that ends in the outage NO_VERDICT must net the "
        "user back to their pre-charge balance, for the FULL surcharged "
        "amount — DEF425 and DEF432 sharing one root"
    )


# ── 4: the live_data_notice.surcharge_charged event reports the real 4 ────


def test_respawn_live_data_notice_reports_the_real_surcharge():
    user_id = _billed_user()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    run_id = _seed_surcharged_stuck_row(user_id, credit_cost=SURCHARGED_COST)
    spend(user_id, SURCHARGED_COST, reason=f"room:AAPL:{run_id}")

    runner = RoomRunner()
    assert len(runner._pending_retry) == 1
    p = runner._pending_retry[0]
    assert p.credit_cost == SURCHARGED_COST

    # `_respawn_run_from_row` pumps its events into a queue consumed via
    # subscribe(), not returned directly — so exercise the underlying
    # `run()` call with the SAME `credit_cost` the respawn now threads
    # through (`credit_cost=p.credit_cost`, exactly as
    # `_respawn_run_from_row` passes it). This isolates the
    # live_data_notice assertion from the respawn's queue/subscribe
    # plumbing, which tests 1-3 already cover end-to-end.
    async def _direct():
        return [
            ev async for ev in runner.run(
                run_id=p.run_id, user_id=p.user_id, ticker=p.ticker,
                mandate=mandate, credit_cost=p.credit_cost,
                char_delay_min=0.0, char_delay_max=0.0,
            )
        ]

    all_events = asyncio.run(_direct())
    notices = [e for e in all_events if e.kind == "live_data_notice"]
    assert len(notices) == 1
    assert notices[0].live_data["surcharge_charged"] == (
        SURCHARGED_COST - room_runner_mod.room_cost_for_plan(
            room_runner_mod.effective_plan_for_user(user_id)
        )
    ), "the respawned run's live_data_notice must report the REAL surcharge, not 0"
