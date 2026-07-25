"""DEF061 — the `no_fossil_fuels` / `no_tobacco_alcohol_gambling` / `esg_lite` mandate
flags are enforced by the deterministic safety floor against a SOURCED sector/industry
exclusion set, mirroring the CR069/CR075 halal architecture.

Fixture-based, never touches the network or yfinance: the classifier is exercised on
hand-built `info` dicts, the resolver + enforcement on hand-built
`ClassificationUniverse` fixtures, and the refresh via an injected classifier. Live
classification pairs with the next promote (like CR075 — the Mac worktree has no DB
parent set to classify).

The load-bearing assertions:
  * a real oil major (XOM) with `no_fossil_fuels` on is BLOCKED, `blocked_by=compliance`;
  * tobacco (MO), brewer/distiller (BUD/STZ), casino (WYNN/LVS) are BLOCKED with the
    sin flag on;
  * a weapons/defense name (LMT/RTX) is BLOCKED with `esg_lite` on — the CURATED proxy
    (fossil ∪ sin ∪ defense), and its verdict names itself as best-effort curation,
    NOT a rated ESG score (CR040 honesty);
  * a clearly-compliant name (AAPL) with all flags on PASSES;
  * an UNKNOWN/unclassified ticker with a flag on is PERMITTED with the disclosure
    attached, NOT blocked (the DEF059-inversion trap — asserted explicitly);
  * a None/unavailable universe PAUSES loudly (mirrors the halal-paused branch);
  * the refresh finding a fresh row is a no-op (mirrors CR075's skipped_fresh).
"""

from datetime import date, datetime, timedelta, timezone

import pytest

from app.agents.safety_floor import check_mandate_compliance
from app.db import get_session
from app.schemas import Compliance, Mandate
from app.schemas.classification import ClassificationKind, ClassificationStatus
from app.schemas.trade import ProposedTrade, Side
from app.services import classification_universe as cu
from app.services.classification_universe import (
    ClassificationSourceError,
    ClassificationUniverse,
    ClassificationUniverseProvider,
    classify_info,
    latest_snapshot,
    run_classification_refresh_tick,
    write_snapshot,
)

# ── A small, realistic sourced universe fixture ──────────────────────────────
# XOM/CVX are S&P Energy oil majors; MO tobacco; BUD brewer; STZ distiller; WYNN/LVS
# casinos; LMT/RTX weapons/defense primes. AAPL/MSFT/JPM are clean. `classified` is
# every name we ran through the classifier — a name absent from it resolves UNKNOWN
# (permitted + disclosed), never a false PERMITTED.
_FOSSIL = frozenset({"XOM", "CVX"})
_SIN = frozenset({"MO", "BUD", "STZ", "WYNN", "LVS"})
_DEFENSE = frozenset({"LMT", "RTX"})
_CLASSIFIED = _FOSSIL | _SIN | _DEFENSE | frozenset({"AAPL", "MSFT", "JPM"})


def _universe(*, stale: bool = False) -> ClassificationUniverse:
    return ClassificationUniverse(
        fossil=_FOSSIL,
        sin=_SIN,
        defense=_DEFENSE,
        classified=_CLASSIFIED,
        as_of=date(2026, 7, 25),
        stale=stale,
    )


def _mandate(base: Mandate, **flags) -> Mandate:
    return base.model_copy(
        update={"compliance": Compliance(long_only=True, liquid_only=True, **flags)}
    )


def _check(mandate: Mandate, ticker: str, universe) -> object:
    return check_mandate_compliance(
        ProposedTrade(ticker=ticker, side=Side.BUY, quantity=1, limit_price=10.0),
        portfolio_value=10_000,
        current_drawdown_pct=0,
        mandate=mandate,
        classification_universe=universe,
    )


# ── classifier (the reviewable core) ─────────────────────────────────────────


@pytest.mark.parametrize(
    "sector,industry,expected",
    [
        ("Energy", "Oil & Gas Integrated", (True, False, False)),
        ("Energy", "Oil & Gas E&P", (True, False, False)),
        ("Energy", "Oil & Gas Midstream", (True, False, False)),
        ("Energy", "Oil & Gas Refining & Marketing", (True, False, False)),
        ("Energy", "Thermal Coal", (True, False, False)),
        ("Consumer Defensive", "Tobacco", (False, True, False)),
        ("Consumer Defensive", "Beverages—Brewers", (False, True, False)),  # em-dash
        ("Consumer Defensive", "Beverages—Wineries & Distilleries", (False, True, False)),
        ("Consumer Cyclical", "Resorts & Casinos", (False, True, False)),
        ("Consumer Cyclical", "Gambling", (False, True, False)),
        ("Industrials", "Aerospace & Defense", (False, False, True)),  # esg-only bucket
        ("Technology", "Consumer Electronics", (False, False, False)),
        ("Financial Services", "Banks—Diversified", (False, False, False)),
        # Sector guard: an oil/gas industry string OUTSIDE the Energy sector must
        # NOT be swept into the fossil set.
        ("Industrials", "Oil & Gas Integrated", (False, False, False)),
    ],
)
def test_classify_info(sector, industry, expected):
    assert classify_info({"sector": sector, "industry": industry}) == expected


def test_classify_info_dash_variants_normalise():
    """yfinance drifts between em-dash/en-dash/hyphen AND spaces the hyphen
    ('Beverages - Brewers') — every form must classify the same (DEF107: the
    spaced-hyphen form is the ACTUAL live yfinance string, and it was silently
    unscreened before the normaliser stripped spaces around hyphens)."""
    for ind in (
        "Beverages—Brewers",  # em-dash (the fixture's old assumption)
        "Beverages–Brewers",  # en-dash
        "Beverages-Brewers",  # compact hyphen
        "Beverages - Brewers",  # spaced hyphen — what yfinance actually returns
        "Beverages - Wineries & Distilleries",  # spaced hyphen, real (BF-B)
    ):
        info = {"sector": "Consumer Defensive", "industry": ind}
        assert classify_info(info) == (False, True, False), ind


# ── resolver (four states, three kinds) ──────────────────────────────────────


def test_resolver_four_states():
    u = _universe()
    assert u.resolve("XOM", ClassificationKind.FOSSIL_FUELS).status is ClassificationStatus.EXCLUDED
    assert u.resolve("MO", ClassificationKind.SIN).status is ClassificationStatus.EXCLUDED
    # AAPL is classified and clean under every kind.
    assert u.resolve("AAPL", ClassificationKind.FOSSIL_FUELS).status is ClassificationStatus.PERMITTED
    assert u.resolve("AAPL", ClassificationKind.SIN).status is ClassificationStatus.PERMITTED
    assert u.resolve("AAPL", ClassificationKind.ESG_LITE).status is ClassificationStatus.PERMITTED
    # XOM is only a fossil exclusion — under SIN it's a permitted classified name.
    assert u.resolve("XOM", ClassificationKind.SIN).status is ClassificationStatus.PERMITTED
    # Unclassified name → UNKNOWN under every kind.
    assert u.resolve("NEVR", ClassificationKind.FOSSIL_FUELS).status is ClassificationStatus.UNKNOWN


def test_esg_is_the_union_of_the_three_buckets():
    u = _universe()
    # fossil, sin AND defense names all fall under esg_lite.
    for t in ("XOM", "MO", "LMT"):
        assert u.resolve(t, ClassificationKind.ESG_LITE).status is ClassificationStatus.EXCLUDED
    assert u.esg == (_FOSSIL | _SIN | _DEFENSE)


def test_stale_universe_resolves_unavailable():
    u = _universe(stale=True)
    v = u.resolve("XOM", ClassificationKind.FOSSIL_FUELS)
    assert v.status is ClassificationStatus.UNAVAILABLE
    assert "paused" in v.message().lower()


# ── enforcement: the three checks bite ───────────────────────────────────────


def test_no_fossil_fuels_blocks_oil_major(base_mandate: Mandate):
    res = _check(_mandate(base_mandate, no_fossil_fuels=True), "XOM", _universe())
    assert not res.passed
    assert res.blocked_by == "compliance"
    assert any("fossil" in v.lower() for v in res.violations)
    assert res.classification_verdicts[0].status is ClassificationStatus.EXCLUDED
    assert res.classification_verdicts[0].kind is ClassificationKind.FOSSIL_FUELS


@pytest.mark.parametrize("ticker", ["MO", "BUD", "STZ", "WYNN", "LVS"])
def test_no_sin_blocks_tobacco_alcohol_gambling(base_mandate: Mandate, ticker):
    res = _check(_mandate(base_mandate, no_tobacco_alcohol_gambling=True), ticker, _universe())
    assert not res.passed
    assert res.blocked_by == "compliance"
    assert res.classification_verdicts[0].status is ClassificationStatus.EXCLUDED
    assert res.classification_verdicts[0].kind is ClassificationKind.SIN


@pytest.mark.parametrize("ticker", ["LMT", "RTX", "XOM", "MO"])
def test_esg_lite_blocks_defense_and_the_other_buckets(base_mandate: Mandate, ticker):
    """esg_lite = fossil ∪ sin ∪ defense — a weapons name AND any fossil/sin name
    are all EXCLUDED, and the verdict names itself as a curated proxy (CR040)."""
    res = _check(_mandate(base_mandate, esg_lite=True), ticker, _universe())
    assert not res.passed
    assert res.blocked_by == "compliance"
    v = res.classification_verdicts[0]
    assert v.status is ClassificationStatus.EXCLUDED
    assert v.kind is ClassificationKind.ESG_LITE
    msg = v.message().lower()
    assert "not a rated esg score" in msg  # honesty: curated proxy, not a rating


def test_compliant_name_passes_all_flags(base_mandate: Mandate):
    m = _mandate(
        base_mandate,
        no_fossil_fuels=True,
        no_tobacco_alcohol_gambling=True,
        esg_lite=True,
    )
    res = _check(m, "AAPL", _universe())
    assert res.passed
    assert not res.violations
    # All three flags active ⇒ three verdicts travel, all PERMITTED.
    assert len(res.classification_verdicts) == 3
    assert all(v.status is ClassificationStatus.PERMITTED for v in res.classification_verdicts)


def test_unknown_is_permitted_with_disclosure_not_blocked(base_mandate: Mandate):
    """The DEF059-inversion trap: an unclassified ticker must be PERMITTED with the
    disclosure attached, never blocked — else the filter rejects every name AMI
    hasn't classified."""
    m = _mandate(
        base_mandate,
        no_fossil_fuels=True,
        no_tobacco_alcohol_gambling=True,
        esg_lite=True,
    )
    res = _check(m, "NEVR", _universe())  # not in the classified set → UNKNOWN
    assert res.passed  # PERMITTED, not blocked
    assert not res.violations
    # But the disclosure must be able to travel on the successful trade.
    assert len(res.classification_verdicts) == 3
    assert all(v.status is ClassificationStatus.UNKNOWN for v in res.classification_verdicts)
    assert any("hasn't classified" in v.message().lower() for v in res.classification_verdicts)


def test_none_universe_pauses_loudly(base_mandate: Mandate):
    """A None/unavailable universe PAUSES (blocks with a pause message), never a
    silent permit — mirrors the halal-paused branch."""
    m = _mandate(base_mandate, no_fossil_fuels=True)
    res = _check(m, "AAPL", None)
    assert not res.passed
    assert res.blocked_by == "compliance"
    assert "paused" in " ".join(res.violations).lower()
    assert res.classification_verdicts[0].status is ClassificationStatus.UNAVAILABLE


def test_flags_off_is_a_noop(base_mandate: Mandate):
    """With no flag set, the classification universe is never consulted — no
    verdicts, no violations (even for a name that WOULD be excluded)."""
    res = _check(base_mandate, "XOM", _universe())
    assert res.passed
    assert res.classification_verdicts == []


# ── provider (cache + loud degrade) ──────────────────────────────────────────


def _fetcher_ok():
    return (_CLASSIFIED, _FOSSIL, _SIN, _DEFENSE, date(2026, 7, 25))


def test_provider_disabled_pauses_without_fetch():
    p = ClassificationUniverseProvider(
        hold_window_days=40, enabled=False,
        fetcher=lambda: (_ for _ in ()).throw(AssertionError("must not fetch when disabled")),
    )
    u = p.get(now=date(2026, 7, 26))
    assert u.stale
    assert u.resolve("XOM", ClassificationKind.FOSSIL_FUELS).status is ClassificationStatus.UNAVAILABLE


def test_provider_enabled_loads_and_resolves():
    p = ClassificationUniverseProvider(hold_window_days=40, enabled=True, fetcher=_fetcher_ok)
    u = p.get(now=date(2026, 7, 26))
    assert not u.stale
    assert u.resolve("XOM", ClassificationKind.FOSSIL_FUELS).status is ClassificationStatus.EXCLUDED
    assert u.resolve("LMT", ClassificationKind.ESG_LITE).status is ClassificationStatus.EXCLUDED
    assert u.resolve("AAPL", ClassificationKind.SIN).status is ClassificationStatus.PERMITTED


def test_provider_stale_row_pauses():
    p = ClassificationUniverseProvider(
        hold_window_days=40, enabled=True,
        fetcher=lambda: (_CLASSIFIED, _FOSSIL, _SIN, _DEFENSE, date(2026, 1, 1)),
    )
    u = p.get(now=date(2026, 7, 26))  # classify date 200+ days old > 40-day window
    assert u.stale
    assert u.resolve("XOM", ClassificationKind.FOSSIL_FUELS).status is ClassificationStatus.UNAVAILABLE


def test_provider_fetch_error_pauses_loudly():
    def boom():
        raise ClassificationSourceError("seed pending")

    p = ClassificationUniverseProvider(hold_window_days=40, enabled=True, fetcher=boom)
    assert p.get(now=date(2026, 7, 26)).stale  # never a silent empty (permit-all) set


# ── network_classify: aggregation + the loud floor ───────────────────────────


def test_network_classify_aggregates_and_passes_floor():
    infos = {}
    for i in range(405):
        infos[f"T{i:03d}"] = {"sector": "Technology", "industry": "Software"}
    infos["T001"] = {"sector": "Energy", "industry": "Oil & Gas Integrated"}
    infos["T002"] = {"sector": "Consumer Defensive", "industry": "Tobacco"}
    infos["T004"] = {"sector": "Industrials", "industry": "Aerospace & Defense"}
    infos["T003"] = {}  # no sector back → left unclassified (UNKNOWN=permitted, safe)

    classified, fossil, sin, defense = cu._network_classify(
        list(infos), info_fetcher=lambda t: infos[t], throttle_s=0
    )
    assert "T003" not in classified
    assert len(classified) == 404
    assert fossil == frozenset({"T001"})
    assert sin == frozenset({"T002"})
    assert defense == frozenset({"T004"})


def test_network_classify_raises_below_floor():
    """A throttled run that classified almost nothing must RAISE, never store a
    short universe that would un-enforce the filter for most names (CR040)."""
    infos = {"XOM": {"sector": "Energy", "industry": "Oil & Gas Integrated"}}
    with pytest.raises(ClassificationSourceError):
        cu._network_classify(list(infos), info_fetcher=lambda t: infos[t], throttle_s=0)


# ── refresh tick (append-only, idempotent) ───────────────────────────────────


def _fixture_classifier():
    return (_CLASSIFIED, _FOSSIL, _SIN, _DEFENSE)


def test_refresh_disabled_is_noop():
    assert run_classification_refresh_tick(enabled=False) == "disabled"
    with get_session() as s:
        assert latest_snapshot(s) is None


def test_refresh_stores_a_snapshot_row():
    cu.reset_refresh_failures()
    status = run_classification_refresh_tick(
        classifier=_fixture_classifier, enabled=True, force=True,
        now=datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc),
    )
    assert status == "stored"
    with get_session() as s:
        row = latest_snapshot(s)
    assert row is not None
    assert set(row.fossil) == set(_FOSSIL)
    assert set(row.sin) == set(_SIN)
    assert set(row.defense) == set(_DEFENSE)
    assert row.as_of == date(2026, 7, 25)


def test_refresh_skips_when_a_fresh_row_exists():
    """CR075's `skipped_fresh` idempotency: a tick that finds a fresh stored row
    does nothing, so a restart shortly after a run never re-classifies."""
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        write_snapshot(
            s, classified=_CLASSIFIED, fossil=_FOSSIL, sin=_SIN, defense=_DEFENSE, fetched_at=now
        )

    def _must_not_classify():
        raise AssertionError("must not re-classify when a fresh row exists")

    status = run_classification_refresh_tick(
        classifier=_must_not_classify, enabled=True, force=False,
        now=now + timedelta(hours=1),
    )
    assert status == "skipped_fresh"


def test_refresh_reclassifies_once_the_row_is_stale():
    old = datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        write_snapshot(
            s, classified=_CLASSIFIED, fossil=_FOSSIL, sin=set(), defense=set(), fetched_at=old
        )
    # A day later (> the 20h fresh window) the tick re-runs and appends a new row.
    status = run_classification_refresh_tick(
        classifier=_fixture_classifier, enabled=True, force=False,
        now=old + timedelta(days=1),
    )
    assert status == "stored"


def test_refresh_fetch_failure_keeps_held_row_and_bumps_counter():
    cu.reset_refresh_failures()
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    with get_session() as s:
        write_snapshot(
            s, classified=_CLASSIFIED, fossil=_FOSSIL, sin=_SIN, defense=_DEFENSE, fetched_at=now
        )

    def boom():
        raise ClassificationSourceError("no parent set to classify")

    status = run_classification_refresh_tick(
        classifier=boom, enabled=True, force=True, now=now + timedelta(days=2),
    )
    assert status == "fetch_failed"
    assert cu.consecutive_refresh_failures() == 1
    # The held row is untouched — the reader keeps serving it (degrade on the refresher).
    with get_session() as s:
        row = latest_snapshot(s)
    assert set(row.fossil) == set(_FOSSIL)
    cu.reset_refresh_failures()


# ── read path degrades loudly with no socket ─────────────────────────────────


def test_default_universe_disabled_pauses_without_db_or_socket():
    """Feature off (the Alpha default until verified) → the read path resolves to a
    paused universe with no fetch and no snapshot row — the CR040 loud-degrade."""
    cu.reset_classification_universe_provider(None)
    try:
        u = cu.default_classification_universe()
        assert u.stale
        assert u.resolve("XOM", ClassificationKind.FOSSIL_FUELS).status is ClassificationStatus.UNAVAILABLE
    finally:
        cu.reset_classification_universe_provider(None)
