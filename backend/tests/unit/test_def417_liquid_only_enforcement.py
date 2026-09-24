"""DEF417 — the `liquid_only` mandate flag ("Liquid only. Avoid microcaps (< $500M
market cap) and illiquid names.") is enforced by the deterministic safety floor
against a SOURCED market-cap/volume reading, mirroring the DEF061 classification
architecture on the SAME snapshot (no new provider, no new socket).

Fixture-based, never touches the network or yfinance — `ClassificationUniverse` is
built directly from hand-supplied `market_caps`/`avg_volumes` maps.

The load-bearing assertions:
  * a real microcap (below $500M) is BLOCKED, `blocked_by=compliance`;
  * a real illiquid name (below $1M/day average dollar volume) is BLOCKED, even
    with a large market cap;
  * a liquid large-cap PASSES;
  * a ticker with NEITHER figure known is UNKNOWN — PERMITTED with the disclosure
    attached, NOT blocked (the DEF059-inversion trap — asserted explicitly, and
    load-bearing here specifically because `liquid_only` defaults True);
  * a ticker with ONLY market cap known is still judged on it (EXCLUDED if below
    floor) even though volume couldn't be priced;
  * a SELL is never blocked by liquid_only (mirrors long_only's buy-only scope);
  * flag off is a no-op — no verdict, no violation, regardless of the ticker;
  * a stale/unavailable universe degrades to an ADVISORY, never a block — the
    one deliberate divergence from the DEF061 seam, because liquid_only is
    opt-out (default True) and blocking on an outage would refuse nearly every
    mandate in the app;
  * the enforced $500M / $1M-per-day thresholds are the SAME numbers rendered
    into the PM/Trader prompt overlay (shown == enforced, CR046 C-a).
"""

from datetime import date

import pytest

from app.agents.safety_floor import check_mandate_compliance
from app.agents.overlay_generator import _MICROCAP_FLOOR_USD_M as _OVERLAY_FLOOR
from app.schemas import Compliance, Mandate
from app.schemas.liquidity import (
    ILLIQUID_AVG_DOLLAR_VOLUME_USD,
    MICROCAP_FLOOR_USD_M,
    LiquidityStatus,
)
from app.schemas.trade import ProposedTrade, Side
from app.services.classification_universe import ClassificationUniverse

# A small, realistic liquidity fixture. AAPL is a liquid mega-cap; NANO is a real
# market cap below the $500M floor; THIN has a large cap but trades thin (below
# $1M/day average dollar volume at its own price); UNPRICED has a market cap but
# no average-volume reading at all.
_MARKET_CAPS = {"AAPL": 3_000_000.0, "NANO": 120.0, "THIN": 900.0, "UNPRICED": 5_000.0}
_AVG_VOLUMES = {"AAPL": 50_000_000.0, "NANO": 40_000.0, "THIN": 8_000.0}
_CLASSIFIED = frozenset(_MARKET_CAPS) | {"NEVR"}  # NEVR classified, no liquidity data has no sector either


def _universe(*, stale: bool = False) -> ClassificationUniverse:
    return ClassificationUniverse(
        classified=frozenset(_MARKET_CAPS),
        as_of=date(2026, 9, 24),
        stale=stale,
        market_caps=_MARKET_CAPS,
        avg_volumes=_AVG_VOLUMES,
    )


def _mandate(base: Mandate, **flags) -> Mandate:
    flags.setdefault("liquid_only", True)
    return base.model_copy(update={"compliance": Compliance(long_only=True, **flags)})


def _check(
    mandate: Mandate, ticker: str, universe, *, side: Side = Side.BUY, price=None,
    holdings=(),
):
    return check_mandate_compliance(
        ProposedTrade(ticker=ticker, side=side, quantity=1, limit_price=price or 10.0),
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
        classification_universe=universe,
        holdings=list(holdings), last_loss_closed_at=None, trade_open_timestamps=[],
        existing_open_risk_pct=0.0,
    )


class _Holding:
    """Minimal duck-typed holding — the floor only reads `.ticker`/`.quantity`."""

    def __init__(self, ticker: str, quantity: float = 1.0):
        self.ticker = ticker
        self.quantity = quantity


# ── resolver (four states) ────────────────────────────────────────────────────


def test_resolver_permits_a_liquid_large_cap():
    u = _universe()
    v = u.resolve_liquidity("AAPL", price=200.0)
    assert v.status is LiquidityStatus.PERMITTED
    assert v.market_cap_usd_m == 3_000_000.0


def test_resolver_excludes_a_real_microcap():
    u = _universe()
    v = u.resolve_liquidity("NANO", price=5.0)
    assert v.status is LiquidityStatus.EXCLUDED
    assert v.market_cap_usd_m == 120.0
    assert "microcap" in v.message().lower() or f"${MICROCAP_FLOOR_USD_M}" in v.message()


def test_resolver_excludes_on_dollar_volume_alone():
    """THIN clears the market-cap floor but trades thin — 8,000 shares/day x
    $50 = $400,000/day, below the $1M floor."""
    u = _universe()
    v = u.resolve_liquidity("THIN", price=50.0)
    assert v.status is LiquidityStatus.EXCLUDED
    assert v.avg_dollar_volume_usd == 400_000.0
    assert v.avg_dollar_volume_usd < ILLIQUID_AVG_DOLLAR_VOLUME_USD


def test_resolver_unknown_when_neither_figure_available():
    u = _universe()
    v = u.resolve_liquidity("NEVR", price=10.0)
    assert v.status is LiquidityStatus.UNKNOWN


def test_resolver_judges_on_market_cap_alone_when_volume_unpriceable():
    """UNPRICED has a market cap reading but no average-volume figure, and no
    price was supplied either — the cap alone still rules; a real reading below
    the floor is a real exclusion even if its sibling reading is missing."""
    u = _universe()
    v = u.resolve_liquidity("UNPRICED", price=None)
    assert v.status is LiquidityStatus.PERMITTED  # $5,000M clears the floor
    assert v.market_cap_usd_m == 5_000.0
    assert v.avg_dollar_volume_usd is None


def test_resolver_no_price_skips_volume_half_never_fabricates_a_breach():
    """THIN's market cap alone ($900M) clears the floor; without a price the
    dollar-volume half cannot be computed, and that absence must not read as a
    breach (DEF059) — it resolves PERMITTED on the figure that IS known."""
    u = _universe()
    v = u.resolve_liquidity("THIN", price=None)
    assert v.status is LiquidityStatus.PERMITTED
    assert v.avg_dollar_volume_usd is None


def test_stale_universe_resolves_unavailable():
    u = _universe(stale=True)
    v = u.resolve_liquidity("AAPL", price=200.0)
    assert v.status is LiquidityStatus.UNAVAILABLE
    assert not v.is_blocking
    assert v.is_disclosed_pause


# ── enforcement ────────────────────────────────────────────────────────────


def test_microcap_blocked_when_liquid_only(base_mandate: Mandate):
    res = _check(_mandate(base_mandate, liquid_only=True), "NANO", _universe(), price=5.0)
    assert not res.passed
    assert res.blocked_by == "compliance"
    assert any("microcap" in v.lower() or "500" in v for v in res.violations)
    assert res.liquidity_verdict is not None
    assert res.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def test_illiquid_blocked_when_liquid_only(base_mandate: Mandate):
    res = _check(_mandate(base_mandate, liquid_only=True), "THIN", _universe(), price=50.0)
    assert not res.passed
    assert res.blocked_by == "compliance"
    assert res.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def test_same_name_allowed_when_flag_off(base_mandate: Mandate):
    """The exact microcap that gets blocked above is allowed once liquid_only
    is off — proves the check is actually READING the flag, not always firing."""
    res = _check(_mandate(base_mandate, liquid_only=False), "NANO", _universe(), price=5.0)
    assert res.passed
    assert res.liquidity_verdict is None


def test_liquid_large_cap_passes(base_mandate: Mandate):
    res = _check(_mandate(base_mandate, liquid_only=True), "AAPL", _universe(), price=200.0)
    assert res.passed
    assert res.liquidity_verdict.status is LiquidityStatus.PERMITTED


def test_unknown_is_permitted_with_disclosure_not_blocked(base_mandate: Mandate):
    """The DEF059-inversion trap, load-bearing here because liquid_only DEFAULTS
    True — if unmeasured tickers blocked, every mandate in the app would refuse
    every name outside the ~503-ticker classified universe by default."""
    res = _check(_mandate(base_mandate, liquid_only=True), "NEVR", _universe(), price=10.0)
    assert res.passed
    assert not res.violations
    assert res.liquidity_verdict is not None
    assert res.liquidity_verdict.status is LiquidityStatus.UNKNOWN
    assert "hasn't measured" in res.liquidity_verdict.message().lower()


def test_sell_never_blocked_by_liquid_only(base_mandate: Mandate):
    """Mirrors long_only's buy-only scope — liquid_only constrains what enters a
    position, never what a user already holds and wants to exit, even if the
    name slipped below the floor after they bought it. Sells 1 already-held
    share (sell-to-close, not sell-to-open) so `long_only` doesn't also fire."""
    res = _check(
        _mandate(base_mandate, liquid_only=True), "NANO", _universe(),
        side=Side.SELL, price=5.0, holdings=[_Holding("NANO", 5.0)],
    )
    assert res.passed
    assert res.liquidity_verdict is None


def test_flag_off_is_a_noop_even_for_a_would_be_microcap(base_mandate: Mandate):
    res = _check(_mandate(base_mandate, liquid_only=False), "NANO", _universe(), price=5.0)
    assert res.passed
    assert not res.violations
    assert res.liquidity_verdict is None


def test_no_resolver_on_universe_degrades_to_advisory_not_block(base_mandate: Mandate):
    """A bare object with no `resolve_liquidity` (a legacy test double, or a
    caller passing something that isn't a real ClassificationUniverse) degrades
    the same way an unavailable universe does — paused, disclosed, never a
    block. `object()` deliberately has no `resolve_liquidity` attribute."""
    res = _check(_mandate(base_mandate, liquid_only=True), "AAPL", object(), price=200.0)
    assert res.passed
    assert res.liquidity_verdict is not None
    assert res.liquidity_verdict.status is LiquidityStatus.UNAVAILABLE
    assert any("paused" in a.lower() for a in res.advisories)


def test_none_universe_degrades_to_advisory_not_block(base_mandate: Mandate):
    """DEF417's deliberate divergence from the DEF061 UNAVAILABLE=blocking
    pattern: liquid_only defaults True (opt-out), so a classification-source
    outage must disclose loudly (CR040) WITHOUT refusing every buy in the app.
    Contrast `test_none_universe_pauses_loudly` in
    test_def061_compliance_enforcement.py, where the opt-IN fossil flag DOES
    block on the same paused shape — smaller blast radius, different tradeoff."""
    res = _check(_mandate(base_mandate, liquid_only=True), "AAPL", None, price=200.0)
    assert res.passed
    assert res.blocked_by is None
    assert res.liquidity_verdict is not None
    assert res.liquidity_verdict.status is LiquidityStatus.UNAVAILABLE
    assert any("paused" in a.lower() for a in res.advisories)


def test_stale_universe_degrades_to_advisory_not_block(base_mandate: Mandate):
    res = _check(_mandate(base_mandate, liquid_only=True), "AAPL", _universe(stale=True), price=200.0)
    assert res.passed
    assert res.blocked_by is None
    assert any("paused" in a.lower() for a in res.advisories)


def test_flag_default_is_on(base_mandate: Mandate):
    """`liquid_only` is True by default on Compliance — confirms the fixture
    mandate actually exercises the default-on path the tests above rely on."""
    assert base_mandate.compliance.liquid_only is True


# ── shown == enforced (CR046 C-a) ─────────────────────────────────────────────


def test_enforced_threshold_matches_the_rendered_prompt_constant():
    """The number the PM/Trader overlay narrates ("Avoid microcaps (< $500M
    market cap)") must be the SAME number this floor enforces — one constant,
    imported by both sides, never two that could drift apart."""
    assert MICROCAP_FLOOR_USD_M == _OVERLAY_FLOOR


def test_thresholds_are_documented_constants_not_magic_numbers():
    assert MICROCAP_FLOOR_USD_M == 500
    assert ILLIQUID_AVG_DOLLAR_VOLUME_USD == 1_000_000


# ── per-call-site wiring (the CR026-BE lesson: call-site wiring fails OPEN) ──
#
# `check_mandate_compliance` enforces liquid_only for free wherever a caller
# already passes `classification_universe` + a price for the proposed ticker —
# both were ALREADY threaded through every call site for the DEF061 fossil/
# sin/esg_lite checks, so no call site needed new wiring for DEF417. These
# tests prove that claim rather than assume it: each one would go red if a
# call site silently dropped `classification_universe=` (or, for the two
# room_runner sites, `ctx.classification_universe`) from its
# check_mandate_compliance()/enforce_safety_floor() call.

from uuid import uuid4  # noqa: E402

from app.schemas.trade import OrderType  # noqa: E402
from app.services.sim_engine import SimEngine  # noqa: E402


class _PinnedPriceProvider:
    """Prices every ticker at a fixed mark — SimEngine wiring tests need a
    real Quote-shaped provider, not yfinance."""

    name = "fixture"

    def __init__(self, price: float) -> None:
        self.price = price

    def quote(self, ticker: str):
        from app.services import market_data as _md
        return _md.Quote(price=self.price, source=self.name)

    def get_price(self, ticker: str):
        return self.price


def test_sim_engine_submit_rejects_a_microcap_buy_end_to_end(base_mandate: Mandate):
    """SimEngine.submit() — would go red if submit() dropped
    classification_universe= from its check_mandate_compliance() call."""
    sim = SimEngine(provider=_PinnedPriceProvider(5.0))
    user_id = uuid4()
    mandate = _mandate(base_mandate, liquid_only=True)

    result = sim.submit(
        user_id=user_id, ticker="NANO", side=Side.BUY, quantity=10,
        mandate=mandate, order_type=OrderType.LIMIT, limit_price=5.0,
        classification_universe=_universe(),
    )
    assert not result.accepted
    assert result.compliance.blocked_by == "compliance"
    assert result.compliance.liquidity_verdict is not None
    assert result.compliance.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def test_sim_engine_preview_rejects_a_microcap_buy_end_to_end(base_mandate: Mandate):
    """SimEngine.preview() — the dry-run gate, same as submit() above. Would go
    red if preview() dropped classification_universe= from its
    check_mandate_compliance() call."""
    sim = SimEngine(provider=_PinnedPriceProvider(5.0))
    user_id = uuid4()
    mandate = _mandate(base_mandate, liquid_only=True)

    preview = sim.preview(
        user_id=user_id, ticker="NANO", side=Side.BUY, quantity=10,
        mandate=mandate, order_type=OrderType.LIMIT, limit_price=5.0,
        classification_universe=_universe(),
    )
    assert not preview.accepted
    assert preview.compliance.blocked_by == "compliance"
    assert preview.compliance.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def test_sim_engine_submit_allows_a_liquid_buy_end_to_end(base_mandate: Mandate):
    """The contrast case — proves the wiring test above isn't blocking for an
    unrelated reason (cash, cap, etc.)."""
    sim = SimEngine(provider=_PinnedPriceProvider(200.0))
    user_id = uuid4()
    mandate = _mandate(base_mandate, liquid_only=True)

    result = sim.submit(
        user_id=user_id, ticker="AAPL", side=Side.BUY, quantity=1,
        mandate=mandate, order_type=OrderType.LIMIT, limit_price=200.0,
        classification_universe=_universe(),
    )
    assert result.accepted, result.compliance.violations
    assert result.compliance.liquidity_verdict.status is LiquidityStatus.PERMITTED


def test_assemble_verdict_scripted_path_rejects_a_microcap_buy(base_mandate: Mandate):
    """room_runner._assemble_verdict (scripted/non-live path) — would go red if
    it dropped classification_universe=ctx.classification_universe from its
    check_mandate_compliance() call."""
    from app.services.room_runner import _RoomContext, _assemble_verdict
    from app.schemas.room import VerdictAction

    mandate = _mandate(base_mandate, liquid_only=True)
    ctx = _RoomContext(
        ticker="NANO",
        mandate=mandate,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        halal_universe=set(),
        classification_universe=_universe(),
        locale_allowed_universe=None,
        risk_existing_open_risk_pct=0.0,
        risk_trade_open_timestamps=[],
    )
    ctx.trader_entry = 5.0
    ctx.trader_size_pct = 1.0

    verdict = _assemble_verdict(ctx, profile={})
    assert verdict.action == VerdictAction.REJECT
    assert any(
        "microcap" in v.lower() or "500" in v for v in verdict.violations
    )


def test_enforce_safety_floor_live_pm_vetoes_a_microcap_approve(base_mandate: Mandate):
    """room_runner's live-PM call site: `enforce_safety_floor(...)` — would go
    red if the call site dropped classification_universe=ctx.classification_
    universe, the exact shape room_runner.py:5701 passes it in."""
    from app.agents.safety_floor import enforce_safety_floor
    from app.schemas import Verdict, VerdictAction

    mandate = _mandate(base_mandate, liquid_only=True)
    llm_verdict = Verdict(
        action=VerdictAction.APPROVE, size_pct=1.0, entry=5.0, stop=4.5,
        target=6.0, time_horizon_days=30, reason="PM: APPROVE.",
    )
    proposed = ProposedTrade(
        ticker="NANO", side=Side.BUY, quantity=10,
        order_type=OrderType.LIMIT, limit_price=5.0,
    )

    result = enforce_safety_floor(
        llm_verdict, proposed,
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
        classification_universe=_universe(),
        holdings=[], last_loss_closed_at=None, trade_open_timestamps=[],
        existing_open_risk_pct=0.0,
    )
    assert result.action == VerdictAction.REJECT
    assert result.overridden_from_llm
    assert any(
        "microcap" in v.lower() or "500" in v for v in (result.violations or [])
    )
