"""CR219 R60 — "what changed since your last convene" delta line.

Source design: `../fable/05_further_improvements.md` §14 (design doc numbers
this item 14; the WP is R60). When a user re-convenes a ticker, the Room
should explain what changed instead of silently re-deciding — a code-built
line injected once into the PM's VERDICT-phase prompt, never composed by the
LLM itself.

Three layers, tested separately because each degrades independently:

  * `room_runner._room_delta_context` — the DB lookup. Picks the latest
    COMPLETED run with a verdict for this exact (user_id, ticker), skips an
    outage abstain (`NO_VERDICT`, R51/DEF376), never crosses users or
    tickers.
  * `room_runner._build_next_convene_delta` — pure arithmetic. Price move %,
    `sheet_state` field transitions, both computed from stored data, both
    degrading to a partial answer (never a fabrication, never a crash) on an
    old-shape prior with no `sheet_state`.
  * `room_prompts._room_delta_line` / `build_room_messages` — the prompt
    injection. Renders the already-built delta once, only into the PM's
    VERDICT-phase turn, and renders nothing at all when there is no usable
    prior.

Plus the bank-time persistence (`Verdict.sheet_state` / `reference_price` /
`next_convene_delta`, written at the `RoomStatus.COMPLETED` branch) — the
comparison basis the NEXT convene's lookup reads back.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from app.db import get_session, init_schema
from app.db.models import RoomRunRow
from app.schemas import AgentId
from app.schemas.room import NextConveneDelta, SheetFieldTransition, Verdict, VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import _room_delta_line, build_room_messages
from app.services.room_runner import RoomRunner, _build_next_convene_delta


# ── fixtures ────────────────────────────────────────────────────────────────


def _mk_run(
    user_id: UUID,
    ticker: str = "AAPL",
    *,
    status: str = "completed",
    finished_at: datetime | None = None,
    verdict: Verdict | None = None,
) -> UUID:
    init_schema()
    rid = uuid4()
    with get_session() as s:
        s.add(RoomRunRow(
            id=rid, user_id=user_id, ticker=ticker,
            started_at=datetime.now(timezone.utc),
            finished_at=finished_at,
            mandate_version=1, model_tier="mid", status=status,
            verdict=verdict.model_dump(mode="json") if verdict else None,
        ))
    return rid


def _ts(days_ago: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


# ── 1. lookup: picks the right prior ──────────────────────────────────────


def test_no_prior_run_returns_none():
    runner = RoomRunner()
    assert runner._room_delta_context(uuid4(), "AAPL") is None


def test_picks_the_latest_completed_run_not_the_oldest():
    user = uuid4()
    _mk_run(
        user, "AAPL", finished_at=_ts(10),
        verdict=Verdict(action=VerdictAction.PASS, reason="old"),
    )
    _mk_run(
        user, "AAPL", finished_at=_ts(1),
        verdict=Verdict(action=VerdictAction.APPROVE, reason="new"),
    )
    runner = RoomRunner()
    ctx = runner._room_delta_context(user, "AAPL")
    assert ctx is not None
    assert ctx["action"] == "APPROVE"


def test_other_user_is_never_the_prior():
    """A different user's convene on the SAME ticker must not leak in —
    the delta line would otherwise show one user their own history built
    from someone else's decision."""
    other_user = uuid4()
    _mk_run(
        other_user, "AAPL", finished_at=_ts(1),
        verdict=Verdict(action=VerdictAction.APPROVE, reason="not this user's"),
    )
    runner = RoomRunner()
    assert runner._room_delta_context(uuid4(), "AAPL") is None


def test_other_ticker_is_never_the_prior():
    user = uuid4()
    _mk_run(
        user, "MSFT", finished_at=_ts(1),
        verdict=Verdict(action=VerdictAction.APPROVE, reason="wrong ticker"),
    )
    runner = RoomRunner()
    assert runner._room_delta_context(user, "AAPL") is None


def test_running_and_failed_runs_are_not_a_prior():
    user = uuid4()
    _mk_run(user, "AAPL", status="running", finished_at=None)
    _mk_run(user, "AAPL", status="failed", finished_at=_ts(1))
    _mk_run(user, "AAPL", status="cancelled", finished_at=_ts(1))
    runner = RoomRunner()
    assert runner._room_delta_context(user, "AAPL") is None


def test_a_completed_run_with_no_verdict_is_not_a_prior():
    """`verdict IS NULL` on a `status=completed` row should not happen in
    practice (every path to COMPLETED assigns one) but the query filters it
    out defensively rather than crashing on `Verdict.model_validate(None)`."""
    user = uuid4()
    _mk_run(user, "AAPL", status="completed", finished_at=_ts(1), verdict=None)
    runner = RoomRunner()
    assert runner._room_delta_context(user, "AAPL") is None


# ── 2. abstain prior (NO_VERDICT) is skipped ──────────────────────────────


def test_a_no_verdict_only_prior_is_skipped_entirely():
    """R51/DEF376's outage abstain is not a real call to compare against —
    the WP's own preferred simpler rule: skip rather than walk further back."""
    user = uuid4()
    _mk_run(
        user, "AAPL", finished_at=_ts(1),
        verdict=Verdict(action=VerdictAction.NO_VERDICT, reason="outage"),
    )
    runner = RoomRunner()
    assert runner._room_delta_context(user, "AAPL") is None


def test_a_no_verdict_most_recent_masks_an_older_real_verdict():
    """The WP explicitly prefers skipping entirely over walking further back
    for simplicity — an older real verdict behind a NO_VERDICT abstain is NOT
    surfaced. Pin the chosen behaviour so a future change is a decision, not
    a drift."""
    user = uuid4()
    _mk_run(
        user, "AAPL", finished_at=_ts(10),
        verdict=Verdict(action=VerdictAction.APPROVE, reason="real, but older"),
    )
    _mk_run(
        user, "AAPL", finished_at=_ts(1),
        verdict=Verdict(action=VerdictAction.NO_VERDICT, reason="outage, most recent"),
    )
    runner = RoomRunner()
    assert runner._room_delta_context(user, "AAPL") is None


# ── 3. bank-time persistence shape ────────────────────────────────────────


def test_a_banked_verdict_carries_sheet_state_and_reference_price():
    v = Verdict(action=VerdictAction.APPROVE, reason="fixture", size_pct=3.0)
    banked = v.model_copy(update={
        "sheet_state": {"margin_trend": "live", "technicals": "live"},
        "reference_price": 231.50,
    })
    round_tripped = Verdict.model_validate(banked.model_dump(mode="json"))
    assert round_tripped.sheet_state == {"margin_trend": "live", "technicals": "live"}
    assert round_tripped.reference_price == 231.50


def test_a_verdict_before_this_wp_has_no_sheet_state_or_reference_price():
    """No migration, no backfill (scope item 1/T-BACKFILL) — an old row
    round-trips with both new fields absent, not zero-filled."""
    old_shape = {"action": "PASS", "reason": "pre-WP60 run"}
    v = Verdict.model_validate(old_shape)
    assert v.sheet_state is None
    assert v.reference_price is None
    assert v.next_convene_delta is None


def test_the_ledger_bank_and_the_delta_persistence_are_independent_fields():
    """R55's `verdict_outcomes` row and R60's `Verdict.sheet_state` /
    `reference_price` are separate persistence: one is a DB table row, the
    other rides the verdict JSONB. Neither is derived from the other on the
    `Verdict` object itself — setting one leaves the other's shape untouched."""
    v = Verdict(action=VerdictAction.APPROVE, reason="fixture", size_pct=1.0)
    banked = v.model_copy(update={"sheet_state": {"news": "live"}, "reference_price": 50.0})
    assert banked.approve_votes is None  # untouched by the R60 update
    assert banked.kill_criterion is None  # untouched by the R60 update


# ── 4. delta correctness: price move %, field transitions ────────────────


def _prior(
    *,
    date: datetime,
    action: str = "APPROVE",
    kill_criterion: str | None = None,
    reference_price: float | None = 100.0,
    sheet_state: dict[str, str] | None = None,
) -> dict:
    return {
        "date": date, "action": action, "kill_criterion": kill_criterion,
        "reference_price": reference_price, "sheet_state": sheet_state,
    }


def _profile(*, last_close: float | None, technicals: str = "live", **field_state) -> dict:
    fs = {"technicals": technicals, **field_state}
    p: dict = {"field_state": fs}
    if last_close is not None:
        p["last_close"] = last_close
    return p


def test_none_prior_yields_none_delta():
    assert _build_next_convene_delta(None, this_profile=_profile(last_close=100.0)) is None


def test_price_move_pct_is_computed_correctly():
    d = _build_next_convene_delta(
        _prior(date=_ts(5), reference_price=100.0),
        this_profile=_profile(last_close=110.0),
    )
    assert d is not None
    assert d.price_move_pct == pytest.approx(10.0)


def test_a_negative_price_move_is_signed_correctly():
    d = _build_next_convene_delta(
        _prior(date=_ts(5), reference_price=200.0),
        this_profile=_profile(last_close=180.0),
    )
    assert d.price_move_pct == pytest.approx(-10.0)


def test_price_move_is_none_when_this_run_has_no_live_technicals():
    """Never a move computed against a price of unknown origin — the same
    reasoning `_reference_close` itself is gated on (CR104)."""
    d = _build_next_convene_delta(
        _prior(date=_ts(5), reference_price=100.0),
        this_profile=_profile(last_close=110.0, technicals="unavailable"),
    )
    assert d.price_move_pct is None


def test_price_move_is_none_when_prior_has_no_reference_price():
    d = _build_next_convene_delta(
        _prior(date=_ts(5), reference_price=None),
        this_profile=_profile(last_close=110.0),
    )
    assert d.price_move_pct is None


def test_field_transitions_only_list_fields_that_actually_changed():
    d = _build_next_convene_delta(
        _prior(date=_ts(5), sheet_state={
            "margin_trend": "live", "technicals": "live", "news": "unavailable",
        }),
        this_profile=_profile(
            last_close=100.0, technicals="live",
            margin_trend="unavailable", news="unavailable",
        ),
    )
    assert d.changed_fields == [
        SheetFieldTransition(field="margin_trend", from_state="live", to_state="unavailable"),
    ]


def test_a_field_present_in_only_one_run_is_not_a_transition():
    """Appeared-or-disappeared is not a claimed state change — only fields
    present in BOTH maps at a different state count."""
    d = _build_next_convene_delta(
        _prior(date=_ts(5), sheet_state={"technicals": "live", "only_in_prior": "live"}),
        this_profile=_profile(last_close=100.0, technicals="live", only_in_this="live"),
    )
    assert d.changed_fields == []


def test_no_transitions_when_nothing_changed():
    d = _build_next_convene_delta(
        _prior(date=_ts(5), sheet_state={"technicals": "live"}),
        this_profile=_profile(last_close=100.0, technicals="live"),
    )
    assert d.changed_fields == []


def test_the_prior_action_date_and_kill_criterion_carry_through():
    when = _ts(7)
    d = _build_next_convene_delta(
        _prior(date=when, action="PASS", kill_criterion="A beat-and-raise quarter"),
        this_profile=_profile(last_close=100.0),
    )
    assert d.prior_date == when
    assert d.prior_action == "PASS"
    assert d.prior_kill_criterion == "A beat-and-raise quarter"


# ── 5. old-shape prior (no sheet_state) degrades without error ───────────


def test_old_shape_prior_degrades_to_the_partial_delta():
    d = _build_next_convene_delta(
        _prior(date=_ts(3), action="APPROVE", reference_price=None, sheet_state=None),
        this_profile=_profile(last_close=100.0, margin_trend="live"),
    )
    assert d is not None
    assert d.prior_action == "APPROVE"
    assert d.price_move_pct is None
    assert d.changed_fields == []


def test_old_shape_prior_still_renders_the_action_and_date_line():
    d = _build_next_convene_delta(
        _prior(date=datetime(2026, 8, 20, tzinfo=timezone.utc), action="PASS",
               reference_price=None, sheet_state=None),
        this_profile=_profile(last_close=100.0),
    )
    line = _room_delta_line(d)
    assert "2026-08-20" in line
    assert "PASS" in line
    assert "Price move" not in line
    assert "changed state" not in line


# ── 6. rendering: absence is absence, never noise ─────────────────────────


def test_a_none_delta_renders_the_empty_string():
    assert _room_delta_line(None) == ""


def test_a_full_delta_renders_every_piece():
    d = NextConveneDelta(
        prior_date=datetime(2026, 8, 20, tzinfo=timezone.utc),
        prior_action="APPROVE",
        price_move_pct=-4.2,
        changed_fields=[
            SheetFieldTransition(field="margin_trend", from_state="live", to_state="unavailable"),
        ],
        prior_kill_criterion="A close under the 200-day SMA at $150.00",
    )
    line = _room_delta_line(d)
    assert "2026-08-20" in line
    assert "APPROVE" in line
    assert "-4.2%" in line
    assert "margin_trend: live -> unavailable" in line
    assert "A close under the 200-day SMA at $150.00" in line


def test_the_copy_names_ami_and_never_the_llm():
    d = NextConveneDelta(
        prior_date=datetime(2026, 8, 20, tzinfo=timezone.utc), prior_action="PASS",
    )
    line = _room_delta_line(d)
    assert "AMI" in line
    for banned in ("the LLM", "the AI", "the model"):
        assert banned not in line


# ── 7. prompt injection: PM VERDICT only, exactly once, first-convene silent ──


_MANDATE = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
_DELTA = NextConveneDelta(
    prior_date=datetime(2026, 8, 20, tzinfo=timezone.utc),
    prior_action="APPROVE",
    price_move_pct=6.0,
    changed_fields=[
        SheetFieldTransition(field="margin_trend", from_state="live", to_state="unavailable"),
    ],
    prior_kill_criterion="A daily close under $150.00",
)


def _pm_prompt(prior_convene: NextConveneDelta | None) -> str:
    sp, _ = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER, mandate=_MANDATE, user_id=None,
        ticker="AAPL", profile={"field_state": {}}, transcript=[],
        prior_convene=prior_convene,
    )
    return sp


def test_the_pm_prompt_carries_the_delta_line_above_the_transcript():
    sp = _pm_prompt(_DELTA)
    assert "What changed since the last convene" in sp
    assert sp.index("What changed since the last convene") < sp.index("Transcript so far:")


def test_the_delta_line_appears_exactly_once():
    sp = _pm_prompt(_DELTA)
    assert sp.count("What changed since the last convene") == 1


def test_first_convene_no_prior_no_injection():
    sp = _pm_prompt(None)
    assert "What changed since the last convene" not in sp


def test_the_arguing_agents_do_not_get_the_delta_line():
    """Same VERDICT-only scope as the R50 scoreboard and R49 floor preview:
    the delta is the CIO's own comparison against a prior CIO decision, not
    evidence the eleven arguing agents' turns exist to weigh."""
    for agent_id in (
        AgentId.NEUTRAL_DEBATOR, AgentId.TRADER, AgentId.RESEARCH_MANAGER,
        AgentId.BULL_RESEARCHER, AgentId.MARKET_ANALYST,
    ):
        sp, _ = build_room_messages(
            agent_id=agent_id, mandate=_MANDATE, user_id=None,
            ticker="AAPL", profile={"field_state": {}}, transcript=[],
            prior_convene=_DELTA,
        )
        assert "What changed since the last convene" not in sp, agent_id


def test_a_kill_criterion_instructs_the_pm_to_address_whether_it_triggered():
    sp = _pm_prompt(_DELTA)
    assert "A daily close under $150.00" in sp
    assert "whether it has triggered" in sp
