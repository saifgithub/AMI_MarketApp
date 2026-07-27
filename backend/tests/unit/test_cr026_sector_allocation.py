"""CR026 — sector-concentration enforcement + Portfolio-screen allocation feed.

Closes the gap where the mandate advertised a sector-concentration rule ("no sector >
40%", default — lifecycle.md) with ZERO backend enforcement. Coverage mirrors the
DEF061/CR075 pattern this rides alongside:

  * `allocate_by_sector` — the pure aggregation (weights, empty, unknown → "Other");
  * the deterministic safety floor BLOCKS a sector-cap breach — a FAIL-WITHOUT-FIX
    regression (delete the CR026 block in `safety_floor.py` and the block test goes
    red — the DEF039/DEF049 adversarial pattern). This is the core deliverable;
  * a compliant portfolio PASSES, and `max_allowed` is READ from the mandate's
    concentration_tolerance (default 0.40), not a constant;
  * the "Other" (unclassified) bucket NEVER breaches (the DEF059 inversion guard);
  * the endpoint returns the contract + enforces ownership (403), mirroring CR029;
  * the ticker → sector resolve serves from the STORED snapshot with NO request-path
    socket (mirrors CR075's no-socket assertion — a D-5 acceptance item);
  * the classify pass captures the per-ticker sector map, and `write_snapshot` /
    `latest_sector_map` round-trip it;
  * the PM prompt context carries the real sector weights, not silence.

Fixture-based: never touches the network on the read/enforcement paths. Live sector
classification pairs with the next promote (like DEF061 — the Mac worktree has no DB
parent set to classify).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.safety_floor import check_mandate_compliance
from app.api.dependencies import get_current_user
from app.api.portfolio import get_sector_map, router as portfolio_router
from app.db import get_session
from app.schemas import Mandate, RiskComponents
from app.schemas.agents import AgentId
from app.schemas.trade import OrderType, ProposedTrade, Side
from app.services import classification_universe as cu
from app.services import sector_allocation as salloc
from app.services.classification_universe import default_classification_universe
from app.services.coach_engine import hydrate_coach_mandate
from app.services.sector_allocation import (
    OTHER,
    SectorMap,
    allocate_by_sector,
    sector_cap_breach,
    sector_concentration_cap,
)
from app.services.sharia_universe import default_halal_universe
from app.services.sim_engine import SimEngine, get_sim_engine
from app.services import market_data as _md


def _collect(coro_gen) -> list:
    async def run():
        events = []
        async for ev in coro_gen:
            events.append(ev)
        return events
    return asyncio.run(run())


# ── Duck-typed holding (only .ticker / .quantity are read) ────────────────────


@dataclass
class _H:
    ticker: str
    quantity: float


_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "JPM": "Financial Services",
    "XOM": "Energy",
}


def _map() -> SectorMap:
    return SectorMap(mapping=dict(_SECTORS))


def _sector_of(ticker: str) -> str:
    return _SECTORS.get(ticker.upper(), OTHER)


# ── 1. allocate_by_sector — the pure aggregation ──────────────────────────────


def test_allocate_by_sector_weights_multi_sector():
    holdings = [_H("AAPL", 10), _H("MSFT", 10), _H("JPM", 10)]
    quotes = {"AAPL": 100.0, "MSFT": 100.0, "JPM": 200.0}
    # Tech = 1000 + 1000 = 2000; FS = 2000; total 4000 → 50/50.
    alloc = allocate_by_sector(holdings, quotes, sector_of=_sector_of)
    assert alloc == pytest.approx({"Technology": 0.5, "Financial Services": 0.5})
    assert sum(alloc.values()) == pytest.approx(1.0)


def test_allocate_by_sector_empty_portfolio_is_empty_dict():
    assert allocate_by_sector([], {}, sector_of=_sector_of) == {}
    # All-zero value (no marks) also collapses to {}.
    assert allocate_by_sector([_H("AAPL", 10)], {}, sector_of=_sector_of) == {}


def test_allocate_by_sector_unknown_ticker_goes_to_other():
    holdings = [_H("AAPL", 10), _H("ZZZZ", 10)]
    quotes = {"AAPL": 100.0, "ZZZZ": 100.0}
    alloc = allocate_by_sector(holdings, quotes, sector_of=_sector_of)
    assert alloc == pytest.approx({"Technology": 0.5, OTHER: 0.5})


# ── 2. The deterministic safety floor BLOCKS a sector-cap breach ──────────────
# FAIL-WITHOUT-FIX: this is the compliance gap CR026 closes. Delete block "6b) in
# safety_floor.check_mandate_compliance and `test_sector_cap_blocks_breaching_buy`
# goes red (the trade is no longer rejected). DEF039/DEF049 adversarial pattern.


def _breach_check(mandate: Mandate, *, buy_value: float):
    """A portfolio at Tech 30% / FS 30% / Energy 40% (total $10k invested); the
    proposed BUY adds Tech at limit $100. buy_value = 100 * qty."""
    holdings = [_H("AAPL", 30), _H("JPM", 30), _H("XOM", 40)]
    quotes = {"AAPL": 100.0, "JPM": 100.0, "XOM": 100.0}
    qty = buy_value / 100.0
    proposed = ProposedTrade(
        ticker="MSFT", side=Side.BUY, quantity=qty, limit_price=100.0
    )
    return check_mandate_compliance(
        proposed,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
        holdings=holdings,
        quotes=quotes,
        sector_map=_map(),
    )


def test_sector_cap_blocks_breaching_buy(base_mandate: Mandate):
    # Buying $2000 MSFT (Tech) → Tech 3000+2000=5000 of 12000 = 41.7% > 40% cap.
    res = _breach_check(base_mandate, buy_value=2000.0)
    assert not res.passed
    assert res.blocked_by == "compliance"
    assert any("technology" in v.lower() for v in res.violations)
    assert any("sector-concentration limit" in v.lower() for v in res.violations)


def test_sector_cap_passes_a_compliant_buy(base_mandate: Mandate):
    # Buying $500 MSFT (Tech) → Tech 3500 of 10500 = 33.3% < 40% cap.
    res = _breach_check(base_mandate, buy_value=500.0)
    assert res.passed
    assert res.blocked_by is None
    assert res.violations == []


def test_sector_check_is_skipped_without_sector_context(base_mandate: Mandate):
    """A caller that passes no sector_map behaves exactly as before CR026 — the
    single-name block is byte-unchanged and no sector violation appears."""
    proposed = ProposedTrade(ticker="MSFT", side=Side.BUY, quantity=20, limit_price=100.0)
    res = check_mandate_compliance(
        proposed,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        mandate=base_mandate,
    )
    assert res.passed
    assert res.violations == []


def test_other_bucket_never_blocks_the_inversion_guard(base_mandate: Mandate):
    """An unclassified ticker resolves to 'Other' and can NEVER breach — blocking on
    unknown would reject every unclassified name (the DEF059 inversion trap)."""
    holdings = [_H("ZZZZ", 100)]  # already 100% 'Other'
    quotes = {"ZZZZ": 100.0}
    # A small buy (10% of portfolio) so the single-name cap isn't the blocker — the
    # point is that the 'Other' sector at ~100% still never triggers a sector block.
    proposed = ProposedTrade(ticker="YYYY", side=Side.BUY, quantity=10, limit_price=100.0)
    res = check_mandate_compliance(
        proposed,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        mandate=base_mandate,
        holdings=holdings,
        quotes=quotes,
        sector_map=_map(),  # neither ZZZZ nor YYYY is in it → both 'Other'
    )
    assert res.passed
    assert not any("sector-concentration" in v.lower() for v in res.violations)


def test_sector_cap_breach_helper_only_flags_the_proposed_sector():
    holdings = [_H("AAPL", 30), _H("JPM", 30), _H("XOM", 40)]
    quotes = {"AAPL": 100.0, "JPM": 100.0, "XOM": 100.0}
    # Buying MORE Energy (already 40%) breaches; buying FS does not.
    breach = sector_cap_breach(
        holdings=holdings, quotes=quotes, proposed_ticker="XOM",
        proposed_value=2000.0, sector_map=_map(), cap=0.40,
    )
    assert breach is not None and breach.sector == "Energy"
    assert breach.projected_weight > 0.40
    ok = sector_cap_breach(
        holdings=holdings, quotes=quotes, proposed_ticker="JPM",
        proposed_value=500.0, sector_map=_map(), cap=0.40,
    )
    assert ok is None


# ── 3. max_allowed reads the mandate, default 0.40 (never a constant) ──────────


def test_sector_cap_reads_mandate_default_is_040(base_mandate: Mandate):
    # base_mandate has concentration_tolerance=3 (the default) → 0.40.
    assert base_mandate.risk_components.concentration_tolerance == 3
    assert sector_concentration_cap(base_mandate) == 0.40


def test_sector_cap_tightens_for_concentration_averse(base_mandate: Mandate):
    m = base_mandate.model_copy(
        update={
            "risk_components": RiskComponents(
                drawdown_response=1, regret_asymmetry=-1, concentration_tolerance=1
            )
        }
    )
    assert sector_concentration_cap(m) == 0.25  # not the 0.40 default → read, not hard-coded


# ── 4. Endpoint: contract + ownership (mirrors CR029 lots endpoint) ───────────


class _ConstProvider:
    name = "fake"

    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def quote(self, ticker: str):
        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price

    def history(self, ticker: str, period: str):
        return None

    def news(self, ticker: str, limit: int = 5):
        return None

    def earnings(self, ticker: str):
        return None


def _engine_with_buy(user_id: UUID, ticker: str, qty: float, price: float) -> SimEngine:
    sim = SimEngine(provider=_ConstProvider(price))
    mandate = hydrate_coach_mandate({"plan": "trader"})
    result = sim.submit(
        user_id=user_id, ticker=ticker, side=Side.BUY, quantity=qty, mandate=mandate,
    )
    assert result.accepted, result.compliance.violations
    return sim


def _app(sim: SimEngine, user_id: UUID) -> FastAPI:
    app = FastAPI()
    app.include_router(portfolio_router)
    app.dependency_overrides[get_sim_engine] = lambda: sim
    app.dependency_overrides[get_current_user] = lambda: _U(id=user_id)
    app.dependency_overrides[get_sector_map] = lambda: _map()
    return app


@dataclass
class _U:
    id: UUID


def test_sector_allocation_endpoint_contract_and_ownership():
    user_id = uuid4()
    sim = _engine_with_buy(user_id, "AAPL", qty=10, price=100.0)
    app = _app(sim, user_id)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.get(f"/v1/portfolio/sector-allocation/{user_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) == {"allocation", "total_value", "compliance"}
    assert body["allocation"] == {"Technology": 1.0}  # 100% AAPL → Technology
    assert body["total_value"] == pytest.approx(1000.0)
    comp = body["compliance"]
    assert set(comp.keys()) == {"max_sector", "max_sector_name", "max_allowed", "compliant"}
    # A single-name Tech book is 100% > 40% → non-compliant, and max_allowed is the
    # mandate default 0.40 (a fresh user resolves to the hydrated default mandate).
    assert comp["max_allowed"] == 0.40
    assert comp["max_sector_name"] == "Technology"
    assert comp["max_sector"] == pytest.approx(1.0)
    assert comp["compliant"] is False

    # Another user cannot read this user's allocation.
    app.dependency_overrides[get_current_user] = lambda: _U(id=uuid4())
    r = client.get(f"/v1/portfolio/sector-allocation/{user_id}")
    assert r.status_code == 403


def test_sector_allocation_endpoint_empty_portfolio():
    user_id = uuid4()
    sim = SimEngine(provider=_ConstProvider(100.0))
    app = _app(sim, user_id)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/v1/portfolio/sector-allocation/{user_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["allocation"] == {}
    assert body["total_value"] == 0.0
    assert body["compliance"]["compliant"] is True  # nothing held → nothing breaches


# ── 5. Sector resolve serves from the STORED snapshot with NO socket ──────────


def _no_yf_socket(monkeypatch):
    """The classify source is 'down' — a read-path resolve must NOT call it."""
    def _boom(*a, **k):
        raise AssertionError("read path opened a yfinance socket — _yf_info called")

    monkeypatch.setattr(cu, "_yf_info", _boom)


def test_sector_map_resolves_from_stored_row_without_a_socket(monkeypatch):
    _no_yf_socket(monkeypatch)
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        cu.write_snapshot(
            s,
            classified={"AAPL", "XOM"},
            fossil={"XOM"},
            sin=set(),
            defense=set(),
            fetched_at=now,
            sectors={"AAPL": "Technology", "XOM": "Energy"},
        )
    salloc.reset_sector_map_provider(None)
    try:
        smap = salloc.default_sector_map()  # production accessor, local read only
        assert smap.sector("AAPL") == "Technology"
        assert smap.sector("XOM") == "Energy"
        assert smap.sector("NEVR") == OTHER  # unknown → Other, still no socket
    finally:
        salloc.reset_sector_map_provider(None)


def test_empty_or_pre_cr026_snapshot_resolves_everything_to_other(monkeypatch):
    _no_yf_socket(monkeypatch)
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        # A pre-CR026 row (no sectors) → the map reads empty, everything is 'Other'.
        cu.write_snapshot(
            s, classified={"AAPL"}, fossil=set(), sin=set(), defense=set(),
            fetched_at=now,
        )
    salloc.reset_sector_map_provider(None)
    try:
        smap = salloc.default_sector_map()
        assert smap.is_empty
        assert smap.sector("AAPL") == OTHER
    finally:
        salloc.reset_sector_map_provider(None)


# ── 6. The classify pass captures sectors; write/read round-trip ──────────────


def test_network_classify_captures_the_sector_map():
    infos = {}
    for i in range(405):
        infos[f"T{i:03d}"] = {"sector": "Technology", "industry": "Software"}
    infos["T001"] = {"sector": "Energy", "industry": "Oil & Gas Integrated"}
    infos["T002"] = {"sector": "Financial Services", "industry": "Banks - Diversified"}
    infos["T003"] = {}  # no sector → left unclassified AND out of the sector map

    sectors: dict[str, str] = {}
    classified, fossil, sin, defense = cu._network_classify(
        list(infos), info_fetcher=lambda t: infos[t], throttle_s=0, sectors_out=sectors,
    )
    assert "T003" not in classified and "T003" not in sectors
    assert sectors["T001"] == "Energy"
    assert sectors["T002"] == "Financial Services"
    assert len(sectors) == len(classified) == 404


def test_write_and_read_sector_map_round_trip():
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        cu.write_snapshot(
            s, classified={"AAPL", "XOM"}, fossil={"XOM"}, sin=set(), defense=set(),
            fetched_at=now, sectors={"aapl": "Technology", "XOM": "Energy"},
        )
    with get_session() as s:
        m = cu.latest_sector_map(s)
    assert m == {"AAPL": "Technology", "XOM": "Energy"}  # keys upper-cased on write


def test_canonical_sector_normalises_and_drops_blank():
    assert cu.canonical_sector("  Technology ") == "Technology"
    assert cu.canonical_sector("Consumer  Defensive") == "Consumer Defensive"
    assert cu.canonical_sector(None) is None
    assert cu.canonical_sector("") is None


# ── 7. PM prompt context carries the real sector weights ──────────────────────


def test_pm_prompt_context_contains_real_sector_weights(base_mandate: Mandate):
    from app.services.room_prompts import build_room_messages

    system_prompt, _msgs = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=base_mandate,
        user_id=None,
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        sector_weights={"Technology": 0.62, "Energy": 0.38},
    )
    assert "current sector allocation" in system_prompt.lower()
    assert "Technology 62%" in system_prompt
    assert "Energy 38%" in system_prompt


def test_pm_prompt_context_states_empty_portfolio_not_silence(base_mandate: Mandate):
    from app.services.room_prompts import build_room_messages

    system_prompt, _msgs = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=base_mandate,
        user_id=None,
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        sector_weights={},
    )
    assert "no open positions yet" in system_prompt.lower()


def test_non_pm_agent_gets_no_sector_line(base_mandate: Mandate):
    from app.services.room_prompts import build_room_messages

    system_prompt, _msgs = build_room_messages(
        agent_id=AgentId.TRADER,
        mandate=base_mandate,
        user_id=None,
        ticker="MSFT",
        profile={"base_price": 100.0},
        transcript=[],
        sector_weights={"Technology": 0.62},
    )
    assert "sector allocation" not in system_prompt.lower()


# ── 8. Round-2 audit requirement — structural per-call-site wiring tests ──────
#
# The round-1 audit (CR026.auditor.md) found that every test above exercises
# the PURE `check_mandate_compliance`/`sector_cap_breach` functions directly
# with hand-built holdings/quotes/sector_map arguments — none of them pin
# that the four REAL call sites actually supply those three arguments. Block
# 6b is designed to silently no-op when sector context is absent (backward
# compat for legacy callers), so a regression that drops the wiring at any
# one of these sites would silently disable the D-5 sector-concentration
# cap with zero test failure. Round 2 requires one structural test per site
# (mirrors CR055's "any call site" pattern) — each verified red when its
# call site's wiring is removed, then restored, before landing this file.


def test_sim_engine_submit_rejects_a_sector_breaching_buy_end_to_end():
    """SimEngine.submit() end-to-end — not check_mandate_compliance() directly.

    Would go red if sim_engine.py's submit() dropped
    holdings=/quotes=/sector_map= from its check_mandate_compliance() call.
    """
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        cu.write_snapshot(
            s, classified=set(_SECTORS), fossil=set(), sin=set(), defense=set(),
            fetched_at=now, sectors=dict(_SECTORS),
        )
    salloc.reset_sector_map_provider(None)
    try:
        user_id = uuid4()
        sim = SimEngine(provider=_ConstProvider(100.0))
        mandate = hydrate_coach_mandate({"plan": "trader"})
        # Tech 30% / FS 30% / Energy 40% book on $10k invested (mirrors the
        # pure-function fixture above).
        for ticker, qty in (("AAPL", 30), ("JPM", 30), ("XOM", 40)):
            r = sim.submit(
                user_id=user_id, ticker=ticker, side=Side.BUY,
                quantity=qty, mandate=mandate,
            )
            assert r.accepted, r.compliance.violations

        # Buying $2000 more Tech (MSFT) → 5000/12000 = 41.7% > 40% cap. LIMIT
        # order (not MARKET) — block 6b prices the proposed BUY off
        # `proposed.limit_price` (the FLAG 2 market-order gap parity noted in
        # the round-1 audit), so a MARKET order here would price at $0 and
        # never reach the sector check at all.
        result = sim.submit(
            user_id=user_id, ticker="MSFT", side=Side.BUY,
            quantity=20, mandate=mandate,
            order_type=OrderType.LIMIT, limit_price=100.0,
        )
        assert not result.accepted
        assert result.compliance.blocked_by == "compliance"
        assert any(
            "sector-concentration limit" in v.lower()
            for v in result.compliance.violations
        )
    finally:
        salloc.reset_sector_map_provider(None)


def test_sim_engine_preview_rejects_a_sector_breaching_buy_end_to_end():
    """SimEngine.preview() end-to-end — the dry-run gate, same as submit().

    Would go red if sim_engine.py's preview() dropped
    holdings=/quotes=/sector_map= from its check_mandate_compliance() call.
    """
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        cu.write_snapshot(
            s, classified=set(_SECTORS), fossil=set(), sin=set(), defense=set(),
            fetched_at=now, sectors=dict(_SECTORS),
        )
    salloc.reset_sector_map_provider(None)
    try:
        user_id = uuid4()
        sim = SimEngine(provider=_ConstProvider(100.0))
        mandate = hydrate_coach_mandate({"plan": "trader"})
        for ticker, qty in (("AAPL", 30), ("JPM", 30), ("XOM", 40)):
            r = sim.submit(
                user_id=user_id, ticker=ticker, side=Side.BUY,
                quantity=qty, mandate=mandate,
            )
            assert r.accepted, r.compliance.violations

        # LIMIT order — see the submit() test above for why (block 6b prices
        # off `proposed.limit_price`, the FLAG 2 market-order gap parity).
        preview = sim.preview(
            user_id=user_id, ticker="MSFT", side=Side.BUY,
            quantity=20, mandate=mandate,
            order_type=OrderType.LIMIT, limit_price=100.0,
        )
        assert not preview.accepted
        assert preview.compliance.blocked_by == "compliance"
        assert any(
            "sector-concentration limit" in v.lower()
            for v in preview.compliance.violations
        )
    finally:
        salloc.reset_sector_map_provider(None)


def test_assemble_verdict_scripted_path_rejects_a_sector_breaching_buy(
    base_mandate: Mandate,
):
    """room_runner._assemble_verdict (scripted/non-live path) — sector context
    (ctx.sector_holdings/ctx.sector_marks/ctx.sector_map) must reach the
    deterministic safety-floor call.

    Would go red if _assemble_verdict dropped
    holdings=ctx.sector_holdings/quotes=ctx.sector_marks/sector_map=ctx.sector_map
    from its check_mandate_compliance() call.
    """
    from app.schemas.room import VerdictAction
    from app.services.room_runner import _RoomContext, _assemble_verdict

    holdings = [_H("AAPL", 30), _H("JPM", 30), _H("XOM", 40)]
    quotes = {"AAPL": 100.0, "JPM": 100.0, "XOM": 100.0}
    ctx = _RoomContext(
        ticker="MSFT",
        mandate=base_mandate,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=default_halal_universe(),
        classification_universe=default_classification_universe(),
        locale_allowed_universe=None,
        sector_map=_map(),
        sector_holdings=holdings,
        sector_marks=quotes,
    )
    # 20% of $10k at $100 entry = 20 shares = $2000 buy — matches the pure-
    # function breach fixture (Tech 3000+2000 of 12000 = 41.7% > 40% cap).
    ctx.trader_entry = 100.0
    ctx.trader_size_pct = 20.0

    verdict = _assemble_verdict(ctx, profile={})
    assert verdict.action == VerdictAction.REJECT
    assert any(
        "sector-concentration limit" in v.lower() for v in verdict.violations
    )


class _SectorPmGateway:
    """Minimal fake LLMGateway whose PM always APPROVEs a large buy — used to
    prove the deterministic safety floor, not the LLM, is what blocks the
    sector-breaching trade on the live-PM path."""

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, *, system_prompt, messages, model_tier,
                           locale="en", max_tokens=1024, **_audit):
        if "speak as the portfolio manager" in system_prompt.lower():
            text = (
                '{"action": "APPROVE", "size_pct": 20.0, "entry": 100, '
                '"stop": 94, "target": 113, "horizon_days": 42, '
                '"narration": "PM: APPROVE; go big."}'
            )
        else:
            text = "Agent reply."
        mid = len(text) // 2
        yield text[:mid]
        yield text[mid:]


def test_room_runner_live_pm_enforce_safety_floor_rejects_sector_breach():
    """room_runner's live-PM enforce_safety_floor call site — sector context
    must reach the deterministic veto of a PM APPROVE, same as the scripted
    path above.

    Would go red if the live-PM `enforce_safety_floor(...)` call dropped
    holdings=ctx.sector_holdings/quotes=ctx.sector_marks/sector_map=ctx.sector_map.
    """
    from app.services.room_runner import RoomRunner
    from app.schemas.room import VerdictAction as _VA

    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        cu.write_snapshot(
            s, classified=set(_SECTORS), fossil=set(), sin=set(), defense=set(),
            fetched_at=now, sectors=dict(_SECTORS),
        )
    salloc.reset_sector_map_provider(None)
    try:
        sim = get_sim_engine()
        user_id = uuid4()
        mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})

        # Tech 30% / FS 30% / Energy 40% book, sized off the REAL deterministic
        # mock-walk price (this is the process-wide sim engine room_runner uses).
        for ticker, target_value in (("AAPL", 3000.0), ("JPM", 3000.0), ("XOM", 4000.0)):
            price = sim.current_price(ticker)
            qty = target_value / price
            r = sim.submit(
                user_id=user_id, ticker=ticker, side=Side.BUY,
                quantity=qty, mandate=mandate,
            )
            assert r.accepted, r.compliance.violations

        # A liberal PM APPROVEs a 20%-of-portfolio ($20k default portfolio_value)
        # Tech (MSFT) buy — massively over the sector cap regardless of exact
        # rounding, so the deterministic floor, not the LLM, must veto it.
        runner = RoomRunner(llm=_SectorPmGateway())  # type: ignore[arg-type]
        events = _collect(runner.run(
            user_id=user_id, ticker="MSFT", mandate=mandate,
            char_delay_min=0.0, char_delay_max=0.0,
        ))
        v = next(e.verdict for e in events if e.kind == "verdict")
        assert v.action == _VA.REJECT.value
        assert v.overridden_from_llm is True
        assert any(
            "sector-concentration limit" in vio.lower() for vio in v.violations
        )
    finally:
        salloc.reset_sector_map_provider(None)
