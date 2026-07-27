"""CR090-ROOM (AT:coder.room) — wire the live-data surcharge into the Room.

CR090-BE shipped the surcharge contract (`LiveDataState`, `resolve_news_feed`,
`resolve_social_feed`, `live_data_surcharge`) and nothing consumed it. This lane
consumes it on the Room surface. These tests pin the five Architect decisions:

  D1 — ONE atomic charge before the run (base + surcharge in a single spend).
  D2 — entitlement is the credit BALANCE, not a plan tier.
  D3 — the "paid feature withheld" disclosure is STRUCTURAL (an event on the
       stream, model out of the loop), not a prompt instruction agents drop.
  D4 — the charge matches what was rendered: charged n_live == feeds marked
       live in the profile handed to the agents (the single most valuable test).
  D5 — WITHHELD_PAID and UNAVAILABLE are charged nothing; UNAVAILABLE keeps the
       honest synthetic fallback.

All feed I/O is stubbed at the `room_runner` module boundary and the gateway is
kept out of the loop (no real provider ⇒ scripted templates), so nothing here
touches the network or an LLM.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import pytest

from app.db import get_session
from app.db.models import User
from app.schemas.mandate import Plan
from app.services import room_runner as room_runner_mod
from app.services.auth_service import AuthService
from app.services.coach_engine import hydrate_coach_mandate
from app.services.credit_service import (
    LIVE_DATA_SURCHARGE,
    ROOM_COST_BASIC,
    ROOM_COST_PREMIUM,
    InsufficientCredits,
    balance_for,
    live_data_surcharge,
)
from app.services.news_context import LiveDataState, LiveHeadline, NewsFeed
from app.services.room_prompts import _format_profile
from app.services.room_runner import RoomRunner
from app.services.social_context import SocialFeed, SocialSentiment


# ── Fixtures / helpers ────────────────────────────────────────────────────


def _new_user(plan: str = "floor_pass") -> UUID:
    auth = AuthService()
    u, _, _ = auth.ensure_anonymous(device_user_id=None)
    if plan != "floor_pass":
        with get_session() as s:
            s.get(User, u.id).plan = plan
    return u.id


def _set_balance(user_id: UUID, amount: int) -> None:
    """Establish the allowance window (so a later read won't re-grant), then pin
    the balance to an exact figure — the CR039/winzip tests use the same trick."""
    balance_for(user_id)  # grants + stamps the period
    with get_session() as s:
        s.get(User, user_id).credit_balance = amount


_HEADLINE = LiveHeadline(
    title="Acme beats Q3 by 6%", link="https://x/1", publisher="Reuters",
    published_at=0, sentiment="Bullish", source="alpha_vantage",
)
_SENTIMENT = SocialSentiment(
    ticker="AAPL", buzz_score=61.0, sentiment_score=0.42, mentions=1234,
    bullish_pct=58, bearish_pct=30, trend="rising", period_days=7,
    top_subreddits=("stocks", "wallstreetbets"), sample_snippets=(),
)


def _stub_feeds(monkeypatch, *, news_available: bool, social_available: bool) -> None:
    """Stub the availability probe. The probe runs at entitled=True, so LIVE ==
    'data exists'; `_resolve_and_charge_feeds` decides the FINAL state from the
    balance. Also force `use_real_market_data` on (the probe gate) and neuter the
    fundamentals overlay so the run stays hermetic — no network, no LLM."""
    monkeypatch.setattr(room_runner_mod.settings, "use_real_market_data", True)

    def _news(ticker, *, entitled, limit=3):
        return NewsFeed(
            LiveDataState.LIVE if news_available else LiveDataState.UNAVAILABLE,
            (_HEADLINE,) if news_available else (),
        )

    def _social(ticker, *, entitled):
        return SocialFeed(
            LiveDataState.LIVE if social_available else LiveDataState.UNAVAILABLE,
            _SENTIMENT if social_available else None,
        )

    monkeypatch.setattr(room_runner_mod, "resolve_news_feed", _news)
    monkeypatch.setattr(room_runner_mod, "resolve_social_feed", _social)
    # Keep the fundamentals/technicals/earnings overlay off the wire.
    monkeypatch.setattr(room_runner_mod, "fetch_live_fundamentals", lambda *a, **k: None)
    monkeypatch.setattr(room_runner_mod, "compute_technicals", lambda *a, **k: None)


class _ExplodingGateway:
    """Proves the LLM is entirely out of the loop: no real provider ⇒ the runner
    takes the scripted-template path and never calls stream_chat. If anything
    tried to, this raises."""

    def has_real_provider(self) -> bool:
        return False

    async def stream_chat(self, *a, **k):  # pragma: no cover - must never run
        raise AssertionError("LLM was invoked; disclosure must be model-free")
        yield  # noqa


async def _drain(runner: RoomRunner, run_id: UUID) -> list:
    return [ev async for ev in runner.subscribe(run_id)]


def _run_room(monkeypatch, user_id: UUID, *, plan="trader", ticker="AAPL") -> list:
    """Run a full Room via start_run and return the collected events."""
    runner = RoomRunner(llm=_ExplodingGateway())
    mandate = hydrate_coach_mandate({"plan": plan, "risk_score": 3})

    async def _go():
        run_id = await runner.start_run(
            user_id=user_id, ticker=ticker, mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        return await _drain(runner, run_id)

    return asyncio.run(_go())


def _notice(events: list) -> dict:
    for ev in events:
        if ev.kind == "live_data_notice":
            return ev.live_data
    raise AssertionError("no live_data_notice event on the stream")


# ── D2 / D1: entitled buys the whole live bundle, one atomic charge ────────


def test_entitled_user_buys_both_live_feeds_debited_base_plus_surcharge(monkeypatch):
    _stub_feeds(monkeypatch, news_available=True, social_available=True)
    user_id = _new_user(plan="floor_pass")
    base = ROOM_COST_BASIC
    _set_balance(user_id, base + 2 * LIVE_DATA_SURCHARGE)  # exactly affordable: 12

    events = _run_room(monkeypatch, user_id, plan="floor_pass")

    # Debited exactly base + 4 — asserted on the real balance, not a mock.
    assert balance_for(user_id)[0] == 0
    notice = _notice(events)
    assert notice == {
        "news": "live", "social": "live",
        "surcharge_charged": 2 * LIVE_DATA_SURCHARGE,
    }


def test_user_with_exactly_base_gets_withheld_paid_and_pays_only_base(monkeypatch):
    """A user who can afford the Room but not the live bundle: WITHHELD_PAID, the
    loud notice, debited exactly base (D2/D5)."""
    _stub_feeds(monkeypatch, news_available=True, social_available=True)
    user_id = _new_user(plan="floor_pass")
    _set_balance(user_id, ROOM_COST_BASIC)  # exactly base — surcharge unaffordable

    events = _run_room(monkeypatch, user_id, plan="floor_pass")

    assert balance_for(user_id)[0] == 0  # debited exactly base, surcharge free
    notice = _notice(events)
    assert notice == {"news": "withheld_paid", "social": "withheld_paid",
                      "surcharge_charged": 0}


def test_entitlement_is_balance_not_plan_tier(monkeypatch):
    """D2: a premium plan with a thin balance is NOT entitled, while a cheaper
    plan with enough credits IS — entitlement rides the balance, not the tier."""
    _stub_feeds(monkeypatch, news_available=True, social_available=True)

    # Floor Manager (premium base 25) with exactly base — can't afford surcharge.
    fm = _new_user(plan="floor_manager")
    _set_balance(fm, ROOM_COST_PREMIUM)
    fm_events = _run_room(monkeypatch, fm, plan="floor_manager")
    assert _notice(fm_events)["news"] == "withheld_paid"
    assert balance_for(fm)[0] == 0  # charged base only

    # Floor Pass (base 8) with base + surcharge — cheaper plan, but entitled.
    fp = _new_user(plan="floor_pass")
    _set_balance(fp, ROOM_COST_BASIC + 2 * LIVE_DATA_SURCHARGE)
    fp_events = _run_room(monkeypatch, fp, plan="floor_pass")
    assert _notice(fp_events)["news"] == "live"


# ── D4: the charge matches what was rendered ───────────────────────────────


@pytest.mark.parametrize(
    "news_avail,social_avail,affordable_extra,expected_live",
    [
        (True, True, 2 * LIVE_DATA_SURCHARGE, 2),   # both live
        (True, False, LIVE_DATA_SURCHARGE, 1),      # only news live
        (False, True, LIVE_DATA_SURCHARGE, 1),      # only social live
        (True, True, LIVE_DATA_SURCHARGE, 0),        # can't afford the bundle
    ],
)
def test_charged_surcharge_equals_rendered_live_feeds(
    monkeypatch, news_avail, social_avail, affordable_extra, expected_live
):
    """The most valuable test in the lane (D4): the surcharge actually debited
    equals live_data_surcharge(number of feeds rendered LIVE in the profile the
    agents saw). A fetch/price divergence would break this."""
    _stub_feeds(monkeypatch, news_available=news_avail, social_available=social_avail)
    user_id = _new_user(plan="floor_pass")
    base = ROOM_COST_BASIC
    _set_balance(user_id, base + affordable_extra)

    # Spy on the exact profile handed to the agents.
    captured: dict = {}
    orig = room_runner_mod._profile_for_ticker

    def _spy(ticker, **kw):
        p = orig(ticker, **kw)
        captured["profile"] = p
        return p

    monkeypatch.setattr(room_runner_mod, "_profile_for_ticker", _spy)

    before = balance_for(user_id)[0]
    events = _run_room(monkeypatch, user_id, plan="floor_pass")
    charged = before - balance_for(user_id)[0]

    profile = captured["profile"]
    n_live_rendered = sum(
        1 for k in ("news_state", "social_state")
        if profile.get(k) == LiveDataState.LIVE.value
    )
    assert n_live_rendered == expected_live
    # charged == base + surcharge(rendered live feeds): the money identity.
    assert charged == base + live_data_surcharge(n_live_rendered)
    # And the notice reports exactly that surcharge (no phantom billing).
    assert _notice(events)["surcharge_charged"] == live_data_surcharge(n_live_rendered)
    # A LIVE feed carries its real payload; a non-LIVE feed never does.
    if profile.get("news_state") == "live":
        assert profile.get("news_source") == "live"
    else:
        assert profile.get("news_source") != "live"


# ── D3: the disclosure is structural, LLM entirely out of the loop ─────────


def test_notice_reaches_the_stream_with_the_llm_stubbed(monkeypatch):
    """D3: the disclosure must be observable on the event stream with the model
    completely out of the loop — never buried inside generated text. The gateway
    used here raises if the LLM is ever called; the notice still fires, and it
    arrives before any agent speaks."""
    _stub_feeds(monkeypatch, news_available=True, social_available=True)
    user_id = _new_user(plan="floor_pass")
    _set_balance(user_id, ROOM_COST_BASIC)  # WITHHELD_PAID path

    events = _run_room(monkeypatch, user_id, plan="floor_pass")

    kinds = [ev.kind for ev in events]
    assert "live_data_notice" in kinds
    # Structural: the notice precedes the first agent token (it does not depend
    # on any agent having spoken).
    notice_idx = kinds.index("live_data_notice")
    if "agent_token" in kinds:
        assert notice_idx < kinds.index("agent_token")
    assert _notice(events)["news"] == "withheld_paid"


def test_format_profile_renders_withheld_paid_anti_fabrication_header():
    """The prompt header's third state (anti-fabrication measure). A withheld
    feed must be told apart from an unavailable one and must NOT read as LIVE."""
    profile = {
        "news_state": "withheld_paid",
        "social_state": "unavailable",
        "base_price": 100.0, "pe": "20.0", "rev_growth": 10, "profit_margin": 20,
        "net_cash": 1000, "rsi": 50, "rsi_tone": "neutral", "trend": "flat",
        "support": 90.0, "breakout": 110.0, "low": 80.0, "high": 120.0,
        "volume_tone": "in-line", "catalyst": "synthetic catalyst",
        "forward_catalyst": "FOMC in 10d", "sentiment_tone": "mixed",
        "sentiment_score": "typical (illustrative)",
    }
    out = _format_profile(profile)
    assert "PAID feature" in out
    assert "withheld" in out.lower()
    # It must not claim the news feed is live.
    assert "Recent catalyst/headline: LIVE" not in out
    # The unavailable social feed still degrades to the plain synthetic line.
    assert "NOT a live social feed" in out


# ── D5: WITHHELD_PAID / UNAVAILABLE cost nothing; UNAVAILABLE keeps fallback ─


def test_no_live_data_available_charges_base_only(monkeypatch):
    """UNAVAILABLE everywhere: no surcharge, both feeds unavailable, and the
    charge stays byte-for-byte the CR039 base path (D5)."""
    _stub_feeds(monkeypatch, news_available=False, social_available=False)
    user_id = _new_user(plan="floor_pass")  # full allowance 13

    events = _run_room(monkeypatch, user_id, plan="floor_pass")

    assert balance_for(user_id)[0] == 13 - ROOM_COST_BASIC  # 5 — base only
    assert _notice(events) == {"news": "unavailable", "social": "unavailable",
                               "surcharge_charged": 0}


def test_failed_run_refunds_the_full_charge_including_surcharge(monkeypatch):
    """The failure-path refund must return base + surcharge, not just base —
    else a bad deploy silently eats the live-data credits the user paid."""
    _stub_feeds(monkeypatch, news_available=True, social_available=True)

    def _boom(**_kwargs):
        raise RuntimeError("simulated agent failure")

    monkeypatch.setattr(room_runner_mod, "_speak_one_agent", _boom)

    user_id = _new_user(plan="floor_pass")
    _set_balance(user_id, ROOM_COST_BASIC + 2 * LIVE_DATA_SURCHARGE)
    before = balance_for(user_id)[0]

    runner = RoomRunner(llm=_ExplodingGateway())
    mandate = hydrate_coach_mandate({"plan": "floor_pass", "risk_score": 3})

    async def _go():
        run_id = await runner.start_run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )
        await _drain(runner, run_id)
        return run_id

    run_id = asyncio.run(_go())
    run = runner.get_run(run_id)
    assert run is not None and run.status == "failed"
    assert run.credit_cost == ROOM_COST_BASIC + 2 * LIVE_DATA_SURCHARGE
    assert balance_for(user_id)[0] == before, "failed live-data run must fully refund"


def test_genuinely_broke_user_still_hits_the_402(monkeypatch):
    """Below base: the existing InsufficientCredits → 402 path is unchanged, and
    no live-data probe changes that."""
    _stub_feeds(monkeypatch, news_available=True, social_available=True)
    user_id = _new_user(plan="floor_pass")
    _set_balance(user_id, ROOM_COST_BASIC - 1)

    runner = RoomRunner(llm=_ExplodingGateway())
    mandate = hydrate_coach_mandate({"plan": "floor_pass", "risk_score": 3})

    async def _go():
        await runner.start_run(
            user_id=user_id, ticker="AAPL", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        )

    with pytest.raises(InsufficientCredits):
        asyncio.run(_go())
    assert balance_for(user_id)[0] == ROOM_COST_BASIC - 1, "refused spend must not debit"
