"""CR098-ROOM (AT:coder.room) — tenure-drip analyst pull-back.

Pins the highest-risk acceptance criteria from
docs/forward_planning/CR098_room_analyst_pullback/CR098_room_analyst_pullback.md:

  #2  — no-op proof: all thresholds 0 -> no withholding, byte-stable shape.
  #3  — resolver matrix (clock-injected thresholds).
  #4  — next_step nearest-upcoming-withhold.
  #6  — fact-sheet stripping: exact declared line, never a synthetic stand-in.
  #10 — NO_VERDICT holds even when the LLM emits a well-formed APPROVE (the
        code path decides, not the prompt — CR038).
  #13 — no agent-voiced prompt string ever sells (no "upgrade", no plan name).
  D2 (assign) — withholding an analyst changes the CHARGE, deliberately: an
        aged FLOOR_PASS user with Social withheld is debited strictly less
        than the same user with Social present, by exactly the surcharge for
        the feeds actually fetched.
  Safety-floor regression (#7/#12) — enforce_safety_floor's signature carries
        no roster/withheld parameter at all, so its REJECT is structurally
        roster-independent; a NO_VERDICT input passed through it is a no-op.
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.agents.safety_floor import enforce_safety_floor
from app.core.config import Settings
from app.db import get_session
from app.db.models import User
from app.schemas import AgentId
from app.schemas.mandate import Mandate, Plan
from app.schemas.room import Verdict, VerdictAction
from app.services import room_runner as room_runner_mod
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import ROOM_COST_BASIC, balance_for, live_data_surcharge
from app.services.entitlements import (
    AnalystRoster,
    _WITHHOLDABLE_ORDER,
    account_age_days,
    resolve_analyst_roster,
)
from app.services.room_prompts import _format_profile
from app.services.room_runner import RoomRunner


def _new_user(plan: str = "floor_pass") -> UUID:
    auth = AuthService()
    u, _, _ = auth.ensure_anonymous(device_user_id=None)
    with get_session() as s:
        row = s.get(User, u.id)
        row.plan = plan
    return u.id


def _age_user(user_id: UUID, days: int) -> None:
    with get_session() as s:
        s.get(User, user_id).created_at = datetime.now(timezone.utc) - timedelta(days=days)


def _set_balance(user_id: UUID, amount: int) -> None:
    balance_for(user_id)  # grants + stamps the period
    with get_session() as s:
        s.get(User, user_id).credit_balance = amount


class _WellFormedApproveGateway:
    """A live gateway that answers every agent, including a syntactically
    perfect PM APPROVE block. Used to prove #10: even if this gateway somehow
    were reached, the NO_VERDICT construction site never routes through
    `_parse_pm_verdict` at all, so the well-formed APPROVE cannot surface."""

    def __init__(self):
        self.pm_called = False

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                          locale="en", max_tokens=1024, **_audit):
        if "speak as the portfolio manager" in system_prompt.lower():
            self.pm_called = True
            text = (
                '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
                '"target": 172, "horizon_days": 42, '
                '"narration": "PM: APPROVE; synthesis defended; mandate clears."}'
            )
        else:
            text = "AMI agent live reply."
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


def _collect(coro_gen) -> list:
    async def go():
        return [ev async for ev in coro_gen]
    return asyncio.run(go())


def _full_roster() -> AnalystRoster:
    return AnalystRoster(
        present=(
            AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST,
            AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
        ),
        withheld=(), next_step=None,
    )


def _market_withheld_roster() -> AnalystRoster:
    return AnalystRoster(
        present=(AgentId.FUNDAMENTALS_ANALYST, AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST),
        withheld=(AgentId.MARKET_ANALYST,), next_step=None,
    )


# ── #3 / #4 — resolver matrix (pure, clock-injected) ───────────────────────


def test_resolver_matrix_floor_pass_tenure_drip(monkeypatch):
    monkeypatch.setattr(room_runner_mod.settings, "room_pullback_days_social", 7)
    monkeypatch.setattr(room_runner_mod.settings, "room_pullback_days_news", 21)
    monkeypatch.setattr(room_runner_mod.settings, "room_pullback_days_market", 42)
    from app.core.config import settings as real_settings
    monkeypatch.setattr(real_settings, "room_pullback_days_social", 7)
    monkeypatch.setattr(real_settings, "room_pullback_days_news", 21)
    monkeypatch.setattr(real_settings, "room_pullback_days_market", 42)

    day3 = resolve_analyst_roster(Plan.FLOOR_PASS, 3)
    assert set(day3.present) == {
        AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST,
        AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
    }
    assert day3.withheld == ()

    day10 = resolve_analyst_roster(Plan.FLOOR_PASS, 10)
    assert set(day10.withheld) == {AgentId.SOCIAL_MEDIA_ANALYST}

    day30 = resolve_analyst_roster(Plan.FLOOR_PASS, 30)
    assert set(day30.withheld) == {AgentId.SOCIAL_MEDIA_ANALYST, AgentId.NEWS_ANALYST}

    day50 = resolve_analyst_roster(Plan.FLOOR_PASS, 50)
    assert set(day50.withheld) == {
        AgentId.SOCIAL_MEDIA_ANALYST, AgentId.NEWS_ANALYST, AgentId.MARKET_ANALYST,
    }
    assert day50.present == (AgentId.FUNDAMENTALS_ANALYST,)

    # Paid plans never degrade, any age.
    for plan in (Plan.TRADER, Plan.FLOOR_MANAGER, Plan.TRIAL_TRADER):
        paid = resolve_analyst_roster(plan, 999)
        assert paid.withheld == ()
        assert len(paid.present) == 4


def test_resolver_next_step_nearest_upcoming(monkeypatch):
    from app.core.config import settings as real_settings
    monkeypatch.setattr(real_settings, "room_pullback_days_social", 7)
    monkeypatch.setattr(real_settings, "room_pullback_days_news", 21)
    monkeypatch.setattr(real_settings, "room_pullback_days_market", 42)

    roster = resolve_analyst_roster(Plan.FLOOR_PASS, 3)
    assert roster.next_step == (AgentId.SOCIAL_MEDIA_ANALYST, 4)


def test_fundamentals_structurally_unwithholdable():
    """No config key exists that can withhold Fundamentals — hard-capped in
    code, not config (non-negotiable)."""
    assert AgentId.FUNDAMENTALS_ANALYST not in _WITHHOLDABLE_ORDER
    roster = resolve_analyst_roster(Plan.FLOOR_PASS, 10_000)
    assert AgentId.FUNDAMENTALS_ANALYST in roster.present
    assert AgentId.FUNDAMENTALS_ANALYST not in roster.withheld


def test_negative_pullback_threshold_fails_boot():
    with pytest.raises(ValidationError):
        Settings(room_pullback_days_social=-1)


def test_account_age_days_whole_days():
    now = datetime(2026, 7, 27, tzinfo=timezone.utc)
    created = now - timedelta(days=10, hours=5)
    assert account_age_days(created, now=now) == 10


# ── #2 — no-op proof: default roster produces no withholding ───────────────


def test_default_roster_is_full_no_op():
    """Acceptance #2 (practical form): the default/unaged roster used by
    `run()` when no roster is threaded resolves to all four analysts present
    — the mechanism, when every threshold reads 0 (default), never emits an
    `agent_withheld` event and never forces NO_VERDICT."""
    runner = RoomRunner()
    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    assert not [ev for ev in events if ev.kind == "agent_withheld"]
    verdict_events = [ev for ev in events if ev.kind == "verdict"]
    assert len(verdict_events) == 1
    verdict = verdict_events[0].verdict
    assert verdict.action != VerdictAction.NO_VERDICT
    assert verdict.opinions_not_included == []


# ── #10 — NO_VERDICT holds even against a well-formed APPROVE fixture ──────


def test_no_verdict_never_reaches_llm_pm_turn():
    """The strongest form of #10: prove the LLM PM turn is never invoked at
    all when Market is withheld, so a well-formed APPROVE block (however
    perfectly it would parse) never has a chance to surface."""
    fake = _WellFormedApproveGateway()
    runner = RoomRunner(llm=fake)  # type: ignore[arg-type]
    mandate = hydrate_coach_mandate({"plan": "floor_pass", "risk_score": 3})
    events = _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
        roster=_market_withheld_roster(),
    ))
    assert fake.pm_called is False

    verdict_events = [ev for ev in events if ev.kind == "verdict"]
    assert len(verdict_events) == 1
    verdict = verdict_events[0].verdict
    assert verdict.action == VerdictAction.NO_VERDICT
    assert verdict.size_pct is None
    assert verdict.entry is None
    assert verdict.target is None
    assert verdict.stop is None
    assert verdict.time_horizon_days is None
    assert "market_analyst" in verdict.opinions_not_included

    withheld_events = [ev for ev in events if ev.kind == "agent_withheld"]
    assert len(withheld_events) == 1
    assert withheld_events[0].agent_id == AgentId.MARKET_ANALYST
    assert withheld_events[0].reason == "upgrade"


# ── #6 — fact-sheet stripping: exact declared line, no synthetic stand-in ──


def test_fact_sheet_strips_market_with_declared_line_no_synthetic():
    profile = {
        "ticker": "AAPL", "base_price": 150.0, "pe": "24.0",
        "rev_growth": 10, "profit_margin": 20, "net_cash": 100,
        "rsi": 999, "rsi_tone": "SHOULD NOT APPEAR", "trend": "SHOULD NOT APPEAR",
        "support": 111.0, "breakout": 222.0, "low": 90.0, "high": 200.0,
        "volume_tone": "SHOULD NOT APPEAR",
        "technicals_state": "withheld_tenure",
        "catalyst": "Q3 earnings", "sentiment_tone": "mixed", "sentiment_score": "typical",
    }
    block = _format_profile(profile)
    assert "RSI:" not in block
    assert "Recent range:" not in block
    assert "Volume:" not in block
    assert "999" not in block
    assert "Market technicals: not included in this session." in block


def test_fact_sheet_strips_news_and_social_with_declared_lines():
    profile = {
        "ticker": "AAPL", "base_price": 150.0, "pe": "24.0",
        "rev_growth": 10, "profit_margin": 20, "net_cash": 100,
        "rsi": 50, "rsi_tone": "neutral", "trend": "trading",
        "support": 111.0, "breakout": 222.0, "low": 90.0, "high": 200.0,
        "volume_tone": "in-line",
        "catalyst": "SHOULD NOT APPEAR", "forward_catalyst": "",
        "news_state": "withheld_tenure",
        "sentiment_tone": "SHOULD NOT APPEAR", "sentiment_score": "SHOULD NOT APPEAR",
        "social_state": "withheld_tenure",
    }
    block = _format_profile(profile)
    assert "SHOULD NOT APPEAR" not in block
    assert "Recent catalyst/headline: not included in this session." in block
    assert "Retail sentiment: not included in this session." in block


# ── #13 (+ non-negotiable): no agent-voiced prompt string ever sells ───────


@pytest.mark.parametrize("state_key,state_field", [
    ("technicals_state", "market"), ("news_state", "news"), ("social_state", "social"),
])
def test_withheld_declared_line_never_sells(state_key, state_field):
    profile = {
        "ticker": "AAPL", "base_price": 150.0, "pe": "24.0",
        "rev_growth": 10, "profit_margin": 20, "net_cash": 100,
        "rsi": 50, "rsi_tone": "n", "trend": "n", "support": 1, "breakout": 2,
        "low": 1, "high": 2, "volume_tone": "n", "catalyst": "c",
        "sentiment_tone": "n", "sentiment_score": "n",
        state_key: "withheld_tenure",
    }
    block = _format_profile(profile)
    # "$" appears legitimately for the reference price line elsewhere in the
    # block, so the ban is scoped to the declared-withheld sentence only.
    declared_lines = [
        ln for ln in block.splitlines()
        if "not included in this session" in ln
    ]
    assert declared_lines, f"no declared line found for {state_key}"
    for ln in declared_lines:
        low = ln.lower()
        assert "upgrade" not in low
        assert "floor pass" not in low
        assert "trader" not in low
        assert "floor manager" not in low
        assert "$" not in ln


def test_no_verdict_fixed_copy_never_sells():
    from app.services.room_runner import _NO_VERDICT_REASON
    text = _NO_VERDICT_REASON.format(ticker="AAPL").lower()
    for banned in ("upgrade", "floor pass", "floor manager", "trader plan", "$"):
        assert banned not in text


# ── D2 (assign) — withholding an analyst changes the CHARGE, deliberately ──


def test_aged_floor_pass_social_withheld_debited_strictly_less(monkeypatch):
    """An aged FLOOR_PASS user with Social withheld by tenure is debited
    strictly less than the same user with Social present, and the amount
    equals base + live_data_surcharge(feeds actually fetched)."""
    from app.services.news_context import LiveDataState, LiveHeadline, NewsFeed
    from app.services.social_context import SocialFeed, SocialSentiment

    monkeypatch.setattr(room_runner_mod.settings, "use_real_market_data", True)
    monkeypatch.setattr(room_runner_mod, "fetch_live_fundamentals", lambda *a, **k: None)
    monkeypatch.setattr(room_runner_mod, "compute_technicals", lambda *a, **k: None)

    headline = LiveHeadline(
        title="Acme beats Q3", link="https://x/1", publisher="Reuters",
        published_at=0, sentiment="Bullish", source="alpha_vantage",
    )
    sentiment = SocialSentiment(
        ticker="AAPL", buzz_score=61.0, sentiment_score=0.42, mentions=1234,
        bullish_pct=58, bearish_pct=30, trend="rising", period_days=7,
        top_subreddits=("stocks",), sample_snippets=(),
    )
    monkeypatch.setattr(
        room_runner_mod, "resolve_news_feed",
        lambda ticker, *, entitled, limit=3: NewsFeed(LiveDataState.LIVE, (headline,)),
    )
    monkeypatch.setattr(
        room_runner_mod, "resolve_social_feed",
        lambda ticker, *, entitled: SocialFeed(LiveDataState.LIVE, sentiment),
    )

    base = ROOM_COST_BASIC
    both_live_amount = base + live_data_surcharge(2)
    social_withheld_amount = base + live_data_surcharge(1)  # only News live
    assert social_withheld_amount < both_live_amount

    from app.core.config import settings as real_settings
    monkeypatch.setattr(real_settings, "room_pullback_days_social", 7)

    # User present on all four (day 3, under the threshold).
    present_user = _new_user(plan="floor_pass")
    _age_user(present_user, 3)
    _set_balance(present_user, both_live_amount)
    news_feed, social_feed, charged_present = room_runner_mod.RoomRunner()._resolve_and_charge_feeds(
        present_user, "AAPL",
        withheld=frozenset(room_runner_mod.resolve_roster_for_user(present_user).withheld),
    )
    assert charged_present == both_live_amount
    assert balance_for(present_user)[0] == 0

    # Aged user (day 10) — Social withheld by tenure.
    withheld_user = _new_user(plan="floor_pass")
    _age_user(withheld_user, 10)
    _set_balance(withheld_user, both_live_amount)  # same starting balance
    roster = room_runner_mod.resolve_roster_for_user(withheld_user)
    assert AgentId.SOCIAL_MEDIA_ANALYST in roster.withheld
    _, _, charged_withheld = room_runner_mod.RoomRunner()._resolve_and_charge_feeds(
        withheld_user, "AAPL", withheld=frozenset(roster.withheld),
    )

    assert charged_withheld < charged_present
    assert charged_withheld == social_withheld_amount
    assert balance_for(withheld_user)[0] == both_live_amount - social_withheld_amount


# ── Safety-floor regression (#7 / #12) — structurally roster-independent ───


def test_enforce_safety_floor_signature_carries_no_roster_param():
    """`enforce_safety_floor` never learned about the roster at all — its
    REJECT/APPROVE decision cannot vary by which analysts were withheld,
    because the function has no parameter through which that could happen."""
    params = set(inspect.signature(enforce_safety_floor).parameters)
    assert "roster" not in params
    assert "withheld" not in params


def test_enforce_safety_floor_passes_no_verdict_through_unchanged():
    """A NO_VERDICT input is a defensive no-op through the floor (it is not
    APPROVE, so the function returns it verbatim) — even though the live
    NO_VERDICT path never calls this function at all (it short-circuits
    before reaching it), the contract holds if anything ever did call it."""
    from app.schemas.trade import OrderType, ProposedTrade, Side

    verdict = Verdict(
        action=VerdictAction.NO_VERDICT, reason="No verdict.",
        opinions_not_included=["market_analyst"],
    )
    proposed = ProposedTrade(
        ticker="AAPL", side=Side.BUY, order_type=OrderType.LIMIT,
        quantity=1, limit_price=150.0,
    )
    mandate = hydrate_coach_mandate({"plan": "floor_pass", "risk_score": 3})
    out = enforce_safety_floor(
        llm_verdict=verdict, proposed=proposed, portfolio_value=100_000.0,
        current_drawdown_pct=0.0, mandate=mandate,
    )
    assert out is verdict


# ── #8 — opinions_not_included deterministic, present everywhere ───────────


def test_opinions_not_included_populated_from_roster_not_llm():
    runner = RoomRunner()  # no real provider -> scripted template path
    mandate = hydrate_coach_mandate({"plan": "floor_pass", "risk_score": 3})
    withheld_roster = AnalystRoster(
        present=(AgentId.FUNDAMENTALS_ANALYST, AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST),
        withheld=(AgentId.SOCIAL_MEDIA_ANALYST,), next_step=None,
    )
    events = _collect(runner.run(
        user_id=uuid4(), ticker="AAPL", mandate=mandate,
        char_delay_min=0.0, char_delay_max=0.0,
        roster=withheld_roster,
    ))
    verdict = [ev for ev in events if ev.kind == "verdict"][0].verdict
    assert verdict.opinions_not_included == ["social_media_analyst"]
    dumped = verdict.model_dump(mode="json")
    assert dumped["opinions_not_included"] == ["social_media_analyst"]


# ── #5 — fetch gating: a withheld analyst's provider is never even probed ──


def test_withholding_social_never_probes_adanos(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("resolve_social_feed called for a roster-withheld analyst")
    monkeypatch.setattr(room_runner_mod, "resolve_social_feed", _boom)
    monkeypatch.setattr(room_runner_mod.settings, "use_real_market_data", True)

    news_feed, social_feed, _ = room_runner_mod.RoomRunner()._resolve_and_charge_feeds(
        _new_user(plan="floor_pass"), "AAPL",
        withheld=frozenset({AgentId.SOCIAL_MEDIA_ANALYST}),
    )
    from app.services.social_context import LiveDataState as SocialLiveDataState
    assert social_feed.state == SocialLiveDataState.WITHHELD_TENURE


def test_withholding_news_never_probes_alpha_vantage(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("resolve_news_feed called for a roster-withheld analyst")
    monkeypatch.setattr(room_runner_mod, "resolve_news_feed", _boom)
    monkeypatch.setattr(room_runner_mod.settings, "use_real_market_data", True)

    news_feed, social_feed, _ = room_runner_mod.RoomRunner()._resolve_and_charge_feeds(
        _new_user(plan="floor_pass"), "AAPL",
        withheld=frozenset({AgentId.NEWS_ANALYST}),
    )
    from app.services.news_context import LiveDataState as NewsLiveDataState
    assert news_feed.state == NewsLiveDataState.WITHHELD_TENURE


def test_withholding_market_never_computes_technicals(monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("compute_technicals called for a roster-withheld Market analyst")
    monkeypatch.setattr(room_runner_mod, "compute_technicals", _boom)
    monkeypatch.setattr(room_runner_mod, "fetch_live_fundamentals", lambda *a, **k: None)
    monkeypatch.setattr(room_runner_mod.settings, "use_real_market_data", True)

    profile = room_runner_mod._profile_for_ticker(
        "AAPL", withheld=frozenset({AgentId.MARKET_ANALYST}),
    )
    assert profile["technicals_state"] == "withheld_tenure"


def test_fundamentals_fetch_always_runs_even_when_others_withheld(monkeypatch):
    calls = []
    monkeypatch.setattr(
        room_runner_mod, "fetch_live_fundamentals",
        lambda ticker: calls.append(ticker) or None,
    )
    monkeypatch.setattr(room_runner_mod, "compute_technicals", lambda *a, **k: None)
    monkeypatch.setattr(room_runner_mod.settings, "use_real_market_data", True)

    room_runner_mod._profile_for_ticker(
        "AAPL",
        withheld=frozenset({
            AgentId.MARKET_ANALYST, AgentId.NEWS_ANALYST, AgentId.SOCIAL_MEDIA_ANALYST,
        }),
    )
    assert calls == ["AAPL"]
