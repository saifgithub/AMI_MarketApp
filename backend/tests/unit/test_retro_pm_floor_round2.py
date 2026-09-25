"""RETRO-PM-FLOOR round 1 (auditor U68) — MAJOR-1 and MAJOR-2 fixes.

`orchestration/audit/cr/RETRO-PM-FLOOR.auditor.md` found two paths where a Room
verdict reaches a user without the safety floor holding — both the floor being
fed a real-looking value in place of a missing one (the CR101-BE2 round-1
BLOCKER shape, surviving on two call paths it did not reach):

MAJOR-1 — `_respawn_run_from_row` (a post-reboot resume of a stuck run) calls
`self.run()` without `portfolio_value`/`current_drawdown_pct`, so `run()`'s
defaults (`$100,000`, `0%` drawdown) are what the floor judges the resumed
convene against. A user actually at/over their drawdown cap gets APPROVE on
the respawned path where the normal (`api/room.py`) path gives REJECT.
Fixed by resolving the user's REAL snapshot (`sim.valuation_snapshot`, the same
call `api/room.py` makes) before respawning; if that snapshot cannot be read,
the run is failed loudly (never silently re-run against a fabricated number).

MAJOR-2 — `_build_room_sector_context` returns `[], {}, None, {}` on ANY
exception, including one from the marks fetch or `allocate_by_sector` that has
nothing to do with sector data. `holdings=[]` reaches `enforce_safety_floor` as
a REAL empty book (`check_mandate_compliance`'s own contract: `holdings=None`
means "not supplied, block loudly"; a real value is never `None`), so rule 6d
(max open positions) counts zero held tickers and passes — REJECT normally,
APPROVE on the failure. Fixed by fetching holdings independently of the sector
resolver, so a resolver failure costs the sector cap ONLY, and reporting a
holdings-read failure as `None` (loud 6d block), never `[]` (a silent pass).

Both tests are written from the auditor's own reproductions: construct the
control (the normal path's REJECT) and the failure path (the pre-fix APPROVE),
and assert the failure path now matches the control.

MINOR-1 — with `pm_self_consistency_samples > 1`, if every draw AND every
reformat-retry replacement is unparseable, the vote's candidate list (`_cands`)
is empty and the verdict tail fell into the single-draw branch, shipping the
FIRST raw draw's reformatted read as if it were a normal single-draw verdict —
`samples`/`approve_votes` stayed `None` (the schema's own "self-consistency is
off" meaning, false here) and no disclosure said only one, unlabelled read
produced the verdict. Fixed by labelling that case explicitly.

MINOR-2 — DEF398's `extract_json_object` takes the FIRST complete JSON object
in a reply (`raw_decode`), so a reply carrying a draft `{"action":"APPROVE",…}`
followed by a retraction and a final `{"action":"PASS",…}` reads as APPROVE —
reachable only when CR210's grammar is not enforced (an `unsupported`
provider). Fixed by failing safe (treating the reply as unparseable) when the
tail after the first object contains a second complete object with a
different `action`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.core.config import settings
from app.db import get_session
from app.db.models import RoomRunRow, SimHoldingRow
from app.schemas.room import RoomStatus, VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.mandate_store import get_mandate_store
from app.services.room_runner import RoomRunner, _PendingRetry, _build_room_sector_context
from app.services.sim_engine import get_sim_engine

from tests.unit.test_cr101_be2_round2_room_wiring import _collect, _LiberalPmGateway

pytestmark = pytest.mark.allow_ledger_drift


class _AllUnparseablePmGateway:
    """A fake LLMGateway whose PM NEVER produces a parseable verdict on any of
    the `samples` independent draws (nor the replacement round) — the
    auditor's MINOR-1 "zero-readable vote" probe. The one-shot DEF058
    reformat retry (only reached for the FIRST raw draw, per
    `_draw_pm_candidates`'s contract) DOES recover a verdict, matching the
    auditor's own measurement (`reformat_calls=1`, an APPROVE recovered) —
    this is the "one reformatted draw ships, unlabelled" shape MINOR-1
    targets, not the unrelated "reformat also fails" case."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                           locale="en", max_tokens=1024, **_audit):
        if "strict formatter" in system_prompt.lower():
            text = (
                '{"action": "APPROVE", "size_pct": 3.0, "entry": 100, '
                '"stop": 94, "target": 113, "horizon_days": 42, '
                '"narration": "Recovered by the reformatter."}'
            )
        elif "chief investment officer" in system_prompt.lower():
            text = "I am thinking about this trade and will decide shortly."
        else:
            text = "Agent reply."
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


# ─────────────────────────────────────────────────────────────────────────────
# MAJOR-1 — respawn must judge the floor against the REAL portfolio, not the
# `run()` defaults ($100k / 0% drawdown).
# ─────────────────────────────────────────────────────────────────────────────


def _drawn_down_user(*, loss_frac: float = 0.5) -> "uuid4":
    """A user whose sim portfolio is real, and really drawn down.

    Drawdown is computed against `starting_capital` (`Portfolio.total_drawdown_pct`
    — no separate high-water-mark column), so writing `current_cash` down
    directly is a genuine drawdown `valuation_snapshot` reads back honestly,
    without a live yfinance fill.
    """
    from app.db.models import SimPortfolioRow

    user_id = uuid4()
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)
    with get_session() as s:
        from sqlalchemy import select as _select

        row = s.execute(
            _select(SimPortfolioRow).where(SimPortfolioRow.user_id == user_id)
        ).scalar_one()
        row.current_cash = float(row.starting_capital) * (1 - loss_frac)
        s.commit()
    return user_id


def test_respawn_reads_the_real_portfolio_not_the_run_defaults(
    monkeypatch: pytest.MonkeyPatch,
):
    """The auditor's MAJOR-1 probe: same user, same always-APPROVE PM, two
    entry points — `api`-shaped call (real pv/dd) vs `_respawn_run_from_row`
    (pre-fix: no pv/dd, `run()`'s $100k/0% defaults). Both must REJECT.

    Pre-fix this is red: the respawn path calls `self.run(...)` with neither
    kwarg, `current_drawdown_pct` defaults to 0.0, rule 7 (drawdown) can never
    fire, and `portfolio_value` defaults to $100k so the sector/position caps
    read a book ~20x too large for this user — the always-APPROVE PM's verdict
    reaches the floor and clears it, landing APPROVE where the real path REJECTs.
    """
    user_id = _drawn_down_user(loss_frac=0.5)
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3}).model_copy(
        update={"max_drawdown_pct": 30}
    )
    get_mandate_store().upsert(user_id, mandate)

    sim = get_sim_engine()
    real_pv, real_dd = sim.valuation_snapshot(user_id)
    assert real_dd >= 30.0, f"fixture did not actually draw the user down: {real_dd}"

    # Control: the normal (api/room.py-shaped) call, real pv/dd supplied.
    control_events = _collect(RoomRunner(llm=_LiberalPmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=real_pv, current_drawdown_pct=real_dd,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    control_verdict = next(e.verdict for e in control_events if e.kind == "verdict")
    assert control_verdict.action == VerdictAction.REJECT.value
    assert any("drawdown" in v.lower() for v in control_verdict.violations)

    # Respawn path: run_id pre-allocated, DB row seeded "running" (as
    # `_sweep_stuck_runs` would leave it), then respawned exactly the way
    # `_respawn_run_from_row` does.
    run_id = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id, user_id=user_id, ticker="MSFT",
            triggered_at=datetime.now(timezone.utc), started_at=datetime.now(timezone.utc),
            mandate_version=mandate.version, model_tier="mid", rounds=1,
            transcript=[], verdict=None, credit_cost=8, status="running", retry_count=1,
        ))
        s.commit()

    runner = RoomRunner(llm=_LiberalPmGateway())  # type: ignore[arg-type]

    async def _respawn_and_wait():
        await runner._respawn_run_from_row(_PendingRetry(
            run_id=run_id, user_id=user_id, ticker="MSFT",
            mandate_version=mandate.version,
        ))
        async for _ in runner.subscribe(run_id):
            pass

    import asyncio
    asyncio.run(_respawn_and_wait())

    with get_session() as s:
        from sqlalchemy import select as _select
        row = s.execute(_select(RoomRunRow).where(RoomRunRow.id == run_id)).scalar_one()

    # The respawned verdict must land the same place the control did — REJECT,
    # not the pre-fix APPROVE against a fabricated $100k/0%-drawdown book.
    assert row.verdict is not None, "respawn produced no verdict at all"
    assert row.verdict["action"] == VerdictAction.REJECT.value, (
        "MAJOR-1: the respawned run judged the floor against a fabricated "
        f"portfolio instead of this user's real {real_dd:.1f}% drawdown — "
        f"got {row.verdict['action']!r}, violations={row.verdict.get('violations')}"
    )
    assert any("drawdown" in v.lower() for v in row.verdict.get("violations", []))
    # Never persisted/journalled as a forbidden APPROVE (DEF384's own bar).
    assert row.status == RoomStatus.COMPLETED.value


def test_respawn_fails_loudly_when_the_real_snapshot_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch,
):
    """If the user's real portfolio genuinely can't be loaded on respawn, the
    fix must not silently fall back to `run()`'s $100k/0%-drawdown defaults —
    that is the exact fabricated-number failure mode MAJOR-1 names. The run
    must fail with a disclosed reason instead of ever reaching an APPROVE-
    capable convene.

    RETRO-PM-FLOOR round 2 (auditor U68, MINOR-3): this branch also must
    refund the credits charged at the original start_run — the auditor's
    probe (`status=failed … refunded=0 (credit_cost 3)`) found it kept them.
    The user is given a real starting balance via `balance_for` (establishes
    the allowance window) so a refund is a MEASURABLE balance change, not
    just a ledger row appearing."""
    import app.services.room_runner as room_runner_mod
    from app.services.auth_service import AuthService
    from app.services.credit_service import balance_for

    # A real `users` row is required to observe a refund at all —
    # `credit_service.refund` silently no-ops when `session.get(User, ...)`
    # finds nothing (by design: nothing to refund for a user that doesn't
    # exist), and a mandate-only fixture (no AuthService call) has no such
    # row, which would pass this test for the wrong reason (refund() never
    # even reaching its no-op-vs-real-refund branch).
    user, _token, _ = AuthService().ensure_anonymous(device_user_id=None)
    user_id = user.id
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    before_balance = balance_for(user_id)[0]

    run_id = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=run_id, user_id=user_id, ticker="MSFT",
            triggered_at=datetime.now(timezone.utc), started_at=datetime.now(timezone.utc),
            mandate_version=mandate.version, model_tier="mid", rounds=1,
            transcript=[], verdict=None, credit_cost=8, status="running", retry_count=1,
        ))
        s.commit()

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated valuation_snapshot outage")

    sim = get_sim_engine()
    monkeypatch.setattr(sim, "valuation_snapshot", _boom)

    runner = RoomRunner(llm=_LiberalPmGateway())  # type: ignore[arg-type]

    async def _respawn_and_wait():
        await runner._respawn_run_from_row(_PendingRetry(
            run_id=run_id, user_id=user_id, ticker="MSFT",
            mandate_version=mandate.version,
        ))
        async for _ in runner.subscribe(run_id):
            pass

    import asyncio
    asyncio.run(_respawn_and_wait())

    with get_session() as s:
        from sqlalchemy import select as _select
        row = s.execute(_select(RoomRunRow).where(RoomRunRow.id == run_id)).scalar_one()

    assert row.status == RoomStatus.FAILED.value, (
        "MAJOR-1: an unreadable real portfolio must fail the respawn loudly, "
        f"never fall back to a fabricated default — got status={row.status!r}, "
        f"verdict={row.verdict!r}"
    )
    assert row.verdict is None or row.verdict.get("action") != VerdictAction.APPROVE.value
    assert row.error_message, "a failed respawn must disclose why (CR040)"

    assert balance_for(user_id)[0] == before_balance + 8, (
        "MINOR-3: a respawn abandoned for an unreadable portfolio must "
        f"refund the run's credit_cost — balance is {balance_for(user_id)[0]}, "
        f"expected {before_balance + 8}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# MAJOR-2 — a sector-context failure must never widen what the floor permits.
# ─────────────────────────────────────────────────────────────────────────────


def _user_with_two_holdings() -> "uuid4":
    user_id = uuid4()
    sim = get_sim_engine()
    portfolio = sim.ensure_portfolio(user_id)
    with get_session() as s:
        s.add(SimHoldingRow(
            portfolio_id=portfolio.id, ticker="AAPL", quantity=10.0, avg_cost=150.0,
        ))
        s.add(SimHoldingRow(
            portfolio_id=portfolio.id, ticker="GOOG", quantity=5.0, avg_cost=120.0,
        ))
        s.commit()
    return user_id


def test_sector_context_failure_still_blocks_the_max_open_positions_cap(
    monkeypatch: pytest.MonkeyPatch,
):
    """The auditor's MAJOR-2 probe: user holds AAPL+GOOG, `max_open_positions=2`,
    PM APPROVEs a new ticker (MSFT). Control (resolver healthy) REJECTs; the
    pre-fix failure path returns `[]` (a real-looking empty book) and APPROVEs.
    Both must REJECT after the fix — a context-build failure costs the sector
    cap only, never the position-count cap."""
    user_id = _user_with_two_holdings()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3}).model_copy(
        update={"max_open_positions": 2}
    )
    get_mandate_store().upsert(user_id, mandate)

    sim = get_sim_engine()
    pv, dd = sim.valuation_snapshot(user_id)

    # Control: sector-context builder healthy.
    control_events = _collect(RoomRunner(llm=_LiberalPmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=pv, current_drawdown_pct=dd,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    control_verdict = next(e.verdict for e in control_events if e.kind == "verdict")
    assert control_verdict.action == VerdictAction.REJECT.value
    assert any("max open positions" in v.lower() for v in control_verdict.violations)

    # Failure path: force the sector resolver to blow up.
    import app.services.room_runner as room_runner_mod

    def _boom():
        raise RuntimeError("simulated sector snapshot outage")

    monkeypatch.setattr(room_runner_mod, "default_sector_map", _boom)

    failure_events = _collect(RoomRunner(llm=_LiberalPmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=pv, current_drawdown_pct=dd,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    failure_verdict = next(e.verdict for e in failure_events if e.kind == "verdict")

    assert failure_verdict.action == VerdictAction.REJECT.value, (
        "MAJOR-2: a sector-context failure widened what the floor permits — "
        f"got {failure_verdict.action!r} where the control REJECTed, "
        f"violations={failure_verdict.violations}"
    )
    assert any(
        "max open positions" in v.lower() or "could not" in v.lower() or "holdings" in v.lower()
        for v in failure_verdict.violations
    ), failure_verdict.violations


def test_sector_context_builder_reports_holdings_as_none_on_failure():
    """Unit-level pin on `_build_room_sector_context` itself: on failure it
    must return `None` for holdings (the safety floor's "not supplied, block
    loudly" sentinel per `check_mandate_compliance`'s own contract), never `[]`
    (a real, empty book that lets rule 6d silently pass)."""
    import app.services.room_runner as room_runner_mod

    def _boom(*_a, **_kw):
        raise RuntimeError("simulated outage")

    class _BoomEngine:
        def ensure_portfolio(self, *_a, **_kw):
            raise RuntimeError("simulated outage")

    orig_get_sim_engine = room_runner_mod.get_sim_engine
    room_runner_mod.get_sim_engine = lambda: _BoomEngine()  # type: ignore[assignment]
    try:
        holdings, marks, smap, weights = _build_room_sector_context(uuid4())
    finally:
        room_runner_mod.get_sim_engine = orig_get_sim_engine

    assert holdings is None, (
        "a sector-context failure must report holdings as None (block loudly), "
        f"not {holdings!r} (a real-looking empty book)"
    )
    assert smap is None
    assert weights == {}


# ─────────────────────────────────────────────────────────────────────────────
# MINOR-1 — a zero-readable vote must be labelled, not shipped as an ordinary
# single-draw verdict.
# ─────────────────────────────────────────────────────────────────────────────


def test_zero_readable_vote_is_labelled_not_a_silent_single_draw(
    monkeypatch: pytest.MonkeyPatch,
):
    """The auditor's MINOR-1 probe: samples=5, every draw AND every reformat
    retry unparseable. Pre-fix: `samples`/`approve_votes` stay `None` (the
    schema's "self-consistency is off" meaning, false here) and `reason`
    carries no disclosure. Post-fix: both are set and `reason` says plainly
    that no independent read was readable."""
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 5)

    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)

    events = _collect(RoomRunner(llm=_AllUnparseablePmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=100_000.0, current_drawdown_pct=0.0,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")

    assert v.samples == 5, (
        "MINOR-1: a zero-readable vote must record the requested sample count "
        f"(the schema's 'self-consistency is off' sentinel is None) — got {v.samples!r}"
    )
    assert v.approve_votes == 0, (
        f"MINOR-1: a zero-readable vote must not leave approve_votes as None — got {v.approve_votes!r}"
    )
    assert "independent reads" in v.reason.lower() and (
        "were machine-readable" in v.reason.lower() or "not a vote" in v.reason.lower()
    ), v.reason


# ─────────────────────────────────────────────────────────────────────────────
# MINOR-2 — two conflicting decisions in one PM reply must fail safe, not
# silently ship the first (draft) one.
# ─────────────────────────────────────────────────────────────────────────────


class _RetractedDraftPmGateway:
    """The auditor's MINOR-2 probes, replayed end to end through the real
    runner: the PM's reply carries a draft APPROVE, a retraction, and a final
    PASS. Pre-fix, `extract_json_object`'s `raw_decode` reads the draft."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                           locale="en", max_tokens=1024, **_audit):
        if "chief investment officer" in system_prompt.lower():
            text = (
                'Draft: {"action": "APPROVE", "size_pct": 3.0, "entry": 100, '
                '"stop": 94, "target": 113, "horizon_days": 42, '
                '"narration": "Draft."} -- on reflection I decline. '
                '{"action": "PASS", "narration": "PM: PASS on reflection."}'
            )
        else:
            text = "Agent reply."
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


def test_a_retracted_draft_approve_fails_safe_not_ships_as_the_verdict(
    monkeypatch: pytest.MonkeyPatch,
):
    """samples=1 (the single-draw path) so `_parse_pm_verdict` -> `extract_json_object`
    is exercised directly, matching the auditor's own probe shape. Pre-fix this
    reads APPROVE (the draft); post-fix, two conflicting decisions in one reply
    is unparseable, and DEF059's outage-shaped fail-safe (PASS,
    `overridden_from_llm=True`) is what a discarded PM reply already produces —
    never a discarded draft's APPROVE."""
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)

    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)

    events = _collect(RoomRunner(llm=_RetractedDraftPmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=100_000.0, current_drawdown_pct=0.0,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")

    assert v.action != VerdictAction.APPROVE.value, (
        "MINOR-2: a retracted draft APPROVE must never ship as the verdict — "
        f"got {v.action!r}"
    )


class _RetractedDraftPmGatewayWithUpgradingReformatter:
    """RETRO-PM-FLOOR round 3 (MINOR-2 residual 1) — the auditor's exact
    residual probe: `PROBE two-decision draft_then_pass, reformatter says
    APPROVE -> APPROVE (reformat_calls=1)`. Round 2's fix returned bare
    `None` for a detected conflict, which is indistinguishable from
    "genuinely unparseable" to the caller — so `_reformat_pm_response` was
    still invoked, and if IT said APPROVE, DEF067's "only ever recover, never
    downgrade" rule accepted it. This gateway's reformatter always answers
    APPROVE, so if the reformat call happens at all, the pre-round-3 bug
    reproduces exactly. Counts calls so the test can assert the call never
    happens, not just that its answer was ignored."""

    def __init__(self) -> None:
        self.reformat_calls = 0

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                           locale="en", max_tokens=1024, **_audit):
        if "strict formatter" in system_prompt.lower():
            self.reformat_calls += 1
            text = (
                '{"action": "APPROVE", "size_pct": 3.0, "entry": 100, '
                '"stop": 94, "target": 113, "horizon_days": 42, '
                '"narration": "Reformatter says APPROVE."}'
            )
        elif "chief investment officer" in system_prompt.lower():
            text = (
                'Draft: {"action": "APPROVE", "size_pct": 3.0, "entry": 100, '
                '"stop": 94, "target": 113, "horizon_days": 42, '
                '"narration": "Draft."} -- on reflection I decline. '
                '{"action": "PASS", "narration": "PM: PASS on reflection."}'
            )
        else:
            text = "Agent reply."
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


def test_a_conflicting_decision_never_reaches_the_reformatter_at_all(
    monkeypatch: pytest.MonkeyPatch,
):
    """RETRO-PM-FLOOR round 3 (MINOR-2 residual 1) — the fix: on a detected
    conflict, `_parse_pm_verdict` returns a real PASS `Verdict` directly
    (never `None`), so the caller's `if parsed is None:` DEF058 gate never
    fires and `_reformat_pm_response` is never called — not "called but its
    APPROVE is discarded", but never invoked. Proven by counting calls on a
    reformatter gateway that would say APPROVE if it were ever asked."""
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)

    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)

    gateway = _RetractedDraftPmGatewayWithUpgradingReformatter()
    events = _collect(RoomRunner(llm=gateway).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=100_000.0, current_drawdown_pct=0.0,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")

    assert gateway.reformat_calls == 0, (
        "MINOR-2 residual 1: a detected conflict must fail straight to PASS "
        "without ever invoking the reformat retry — the retry was called "
        f"{gateway.reformat_calls} time(s)"
    )
    assert v.action == VerdictAction.PASS.value, (
        f"MINOR-2 residual 1: expected PASS, got {v.action!r}"
    )


class _QuotedBraceThenConflictPmGateway:
    """RETRO-PM-FLOOR round 3 (MINOR-2 residual 2) — the auditor's other
    residual probe: `PROBE extract quoted-brace-tail -> APPROVE`. Round 2's
    `_extract_second_decision` only scanned the FIRST `{` in the tail — this
    is DEF398's own measured shape, the PM quoting its own "begin with '{'
    and end with '}'" contract back at us, which put a non-decision brace
    before the real second decision and made the scan miss it entirely."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                           locale="en", max_tokens=1024, **_audit):
        if "chief investment officer" in system_prompt.lower():
            text = (
                '{"action": "APPROVE", "size_pct": 3.0, "entry": 100, '
                '"stop": 94, "target": 113, "horizon_days": 42, '
                '"narration": "Draft."}\n\n'
                'DATA I LACKED: the contract says "begin with \'{\' and end '
                'with \'}\'". On reflection: '
                '{"action": "PASS", "narration": "PM: PASS on reflection."}'
            )
        else:
            text = "Agent reply."
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


def test_a_quoted_brace_before_the_real_conflict_is_still_caught(
    monkeypatch: pytest.MonkeyPatch,
):
    """RETRO-PM-FLOOR round 3 (MINOR-2 residual 2) — `_extract_second_decision`
    now scans every top-level object in the tail, not just the first `{`, so
    a stray quoted brace ahead of the real second decision can no longer hide
    it. Pre-fix this read APPROVE (the draft); post-fix it must fail safe."""
    monkeypatch.setattr(settings, "pm_self_consistency_samples", 1)

    user_id = uuid4()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    get_mandate_store().upsert(user_id, mandate)
    sim = get_sim_engine()
    sim.ensure_portfolio(user_id)

    events = _collect(RoomRunner(llm=_QuotedBraceThenConflictPmGateway()).run(  # type: ignore[arg-type]
        user_id=user_id, ticker="MSFT", mandate=mandate,
        portfolio_value=100_000.0, current_drawdown_pct=0.0,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")

    assert v.action != VerdictAction.APPROVE.value, (
        "MINOR-2 residual 2: a quoted brace ahead of the real conflicting "
        f"decision must not hide it from the scan — got {v.action!r}"
    )
