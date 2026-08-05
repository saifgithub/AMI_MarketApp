"""CR136 M04 — engine pipeline, sufficiency boundaries at ±1, and uncertainty-contract shape tests.

Everything here drives the pure `compute_health`, with synthetic seeded walks:
the math itself is pinned by M02's known-answer fixtures against an independent
numpy implementation, so what is under test here is the PIPELINE — which
holdings get dropped and why, which blocks go insufficient and with which cause,
and whether the uncertainty contract actually holds on every path.

The boundary cases are the point. Rev 4's thresholds were each fixed by a
measurement, and a gate that fires at 125 or 127 instead of 126 is a different
product from the one that was justified.
"""

from __future__ import annotations

import json
import math
import random
from datetime import date, timedelta

import pytest

from app.services.portfolio_health import _block, compute_health
from app.services.portfolio_health_constants import (
    BASIS_INVESTED_SLEEVE,
    BASIS_TOTAL_VALUE,
    BASIS_WEIGHTS,
    BENCHMARK_TICKER,
    DAILY_CAP_DEFAULT,
    DROPPED_WEIGHT_MAX,
    ENGINE_VERSION,
    GATE_MODE_DEFAULT,
    GRID_DENSITY_MAX,
    INSUFFICIENT_BENCHMARK_MISALIGNED,
    INSUFFICIENT_DROPPED_WEIGHT,
    INSUFFICIENT_SHORT_WINDOW,
    INSUFFICIENT_SPARSE_GRID,
    INSUFFICIENT_T_OVER_N,
    LOW_R2_THRESHOLD,
    PLANS_DEFAULT,
    T_MIN,
    TRIAL_DAYS_DEFAULT,
    TRIAL_FINDINGS_DEFAULT,
)
from app.trading_math import EWMA_LAMBDA, t_eff

_CONTRACT_FIELDS = {
    "metric", "value", "standard_error", "n_observations", "t_eff",
    "window_days", "sufficient", "partial", "dropped_holdings",
    "low_explanatory_power", "contains_etfs", "backcast", "basis",
    "engine_version",
}
_ESTIMATOR_BLOCKS = (
    "portfolio_volatility", "beta", "tracking_error", "effective_bets",
    "risk_contribution", "mcr", "typical_bad_month", "scenario_panel",
)


# ── Fixture helpers ─────────────────────────────────────────────────────────


def _dates(n: int, *, end: date = date(2026, 7, 31)) -> list[str]:
    """`n` weekday iso dates ending at `end`, ascending."""
    out: list[date] = []
    cursor = end
    while len(out) < n:
        if cursor.weekday() < 5:
            out.append(cursor)
        cursor -= timedelta(days=1)
    return [d.isoformat() for d in reversed(out)]


def _walk(
    seed: int, n: int, *, sigma: float = 0.012, start: float = 100.0,
    dates: list[str] | None = None, market: list[float] | None = None,
    beta: float = 0.0,
) -> list[tuple[str, float]]:
    """A deterministic close series. With `market` and `beta`, the series is
    `beta` times the market's daily move plus its own idiosyncratic noise —
    which is how a book with a KNOWN beta and R² is constructed."""
    grid = dates or _dates(n)
    rnd = random.Random(seed)
    closes = [start]
    for i in range(1, len(grid)):
        shock = rnd.gauss(0.0, sigma)
        if market is not None:
            shock += beta * (market[i] / market[i - 1] - 1.0)
        closes.append(closes[-1] * (1.0 + shock))
    return list(zip(grid, closes))


def _closes(series: list[tuple[str, float]]) -> list[float]:
    return [c for _d, c in series]


def _book(
    n_obs: int = T_MIN + 1,
    *,
    tickers: tuple[str, ...] = ("AAA", "BBB", "CCC"),
    cash: float = 0.0,
    seed: int = 11,
    with_benchmark: bool = True,
    benchmark_dates: list[str] | None = None,
) -> dict:
    """A complete `compute_health` kwargs dict. `n_obs` counts CLOSES, so the
    return count is one less."""
    grid = _dates(n_obs)
    market = _closes(_walk(1, n_obs, sigma=0.009, dates=grid))
    series: dict[str, list[tuple[str, float]]] = {}
    for i, ticker in enumerate(tickers):
        series[ticker] = _walk(
            seed + i, n_obs, sigma=0.010, dates=grid, market=market, beta=1.0 + 0.2 * i,
        )
    if with_benchmark:
        series[BENCHMARK_TICKER] = list(zip(benchmark_dates or grid, market))
    return {
        "holdings": [(t, 10.0) for t in tickers],
        "marks": {t: 100.0 for t in tickers},
        "cash": cash,
        "series": series,
        "sector_of": lambda t: "Tech",
        "etf_tickers": frozenset(),
        "as_of": grid[-1],
    }


def _book_aligned(
    core_closes: int, *, tail: int = 40, tickers: tuple[str, ...] = ("AAA", "BBB", "CCC"),
) -> dict:
    """A book where every holding has plenty of its OWN history but the ALIGNED
    window is exactly `core_closes` long.

    Needed because the per-holding drop rule and the aligned-window floor are
    the same number (126): a holding trimmed to 126 closes is dropped outright,
    so the only way to shorten the intersection without dropping anyone is to
    give each series a disjoint tail of its own."""
    names = [*tickers, BENCHMARK_TICKER]
    total = core_closes + tail * len(names)
    grid = _dates(total)
    core, extras = grid[:core_closes], grid[core_closes:]

    own: dict[str, list[str]] = {n: list(core) for n in names}
    for i, day in enumerate(extras):
        own[names[i % len(names)]].append(day)

    market_by_date = dict(zip(grid, _closes(_walk(1, total, sigma=0.009, dates=grid))))
    series: dict[str, list[tuple[str, float]]] = {}
    for k, name in enumerate(names):
        days = sorted(own[name])
        if name == BENCHMARK_TICKER:
            series[name] = [(d, market_by_date[d]) for d in days]
        else:
            series[name] = _walk(
                11 + k, len(days), sigma=0.010, dates=days,
                market=[market_by_date[d] for d in days], beta=1.0 + 0.2 * k,
            )
    return {
        "holdings": [(t, 10.0) for t in tickers],
        "marks": {t: 100.0 for t in tickers},
        "cash": 0.0,
        "series": series,
        "sector_of": lambda t: "Tech",
        "etf_tickers": frozenset(),
        "as_of": grid[-1],
    }


# ── 1-3. Sufficiency boundaries ─────────────────────────────────────────────


def test_sufficiency_boundary_125_126() -> None:
    """Rev 4's floor is 126 observed RETURNS. 125 must fail and 126 must pass —
    an off-by-one here silently changes which users get a product at all."""
    short = compute_health(**_book_aligned(T_MIN))       # 126 closes → 125 returns
    block = short["blocks"]["portfolio_volatility"]
    assert short["dropped_holdings"] == [], "no holding is short — the WINDOW is"
    assert block["n_observations"] == T_MIN - 1
    assert block["sufficient"] is False
    assert block["value"] is None and block["standard_error"] is None
    assert block["insufficient_cause"] == INSUFFICIENT_SHORT_WINDOW

    ok = compute_health(**_book_aligned(T_MIN + 1))      # 127 closes → 126 returns
    block = ok["blocks"]["portfolio_volatility"]
    assert block["n_observations"] == T_MIN
    assert block["sufficient"] is True
    assert block["value"] is not None and block["standard_error"] is not None


def test_a_holding_shorter_than_the_floor_is_dropped_not_averaged_in() -> None:
    """The other half of the same threshold: a holding with fewer than 126
    observations of its own leaves Σ entirely, with the reason recorded."""
    kwargs = _book(T_MIN + 1)
    kwargs["marks"] = {"AAA": 100.0, "BBB": 100.0, "CCC": 10.0}
    kwargs["series"]["CCC"] = kwargs["series"]["CCC"][-T_MIN:]      # 125 returns
    payload = compute_health(**kwargs)
    assert payload["dropped_holdings"] == [
        {"ticker": "CCC", "reason": "short_history"}
    ]

    kwargs["series"]["CCC"] = _book(T_MIN + 1)["series"]["CCC"][-(T_MIN + 1):]
    assert compute_health(**kwargs)["dropped_holdings"] == []


def test_tn_gate_boundary_leaves_sigma_and_beta_alone() -> None:
    """Rev 4 F17, measured: the relative sampling error of σ̂ₚ is 1/√(2T)
    INDEPENDENT of N, so the T/N gate applies ONLY to the quantities that touch
    off-diagonals. A 50-name book must still get its volatility and its beta."""
    fifty = tuple(f"T{i:02d}" for i in range(50))

    tight = compute_health(**_book(250, tickers=fifty))     # 249 returns / 50 = 4.98
    assert tight["blocks"]["portfolio_volatility"]["sufficient"] is True
    assert tight["blocks"]["beta"]["sufficient"] is True
    for name in ("effective_bets", "risk_contribution", "mcr"):
        block = tight["blocks"][name]
        assert block["sufficient"] is False, name
        assert block["insufficient_cause"] == INSUFFICIENT_T_OVER_N, name
        assert block["value"] is None, name

    passing = compute_health(**_book(251, tickers=fifty))   # 250 / 50 = 5.00
    for name in ("effective_bets", "risk_contribution", "mcr"):
        assert passing["blocks"][name]["sufficient"] is True, name


def test_dropped_weight_boundary() -> None:
    """19.9% of invested value dropped is a partial answer; 20.1% is not an
    answer at all. Weight concentration survives either way — counting weights
    needs no history."""
    def book_with_dropped_fraction(fraction: float) -> dict:
        kwargs = _book(T_MIN + 1, tickers=("AAA", "BBB"))
        kwargs["holdings"] = [("AAA", 10.0), ("BBB", 10.0)]
        kwargs["marks"] = {"AAA": 100.0 * (1 - fraction) / fraction, "BBB": 100.0}
        # BBB has only 60 closes → dropped for short history.
        kwargs["series"]["BBB"] = kwargs["series"]["BBB"][-60:]
        return kwargs

    partial = compute_health(**book_with_dropped_fraction(0.199))
    assert partial["partial"] is True
    assert partial["blocks"]["portfolio_volatility"]["sufficient"] is True
    assert partial["blocks"]["portfolio_volatility"]["partial"] is True

    blocked = compute_health(**book_with_dropped_fraction(0.201))
    for name in _ESTIMATOR_BLOCKS:
        block = blocked["blocks"][name]
        assert block["sufficient"] is False, name
        assert block["insufficient_cause"] == INSUFFICIENT_DROPPED_WEIGHT, name
    assert blocked["blocks"]["weight_concentration"]["sufficient"] is True


# ── 4. The uncertainty contract itself ──────────────────────────────────────


def test_strip_readiness_null_never_zero() -> None:
    """`sufficient: false ⇒ value AND standard_error are null, never 0.0`. This
    is what makes the contract enforceable: null has exactly one meaning, so an
    insufficient metric cannot be narrated as a real number."""
    for payload in (compute_health(**_book(T_MIN)), compute_health(**_book(T_MIN + 1))):
        for name, block in payload["blocks"].items():
            if block["sufficient"]:
                assert block["value"] is not None, name
            else:
                assert block["value"] is None, name
                assert block["standard_error"] is None, name
                assert block["t_eff"] is None, name
                assert block["insufficient_cause"] is not None, name


def test_the_null_forcing_holds_against_a_caller_that_computed_a_value() -> None:
    """AT:R66 — CR136-M04 audit round 1, MINOR m1.

    `test_strip_readiness_null_never_zero` above reads the ENGINE's payload, and
    every call site in the engine already passes `None` when it passes
    `sufficient=False` — so deleting `_block`'s null-forcing outright left all
    39 module tests and all 285 CR136 tests green (auditor's MUT-1). The
    docstring calls that block "the contract's teeth, applied here rather than
    at each call site", and teeth nothing pins are teeth a future call site can
    walk straight through: compute a value, pass `sufficient=False`, publish
    both. This addresses `_block` directly, which is the only way to test the
    forcing rather than the callers' good manners."""
    block = _block(
        "portfolio_volatility",
        value=1.0,
        standard_error=0.5,
        t_eff_value=99.0,
        basis=BASIS_TOTAL_VALUE,
        sufficient=False,
        insufficient_cause=INSUFFICIENT_SHORT_WINDOW,
        n_observations=10,
        window_days=10,
    )
    assert block["value"] is None
    assert block["standard_error"] is None
    assert block["t_eff"] is None

    kept = _block(
        "portfolio_volatility",
        value=1.0,
        standard_error=0.5,
        t_eff_value=99.0,
        basis=BASIS_TOTAL_VALUE,
        sufficient=True,
        insufficient_cause=None,
        n_observations=T_MIN,
        window_days=T_MIN,
    )
    # Non-vacuity: the forcing has to be what nulls them, not the helper
    # dropping all three on every path.
    assert (kept["value"], kept["standard_error"], kept["t_eff"]) == (1.0, 0.5, 99.0)


def test_every_block_carries_the_full_contract() -> None:
    payload = compute_health(**_book(T_MIN + 1))
    assert set(payload["blocks"]) == set(_ESTIMATOR_BLOCKS) | {"weight_concentration"}
    for name, block in payload["blocks"].items():
        missing = _CONTRACT_FIELDS - set(block)
        assert not missing, (name, missing)
        assert block["metric"] == name
    json.dumps(payload)          # the payload is an LLM input and a journal row


def test_basis_per_block() -> None:
    payload = compute_health(**_book(T_MIN + 1))
    expected = {
        "portfolio_volatility": BASIS_TOTAL_VALUE,
        "beta": BASIS_TOTAL_VALUE,
        "tracking_error": BASIS_TOTAL_VALUE,
        "typical_bad_month": BASIS_TOTAL_VALUE,
        "scenario_panel": BASIS_TOTAL_VALUE,
        "effective_bets": BASIS_INVESTED_SLEEVE,
        "risk_contribution": BASIS_INVESTED_SLEEVE,
        "mcr": BASIS_INVESTED_SLEEVE,
        "weight_concentration": BASIS_WEIGHTS,
    }
    assert {n: b["basis"] for n, b in payload["blocks"].items()} == expected


def test_backcast_flag_is_true_exactly_on_sigma_derived_blocks() -> None:
    """Rev 4 F14: every Σ-derived number is today's weights applied to past
    returns, and every surface has to say so. Weight concentration is the one
    block that is not — it reads today's book and nothing else."""
    payload = compute_health(**_book(T_MIN + 1))
    for name in _ESTIMATOR_BLOCKS:
        assert payload["blocks"][name]["backcast"] is True, name
    assert payload["blocks"]["weight_concentration"]["backcast"] is False


def test_engine_version_everywhere() -> None:
    payload = compute_health(**_book(T_MIN + 1))
    assert payload["engine_version"] == ENGINE_VERSION == "cr136.v1"
    for name, block in payload["blocks"].items():
        assert block["engine_version"] == ENGINE_VERSION, name


# ── 5-6. Refusals and the benchmark ─────────────────────────────────────────


def test_mock_mode_refusal_loads_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serving mock-walk prices as a risk analysis is the CR040 question
    answered the wrong way: the numbers would look entirely plausible and mean
    nothing. The refusal must come before any load, not after."""
    from uuid import uuid4

    from app.core.config import settings
    from app.services import portfolio_health

    monkeypatch.setattr(settings, "use_real_market_data", False)

    def _explode(*a, **k):
        raise AssertionError("mock refusal must load nothing")

    monkeypatch.setattr(portfolio_health, "_gather_inputs", _explode)

    payload = portfolio_health.build_health_context(uuid4(), sim=object())
    assert payload["status"] == "refused_mock_data"
    assert payload["reason"] == "use_real_market_data=false"
    assert "blocks" not in payload
    assert payload["engine_version"] == ENGINE_VERSION


def test_the_entry_point_matches_the_pinned_seam() -> None:
    """build/README.md's seam register pins `build_health_context(user_id)` as
    the M04 → M06/M07 entry point, and M07's plan calls it as
    `asyncio.to_thread(build_health_context, user_id)` — which requires it to be
    single-argument AND synchronous, or the call returns an un-awaited coroutine
    instead of a payload."""
    import inspect

    from app.services.portfolio_health import build_health_context

    assert not inspect.iscoroutinefunction(build_health_context)
    params = inspect.signature(build_health_context).parameters
    required = [
        name for name, p in params.items()
        if p.default is inspect.Parameter.empty
    ]
    assert required == ["user_id"], required


def test_fabricated_marks_are_refused_like_fabricated_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The other half of the mock refusal. `portfolio_marks_snapshot` resolves
    through FallbackProvider(cache(yfinance) -> mock_walk), so a Yahoo outage
    puts random-walk prices into EVERY weight in the payload — risk shares, HHI,
    cash fraction, the LEVEL denominator — while the report still says ok."""
    from uuid import uuid4

    from app.core.config import settings
    from app.services import portfolio_health

    monkeypatch.setattr(settings, "use_real_market_data", True)

    class _Holding:
        ticker, quantity = "AAA", 10.0

    class _Portfolio:
        holdings = [_Holding()]
        current_cash = 100.0

    class _Sim:
        def portfolio_marks_snapshot(self, _user_id):
            return _Portfolio(), {"AAA": 100.0}, 1100.0, 0.0, "mock_walk"

    payload = portfolio_health.build_health_context(uuid4(), sim=_Sim())
    assert payload["status"] == "refused_mock_data"
    assert payload["reason"] == "marks_source=mock_walk"
    assert "blocks" not in payload


def test_benchmark_misalignment_is_never_re_gridded() -> None:
    """A benchmark of the right LENGTH but the wrong DATES is exactly the silent
    failure `portfolio_stats.beta()` allows (it validates length, not dates).
    Beta must go null, not be computed on a mismatched grid — and the book's own
    volatility, which needs no benchmark, must survive."""
    kwargs = _book(T_MIN + 1, with_benchmark=False)
    off_grid = _dates(T_MIN + 1, end=date(2021, 7, 30))
    assert len(off_grid) == T_MIN + 1
    kwargs["series"][BENCHMARK_TICKER] = _walk(99, T_MIN + 1, dates=off_grid)

    payload = compute_health(**kwargs)
    assert payload["blocks"]["portfolio_volatility"]["sufficient"] is True
    for name in ("beta", "tracking_error", "scenario_panel"):
        block = payload["blocks"][name]
        assert block["sufficient"] is False, name
        assert block["value"] is None, name
        assert block["insufficient_cause"] == INSUFFICIENT_BENCHMARK_MISALIGNED, name
    assert payload["context"]["benchmark_vol_ann"] is None


# ── 7-9. Disclosure, bases, sectors ─────────────────────────────────────────


def test_etf_flag_is_carried_where_the_blindness_is() -> None:
    """Rev 4 F21: covariance metrics already price ETF overlap. It is the
    WEIGHT-based outputs that count an ETF as one holding, so the disclosure
    belongs on those and nowhere else."""
    kwargs = _book(T_MIN + 1)
    kwargs["etf_tickers"] = frozenset({"AAA"})
    payload = compute_health(**kwargs)

    assert payload["contains_etfs"] is True
    assert payload["blocks"]["weight_concentration"]["contains_etfs"] is True
    for name in _ESTIMATOR_BLOCKS:
        assert payload["blocks"][name]["contains_etfs"] is False, name

    clean = compute_health(**_book(T_MIN + 1))
    assert clean["contains_etfs"] is False


def test_sector_aggregation_uses_the_shared_resolver() -> None:
    kwargs = _book(T_MIN + 1)
    sectors = {"AAA": "Tech", "BBB": "Tech"}
    kwargs["sector_of"] = lambda t: sectors.get(t, "Other")
    payload = compute_health(**kwargs)

    per_sector = payload["blocks"]["risk_contribution"]["per_sector"]
    by_name = {e["sector"]: e["risk_share"] for e in per_sector}
    assert set(by_name) == {"Tech", "Other"}
    per_holding = {
        e["ticker"]: e["risk_share"]
        for e in payload["blocks"]["risk_contribution"]["per_holding"]
    }
    assert by_name["Tech"] == pytest.approx(per_holding["AAA"] + per_holding["BBB"])
    assert by_name["Other"] == pytest.approx(per_holding["CCC"])
    assert math.fsum(by_name.values()) == pytest.approx(1.0, abs=1e-9)


# ── 10-12. Identities ───────────────────────────────────────────────────────


def test_euler_and_cash_identity() -> None:
    """Cash scales the whole-book volatility by exactly (1−c) and leaves the
    invested sleeve's risk shares untouched — Rev 4 R4's rewritten copy says
    precisely this, so it had better be exactly true."""
    no_cash = compute_health(**_book(T_MIN + 1, cash=0.0))
    shares = [
        e["risk_share"]
        for e in no_cash["blocks"]["risk_contribution"]["per_holding"]
    ]
    assert math.fsum(shares) == pytest.approx(1.0, abs=1e-9)

    invested = no_cash["invested_value"]
    cash = invested          # 50% cash
    with_cash = compute_health(**_book(T_MIN + 1, cash=cash))
    c = with_cash["cash_fraction"]
    assert c == pytest.approx(0.5)

    sigma_full = no_cash["blocks"]["portfolio_volatility"]["value"]
    sigma_cash = with_cash["blocks"]["portfolio_volatility"]["value"]
    assert sigma_cash == pytest.approx((1.0 - c) * sigma_full, rel=1e-12)

    beta_full = no_cash["blocks"]["beta"]["value"]
    beta_cash = with_cash["blocks"]["beta"]["value"]
    assert beta_cash == pytest.approx((1.0 - c) * beta_full, rel=1e-12)

    # ...and the SHARE-basis quantities are exactly invariant.
    assert with_cash["blocks"]["effective_bets"]["value"] == pytest.approx(
        no_cash["blocks"]["effective_bets"]["value"], rel=1e-12,
    )
    assert no_cash["blocks"]["beta"]["r_squared"] == pytest.approx(
        with_cash["blocks"]["beta"]["r_squared"], rel=1e-12,
    )
    cash_shares = [
        e["risk_share"]
        for e in with_cash["blocks"]["risk_contribution"]["per_holding"]
    ]
    for a, b in zip(shares, cash_shares):
        assert a == pytest.approx(b, rel=1e-12)


def test_se_uses_t_eff_not_the_raw_observation_count() -> None:
    """Rev 4: publishing σ̂/√(2T) under EWMA understates the true sampling SE by
    ~27%, i.e. reports a confidence the data does not support."""
    payload = compute_health(**_book(T_MIN + 1))
    block = payload["blocks"]["portfolio_volatility"]
    t_obs = block["n_observations"]

    expected_t_eff = t_eff(EWMA_LAMBDA, t_obs)
    assert block["t_eff"] == pytest.approx(expected_t_eff)
    assert block["standard_error"] == pytest.approx(
        block["value"] / math.sqrt(2.0 * expected_t_eff)
    )
    naive = block["value"] / math.sqrt(2.0 * t_obs)
    assert block["standard_error"] > naive


def test_scenario_and_bad_month_arithmetic() -> None:
    payload = compute_health(**_book(T_MIN + 1))
    beta = payload["blocks"]["beta"]["value"]
    episodes = payload["blocks"]["scenario_panel"]["episodes"]
    assert [e["id"] for e in episodes] == ["covid_2020", "drawdown_2022"]
    # The pinned constants themselves, not the payload's own echo of them.
    # Verified 2026-08-02 against ^GSPC (the S&P 500 PRICE index) to 0.02pp and
    # 0.03pp; a total-return series misses the 2022 episode by 0.91pp.
    assert [e["benchmark_return"] for e in episodes] == [-0.339, -0.254]
    assert [e["start"] for e in episodes] == ["2020-02-19", "2022-01-03"]
    assert [e["end"] for e in episodes] == ["2020-03-23", "2022-10-12"]
    for episode in episodes:
        assert episode["implied_portfolio_return"] == pytest.approx(
            beta * episode["benchmark_return"]
        )
    assert payload["blocks"]["scenario_panel"]["value"] == pytest.approx(
        min(e["implied_portfolio_return"] for e in episodes)
    )

    vol = payload["blocks"]["portfolio_volatility"]["value"]
    assert payload["blocks"]["typical_bad_month"]["value"] == pytest.approx(
        1.645 * vol * math.sqrt(21 / 252)
    )


# ── 13-16. Flags, drops, inheritance ────────────────────────────────────────


def test_low_explanatory_power_still_ships_the_beta() -> None:
    """Rev 4: beta on a book the market barely explains is labelled, not
    withheld. Withholding it would leave the reader with no number at all;
    labelling it says exactly how much to trust the one they have."""
    kwargs = _book(T_MIN + 1)
    grid = _dates(T_MIN + 1)
    market = _closes(_walk(1, T_MIN + 1, sigma=0.009, dates=grid))
    for i, ticker in enumerate(("AAA", "BBB", "CCC")):
        kwargs["series"][ticker] = _walk(
            500 + i, T_MIN + 1, sigma=0.020, dates=grid, market=market, beta=0.0,
        )
    kwargs["series"][BENCHMARK_TICKER] = list(zip(grid, market))

    block = compute_health(**kwargs)["blocks"]["beta"]
    assert block["sufficient"] is True
    assert block["value"] is not None
    assert block["r_squared"] < LOW_R2_THRESHOLD
    assert block["low_explanatory_power"] is True

    normal = compute_health(**_book(T_MIN + 1))["blocks"]["beta"]
    assert normal["r_squared"] > LOW_R2_THRESHOLD
    assert normal["low_explanatory_power"] is False


def test_low_explanatory_power_is_null_on_every_other_block() -> None:
    payload = compute_health(**_book(T_MIN + 1))
    for name, block in payload["blocks"].items():
        if name == "beta":
            assert isinstance(block["low_explanatory_power"], bool)
        else:
            assert block["low_explanatory_power"] is None, name


def test_bad_print_holding_is_dropped_for_quality() -> None:
    """Wiring test — the detector's semantics are M01's. What matters here is
    that a flagged holding is dropped with the RIGHT reason, and that a genuine
    crash day is not."""
    kwargs = _book(T_MIN + 60)
    grid = [d for d, _c in kwargs["series"]["AAA"]]
    closes = _closes(kwargs["series"]["AAA"])
    spike = list(closes)
    spike[100] = spike[99] * 1.45                    # phantom print...
    spike[101] = spike[99]                           # ...fully reversed next day
    kwargs["series"]["AAA"] = list(zip(grid, spike))

    payload = compute_health(**kwargs)
    assert {d["ticker"] for d in payload["dropped_holdings"]} == {"AAA"}
    assert payload["dropped_holdings"][0]["reason"] == "data_quality"
    assert payload["partial"] is True

    crash = list(closes)
    for i in range(100, len(crash)):
        crash[i] *= 0.70                             # a real -30% that stays
    kwargs["series"]["AAA"] = list(zip(grid, crash))
    assert compute_health(**kwargs)["dropped_holdings"] == []


def test_short_history_holding_is_dropped_and_weights_renormalise() -> None:
    kwargs = _book(T_MIN + 1)
    # CCC is deliberately a small position: dropping a third of the book would
    # trip the 20% dropped-weight rule and blank every block, which is a
    # different case (covered above).
    kwargs["marks"] = {"AAA": 100.0, "BBB": 100.0, "CCC": 10.0}
    kwargs["series"]["CCC"] = kwargs["series"]["CCC"][-60:]

    payload = compute_health(**kwargs)
    assert payload["dropped_holdings"] == [
        {"ticker": "CCC", "reason": "short_history"}
    ]
    assert payload["partial"] is True
    assert payload["risky_holdings_count"] == 2
    assert payload["holdings_count"] == 3

    weights = [
        e["invested_weight"]
        for e in payload["blocks"]["risk_contribution"]["per_holding"]
    ]
    assert math.fsum(weights) == pytest.approx(1.0, abs=1e-12)

    # partial ⇒ non-empty dropped_holdings on EVERY estimator-derived block.
    for name in _ESTIMATOR_BLOCKS:
        block = payload["blocks"][name]
        assert block["partial"] is True, name
        assert block["dropped_holdings"], name
    assert payload["blocks"]["weight_concentration"]["partial"] is False
    # ...and the weight tile still counts the dropped holding, because counting
    # weights needs no history.
    assert payload["blocks"]["weight_concentration"]["holdings_count"] == 3


def test_derived_blocks_inherit_their_parents_sufficiency() -> None:
    ok = compute_health(**_book(T_MIN + 1))
    assert ok["blocks"]["typical_bad_month"]["sufficient"] == (
        ok["blocks"]["portfolio_volatility"]["sufficient"]
    )
    assert ok["blocks"]["scenario_panel"]["sufficient"] == (
        ok["blocks"]["beta"]["sufficient"]
    )
    assert ok["blocks"]["tracking_error"]["sufficient"] == (
        ok["blocks"]["beta"]["sufficient"]
    )

    short = compute_health(**_book(T_MIN))
    for name in ("typical_bad_month", "scenario_panel", "tracking_error"):
        assert short["blocks"][name]["sufficient"] is False, name


# ── 17-19. Small books and precomputed comparisons ──────────────────────────


def test_no_holdings_state() -> None:
    kwargs = _book(T_MIN + 1)
    kwargs["holdings"] = []
    payload = compute_health(**kwargs)
    assert payload["status"] == "no_holdings"
    assert "blocks" not in payload


def test_single_holding_book() -> None:
    """Rev 4's small-book pin: N=1 produces DEFINED outputs. DR² is exactly 1,
    the risk share is exactly 100%, and σₚ is the holding's own volatility
    scaled by the invested fraction."""
    kwargs = _book(T_MIN + 1, tickers=("AAA",), cash=500.0)
    payload = compute_health(**kwargs)

    assert payload["blocks"]["effective_bets"]["value"] == pytest.approx(1.0)
    top = payload["blocks"]["risk_contribution"]["top"]
    assert top["ticker"] == "AAA"
    assert top["risk_share"] == pytest.approx(1.0)
    assert payload["blocks"]["portfolio_volatility"]["value"] is not None

    solo = compute_health(**_book(T_MIN + 1, tickers=("AAA",), cash=0.0))
    c = payload["cash_fraction"]
    assert payload["blocks"]["portfolio_volatility"]["value"] == pytest.approx(
        (1.0 - c) * solo["blocks"]["portfolio_volatility"]["value"], rel=1e-12,
    )


def test_correlation_pairs_are_precomputed_and_weight_gated() -> None:
    """Rev 4 prompt-contract pt 2: if a comparison is not in the payload it may
    not be said. R2b reads these, and the weight floor is what stops a 4%
    sliver of a book generating a headline."""
    grid = _dates(T_MIN + 1)
    market = _closes(_walk(1, T_MIN + 1, sigma=0.009, dates=grid))
    twin = _walk(7, T_MIN + 1, sigma=0.001, dates=grid, market=market, beta=1.0)
    kwargs = _book(T_MIN + 1, tickers=("AAA", "BBB", "TINY"))
    kwargs["series"]["AAA"] = twin
    kwargs["series"]["BBB"] = _walk(
        8, T_MIN + 1, sigma=0.001, dates=grid, market=market, beta=1.0,
    )
    kwargs["marks"] = {"AAA": 100.0, "BBB": 100.0, "TINY": 4.0}

    payload = compute_health(**kwargs)
    pairs = {(p["a"], p["b"]): p for p in payload["context"]["correlation_pairs"]}
    assert ("AAA", "BBB") in pairs
    assert pairs[("AAA", "BBB")]["rho"] > 0.9
    assert all("TINY" not in key for key in pairs), (
        "a holding under the 5% invested-weight floor must appear in no pair"
    )


def test_r2b_pair_floor_uses_the_same_basis_the_rule_engine_re_checks() -> None:
    """AT:R66 — CR136-M05 audit round 1, MAJOR M1 regression. M04 used to gate correlation-
    pair emission on the COVERED-sleeve weight (survivors only, `v_weights`)
    while M05 re-filters the same list on the FULL invested weight
    (`HoldingInput.invested_weight_pct`, dropped holdings still counted). With
    one holding dropped at exactly `DROPPED_WEIGHT_MAX` (20%), the two bases
    diverge by 1/(1-0.20)=1.25 — enough to put a pair genuinely BELOW the
    5.0pp floor on the full basis (4.5pp) OVER it on the covered basis
    (5.625pp, the auditor's own reproduction numbers). Before the fix, M04
    emitted this pair into the payload and M05 silently discarded it — which
    is not the same as never emitting it, since anything reading
    `context["correlation_pairs"]` directly (not through the rule engine)
    would still see a pair whose weights don't clear the one basis Rev 4
    pins."""
    grid = _dates(T_MIN + 1)
    market = _closes(_walk(1, T_MIN + 1, sigma=0.009, dates=grid))
    kwargs = _book(T_MIN + 1, tickers=("AAA", "BBB", "CCC", "BIG"))
    kwargs["series"]["AAA"] = _walk(7, T_MIN + 1, sigma=0.001, dates=grid, market=market, beta=1.0)
    kwargs["series"]["BBB"] = _walk(8, T_MIN + 1, sigma=0.001, dates=grid, market=market, beta=1.0)
    # CCC dropped for short history, sized to exactly DROPPED_WEIGHT_MAX of
    # full invested value — the boundary the engine still calls "sufficient".
    kwargs["series"]["CCC"] = kwargs["series"]["CCC"][-T_MIN:]
    kwargs["marks"] = {"AAA": 1.0, "BBB": 1.0, "CCC": 1.0, "BIG": 1.0}
    kwargs["holdings"] = [
        ("AAA", 4.5), ("BBB", 4.5),
        ("CCC", DROPPED_WEIGHT_MAX * 100.0), ("BIG", 71.0),
    ]

    payload = compute_health(**kwargs)
    assert payload["dropped_holdings"] == [{"ticker": "CCC", "reason": "short_history"}]
    assert payload["partial"] is True, "20% dropped is partial, not blocked"

    pairs = {(p["a"], p["b"]) for p in payload["context"]["correlation_pairs"]}
    assert ("AAA", "BBB") not in pairs, (
        "AAA/BBB are 4.5% of FULL invested value each — below the 5.0pp floor "
        "on the one basis M05 re-checks against. Only the covered-sleeve "
        "basis (5.625%, inflated by CCC's drop) clears the floor, and that "
        "basis is not the one the payload may gate on."
    )


# ── 20-22. Constants and module hygiene ─────────────────────────────────────


def test_gate_default_constants() -> None:
    assert GATE_MODE_DEFAULT == "trial"
    assert TRIAL_DAYS_DEFAULT == 14
    assert TRIAL_FINDINGS_DEFAULT == 7
    assert DAILY_CAP_DEFAULT == 2
    assert PLANS_DEFAULT == "TRADER,FLOOR_MANAGER"


def test_constants_module_is_import_pure() -> None:
    """`app/core/config.py` reads the gate defaults from here and M01 reads the
    data-layer pins — either import becomes a cycle the moment this module
    reaches back into `app`."""
    import ast
    from pathlib import Path

    from app.services import portfolio_health_constants

    tree = ast.parse(Path(portfolio_health_constants.__file__).read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    assert not any(name.split(".")[0] == "app" for name in imported), imported


def test_the_engine_holds_no_scattered_literals() -> None:
    """Rev 4's "never scattered literals" made structural: every threshold was
    fixed by a measurement, and a number copied into a call site is a number
    nobody can trace back to the simulation that justified it."""
    import re
    from pathlib import Path

    from app.services import portfolio_health

    source = Path(portfolio_health.__file__).read_text()
    code = "\n".join(
        line for line in source.splitlines()
        if not line.strip().startswith("#")
    )
    for literal in ("0.415", "1.85", "0.97", "126", "0.20", "1.645", "0.339"):
        assert not re.search(rf"(?<![\w.]){re.escape(literal)}(?![\w.])", code), literal


# ── Value leaves the first pass never pinned (M04 audit, test-adequacy lens) ──


def test_risk_contribution_value_is_the_risk_share_not_the_weight() -> None:
    """The headline number of the whole feature is "X% of risk vs Y% of money".
    A book where the two coincide cannot tell them apart, so this one is built
    so the top RISK contributor is not the top holding by WEIGHT."""
    kwargs = _book(T_MIN + 1)
    kwargs["marks"] = {"AAA": 30.0, "BBB": 100.0, "CCC": 100.0}
    payload = compute_health(**kwargs)
    block = payload["blocks"]["risk_contribution"]

    top = block["top"]
    assert block["value"] == pytest.approx(top["risk_share"])
    assert block["value"] != pytest.approx(top["invested_weight"]), (
        "vacuity guard — on this book the two must differ, or the assertion "
        "above proves nothing"
    )
    by_share = max(block["per_holding"], key=lambda e: e["risk_share"])
    assert top["ticker"] == by_share["ticker"]


def test_mcr_value_is_the_maximum_not_the_minimum() -> None:
    payload = compute_health(**_book(T_MIN + 1))
    block = payload["blocks"]["mcr"]
    values = [e["mcr"] for e in block["per_holding"]]
    assert len(set(values)) > 1, "vacuity guard — a flat book cannot tell max from min"
    assert block["value"] == pytest.approx(max(values))
    assert block["value"] != pytest.approx(min(values))


def test_weight_concentration_counts_the_full_invested_sleeve() -> None:
    """Counting weights needs no history, so a dropped holding still occupies
    its share of the user's money and still counts here — computing HHI over the
    survivors instead would flatter a book precisely when it is least
    understood."""
    kwargs = _book(T_MIN + 1)
    kwargs["marks"] = {"AAA": 100.0, "BBB": 100.0, "CCC": 10.0}
    kwargs["series"]["CCC"] = kwargs["series"]["CCC"][-60:]
    payload = compute_health(**kwargs)

    values = {"AAA": 1000.0, "BBB": 1000.0, "CCC": 100.0}
    total = sum(values.values())
    expected_hhi = sum((v / total) ** 2 for v in values.values())

    block = payload["blocks"]["weight_concentration"]
    assert block["value"] == pytest.approx(expected_hhi)
    assert block["effective_n"] == pytest.approx(1.0 / expected_hhi)
    assert block["holdings_count"] == 3

    survivors_only = sum(
        (v / 2000.0) ** 2 for k, v in values.items() if k != "CCC"
    )
    assert block["value"] != pytest.approx(survivors_only)


def test_window_days_is_the_calendar_span_of_the_aligned_window() -> None:
    """A drawdown or volatility figure without its window is not interpretable,
    so the span has to be a real number rather than a present key."""
    payload = compute_health(**_book(T_MIN + 1))
    grid = _dates(T_MIN + 1)
    span = (date.fromisoformat(grid[-1]) - date.fromisoformat(grid[0])).days
    assert span > T_MIN, "vacuity guard — weekdays span more calendar days than rows"
    for name, block in payload["blocks"].items():
        assert block["window_days"] == span, name


def test_benchmark_vol_is_annualised() -> None:
    """Dropping the √252 is a 15.9x error that still produces a plausible-looking
    number, which is the only kind of error worth a test."""
    payload = compute_health(**_book(T_MIN + 1))
    benchmark_vol = payload["context"]["benchmark_vol_ann"]
    assert benchmark_vol is not None

    grid = _dates(T_MIN + 1)
    market = _closes(_walk(1, T_MIN + 1, sigma=0.009, dates=grid))
    returns = [market[i] / market[i - 1] - 1.0 for i in range(1, len(market))]
    from app.trading_math import annualize_vol, ewma_covariance

    daily = math.sqrt(ewma_covariance([returns])[0][0])
    assert benchmark_vol == pytest.approx(annualize_vol(daily))
    assert benchmark_vol > 5.0 * daily, "vacuity guard — annualisation must bite"


def test_the_level_denominator_is_the_covered_sleeve_plus_cash() -> None:
    """In a partial book the LEVEL basis must be covered_invested + cash, not
    full_invested + cash: σₚ describes the sleeve the engine actually measured,
    and dividing by money it could not see would understate it."""
    kwargs = _book(T_MIN + 1, cash=1000.0)
    kwargs["marks"] = {"AAA": 100.0, "BBB": 100.0, "CCC": 10.0}
    kwargs["series"]["CCC"] = kwargs["series"]["CCC"][-60:]
    partial = compute_health(**kwargs)

    covered = partial["covered_invested_value"]
    assert covered == pytest.approx(2000.0)
    assert partial["invested_value"] == pytest.approx(2100.0)

    clean = dict(kwargs)
    clean["holdings"] = [("AAA", 10.0), ("BBB", 10.0)]
    clean_payload = compute_health(**clean)
    ratio = covered / (covered + 1000.0)
    assert partial["blocks"]["portfolio_volatility"]["value"] == pytest.approx(
        ratio * clean_payload["blocks"]["portfolio_volatility"]["value"] /
        (2000.0 / 3000.0), rel=1e-9,
    )


def test_a_feed_outage_is_not_reported_as_a_young_security() -> None:
    """CR040, at the M04 seam this time. The engine must not tell a user "not
    enough price history for this holding" when the truth is "our feed is down"
    — the two call for completely different actions from them."""
    kwargs = _book(T_MIN + 1)
    kwargs["marks"] = {"AAA": 100.0, "BBB": 100.0, "CCC": 10.0}
    kwargs["series"]["CCC"] = []
    kwargs["feed_failed"] = frozenset({"CCC"})

    payload = compute_health(**kwargs)
    assert payload["dropped_holdings"] == [
        {"ticker": "CCC", "reason": "feed_unavailable"}
    ]

    kwargs["feed_failed"] = frozenset()
    payload = compute_health(**kwargs)
    assert payload["dropped_holdings"] == [
        {"ticker": "CCC", "reason": "short_history"}
    ]


def test_a_benchmark_feed_outage_says_so() -> None:
    kwargs = _book(T_MIN + 1, with_benchmark=False)
    kwargs["series"][BENCHMARK_TICKER] = []
    kwargs["feed_failed"] = frozenset({BENCHMARK_TICKER})

    payload = compute_health(**kwargs)
    assert payload["blocks"]["beta"]["insufficient_cause"] == "feed_unavailable"
    assert payload["blocks"]["portfolio_volatility"]["sufficient"] is True


def test_a_zero_variance_book_is_insufficient_not_a_confident_zero() -> None:
    """A book whose adjusted closes never move has zero variance. M02 raises on
    it by contract; shipping 0.0 with sufficient:true would be a confident
    claim of no risk at all."""
    grid = _dates(T_MIN + 1)
    flat = [(d, 100.0) for d in grid]
    kwargs = _book(T_MIN + 1)
    for ticker in ("AAA", "BBB", "CCC"):
        kwargs["series"][ticker] = flat

    payload = compute_health(**kwargs)
    block = payload["blocks"]["portfolio_volatility"]
    assert block["sufficient"] is False
    assert block["value"] is None
    assert block["insufficient_cause"] == "zero_variance"


# ── DEF213: the joined grid's density ───────────────────────────────────────


def _book_thinned(total: int, keep: int, *, seed: int = 11, private: int = 0) -> dict:
    """A book where every holding has plenty of its OWN history but ONE of them
    is missing days, so the JOINED grid is `keep` dates long.

    First and last date are always kept, so `window_days` is identical to the
    clean book's and the only thing that moves is `n_observations` — which is
    exactly the shape DEF213 describes: `_join` intersects, so one thinly-traded
    holding thins the grid every metric in the book is computed on.

    `private` gives every name that many dates of its own beyond the shared
    span, disjoint from everyone else's. Needed whenever `keep` falls under the
    126-close drop rule: without it the thin holding is dropped outright and the
    join quietly reverts to the full grid — which is what the intersection does,
    not what the test meant to build."""
    tickers = ("AAA", "BBB", "CCC")
    names = [*tickers, BENCHMARK_TICKER]
    grid = _dates(total + private * len(names))
    shared, extras = grid[:total], grid[total:]

    market_by_date = dict(zip(grid, _closes(_walk(1, len(grid), sigma=0.009, dates=grid))))

    step = (total - 1) / (keep - 1)
    thin = sorted({shared[0], shared[-1]} | {shared[round(i * step)] for i in range(keep)})

    own: dict[str, list[str]] = {}
    for i, name in enumerate(names):
        base = thin if name == tickers[0] else list(shared)
        own[name] = sorted(base + extras[i::len(names)])

    series: dict[str, list[tuple[str, float]]] = {}
    for i, ticker in enumerate(tickers):
        days = own[ticker]
        series[ticker] = _walk(
            seed + i, len(days), sigma=0.010, dates=days,
            market=[market_by_date[d] for d in days], beta=1.0 + 0.2 * i,
        )
    series[BENCHMARK_TICKER] = [(d, market_by_date[d]) for d in own[BENCHMARK_TICKER]]
    return {
        "holdings": [(t, 10.0) for t in tickers],
        "marks": {t: 100.0 for t in tickers},
        "cash": 0.0,
        "series": series,
        "sector_of": lambda t: "Tech",
        "etf_tickers": frozenset(),
        "as_of": shared[-1],
    }


def test_a_gappy_joined_grid_is_refused_not_annualised_as_if_daily() -> None:
    """DEF213. Every return is a close-to-close ratio on the JOINED grid and
    `annualize_vol` scales all of them by √252, so a return spanning several
    trading days is annualised as though it spanned one — measured at +12.5% on
    σ with 20% of one holding's days missing, and +29.8% at 40%.

    The half that makes it a defect rather than an estimator limitation is the
    silence: nothing is dropped and nothing is partial, because the days simply
    never lined up. This asserts the silence is over."""
    payload = compute_health(**_book_thinned(500, 300))

    for name in (
        "portfolio_volatility", "beta", "effective_bets", "risk_contribution",
    ):
        block = payload["blocks"][name]
        assert block["sufficient"] is False, name
        assert block["value"] is None, name
        assert block["insufficient_cause"] == INSUFFICIENT_SPARSE_GRID, name

    vol = payload["blocks"]["portfolio_volatility"]
    # Counting observations cannot see this: 299 returns is more than twice the
    # 126-return floor, so every pre-DEF213 sufficiency check passes.
    assert vol["n_observations"] > 2 * T_MIN
    assert vol["window_days"] / vol["n_observations"] > GRID_DENSITY_MAX
    # ...and this is what it looked like before the guard: a clean, confident
    # measurement with nothing anywhere to say the grid had holes.
    assert payload["dropped_holdings"] == []
    assert vol["partial"] is False


def test_the_grid_density_threshold_is_where_the_constant_says_it_is() -> None:
    """Straddles GRID_DENSITY_MAX on one calendar span, so the test pins the
    threshold rather than merely exercising the branch. Both books have the same
    first and last date — only the observation count differs."""
    grid = _dates(500)
    span = (
        date.fromisoformat(grid[-1]) - date.fromisoformat(grid[0])
    ).days

    # keep = returns + 1; ratio = span / returns.
    just_under = math.floor(span / GRID_DENSITY_MAX) + 1
    just_over = just_under - 1
    assert span / just_under < GRID_DENSITY_MAX < span / just_over

    dense = compute_health(**_book_thinned(500, just_under + 1))
    sparse = compute_health(**_book_thinned(500, just_over + 1))

    assert dense["blocks"]["portfolio_volatility"]["sufficient"] is True
    assert dense["blocks"]["portfolio_volatility"]["value"] is not None
    assert sparse["blocks"]["portfolio_volatility"]["sufficient"] is False
    assert (
        sparse["blocks"]["portfolio_volatility"]["insufficient_cause"]
        == INSUFFICIENT_SPARSE_GRID
    )


def test_a_clean_book_never_trips_the_density_guard() -> None:
    """The false-fire half. A guard that withholds every Σ-derived metric from a
    user whose data is fine is worse than the overstatement it prevents, so the
    threshold was set from the WORST clean window on the real US-equity calendar
    (measured 1.4921 over 11,038 rolling windows; 1.5556 with a 5-session
    closure constructed into it) — see GRID_DENSITY_MAX."""
    for n_obs in (T_MIN + 1, 250, 400, 505):
        payload = compute_health(**_book(n_obs))
        vol = payload["blocks"]["portfolio_volatility"]
        assert vol["window_days"] / vol["n_observations"] < GRID_DENSITY_MAX
        assert vol["insufficient_cause"] != INSUFFICIENT_SPARSE_GRID
        assert vol["sufficient"] is True, n_obs

    # The loop above is NOT the guard: `_dates` is weekdays only, so every grid
    # it builds sits at exactly 7/5 = 1.40 and the assertion holds for any
    # threshold above that — including one well under the real calendar's worst
    # clean window, which is the mistake that matters here. Measured on the real
    # calendar, market holidays push a legitimate 126-return window to 1.4921,
    # and a constructed 5-session closure inside one to 1.5556; a threshold set
    # below either of those withholds every Σ-derived metric from a user whose
    # data is fine. Both densities are reproduced exactly, and both must pass.
    for keep, floor in ((468, 1.4921), (449, 1.5556)):
        payload = compute_health(**_book_thinned(500, keep))
        vol = payload["blocks"]["portfolio_volatility"]
        assert vol["window_days"] / vol["n_observations"] >= floor
        assert vol["sufficient"] is True, floor
        assert vol["value"] is not None, floor


def test_a_short_grid_reads_short_not_sparse() -> None:
    """A book below the 126-return floor is BOTH short and — on a weekday grid
    with a long tail — arbitrarily sparse. `short_window` is the more
    fundamental fact and must win, or the user is told their feed has holes
    when the truth is AMI has not watched them long enough yet."""
    payload = compute_health(**_book_thinned(500, 100, private=60))
    vol = payload["blocks"]["portfolio_volatility"]
    assert payload["dropped_holdings"] == [], "no holding is short — the WINDOW is"
    assert vol["n_observations"] < T_MIN
    assert vol["window_days"] / vol["n_observations"] > GRID_DENSITY_MAX
    assert vol["insufficient_cause"] == INSUFFICIENT_SHORT_WINDOW


# ── DEF216. The block SET ───────────────────────────────────────────────────


_TIER2_BLOCKS = {"realised_max_drawdown", "realised_return"}


def test_the_payload_publishes_every_block_the_card_can_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEF216. `tier2_blocks` and `equity_curve` had no production caller at all
    — `grep -rn` outside `backend/tests/` returned only their definitions — so
    `realised_max_drawdown` and `realised_return` could not render. Live Alpha
    served 9 blocks; M09's card, its `portfolioHealthMddNote` string and both
    Dart percent-unit mappings were unreachable, and no test failed, because
    every existing assertion NAMES the block it wants and nothing ever counted
    them. This one counts them.

    It survived two audits because each lane was correctly scoped to itself:
    M03 §4 assigned the consumer to M07 in as many words, and M07 closed
    COMPLETE at round 4 without wiring it. The seam is what nobody owned.
    """
    from uuid import uuid4

    from app.core.config import settings
    from app.services import portfolio_health

    monkeypatch.setattr(settings, "use_real_market_data", True)

    book = _book()
    tier1 = set(compute_health(**book)["blocks"])
    assert not (tier1 & _TIER2_BLOCKS), "Tier 2 is not computed by compute_health"

    portfolio_id = uuid4()
    monkeypatch.setattr(
        portfolio_health, "_gather_inputs", lambda *_a, **_k: (portfolio_id, book),
    )
    monkeypatch.setattr(portfolio_health, "equity_curve", lambda _pid: [])

    payload = portfolio_health.build_health_context(uuid4(), sim=object())
    assert payload["status"] == "ok"
    assert set(payload["blocks"]) == tier1 | _TIER2_BLOCKS, (
        "the entry point must publish Tier 1 AND Tier 2 — count them, never "
        "name the one you expect"
    )


def test_tier2_carries_real_snapshot_values_through_the_seam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Wiring the names through is not the fix; wiring the NUMBERS through is.
    A merge that always produced empty blocks would pass the set test above."""
    from uuid import uuid4

    from app.core.config import settings
    from app.services import portfolio_health
    from app.services.portfolio_snapshot import SnapshotPoint

    monkeypatch.setattr(settings, "use_real_market_data", True)

    values = [100.0] * 19 + [150.0, 120.0]
    points = [
        SnapshotPoint(
            as_of=date(2026, 1, 5) + timedelta(days=i), total_value=v, cash=0.0,
            invested_value=v, drawdown_pct=99.0, source="yfinance",
            predicted_vol_ann=0.262,
        )
        for i, v in enumerate(values)
    ]

    book = _book()
    portfolio_id = uuid4()
    monkeypatch.setattr(
        portfolio_health, "_gather_inputs", lambda *_a, **_k: (portfolio_id, book),
    )
    monkeypatch.setattr(portfolio_health, "equity_curve", lambda _pid: points)

    blocks = portfolio_health.build_health_context(uuid4(), sim=object())["blocks"]
    assert blocks["realised_max_drawdown"]["value"] == pytest.approx(20.0)
    assert blocks["realised_max_drawdown"]["sufficient"] is True
    assert blocks["realised_return"]["value"] == pytest.approx(20.0)


def test_the_snapshot_path_does_not_load_the_curve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier 2 is built FROM snapshots. Loading the curve in order to write the
    next snapshot row is a query per portfolio per tick for a number nothing on
    that path reads."""
    from uuid import uuid4

    from app.core.config import settings
    from app.services import portfolio_health

    monkeypatch.setattr(settings, "use_real_market_data", True)

    def _explode(_pid):
        raise AssertionError("the snapshot path must not load the equity curve")

    monkeypatch.setattr(
        portfolio_health, "_gather_inputs", lambda *_a, **_k: (uuid4(), _book()),
    )
    monkeypatch.setattr(portfolio_health, "equity_curve", _explode)

    predicted = portfolio_health.predicted_vol_for_snapshot(uuid4())
    assert predicted is not None
    assert predicted.predicted_vol_ann > 0.0
