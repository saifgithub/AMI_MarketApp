"""CR153 B ≡ CR154 B ≡ CR155 C ≡ CR156 C — the Room can finally see what the
risk budget has already spent.

Four CRs filed the same finding against four different agents. CR156 states the
dedupe rule: thread it into the shared mandate snapshot ONCE. This is that tier.

The mandate snapshot carried only the *limits* — `max_drawdown_pct: 20`,
`single_name_cap_pct` — and never the *consumption*. So every agent argued about
how much risk to add while blind to how much was already spent, which makes
"sized against the cap" literally unanswerable: 3% more is prudent at 2%
drawdown and reckless at 19%. The numbers existed on `_RoomContext` the whole
time (CR101-BE2 threaded them for the safety floor) and reached no prompt.

**Three absences, kept distinct — this is the batch's real risk.** The lazy
version renders `0.0` for all three and is wrong in the most dangerous
direction, telling the Room the book is flat when the computation actually
failed:

- `CONTEXT_NOT_SUPPLIED` — the computation FAILED. Says so. This sentinel exists
  precisely because a real "no prior loss" and an outage computing one must not
  be indistinguishable (CR040, DEF059).
- `None` — not supplied by this caller. Renders nothing rather than claiming zero.
- a real `0.0` — genuinely no open risk. Stated as fact.

The end-to-end test at the bottom is not optional decoration. DEF241's mutation
proof showed MUT-1/MUT-2 die *only* under a real `RoomRunner.run()`, because
every other test passes the kwarg itself and therefore proves the builder while
saying nothing about the caller — the exact blind spot that let DEF238 ship a
PM-only feature that never worked once in production.
"""

from __future__ import annotations

import pytest

from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED
from app.schemas import AgentId
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import _PHASE_FOR_AGENT, build_room_messages


def _mandate():
    return hydrate_coach_mandate({"plan": "trader", "risk_score": 3})


def _prompt(agent_id=AgentId.NEUTRAL_DEBATOR, **risk):
    sp, _ = build_room_messages(
        agent_id=agent_id, mandate=_mandate(), user_id=None, ticker="AAPL",
        profile={"field_state": {}}, transcript=[], **risk,
    )
    return sp


# ── The consumption figures reach the prompt ──────────────────────────────────


def test_drawdown_used_and_headroom_both_render():
    """The cap alone was never the actionable number — the headroom is."""
    sp = _prompt(current_drawdown_pct=12.5)
    assert "Drawdown USED: 12.5 pt" in sp
    assert "headroom remains" in sp
    assert "Size against the headroom, not against the cap." in sp


def test_open_risk_renders_with_the_qualifier_that_makes_it_honest():
    """`_risk_limit_context` sums only positions carrying a stop, so an
    unqualified "open risk 4.2%" reads as complete when the book may hold
    unstopped positions the figure cannot see."""
    sp = _prompt(existing_open_risk_pct=4.2)
    assert "Open risk already committed: 4.2%" in sp
    assert "across open positions carrying a stop" in sp
    assert "Positions with no stop recorded are NOT in this figure" in sp


def test_a_real_zero_is_stated_as_a_fact():
    """A genuinely flat book is information, not an absence."""
    sp = _prompt(existing_open_risk_pct=0.0)
    assert "Open risk already committed: 0.0%" in sp


# ── The three absences stay distinct (CR040 / DEF059) ─────────────────────────


def test_a_failed_computation_says_so_and_never_reads_as_zero():
    """The dangerous failure: rendering 0.0 for an outage tells the Room the book
    is flat and invites exactly the added size the floor is blocking."""
    sp = _prompt(existing_open_risk_pct=CONTEXT_NOT_SUPPLIED)
    assert "COULD NOT BE COMPUTED" in sp
    assert "Treat it as unknown, not as zero" in sp
    assert "Open risk already committed" not in sp


def test_a_failed_stop_out_lookup_says_unknown_not_none():
    sp = _prompt(last_loss_closed_at=CONTEXT_NOT_SUPPLIED)
    assert "Last stop-out: COULD NOT BE COMPUTED" in sp
    assert "unknown, not 'none'" in sp


def test_not_supplied_renders_nothing_rather_than_claiming_zero():
    """Non-Room callers and older tests pass nothing. Silence is correct there —
    inventing a 0.0 would be a fabricated fact, not a default."""
    sp = _prompt()
    assert "Live risk state" not in sp
    assert "Drawdown USED" not in sp
    assert "Open risk" not in sp


def test_the_sentinel_is_not_confused_with_a_falsy_value():
    """`CONTEXT_NOT_SUPPLIED` is an `object()`, and `0.0`/`None`/`[]` are all
    falsy — an `if not value` check would collapse all four into one branch.
    This is the assertion that keeps the three renderings apart."""
    failed = _prompt(existing_open_risk_pct=CONTEXT_NOT_SUPPLIED)
    zero = _prompt(existing_open_risk_pct=0.0)
    absent = _prompt()
    assert failed != zero != absent
    assert "COULD NOT BE COMPUTED" in failed
    assert "0.0%" in zero
    assert "Open risk" not in absent


# ── Every agent gets it, at every phase ───────────────────────────────────────


# The twelve Room agents. NOT `list(AgentId)` — the Concierge is not a Room
# agent and has no phase, so `build_room_messages` rightly refuses it.
@pytest.mark.parametrize("agent_id", list(_PHASE_FOR_AGENT))
def test_every_agent_sees_the_risk_state(agent_id):
    """Deliberately NOT phase-gated, unlike `trade_proposal`. The consumption
    figures are real at every phase, and all four source CRs filed this against
    a different agent — a gate would just recreate the gap for whichever agents
    fell outside it."""
    sp = _prompt(agent_id=agent_id, current_drawdown_pct=8.0, existing_open_risk_pct=3.0)
    assert "Live risk state" in sp
    assert "Drawdown USED: 8.0 pt" in sp


# ── DEF241 residue: the deferral is recorded, not silently dropped ────────────


def test_the_researchers_still_get_no_worked_contribution_figure():
    """DEF241's residue is DEFERRED, and this pins the deferral so a later reader
    finds a decision rather than an oversight.

    CR151 adjudicated this and rejected widening: at RESEARCHERS and SYNTHESIS
    the Trader has not spoken, so there is no proposal, and any figure would be
    minted from a stop nobody set — read as a measurement, which is the DEF235
    class. What those phases actually lacked is the consumption, and they now
    have it.
    """
    for agent_id in (AgentId.BULL_RESEARCHER, AgentId.RESEARCH_MANAGER):
        sp = _prompt(agent_id=agent_id, current_drawdown_pct=8.0,
                     trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0})
        assert "Reference position" not in sp, (
            f"{agent_id.value} got a worked figure from a proposal that does not "
            "exist at its phase — see CR151's rejected item 2"
        )
        # …but it DOES get the half that is real.
        assert "Drawdown USED: 8.0 pt" in sp


# ── The call site, not just the builder (the DEF238 blind spot) ───────────────


def test_the_runner_actually_threads_the_risk_state():
    """Every test above passes the kwargs itself, which proves the builder and
    says nothing about the caller. DEF238 shipped a PM-only feature that never
    worked once in production because its argument was missing at the only call
    site that mattered, and every test passed the whole time.

    RED without the runner change: no prompt contains "Live risk state" at all.
    """
    import asyncio
    from uuid import uuid4

    from app.services.room_runner import RoomRunner

    captured: dict[str, str] = {}

    class _Gateway:
        def has_real_provider(self) -> bool:
            return True

        async def stream_chat(self, *, system_prompt, messages, model_tier,
                              locale="en", max_tokens=1024, **_audit):
            captured[_audit.get("audit_agent_id") or "?"] = system_prompt
            yield (
                '{"action": "PASS", "narration": "PM: hold."}'
                if "speak as the chief investment officer" in system_prompt.lower()
                else "[STANCE: neutral | CONVICTION: low | HEADLINE: x]\nA reply."
            )

    async def _drain():
        async for _ev in RoomRunner(llm=_Gateway()).run(  # type: ignore[arg-type]
            user_id=uuid4(), ticker="MSFT", mandate=_mandate(),
            char_delay_min=0.0, char_delay_max=0.0,
        ):
            pass

    asyncio.run(_drain())

    assert captured, "no agent spoke — the harness is wired wrong"
    missing = [a for a, sp in captured.items() if "Live risk state" not in sp]
    assert not missing, (
        f"these agents' prompts carry no risk state, so the runner is not "
        f"threading it: {sorted(missing)}"
    )
    # The PM is the agent whose verdict the floor vetoes — it must be covered.
    assert "portfolio_manager" in captured


# ── DEF263 — the three findings the R68-BATCH7 auditor returned ──────────────


def test_the_outage_the_runner_actually_produces_is_loud():
    """The `CONTEXT_NOT_SUPPLIED` branch for open risk was UNREACHABLE from the
    Room, and this test drives the translation that makes it reachable.

    `_build_room_risk_limit_context` returns `(CONTEXT_NOT_SUPPLIED, None, None)`
    on every failure path — the sentinel lands on `last_loss_closed_at` and open
    risk arrives as a plain `None` MEANING "could not compute". The renderer
    reads that as "the caller never asked" and prints nothing, so on a real
    outage the line was silent — while `enforce_safety_floor` was blocking every
    BUY on that same `None`. The sentence written for exactly that state was
    dead code.

    Every other absence test in this file passes the sentinel itself, which is
    the DEF238 blind spot applied to this batch's own sentinel handling. This
    one starts from the runner's real failure value.
    """
    from app.services.room_runner import _prompt_open_risk

    runner_value_on_failure = None
    sp = _prompt(existing_open_risk_pct=_prompt_open_risk(runner_value_on_failure))
    assert "Open risk: COULD NOT BE COMPUTED" in sp
    assert "the safety floor is blocking on this" in sp


def test_the_translation_never_rewrites_a_real_figure():
    """Only the ambiguous `None` moves. A real 0.0 is a fact and must survive as
    one — collapsing it would be the fabricated-flat-book direction the whole
    absence design exists to prevent."""
    from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED
    from app.services.room_runner import _prompt_open_risk

    assert _prompt_open_risk(None) is CONTEXT_NOT_SUPPLIED
    assert _prompt_open_risk(0.0) == 0.0
    assert _prompt_open_risk(4.2) == 4.2
    assert _prompt_open_risk(CONTEXT_NOT_SUPPLIED) is CONTEXT_NOT_SUPPLIED
    assert "Open risk already committed: 0.0%" in _prompt(
        existing_open_risk_pct=_prompt_open_risk(0.0)
    )


def test_the_renderer_still_says_nothing_to_a_caller_that_never_asked():
    """The fix is deliberately NOT in the renderer. `prompt_version.py` and every
    non-Room caller omit these kwargs, and collapsing `None` into the loud branch
    there would have them announce that the safety floor is blocking a BUY nobody
    proposed — a fabricated alarm, the same class of harm as the silence it
    replaced, pointed the other way."""
    assert "Open risk" not in _prompt()


def test_the_trade_pace_counts_the_windows_the_brake_counts():
    """It printed `len()` of the whole list under the label "in the recent
    window". `_risk_limit_context` builds it as `list_trades(user_id)` with no
    date filter, so it was a LIFETIME count: 40 trades opened 90–130 days ago
    rendered "40" while both brakes counted 0."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    stale = [now - timedelta(days=d) for d in (90, 100, 110, 120, 130)]
    sp = _prompt(trade_open_timestamps=stale)
    assert "Trades opened today: 0" in sp
    assert "this ISO week (from Monday 00:00 UTC): 0" in sp
    assert "Trades opened in the recent window: 5" not in sp


def test_the_trade_pace_agrees_with_the_floors_own_counters():
    """Computed with the floor's OWN helpers, against the same UTC day boundary
    and Monday-00:00-UTC ISO week — a second implementation of "today" is how
    the prompt and the brake come to disagree."""
    from datetime import datetime, timedelta, timezone

    from app.trading_math.risk_limits import (
        trades_since, utc_day_start, utc_week_start,
    )

    now = datetime.now(timezone.utc)
    stamps = [now - timedelta(hours=h) for h in (1, 3, 30, 100, 400)]
    sp = _prompt(trade_open_timestamps=stamps)
    assert f"Trades opened today: {trades_since(stamps, utc_day_start(now))}" in sp
    assert (
        f"this ISO week (from Monday 00:00 UTC): "
        f"{trades_since(stamps, utc_week_start(now))}" in sp
    )


# ── DEF263 — `_stop_clause` had no regression protection at all ──────────────
#
# The auditor mutated it into exactly the two behaviours the batch claims it
# avoids — averaging the stops, and rendering "" for an unstopped lot — and the
# whole suite stayed green. The behaviour was correct; nothing held it there.


def test_a_single_stop_renders_its_own_level():
    from app.services.room_runner import _stop_clause

    assert _stop_clause("AAPL", {"AAPL": {188.5}}, {}) == " — stop $188.5"


def test_multiple_lots_list_their_stops_and_never_average_them():
    """A mean of two stops is a level nobody set. Minting one here is the
    DEF235 class, and the numbers are chosen so an average (185.0) would be
    visible if it were ever computed."""
    from app.services.room_runner import _stop_clause

    clause = _stop_clause("AAPL", {"AAPL": {180.0, 190.0}}, {})
    assert clause == " — stops $180, $190"
    assert "185" not in clause


def test_an_unstopped_lot_is_loud_and_never_silent():
    """CR040. Before this the holdings block stated size and unrealised P&L and
    said nothing about protection, so a Room reasoning about open risk could not
    tell a fully-stopped book from a naked one."""
    from app.services.room_runner import _stop_clause

    clause = _stop_clause("AAPL", {}, {"AAPL": 2})
    assert clause != ""
    assert "NO stop recorded" in clause


def test_a_partly_stopped_name_names_both_halves():
    """The dangerous render is the one that shows the stops and stays quiet
    about the naked lots — it reads as a fully protected position."""
    from app.services.room_runner import _stop_clause

    clause = _stop_clause("AAPL", {"AAPL": {180.0}}, {"AAPL": 3})
    assert "$180" in clause
    assert "3 lots with NO stop recorded" in clause


def test_the_fallthrough_is_loud_rather_than_silent():
    """A name in neither dict cannot occur today — both are built from the same
    lot iteration, so every held name lands in one of them. The branch is
    defensive, and it defends in the CR040 direction: if the two dicts ever come
    to be built differently, a held position renders as unprotected rather than
    as nothing. Silence is the failure mode this whole clause exists to remove,
    so it must not be what the unreachable path returns."""
    from app.services.room_runner import _stop_clause

    assert _stop_clause("MSFT", {"AAPL": {180.0}}, {"AAPL": 1}) == (
        " — NO stop recorded (this position is unprotected)"
    )
