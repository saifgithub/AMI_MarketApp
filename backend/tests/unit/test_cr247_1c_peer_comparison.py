"""CR247 Phase 1C — the same-4-digit-SIC peer basket and its rendered line.

The Fundamentals lane carried the company's own multiples and, since CR219
R37, its multiples against its OWN history — but never a read across OTHER
companies. This is the cross-company line: median trailing P/E, median
EV/EBITDA and median net margin across the basket of same-4-digit-SIC
market-cap neighbours, with the basket size, SIC and resolution date stated.

The rules pinned here:

**LLMs never compute the figures.** Medians are `statistics.median` in
`peer_basket.compute_medians`, per field, with the effective n carried
alongside — a peer missing a field is excluded from THAT median only, and the
line says how many remain when the count drops below the basket size.

**Never fabricated, never widened.** Membership is verified live per
candidate against its own submissions JSON; fewer than three verified
same-SIC peers is `unavailable` with the reason "insufficient peer coverage"
— the SIC is never fuzzy-matched to reach the floor.

**Weekly, lazy, per ticker.** `refresh_peer_basket` re-resolves at most once
per 7 days per ticker (the stale basket serves until then); a failed
resolution retries after an hour, not the week.

**Live-only.** A past-dated sheet gets `unavailable` with that reason (no
historical peer store), and the neighbourhood anchor is the company's own
live market cap — without it there is no basket.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.config import settings
from app.schemas.agents import AgentId
from app.services import peer_basket, room_prompts, room_runner
from app.services.fundamentals import peer_comparison_line

_T0 = datetime(2026, 9, 29, 12, 0, 0, tzinfo=UTC)

# AAPL's real group. The tests build their fixtures FROM the module's own
# candidate tuple so a universe edit cannot silently desync the fixtures.
_3674 = peer_basket._CANDIDATES_BY_SIC["3674"]


def _3674_cik_map() -> dict[str, int]:
    """The fixture CIK assignment: candidate i is CIK 100+i (AAPL itself is 1)."""
    return {cand: 100 + i for i, cand in enumerate(_3674)}

# The 7 peers the fixtures serve quotes for, with eyeball-checkable figures.
# Trailing P/Es 10..70 → median 40; EV/EBITDA 5..35 → median 20; margins
# 5..35% → median 20. Caps sit in a tight band around AAPL's so all 7 are the
# nearest; the other candidates get no info (unserved quote → excluded).
_PEERS = {
    "NVDA": {"cap": 3.4e12, "pe": 10.0, "ev": 5.0, "margin": 0.05},
    "AVGO": {"cap": 3.6e12, "pe": 20.0, "ev": 10.0, "margin": 0.10},
    "AMD":  {"cap": 3.3e12, "pe": 30.0, "ev": 15.0, "margin": 0.15},
    "TXN":  {"cap": 3.7e12, "pe": 40.0, "ev": 20.0, "margin": 0.20},
    "QCOM": {"cap": 3.2e12, "pe": 50.0, "ev": 25.0, "margin": 0.25},
    "INTC": {"cap": 3.8e12, "pe": 60.0, "ev": 30.0, "margin": 0.30},
    "MU":   {"cap": 3.1e12, "pe": 70.0, "ev": 35.0, "margin": 0.35},
}


def _install_universe(monkeypatch, *, sic: str = "3674", description: str | None = "Semiconductors & Related Devices"):
    """Fake the whole network surface: CIK map, submissions JSON, .info.

    AAPL is CIK 1 under `sic`; every 3674 candidate is CIK 100+i under the
    same SIC; quotes exist for `_PEERS` only. Returns the call logs so tests
    can assert WHAT was probed (no SIC widening, cache hits never fetch).
    """
    cik_map = {"AAPL": 1, **_3674_cik_map()}
    sic_by_cik: dict[int, dict] = {1: {"sic": sic, "sicDescription": description}}
    for cik in _3674_cik_map().values():
        sic_by_cik[cik] = {"sic": sic, "sicDescription": description}

    submissions_calls: list[int] = []
    info_calls: list[str] = []

    monkeypatch.setattr(peer_basket, "resolve_cik", lambda t: cik_map.get(t.upper()))

    def fake_submissions(cik: int) -> dict | None:
        submissions_calls.append(cik)
        return sic_by_cik.get(cik)

    def fake_info(ticker: str) -> dict | None:
        info_calls.append(ticker)
        p = _PEERS.get(ticker.upper())
        if p is None:
            return None
        return {
            "marketCap": p["cap"],
            "trailingPE": p["pe"],
            "enterpriseToEbitda": p["ev"],
            "profitMargins": p["margin"],
        }

    peer_basket.set_peer_fetchers(submissions=fake_submissions, info=fake_info)
    peer_basket.clear_peer_basket_store()
    return submissions_calls, info_calls


def _row(ticker: str, *, cap: float = 1e12, pe=None, ev=None, margin=None) -> peer_basket.PeerRow:
    return peer_basket.PeerRow(
        ticker=ticker, cik=1, sic="3674", market_cap=cap,
        trailing_pe=pe, ev_to_ebitda=ev,
        net_margin_pct=margin,
    )


# ── The median math (computed in Python, per field, effective n) ────────────


def test_medians_are_code_computed_and_pinned() -> None:
    members = [_row(t, pe=v, ev=v / 2, margin=v / 10) for t, v in
               zip(("A", "B", "C", "D", "E"), (10.0, 20.0, 30.0, 40.0, 50.0), strict=True)]
    m = peer_basket.compute_medians(members)
    assert m.trailing_pe == 30.0 and m.trailing_pe_n == 5
    assert m.ev_ebitda == 15.0 and m.ev_ebitda_n == 5
    assert m.net_margin_pct == 3.0 and m.net_margin_n == 5  # margins 1..5 %


def test_an_even_count_median_is_the_midpoint_of_the_middle_two() -> None:
    members = [_row(t, pe=v) for t, v in zip(("A", "B", "C", "D"), (10.0, 20.0, 30.0, 44.0), strict=True)]
    m = peer_basket.compute_medians(members)
    assert m.trailing_pe == 25.0  # (20 + 30) / 2, not a mean of the set (26.0)


def test_a_peer_missing_a_field_is_excluded_from_that_median_only() -> None:
    members = [
        _row("A", pe=10.0, ev=5.0, margin=5.0),
        _row("B", pe=20.0, ev=None, margin=11.0),
        _row("C", pe=30.0, ev=15.0, margin=None),
    ]
    m = peer_basket.compute_medians(members)
    assert m.trailing_pe == 20.0 and m.trailing_pe_n == 3
    assert m.ev_ebitda == 10.0 and m.ev_ebitda_n == 2
    assert m.net_margin_pct == 8.0 and m.net_margin_n == 2  # median of 5 and 11


def test_a_field_no_peer_reports_is_absent_not_zero() -> None:
    members = [_row("A", pe=10.0), _row("B", pe=20.0)]
    m = peer_basket.compute_medians(members)
    assert m.ev_ebitda is None and m.ev_ebitda_n == 0
    assert m.net_margin_pct is None and m.net_margin_n == 0


def test_the_margin_conversion_is_a_whole_percent_like_the_sheets_own(monkeypatch) -> None:
    """`.info` serves `profitMargins` as a fraction (0.05); the sheet's own
    margin figures are whole percents. The conversion lives at resolution —
    pinned on a resolved member, not re-derived by the line."""
    _install_universe(monkeypatch)
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is not None
    by_ticker = {m.ticker: m for m in result.basket.members}
    assert by_ticker["NVDA"].net_margin_pct == 5.0  # 0.05 → 5, whole percent
    assert result.basket.medians.net_margin_pct == 20.0


# ── The line ────────────────────────────────────────────────────────────────


def _line_args(**over):
    args = {
        "ticker": "AAPL", "sic": "3674", "sic_description": "Semiconductors & Related Devices",
        "basket_size": 7, "basket_as_of": "2026-09-29",
        "median_trailing_pe": 24.1, "n_trailing_pe": 7,
        "median_ev_ebitda": 14.2, "n_ev_ebitda": 7,
        "median_net_margin": 18.0, "n_net_margin": 7,
        "own_trailing_pe": "38.8",
    }
    args.update(over)
    return peer_comparison_line(**args)


def test_the_line_states_every_fact_the_spec_example_names() -> None:
    line = _line_args()
    assert "Peer comparison (LIVE)" in line
    assert "median trailing P/E 24.1x" in line
    assert "median EV/EBITDA 14.2x" in line
    assert "median net margin 18%" in line
    assert "across 7 peers in SIC 3674 (Semiconductors & Related Devices)" in line
    assert "basket as of 2026-09-29" in line
    assert "AAPL trades at 38.8x trailing P/E" in line
    assert "AMI's own computation in code" in line


def test_a_reduced_n_is_stated_on_that_median() -> None:
    line = _line_args(n_ev_ebitda=6)
    assert "median EV/EBITDA 14.2x (6 of 7 peers report it)" in line
    assert "median trailing P/E 24.1x (6 of" not in line


def test_the_own_figure_tail_is_omitted_when_the_sheet_has_no_trailing_pe() -> None:
    line = _line_args(own_trailing_pe=None)
    assert "trades at" not in line
    assert "median trailing P/E 24.1x" in line


def test_no_medians_no_line_and_no_basket_facts_no_line() -> None:
    assert _line_args(median_trailing_pe=None, median_ev_ebitda=None, median_net_margin=None) is None
    assert peer_comparison_line(
        ticker="AAPL", sic=None, sic_description=None, basket_size=7, basket_as_of="2026-09-29",
        median_trailing_pe=24.1, n_trailing_pe=7,
        median_ev_ebitda=None, n_ev_ebitda=0,
        median_net_margin=None, n_net_margin=0,
        own_trailing_pe="38.8",
    ) is None


# ── The store: lazy seed, weekly throttle, failure retry ───────────────────


def test_refresh_seeds_lazily_and_serves_the_week_without_refetching(monkeypatch) -> None:
    submissions_calls, info_calls = _install_universe(monkeypatch)
    first = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert first.basket is not None
    assert first.basket.sic == "3674"
    assert first.basket.as_of == _T0.date()
    assert len(first.basket.members) == 7
    n_submissions = len(submissions_calls)
    n_info = len(info_calls)

    # Same week — the cached snapshot serves; nothing is re-fetched.
    again = peer_basket.refresh_peer_basket(
        "AAPL", target_market_cap=3.5e12, now=_T0 + peer_basket.timedelta(days=6)
    )
    assert again.basket is first.basket
    assert len(submissions_calls) == n_submissions
    assert len(info_calls) == n_info


def test_refresh_re_resolves_once_the_basket_is_stale(monkeypatch) -> None:
    submissions_calls, _ = _install_universe(monkeypatch)
    peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    n = len(submissions_calls)
    fresh = peer_basket.refresh_peer_basket(
        "AAPL", target_market_cap=3.5e12, now=_T0 + peer_basket.timedelta(days=8)
    )
    assert fresh.basket is not None
    assert len(submissions_calls) > n  # stale → re-resolved on next convene


def test_clearing_the_store_forces_a_fresh_resolution(monkeypatch) -> None:
    submissions_calls, _ = _install_universe(monkeypatch)
    peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    n = len(submissions_calls)
    peer_basket.clear_peer_basket_store()
    peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert len(submissions_calls) > n


def test_a_failed_resolution_retries_after_the_short_window_not_the_week(monkeypatch) -> None:
    submissions_calls, _ = _install_universe(monkeypatch, sic="9999")  # no candidate group
    failed = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert failed.basket is None
    assert "insufficient peer coverage" in (failed.reason or "")
    n = len(submissions_calls)
    # Inside the failure window: cached, no re-fetch.
    cached = peer_basket.refresh_peer_basket(
        "AAPL", target_market_cap=3.5e12, now=_T0 + peer_basket.timedelta(minutes=10)
    )
    assert cached.basket is None and len(submissions_calls) == n
    # Past it: retried.
    retried = peer_basket.refresh_peer_basket(
        "AAPL", target_market_cap=3.5e12, now=_T0 + peer_basket.timedelta(hours=2)
    )
    assert retried.basket is None and len(submissions_calls) > n


def test_a_successful_basket_survives_the_failure_window_length(monkeypatch) -> None:
    """TTL discipline check: the 1h failure retry must NOT apply to live
    baskets — a good basket serves the full week."""
    submissions_calls, _ = _install_universe(monkeypatch)
    peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    n = len(submissions_calls)
    peer_basket.refresh_peer_basket(
        "AAPL", target_market_cap=3.5e12, now=_T0 + peer_basket.timedelta(hours=2)
    )
    assert len(submissions_calls) == n


# ── Degrade states (never fabricated, never widened) ───────────────────────


def test_fewer_than_three_verified_peers_is_insufficient_coverage(monkeypatch) -> None:
    # Two of the 3674 candidates file under the target's SIC; the rest file
    # somewhere else entirely (sic "0100" — crop production, not in any
    # candidate group).
    cik_map = {"AAPL": 1, **_3674_cik_map()}
    monkeypatch.setattr(peer_basket, "resolve_cik", lambda t: cik_map.get(t.upper()))
    info_calls: list[str] = []
    peer_basket.set_peer_fetchers(
        submissions=lambda cik: (
            {"sic": "3674", "sicDescription": "Semiconductors & Related Devices"} if cik == 1
            else {"sic": "3674"} if cik in (100, 101) else {"sic": "0100"}
        ),
        info=lambda t: info_calls.append(t) or None,
    )
    peer_basket.clear_peer_basket_store()
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is None
    assert "insufficient peer coverage" in (result.reason or "")
    assert "2 same-SIC peers" in (result.reason or "")
    # Coverage failures never reach the quote fetcher.
    assert info_calls == []


def test_an_unknown_sic_never_probes_anything(monkeypatch) -> None:
    submissions_calls, info_calls = _install_universe(monkeypatch, sic="9999", description="Unclassified")
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is None
    assert "insufficient peer coverage" in (result.reason or "")
    assert "no candidate universe" in (result.reason or "")
    assert submissions_calls == [1]  # only the target's own SIC was read
    assert info_calls == []


def test_throttled_candidate_fetches_are_unverified_not_absent(monkeypatch) -> None:
    """A candidate whose submissions could not be READ is not evidence of
    non-membership: below the floor the reason says membership is UNVERIFIED
    for those candidates, distinct from genuinely having too few same-SIC
    filers (CR040 — an outage and a coverage gap must never read the same)."""
    cik_map = {"AAPL": 1, **_3674_cik_map()}
    monkeypatch.setattr(peer_basket, "resolve_cik", lambda t: cik_map.get(t.upper()))

    def fake_submissions(cik: int) -> dict | None:
        if cik == 1:
            return {"sic": "3674", "sicDescription": "Semiconductors & Related Devices"}
        if cik == 100:  # NVDA verifies…
            return {"sic": "3674"}
        return None  # …the rest of SEC is unreadable this call (429 storm)

    peer_basket.set_peer_fetchers(submissions=fake_submissions, info=lambda _t: None)
    peer_basket.clear_peer_basket_store()
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is None
    reason = result.reason or ""
    assert "insufficient peer coverage" in reason
    assert "unverified" in reason
    assert "could not be read this call" in reason


def test_a_missing_sic_on_the_submissions_is_a_failure(monkeypatch) -> None:
    _install_universe(monkeypatch, sic="", description=None)
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is None
    assert "no usable 4-digit SIC" in (result.reason or "")


def test_unreadable_submissions_degrade_loudly(monkeypatch) -> None:
    monkeypatch.setattr(peer_basket, "resolve_cik", lambda _t: 1)
    peer_basket.set_peer_fetchers(submissions=lambda _cik: None, info=lambda _t: None)
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is None
    assert "could not be read" in (result.reason or "")


def test_fewer_than_three_peers_serving_caps_is_insufficient_coverage(monkeypatch) -> None:
    _install_universe(monkeypatch)
    peer_basket.set_peer_fetchers(
        submissions=lambda cik: {"sic": "3674"} if cik >= 100 else {"sic": "3674", "sicDescription": "X"},
        info=lambda _t: None,  # every quote unserved
    )
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is None
    assert "insufficient peer coverage" in (result.reason or "")
    assert "served market caps" in (result.reason or "")


def test_a_basket_with_no_usable_multiples_is_a_failure(monkeypatch) -> None:
    _install_universe(monkeypatch)
    peer_basket.set_peer_fetchers(
        submissions=lambda cik: {"sic": "3674"} if cik >= 100 else {"sic": "3674", "sicDescription": "X"},
        info=lambda t: {"marketCap": 3.5e12},  # caps but no multiples
    )
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is None
    assert "no multiples" in (result.reason or "")


def test_a_non_positive_target_cap_declines_instead_of_dividing(monkeypatch) -> None:
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=0.0, now=_T0)
    assert result.basket is None
    assert "market-cap neighbours cannot be chosen" in (result.reason or "")


def test_the_neighbourhood_is_by_log_distance_not_absolute_dollars(monkeypatch) -> None:
    """A peer 2x LARGER (log 0.69) is nearer than a peer ~3.5x SMALLER
    (log 1.25) even though the small one is closer in absolute dollars
    ($2.5T away vs $3.5T). Eight peers serve caps (six cluster + the two
    outliers); the basket takes seven, so exactly one outlier is dropped —
    log-distance drops the SMALL peer, absolute-dollar distance would drop
    the BIG one. Membership is the discriminator; a silent flip to absolute
    distance changes it."""
    _install_universe(monkeypatch)
    peer_basket.set_peer_fetchers(
        submissions=lambda cik: {"sic": "3674"} if cik >= 100 else {"sic": "3674", "sicDescription": "X"},
        info=lambda t: (
            {"marketCap": 7.0e12, "trailingPE": 88.0, "enterpriseToEbitda": 44.0, "profitMargins": 0.50}
            if t == "TER" else (
                {"marketCap": 1.0e12, "trailingPE": 99.0, "enterpriseToEbitda": 55.0, "profitMargins": 0.20}
                if t == "ADI" else (
                    {  # five of the six remaining fixture peers serve their cluster quotes
                        "marketCap": _PEERS[t]["cap"], "trailingPE": _PEERS[t]["pe"],
                        "enterpriseToEbitda": _PEERS[t]["ev"], "profitMargins": _PEERS[t]["margin"],
                    } if t in _PEERS and t != "MU" else None  # MU's quote is unserved this call
                )
            )
        ),
    )
    result = peer_basket.refresh_peer_basket("AAPL", target_market_cap=3.5e12, now=_T0)
    assert result.basket is not None
    members = {m.ticker for m in result.basket.members}
    assert members == {"NVDA", "AVGO", "AMD", "TXN", "QCOM", "INTC", "TER"}
    assert "ADI" not in members  # the 3.5x-smaller peer is farther than the 2x-larger one


# ── The overlay (room_runner) ──────────────────────────────────────────────


@pytest.fixture
def real_market_data():
    """The overlay declines in mock mode by design; the tests that exercise
    the live path flip the setting the way the guard fixture does."""
    prior = settings.use_real_market_data
    settings.use_real_market_data = True
    yield
    settings.use_real_market_data = prior


def _profile_with_live_cap() -> dict:
    return {
        "ticker": "AAPL",
        "market_cap": 3_500_000,  # $M, the sheet's own convention
        "pe": "38.8",
        "field_state": {"market_cap": "live", "pe": "live"},
    }


def test_the_overlay_populates_the_profile_and_state(monkeypatch, real_market_data) -> None:
    _install_universe(monkeypatch)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # noqa: ARG003 - the seam IS the fixed instant
            return _T0

    monkeypatch.setattr(peer_basket, "datetime", _FrozenDateTime)
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    assert fs["peer_comparison"] == "live"
    assert profile["peer_comparison_sic"] == "3674"
    assert profile["peer_comparison_sic_description"] == "Semiconductors & Related Devices"
    assert profile["peer_comparison_basket_size"] == 7
    assert profile["peer_comparison_as_of"] == _T0.date().isoformat()
    assert profile["peer_comparison_median_pe"] == 40.0
    assert profile["peer_comparison_median_pe_n"] == 7
    assert profile["peer_comparison_median_ev_ebitda"] == 20.0
    assert profile["peer_comparison_median_net_margin"] == 20.0


def test_the_overlay_is_live_only(monkeypatch) -> None:
    _install_universe(monkeypatch)
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", _T0.date())
    assert fs["peer_comparison"] == "unavailable"
    assert "past-dated" in profile["peer_comparison_unavailable_reason"]


def test_the_overlay_declines_in_mock_mode(monkeypatch) -> None:
    prior = settings.use_real_market_data
    settings.use_real_market_data = False
    try:
        profile = _profile_with_live_cap()
        fs = profile["field_state"]
        room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
        assert fs["peer_comparison"] == "unavailable"
        assert "mock mode" in profile["peer_comparison_unavailable_reason"]
    finally:
        settings.use_real_market_data = prior


def test_the_overlay_declines_when_the_own_cap_is_not_live(monkeypatch, real_market_data) -> None:
    _install_universe(monkeypatch)
    profile = _profile_with_live_cap()
    profile["field_state"]["market_cap"] = "unavailable"
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    assert fs["peer_comparison"] == "unavailable"
    assert "market-cap neighbours cannot be chosen" in profile["peer_comparison_unavailable_reason"]


def test_the_overlay_absorbs_a_resolution_exception_loudly(monkeypatch, real_market_data) -> None:
    def _boom(*_a, **_k):
        raise RuntimeError("store exploded")
    monkeypatch.setattr(peer_basket, "refresh_peer_basket", _boom)
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    assert fs["peer_comparison"] == "unavailable"
    assert "resolution failed" in profile["peer_comparison_unavailable_reason"]


def test_the_overlay_surfaces_the_failure_reason(monkeypatch, real_market_data) -> None:
    _install_universe(monkeypatch, sic="9999")
    profile = _profile_with_live_cap()
    fs = profile["field_state"]
    room_runner._overlay_peer_comparison(profile, fs, "AAPL", None)
    assert fs["peer_comparison"] == "unavailable"
    assert "insufficient peer coverage" in profile["peer_comparison_unavailable_reason"]


# ── The render seam ────────────────────────────────────────────────────────


def _profile() -> dict:
    return {
        "ticker": "AAPL",
        "field_state": {"peer_comparison": "live", "pe": "live"},
        "pe": "38.8",
        "peer_comparison_sic": "3674",
        "peer_comparison_sic_description": "Semiconductors & Related Devices",
        "peer_comparison_basket_size": 7,
        "peer_comparison_as_of": "2026-09-29",
        "peer_comparison_median_pe": 24.1,
        "peer_comparison_median_pe_n": 7,
        "peer_comparison_median_ev_ebitda": 14.2,
        "peer_comparison_median_ev_ebitda_n": 6,
        "peer_comparison_median_net_margin": 18.0,
        "peer_comparison_median_net_margin_n": 7,
    }


@pytest.fixture(autouse=True)
def _flag_restored():
    before = settings.room_peer_comparison_enabled
    yield
    settings.room_peer_comparison_enabled = before


def test_nothing_renders_with_the_flag_off() -> None:
    settings.room_peer_comparison_enabled = False
    assert "Peer comparison" not in room_prompts._format_profile(
        _profile(), AgentId.FUNDAMENTALS_ANALYST)


def test_the_flag_is_on_by_default() -> None:
    """ON 2026-09-29 (CR247 Phase 1C — unit suite + the live AAPL render
    probe). The env var stays as the kill switch; the flag-off render is
    pinned above."""
    assert settings.room_peer_comparison_enabled is True


def test_the_line_renders_with_the_flag_on() -> None:
    settings.room_peer_comparison_enabled = True
    sheet = room_prompts._format_profile(_profile(), AgentId.FUNDAMENTALS_ANALYST)
    assert "Peer comparison (LIVE)" in sheet
    assert "median trailing P/E 24.1x" in sheet
    assert "median EV/EBITDA 14.2x (6 of 7 peers report it)" in sheet
    assert "across 7 peers in SIC 3674 (Semiconductors & Related Devices), basket as of 2026-09-29" in sheet
    assert "AAPL trades at 38.8x trailing P/E" in sheet


def test_presence_is_not_provenance() -> None:
    """A hand-built profile with no recorded provenance must not render the
    LIVE line. The not-available degrade line still names the field (the
    put_call precedent: the flag-on sheet says what is missing and why) — the
    pin is on the (LIVE) figures, which only `field_state` may authorize."""
    settings.room_peer_comparison_enabled = True
    profile = _profile()
    profile["field_state"] = {}
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "Peer comparison (LIVE)" not in sheet
    assert "median trailing P/E 24.1x" not in sheet


def test_an_unavailable_block_renders_its_reason_even_with_the_flag_on() -> None:
    settings.room_peer_comparison_enabled = True
    profile = _profile()
    profile["field_state"] = {"peer_comparison": "unavailable"}
    profile["peer_comparison_unavailable_reason"] = (
        "insufficient peer coverage — 2 same-SIC peers from data in hand, 3 needed"
    )
    sheet = room_prompts._format_profile(profile, AgentId.FUNDAMENTALS_ANALYST)
    assert "Peer comparison: not available this call" in sheet
    assert "insufficient peer coverage" in sheet
    assert "Do not estimate peer or sector-average figures from memory" in sheet


def test_the_line_reaches_the_full_sheet_default_render() -> None:
    """`agent_id=None` renders every lane (the parity surface) — the peer
    line must be there too, beside the own-history multiples it complements."""
    settings.room_peer_comparison_enabled = True
    sheet = room_prompts._format_profile(_profile())
    assert "Peer comparison (LIVE)" in sheet
