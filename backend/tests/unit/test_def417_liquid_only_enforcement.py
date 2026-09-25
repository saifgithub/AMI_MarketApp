"""DEF417 — the `liquid_only` mandate flag ("Liquid only. Avoid microcaps (< $500M
market cap) and illiquid names.") is enforced by the deterministic safety floor
against a SOURCED market-cap/volume reading, mirroring the DEF061 classification
architecture on the SAME snapshot (no new provider, no new socket).

Fixture-based, never touches the network or yfinance — `ClassificationUniverse` is
built directly from hand-supplied `market_caps`/`avg_volumes` maps, and the round-2
on-demand path (below) is driven through `liquidity_lookup.set_on_demand_fetcher`,
never a real `yf.Ticker(...).info` call.

The load-bearing assertions (round 1):
  * a real microcap (below $500M) is BLOCKED, `blocked_by=compliance`;
  * a real illiquid name (below $1M/day average dollar volume) is BLOCKED, even
    with a large market cap;
  * a liquid large-cap PASSES;
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

Round 2 (Saiful, 2026-09-25, "Look it up on demand" — auditor MAJOR-1/MAJOR-2):
  * a ticker OUTSIDE the classified snapshot (UNKNOWN at the snapshot level) now
    triggers an ON-DEMAND lookup, not an automatic permit — a real-microcap-shaped
    on-demand reading (the auditor's GNS probe) is BLOCKED exactly like a
    snapshot-measured one;
  * a ticker the on-demand lookup ALSO can't measure (neither field returned)
    stays UNKNOWN — no ruling either way, the DEF059 direction preserved one
    layer deeper;
  * a lookup that itself fails or times out is `LOOKUP_FAILED` — permitted, and
    disclosed via `advisories` (MAJOR-2: the channel the trade ticket already
    renders — no new mobile surface needed);
  * a cache hit never calls the fetcher twice;
  * per-call-site wiring: `room_runner`'s live-PM path AND `SimEngine.
    fill_resting_order` (the two sites the auditor found unguarded, MINOR-1) are
    each driven end-to-end and proven to fail if the check is removed there.
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
from app.services import liquidity_lookup as _liq
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
    # Real callers fetch into the cache first (SimEngine: `ensure_liquidity_cached`;
    # the Room: its pre-warm) and the floor only reads it, so the helper does too.
    proposed = ProposedTrade(ticker=ticker, side=side, quantity=1, limit_price=price or 10.0)
    _liq.ensure_liquidity_cached(universe, proposed, mandate)
    return check_mandate_compliance(
        proposed,
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


def test_unknown_is_permitted_with_disclosure_not_blocked(base_mandate: Mandate, monkeypatch):
    """The DEF059-inversion trap, load-bearing here because liquid_only DEFAULTS
    True — if unmeasured tickers blocked, every mandate in the app would refuse
    every name outside the ~503-ticker classified universe by default.

    Round 2: NEVR is outside the snapshot, so this now drives the ON-DEMAND
    path — the fixture fetcher answers with neither field (a genuinely
    un-priced name AMI's on-demand read also can't rule on), so this still
    proves the DEF059 direction one layer deeper than round 1 did, rather than
    silently degrading into `test_on_demand_lookup_failure_is_permitted_and_
    disclosed` below's different case (a fetch that ERRORS, not one that
    answers empty)."""
    monkeypatch.setattr(_liq, "_fetcher_override", lambda t: None)
    res = _check(_mandate(base_mandate, liquid_only=True), "NEVR", _universe(), price=10.0)
    assert res.passed
    assert not res.violations
    assert res.liquidity_verdict is not None
    assert res.liquidity_verdict.status is LiquidityStatus.UNKNOWN
    assert "liquidity filter couldn't check" in res.liquidity_verdict.message().lower()


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

from app.schemas.room import VerdictAction  # noqa: E402
from app.schemas.trade import OrderType  # noqa: E402
from app.services.room_runner import RoomRunner  # noqa: E402
from app.services.sim_engine import SimEngine, SimRestingOrder  # noqa: E402


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


# ── round 2 — on-demand lookup (Saiful, 2026-09-25: "Look it up on demand") ──
#
# The auditor's MAJOR-1: `resolve_liquidity` only ever measures the ~503-name
# snapshot, so 96% of tradable symbols resolved UNKNOWN=permitted and a real
# microcap outside the S&P (the auditor's own GNS probe) could never be
# refused. These tests drive `resolve_liquidity_with_lookup` — never the raw
# yfinance socket, always `liquidity_lookup.set_on_demand_fetcher` — and then
# the two call sites the auditor's MINOR-1 found unguarded end-to-end.

from app.schemas.liquidity import ON_DEMAND_SOURCE  # noqa: E402
from app.services.liquidity_lookup import (  # noqa: E402
    resolve_liquidity_with_lookup,
    set_on_demand_fetcher,
)


def test_on_demand_lookup_refuses_a_real_microcap_outside_the_snapshot():
    """The auditor's own reproduction, shaped as a fixture: GNS is a real,
    active microcap that sits outside the ~503-name S&P snapshot (`_universe()`
    doesn't know it at all — absent from both `_MARKET_CAPS`/`_AVG_VOLUMES`).
    The on-demand fetcher answers as yfinance would for a genuine sub-$500M
    name; the resolver must now EXCLUDE it, where round 1 shipped UNKNOWN
    (permitted, unconditionally) for exactly this case."""
    set_on_demand_fetcher(lambda t: {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0})
    v = resolve_liquidity_with_lookup(_universe(), "GNS", price=3.0)
    assert v.status is LiquidityStatus.EXCLUDED
    assert v.market_cap_usd_m == 85.0
    assert v.source == ON_DEMAND_SOURCE
    assert "microcap" in v.message().lower() or f"${MICROCAP_FLOOR_USD_M}" in v.message()


def test_on_demand_lookup_permits_a_real_large_cap_outside_the_snapshot():
    """The contrast case — a ticker outside the snapshot that clears both
    floors on the on-demand reading is PERMITTED, not blocked for the mere
    fact of being unclassified."""
    set_on_demand_fetcher(
        lambda t: {"market_cap_usd_m": 45_000.0, "avg_volume": 2_000_000.0}
    )
    v = resolve_liquidity_with_lookup(_universe(), "NEWCO", price=40.0)
    assert v.status is LiquidityStatus.PERMITTED
    assert v.source == ON_DEMAND_SOURCE


def test_on_demand_lookup_never_fires_for_a_ticker_the_snapshot_already_knows():
    """AAPL resolves PERMITTED off the snapshot alone — the on-demand fetcher
    must never even be consulted for a ticker the snapshot already measured."""
    calls: list[str] = []
    set_on_demand_fetcher(lambda t: calls.append(t) or {"market_cap_usd_m": 1.0})
    v = resolve_liquidity_with_lookup(_universe(), "AAPL", price=200.0)
    assert v.status is LiquidityStatus.PERMITTED
    assert v.market_cap_usd_m == 3_000_000.0  # the SNAPSHOT figure, not the fetcher's
    assert calls == []


def test_on_demand_lookup_unmeasurable_ticker_stays_unknown():
    """The fetcher runs and answers, but yfinance genuinely has neither field
    for this ticker (e.g. a delisted-adjacent or pre-IPO symbol) — UNKNOWN,
    not LOOKUP_FAILED, because the lookup itself did not fail; it ran and
    found nothing. Distinguishes an EMPTY answer from a FAILED one, the
    distinction `_LookupFailed` exists to preserve."""
    set_on_demand_fetcher(lambda t: None)
    v = resolve_liquidity_with_lookup(_universe(), "GHOST", price=10.0)
    assert v.status is LiquidityStatus.UNKNOWN
    assert v.source == ON_DEMAND_SOURCE


def test_on_demand_lookup_failure_is_permitted_and_disclosed():
    """Saiful's ruling, verbatim: 'Only if the lookup itself fails/times out
    does allow + disclose apply.' A fetcher that RAISES (simulating a real
    yfinance/network error) must permit the trade and disclose — never block,
    never silently pass with no verdict at all."""
    def _boom(t: str):
        raise RuntimeError("simulated yfinance error")

    set_on_demand_fetcher(_boom)
    v = resolve_liquidity_with_lookup(_universe(), "ERRTICK", price=10.0)
    assert v.status is LiquidityStatus.LOOKUP_FAILED
    assert not v.is_blocking
    assert v.is_disclosed_pause
    assert "couldn't get an answer" in v.message().lower()


def test_an_unmeasurable_name_is_permitted_but_never_silently(base_mandate: Mandate):
    """UNKNOWN (the lookup ran and Yahoo had neither figure) is permitted, but
    the user opted into a screen that could not rule — it must reach the
    advisories, not pass in silence (DEF417 round 2 MINOR-1)."""
    set_on_demand_fetcher(lambda t: None)
    res = _check(_mandate(base_mandate, liquid_only=True), "NEVR", _universe(), price=10.0)
    assert res.passed
    assert res.liquidity_verdict.status is LiquidityStatus.UNKNOWN
    assert any("liquidity filter couldn't check" in a for a in res.advisories)


def test_yahoo_symbol_maps_class_shares_and_nasdaq_preferreds():
    from app.services.liquidity_lookup import _yahoo_symbol

    assert _yahoo_symbol("brk.b") == "BRK-B"
    assert _yahoo_symbol("BAC$L") == "BAC-PL"
    assert _yahoo_symbol("AAPL") == "AAPL"


def test_the_floor_itself_never_fetches_and_a_miss_is_disclosed(base_mandate: Mandate):
    """The Room runs the floor ON the event loop, so the floor may only read the
    cache. With nothing fetched beforehand, a name outside the snapshot must come
    back LOOKUP_FAILED (permitted, disclosed) and the fetcher must never run."""
    calls: list[str] = []

    def _fetcher(t: str):
        calls.append(t)
        return {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0}

    set_on_demand_fetcher(_fetcher)
    res = check_mandate_compliance(
        ProposedTrade(ticker="GNS", side=Side.BUY, quantity=1, limit_price=3.0),
        portfolio_value=10_000, current_drawdown_pct=0,
        mandate=_mandate(base_mandate, liquid_only=True),
        classification_universe=_universe(),
        holdings=[], last_loss_closed_at=None, trade_open_timestamps=[],
        existing_open_risk_pct=0.0,
    )
    assert calls == []
    assert res.passed
    assert res.liquidity_verdict.status is LiquidityStatus.LOOKUP_FAILED
    assert any("couldn't get an answer" in a.lower() for a in res.advisories)


def test_on_demand_lookup_timeout_is_permitted_and_disclosed(monkeypatch):
    """The other half of Saiful's ruling — a fetch that never returns within
    the bounded timeout must degrade exactly like an outright error, never
    hang the caller. Timed, not just status-checked: a status-only version of
    this test passed while the caller silently waited out the whole hang."""
    import time as _time

    from app.services import liquidity_lookup as _liq_mod

    monkeypatch.setattr(_liq_mod, "_ON_DEMAND_TIMEOUT_S", 0.2)

    def _hangs(t: str):
        _time.sleep(3.0)
        return {"market_cap_usd_m": 1.0}

    set_on_demand_fetcher(_hangs)
    started = _time.monotonic()
    v = resolve_liquidity_with_lookup(_universe(), "SLOWTICK", price=10.0)
    elapsed = _time.monotonic() - started
    assert v.status is LiquidityStatus.LOOKUP_FAILED
    assert v.is_disclosed_pause
    assert elapsed < 1.0, f"caller held {elapsed:.2f}s by a 0.2s-bounded lookup"


def test_a_failed_lookup_is_retried_after_minutes_not_a_day(monkeypatch):
    """A failure means allowed-with-a-disclosure. Cached for 24h, one Yahoo blip
    would open a microcap to liquid_only buys all day; it must be re-asked once
    the short failure window passes, and the real answer then refuses it."""
    from app.services import liquidity_lookup as _liq_mod

    clock = [1_000_000.0]
    monkeypatch.setattr(_liq_mod.time, "time", lambda: clock[0])
    answers = [RuntimeError("yahoo blip"), {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0}]

    def _fetcher(t: str):
        a = answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return a

    set_on_demand_fetcher(_fetcher)
    first = resolve_liquidity_with_lookup(_universe(), "GNS", price=3.0)
    assert first.status is LiquidityStatus.LOOKUP_FAILED
    clock[0] += 60
    assert resolve_liquidity_with_lookup(_universe(), "GNS", price=3.0).status is LiquidityStatus.LOOKUP_FAILED
    clock[0] += 10 * 60
    assert resolve_liquidity_with_lookup(_universe(), "GNS", price=3.0).status is LiquidityStatus.EXCLUDED
    assert answers == []


def test_on_demand_lookup_end_to_end_reaches_advisories(base_mandate: Mandate):
    """MAJOR-2's exact fix: the on-demand failure disclosure must reach
    `ComplianceResult.advisories` — the SAME channel the trade ticket already
    renders (`trade_ticket_sheet.dart`'s `_pendingAdvisories`), not just the
    `LiquidityVerdict` object in isolation."""
    def _boom(t: str):
        raise RuntimeError("simulated yfinance error")

    set_on_demand_fetcher(_boom)
    res = _check(_mandate(base_mandate, liquid_only=True), "ERRTICK", _universe(), price=10.0)
    assert res.passed
    assert res.blocked_by is None
    assert res.liquidity_verdict.status is LiquidityStatus.LOOKUP_FAILED
    assert any("couldn't get an answer" in a.lower() for a in res.advisories)


def test_on_demand_cache_hit_never_calls_the_fetcher_twice():
    """24h cache, Saiful's ruling verbatim. A second resolve for the SAME
    ticker must not re-invoke the fetcher — proven by counting calls, not by
    inspecting internals."""
    calls: list[str] = []

    def _fetcher(t: str):
        calls.append(t)
        return {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0}

    set_on_demand_fetcher(_fetcher)
    v1 = resolve_liquidity_with_lookup(_universe(), "GNS", price=3.0)
    v2 = resolve_liquidity_with_lookup(_universe(), "GNS", price=3.0)
    assert v1.status is LiquidityStatus.EXCLUDED
    assert v2.status is LiquidityStatus.EXCLUDED
    assert calls == ["GNS"]


def test_on_demand_cache_hit_avoids_a_second_fetch_across_lowercase_and_case():
    """The cache key is the upper-cased ticker — a mixed-case caller (the
    Room/SimEngine always upper-case before this point, but the cache itself
    must not rely on that) still hits."""
    calls: list[str] = []

    def _fetcher(t: str):
        calls.append(t)
        return {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0}

    set_on_demand_fetcher(_fetcher)
    resolve_liquidity_with_lookup(_universe(), "gns", price=3.0)
    resolve_liquidity_with_lookup(_universe(), "GNS", price=3.0)
    assert calls == ["GNS"]


# ── round 2 — call-site wiring the auditor's MINOR-1 found unguarded ────────


def test_room_runner_live_pm_end_to_end_refuses_an_on_demand_microcap(base_mandate: Mandate):
    """Drives the FULL `RoomRunner.run()` live-PM path — not a direct
    `enforce_safety_floor` call (the auditor's exact MINOR-1 finding: the
    existing direct-call test never reached room_runner.py's own call site at
    all). GNS is outside `_universe()`'s snapshot; the on-demand fetcher
    answers with a real sub-$500M reading, so the PM's raw APPROVE must be
    vetoed by the deterministic floor, not waved through as UNKNOWN=permitted.
    """
    from tests.unit.test_cr101_be2_round2_room_wiring import _collect, _LiberalPmGateway

    set_on_demand_fetcher(lambda t: {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0})
    mandate = _mandate(base_mandate, liquid_only=True)
    runner = RoomRunner(llm=_LiberalPmGateway())  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(), ticker="GNS", mandate=mandate,
        portfolio_value=10_000.0,
        classification_universe=_universe(),
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.REJECT.value
    assert v.overridden_from_llm is True
    assert any(
        "microcap" in vio.lower() or f"${MICROCAP_FLOOR_USD_M}" in vio
        for vio in v.violations
    )


def test_room_runner_live_pm_wiring_fails_red_if_the_check_is_removed(
    base_mandate: Mandate, monkeypatch: pytest.MonkeyPatch,
):
    """Mutation-verified: if room_runner.py's live-PM call site ever drops
    `classification_universe=ctx.classification_universe` (replacing it with
    `None`), this test must fail. Proven here by patching `enforce_safety_
    floor` itself to simulate exactly that dropped argument, the same
    call-site-mutation shape the auditor used by hand."""
    from tests.unit.test_cr101_be2_round2_room_wiring import _collect, _LiberalPmGateway

    import app.services.room_runner as _rr

    set_on_demand_fetcher(lambda t: {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0})
    mandate = _mandate(base_mandate, liquid_only=True)

    real_enforce = _rr.enforce_safety_floor

    def _dropped_classification_universe(*args, **kwargs):
        kwargs["classification_universe"] = None
        return real_enforce(*args, **kwargs)

    monkeypatch.setattr(_rr, "enforce_safety_floor", _dropped_classification_universe)
    runner = RoomRunner(llm=_LiberalPmGateway())  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(), ticker="GNS", mandate=mandate,
        portfolio_value=10_000.0,
        classification_universe=_universe(),
        char_delay_min=0.0, char_delay_max=0.0,
    ))
    v = next(e.verdict for e in events if e.kind == "verdict")
    assert v.action == VerdictAction.APPROVE.value, (
        "dropping classification_universe= at the live-PM call site must "
        "un-enforce liquid_only — if this REJECTs, the mutation didn't "
        "actually remove the wiring this test is supposed to guard"
    )


def test_sim_engine_fill_resting_order_rejects_a_microcap_at_fill_time(base_mandate: Mandate):
    """The auditor's other unguarded site: `SimEngine.fill_resting_order`
    (the resting-order sweep's fill-time compliance re-check) must still
    enforce liquid_only — a resting order must never become a time-delayed
    bypass of the floor (the method's own docstring), and round 1 shipped
    with a call site nothing tested actually exercised."""
    from datetime import datetime, timezone
    from uuid import uuid4 as _uuid4

    sim = SimEngine(provider=_PinnedPriceProvider(5.0))
    mandate = _mandate(base_mandate, liquid_only=True)
    user_id = _uuid4()
    sim.ensure_portfolio(user_id)
    order = SimRestingOrder(
        id=_uuid4(), user_id=user_id, portfolio_id=sim.ensure_portfolio(user_id).id,
        ticker="NANO", side=Side.BUY, quantity=10, order_type=OrderType.LIMIT,
        state="working", tif="day",
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        placed_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
        limit_price=5.0,
    )

    result = sim.fill_resting_order(
        order=order, mark=5.0, mandate=mandate,
        classification_universe=_universe(),
    )
    assert not result.accepted
    assert result.compliance.blocked_by == "compliance"
    assert result.compliance.liquidity_verdict is not None
    assert result.compliance.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def test_fill_resting_order_fetches_an_unmeasured_name_before_its_check(base_mandate: Mandate):
    """A resting order can outlive the lookup cache, so the fill-time check must
    fetch for itself rather than rely on the cache its submit warmed. GNS is
    outside the snapshot and the cache is empty: the fill must look it up and
    refuse the microcap."""
    from datetime import datetime, timezone
    from uuid import uuid4 as _uuid4

    calls: list[str] = []

    def _fetcher(t: str):
        calls.append(t)
        return {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0}

    set_on_demand_fetcher(_fetcher)
    _liq.clear_on_demand_liquidity_cache()
    sim = SimEngine(provider=_PinnedPriceProvider(3.0))
    user_id = _uuid4()
    order = SimRestingOrder(
        id=_uuid4(), user_id=user_id, portfolio_id=sim.ensure_portfolio(user_id).id,
        ticker="GNS", side=Side.BUY, quantity=10, order_type=OrderType.LIMIT,
        state="working", tif="day",
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        placed_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
        limit_price=3.0,
    )
    result = sim.fill_resting_order(
        order=order, mark=3.0, mandate=_mandate(base_mandate, liquid_only=True),
        classification_universe=_universe(),
    )
    assert calls == ["GNS"]
    assert not result.accepted
    assert result.compliance.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def _gns_microcap_fetcher() -> list[str]:
    calls: list[str] = []

    def _fetcher(t: str):
        calls.append(t)
        return {"market_cap_usd_m": 85.0, "avg_volume": 250_000.0}

    set_on_demand_fetcher(_fetcher)
    _liq.clear_on_demand_liquidity_cache()
    return calls


def test_submit_fetches_an_unmeasured_name_before_its_check(base_mandate: Mandate):
    """DEF417 r3 MINOR-1 (u66): the submit/preview microcap tests above use NANO,
    which is inside the snapshot, so dropping `ensure_liquidity_cached` from
    submit left every test green and reopened every microcap outside the
    snapshot. GNS is outside it and the cache is empty: submit must look it up
    and refuse."""
    calls = _gns_microcap_fetcher()
    sim = SimEngine(provider=_PinnedPriceProvider(3.0))
    result = sim.submit(
        user_id=uuid4(), ticker="GNS", side=Side.BUY, quantity=10,
        mandate=_mandate(base_mandate, liquid_only=True),
        order_type=OrderType.LIMIT, limit_price=3.0,
        classification_universe=_universe(),
    )
    assert calls == ["GNS"]
    assert not result.accepted
    assert result.compliance.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def test_preview_fetches_an_unmeasured_name_before_its_check(base_mandate: Mandate):
    """The preview twin of the test above: the dry-run gate must fetch too."""
    calls = _gns_microcap_fetcher()
    sim = SimEngine(provider=_PinnedPriceProvider(3.0))
    preview = sim.preview(
        user_id=uuid4(), ticker="GNS", side=Side.BUY, quantity=10,
        mandate=_mandate(base_mandate, liquid_only=True),
        order_type=OrderType.LIMIT, limit_price=3.0,
        classification_universe=_universe(),
    )
    assert calls == ["GNS"]
    assert not preview.accepted
    assert preview.compliance.liquidity_verdict.status is LiquidityStatus.EXCLUDED


def test_sim_engine_fill_resting_order_wiring_fails_red_if_the_check_is_removed(
    base_mandate: Mandate, monkeypatch: pytest.MonkeyPatch,
):
    """Mutation-verified companion to the test above: if `fill_resting_order`
    ever drops `classification_universe=` from its `check_mandate_compliance`
    call (replacing it with `None`, simulating the argument being lost), the
    fill must go from REJECTED to ACCEPTED — proving this test would actually
    go red under that regression, not just under a contrived direct call."""
    from datetime import datetime, timezone
    from uuid import uuid4 as _uuid4

    import app.services.sim_engine as _se

    real_check = _se.check_mandate_compliance

    def _dropped_classification_universe(*args, **kwargs):
        kwargs["classification_universe"] = None
        return real_check(*args, **kwargs)

    monkeypatch.setattr(_se, "check_mandate_compliance", _dropped_classification_universe)

    sim = SimEngine(provider=_PinnedPriceProvider(5.0))
    mandate = _mandate(base_mandate, liquid_only=True)
    user_id = _uuid4()
    sim.ensure_portfolio(user_id)
    order = SimRestingOrder(
        id=_uuid4(), user_id=user_id, portfolio_id=sim.ensure_portfolio(user_id).id,
        ticker="NANO", side=Side.BUY, quantity=10, order_type=OrderType.LIMIT,
        state="working", tif="day",
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        placed_at=datetime(2026, 9, 25, tzinfo=timezone.utc),
        limit_price=5.0,
    )

    result = sim.fill_resting_order(
        order=order, mark=5.0, mandate=mandate,
        classification_universe=_universe(),
    )
    assert result.accepted, (
        "dropping classification_universe= at fill_resting_order's compliance "
        "call must un-enforce liquid_only — if this is refused, the mutation "
        "didn't actually remove the wiring this test is supposed to guard"
    )
