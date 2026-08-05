"""CR136 M11 live cross-check (dev-only, run inside ami_api_alpha) — recomputes σₚ/β/R²/DR²/risk shares/TE for one real book from raw price_history_daily rows with an independent numpy implementation and diffs against the live /v1/portfolio/health payload to 2 dp. Never imported by tests or app code; must not import app.trading_math.

The engine's own unit tests prove it matches its fixtures. They cannot prove the
fixtures describe the same arithmetic an independent reader would do, and they
say nothing at all about the LIVE book on Alpha. This script closes both gaps:
it reads the stored closes with its own `SELECT`, redoes the joins and the
returns, and recomputes every published number in numpy from the formula —
never by calling `app.trading_math`, which is the code under test.

The formulas are reimplemented from Rev 4's own definitions, not copied:

    EWMA weights   wⱼ = λ^(T-1-j) / Σ λ^(T-1-k)      (normalised over the
                                                      AVAILABLE window, newest
                                                      last, λ = 0.97)
    covariance     Σ_ab = Σⱼ wⱼ (r_aj − μ_a)(r_bj − μ_b),  μ_a = Σⱼ wⱼ r_aj
                   — weighted-demeaned, population style, no dof correction
    σₚ             √(wᵀΣw) · √252, w over the TOTAL book (cash as a zero row
                   appended AFTER estimation, benchmark leg weighted exactly 0)
    β, R²          Cov_w(p,b)/Var(b) and Cov_w(p,b)²/(Var(p)·Var(b)) — both
                   read off the ONE joint matrix, so the two sides can never
                   come from different windows
    TE             √(σₚ² + σ_b² − 2βσ_b²), annualised inputs
    DR²            ((Σᵢ wᵢσᵢ)/σₚ)², invested-sleeve weights, risky block only
    risk shares    wᵢ(Σw)ᵢ / σₚ², same invested-sleeve block — Euler's theorem,
                   so they sum to 1

λ, √252 and the 504-return cap are spelled as literals here rather than
imported from the constants module: that module re-exports from
`app.trading_math`, and an "independent" check that imports the thing it checks
is not one. If a constant ever changes, this script failing IS the signal.

Usage — inside the api container, which is the only place with both the DB and
a reachable API:

    ssh melehost "docker exec ami_api_alpha python -m scripts.cr136_live_crosscheck \\
      --user-id <uuid> --api-base http://localhost:8000 --token <bearer-for-that-user>"

The route is `_own`-guarded, so the bearer token must belong to `--user-id`.

BOOK SELECTION — one REAL tester book. Exclude the 13 CR035 room-benchmark
synthetics (`last_app_version = 'room-benchmark'`) and the 10 seed rows from the
05-24 05:10 batch; the deterministic filter lives in
`memory/feedback_user_report_exclusions.md`. Prefer ≥ 4 risky holdings with
T ≥ 126. If no real book qualifies at ship time, Saiful's own account is
acceptable and the choice is recorded with the run output.

Exit codes — a FAIL is never silent:

    0  every |diff| ≤ 0.005 in the rendered unit (Rev 4's "to 2dp")
    1  numeric FAIL — the diff table is printed with the offending rows marked
    2  preconditions unmet: unknown user, HTTP error, an engine status other
       than `ok`, an insufficient σₚ block, or a stored-history window that
       does not match the payload's own `n_observations`

Read-only: this script issues no INSERT, UPDATE or DELETE, and never writes to
the journal.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request
from datetime import date
from uuid import UUID

import numpy as np
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import PriceHistoryDailyRow
# The mock-source sentinel, imported rather than retyped. Independence here is
# about the ARITHMETIC — this is a data-hygiene rule, and a second hardcoded
# copy of the string would silently stop filtering the day M01 renamed it.
from app.services.price_history import _MOCK_SOURCE

# Deliberately literals — see the module docstring. Importing these from the
# constants module would route them through `app.trading_math`.
_LAMBDA = 0.97
_TRADING_DAYS = 252.0
_MAX_RETURNS = 504
_BENCHMARK = "SPY"
_TOL = 0.005          # 2 dp in the rendered unit


# ── The payload under test ──────────────────────────────────────────────────


def _fetch_health(api_base: str, user_id: UUID, token: str) -> dict:
    url = f"{api_base.rstrip('/')}/v1/portfolio/health/{user_id}"
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


# ── Raw history, read with this script's own SELECT ─────────────────────────


def _load_closes(
    tickers: list[str],
) -> tuple[dict[str, dict[date, float]], dict[str, int]]:
    """`adj_close` per (ticker, day) out of M01's table, plus a per-ticker count
    of mock-source rows skipped.

    Not via M01's series helpers: the point is to re-do the joining and the
    trimming here, so a bug in that layer shows up as a disagreement rather
    than being inherited by both sides of the comparison.

    **But the same-source filter IS applied.** In real mode the engine reads
    `source != 'mock_walk'` (`price_history._load_rows`, and `latest_trading_day`
    likewise), so a table holding both real and fabricated bars — which this
    codebase explicitly anticipates and tests for — would otherwise have the
    harness recomputing from prices the live engine correctly refused. That is
    not an independent check; it is a different question asked of different
    data, and it would report a FAIL against an engine that was right. The
    filter is a hygiene rule, not arithmetic, so mirroring it is what keeps the
    comparison honest.
    """
    real_mode = bool(settings.use_real_market_data)
    out: dict[str, dict[date, float]] = {t: {} for t in tickers}
    skipped: dict[str, int] = {t: 0 for t in tickers}
    with get_session() as session:
        rows = session.execute(
            select(
                PriceHistoryDailyRow.ticker,
                PriceHistoryDailyRow.date,
                PriceHistoryDailyRow.adj_close,
                PriceHistoryDailyRow.source,
            ).where(PriceHistoryDailyRow.ticker.in_(tickers))
        ).all()
    for ticker, day, adj_close, source in rows:
        if real_mode and source == _MOCK_SOURCE:
            skipped[ticker] += 1
            continue
        out[ticker][day] = float(adj_close)
    return out, skipped


def _joined_returns(
    closes: dict[str, dict[date, float]], tickers: list[str],
) -> tuple[np.ndarray, list[date]]:
    """(assets × time) simple returns over the shared trading days, newest last.

    **This does NOT mirror M04's order, and the docstring used to claim it did**
    (M11 m2). Here: per-ticker trim to the newest 505 dates FIRST, then
    intersect, then trim. Engine `_join` (`portfolio_health.py:302-307`):
    intersect the FULL date sets, then trim once at the end. On a book where one
    holding sits on a sparser calendar than the rest the two diverge hard —
    measured at 390 dates engine vs 252 harness on a 780/390-weekday pair.

    Left as-is rather than realigned, because the divergence is structurally
    loud: pre-trimming can only REMOVE candidate dates, so the harness's
    intersection is always a subset of the engine's, its count is always ≤ the
    payload's `n_observations`, and `main()`'s window check fires and exits 2
    before a single number is compared. The dangerous corner — equal counts over
    different dates, yielding a spurious FAIL that blames a correct engine — is
    unreachable: a subset still holding 505 dates must reach further back, so
    the counts diverge first. What was wrong was the comment, and a comment that
    misdescribes the one thing it exists to explain is graded as hard as code.
    """
    trimmed = {
        t: sorted(closes.get(t, {}))[-(_MAX_RETURNS + 1):] for t in tickers
    }
    if any(not days for days in trimmed.values()):
        return np.empty((0, 0)), []
    common = set.intersection(*(set(days) for days in trimmed.values()))
    days = sorted(common)[-(_MAX_RETURNS + 1):]
    if len(days) < 2:
        return np.empty((0, 0)), []

    matrix = np.array(
        [[closes[t][d] for d in days] for t in tickers], dtype=float,
    )
    returns = matrix[:, 1:] / matrix[:, :-1] - 1.0
    return returns, days


# ── The independent implementation ──────────────────────────────────────────


def ewma_weights(t: int) -> np.ndarray:
    ages = np.arange(t - 1, -1, -1, dtype=float)      # newest last ⇒ age 0 last
    raw = _LAMBDA ** ages
    return raw / raw.sum()


def ewma_covariance(returns: np.ndarray) -> np.ndarray:
    weights = ewma_weights(returns.shape[1])
    means = returns @ weights
    deviations = returns - means[:, None]
    return (deviations * weights) @ deviations.T


def append_cash_row(cov: np.ndarray) -> np.ndarray:
    n = cov.shape[0]
    out = np.zeros((n + 1, n + 1))
    out[:n, :n] = cov
    return out


def variance(w: np.ndarray, cov: np.ndarray) -> float:
    return float(w @ cov @ w)


def risk_shares(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    var = variance(w, cov)
    return w * (cov @ w) / var


def dr_squared(w: np.ndarray, cov: np.ndarray) -> float:
    weighted_vol = float(w @ np.sqrt(np.diag(cov)))
    return (weighted_vol / math.sqrt(variance(w, cov))) ** 2


def beta_r2(w: np.ndarray, cov: np.ndarray, b_index: int) -> tuple[float, float]:
    var_b = float(cov[b_index, b_index])
    var_p = variance(w, cov)
    cov_pb = float(w @ cov[:, b_index])
    return cov_pb / var_b, (cov_pb * cov_pb) / (var_p * var_b)


def tracking_error(sigma_p: float, sigma_b: float, beta: float) -> float:
    radicand = sigma_p ** 2 + sigma_b ** 2 - 2.0 * beta * sigma_b ** 2
    return math.sqrt(max(0.0, radicand))


# ── Comparison ──────────────────────────────────────────────────────────────


class _Row:
    def __init__(self, metric: str, api: float | None, mine: float, unit: str):
        self.metric = metric
        self.api = api
        self.mine = mine
        self.unit = unit

    @property
    def diff(self) -> float | None:
        return None if self.api is None else self.api - self.mine

    @property
    def ok(self) -> bool:
        return self.diff is not None and abs(self.diff) <= _TOL

    def line(self) -> str:
        api = "—" if self.api is None else f"{self.api:>12.4f}"
        diff = "—" if self.diff is None else f"{self.diff:>+10.4f}"
        flag = "" if self.ok else "   <-- FAIL"
        return (
            f"  {self.metric:<28} {self.unit:<10} {api}  {self.mine:>12.4f}  "
            f"{diff}{flag}"
        )


def _fail(message: str) -> int:
    print(f"\nPRECONDITION NOT MET: {message}")
    return 2


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="CR136 M11 live cross-check")
    ap.add_argument("--user-id", required=True)
    ap.add_argument("--api-base", default="http://localhost:8000")
    ap.add_argument("--token", required=True, help="bearer token for --user-id")
    ap.add_argument(
        "--allow-unchecked", default="",
        help=(
            "comma-separated metrics the payload is EXPECTED not to publish on "
            "this book (e.g. beta,r_squared,tracking_error for a book whose "
            "benchmark is unusable). Anything unpublished and not named here "
            "fails the run — see M11 A1."
        ),
    )
    args = ap.parse_args(argv)
    allowed_unchecked = {
        m.strip() for m in args.allow_unchecked.split(",") if m.strip()
    }

    user_id = UUID(args.user_id)
    try:
        envelope = _fetch_health(args.api_base, user_id, args.token)
    except urllib.error.HTTPError as exc:
        return _fail(f"GET /v1/portfolio/health/{user_id} returned {exc.code}")
    except Exception as exc:                      # noqa: BLE001
        return _fail(f"GET /v1/portfolio/health/{user_id} failed: {exc}")

    metrics = envelope.get("metrics") or envelope
    status = metrics.get("status") or envelope.get("status")
    if status != "ok":
        return _fail(f"engine status is {status!r}, not 'ok' — nothing to check")

    blocks = metrics.get("blocks") or {}
    vol_block = blocks.get("portfolio_volatility") or {}
    if not vol_block.get("sufficient"):
        return _fail(
            "portfolio_volatility is insufficient "
            f"(cause {vol_block.get('insufficient_cause')!r}) — pick a book "
            f"with T ≥ 126"
        )

    risk_block = blocks.get("risk_contribution") or {}
    per_holding = risk_block.get("per_holding") or []
    if not per_holding:
        return _fail("no per-holding risk breakdown in the payload")

    tickers = [str(row["ticker"]) for row in per_holding]
    invested_weights = np.array(
        [float(row["invested_weight"]) for row in per_holding],
    )
    api_shares = {str(row["ticker"]): float(row["risk_share"]) for row in per_holding}

    covered_invested = float(metrics.get("covered_invested_value") or 0.0)
    total_value = float(metrics.get("total_value") or 0.0)
    cash = float(metrics.get("cash_fraction") or 0.0) * total_value
    covered_total = covered_invested + cash
    if covered_total <= 0.0:
        return _fail("covered invested value + cash is zero — nothing to weight")

    dropped = [d.get("ticker") for d in (metrics.get("dropped_holdings") or [])]
    if metrics.get("partial") and not dropped:
        return _fail("payload says partial but names no dropped holdings")

    # ── Rebuild the window from stored history ──────────────────────────────
    closes, skipped_mock = _load_closes([*tickers, _BENCHMARK])
    missing = [t for t in [*tickers, _BENCHMARK] if not closes.get(t)]
    if missing:
        return _fail(f"no usable price_history_daily rows for {missing}")

    returns, days = _joined_returns(closes, [*tickers, _BENCHMARK])
    if returns.size == 0:
        return _fail("the joined window has fewer than two shared trading days")

    t_obs = returns.shape[1]
    api_t = int(vol_block.get("n_observations") or 0)
    if t_obs != api_t:
        # Not a numeric FAIL: the engine and this script disagree about WHICH
        # observations they are looking at, so any diff below would be
        # comparing two different windows and would mean nothing.
        return _fail(
            f"window mismatch — this script joined {t_obs} returns, the payload "
            f"reports n_observations={api_t}. Re-run after the history warmer "
            f"has caught up, or investigate M01's join."
        )

    n_risky = len(tickers)
    b_index = n_risky                       # benchmark is the last estimated leg
    cov_joint = ewma_covariance(returns)
    cov_risky = cov_joint[:n_risky, :n_risky]

    # LEVEL basis: total book, benchmark leg weighted 0, cash appended after.
    w_full = np.zeros(n_risky + 2)
    w_full[:n_risky] = invested_weights * (covered_invested / covered_total)
    w_full[b_index] = 0.0
    w_full[-1] = cash / covered_total
    cov_full = append_cash_row(cov_joint)

    sigma_daily = math.sqrt(variance(w_full, cov_full))
    sigma_ann = sigma_daily * math.sqrt(_TRADING_DAYS)
    beta, r_squared = beta_r2(w_full, cov_full, b_index)
    sigma_b_ann = math.sqrt(cov_joint[b_index, b_index] * _TRADING_DAYS)
    te_ann = tracking_error(sigma_ann, sigma_b_ann, beta)

    # SHARE basis: invested sleeve, risky block only.
    dr2 = dr_squared(invested_weights, cov_risky)
    shares = risk_shares(invested_weights, cov_risky)

    def _value(metric: str) -> float | None:
        block = blocks.get(metric) or {}
        return None if block.get("value") is None else float(block["value"])

    rows: list[_Row] = [
        # Percentage-point comparisons — the unit the card and the Finding print.
        _Row("portfolio_volatility", _pp(_value("portfolio_volatility")),
             sigma_ann * 100.0, "pp"),
        _Row("beta", _value("beta"), beta, "ratio"),
        _Row("r_squared",
             (blocks.get("beta") or {}).get("r_squared"), r_squared, "ratio"),
        _Row("tracking_error", _pp(_value("tracking_error")), te_ann * 100.0, "pp"),
        _Row("effective_bets", _value("effective_bets"), dr2, "ratio"),
    ]
    for i, ticker in enumerate(tickers):
        rows.append(
            _Row(f"risk_share[{ticker}]", _pp(api_shares[ticker]),
                 float(shares[i]) * 100.0, "pp"),
        )

    print("CR136 M11 live cross-check")
    print("=" * 78)
    print(f"user            : {user_id}")
    print(f"engine_version  : {metrics.get('engine_version')}")
    print(f"as_of           : {metrics.get('as_of')}")
    print(f"window          : {t_obs} returns, {days[0]}..{days[-1]}")
    print(f"risky holdings  : {', '.join(tickers)}")
    if dropped:
        print(f"dropped (partial): {', '.join(str(d) for d in dropped)}")
    fabricated = {t: n for t, n in skipped_mock.items() if n}
    if fabricated:
        # Loud, not silent: the engine excluded these too, so the comparison is
        # still valid — but a book being priced off a partially-fabricated
        # table is something the operator should know before trusting a PASS.
        print(f"mock-source rows skipped (real mode): {fabricated}")
    print(f"cash fraction   : {cash / total_value if total_value else 0.0:.4f}")
    print("-" * 78)
    print(f"  {'metric':<28} {'unit':<10} {'api':>12}  {'recomputed':>12}  "
          f"{'diff':>10}")
    print("-" * 78)
    for row in rows:
        print(row.line())
    print("-" * 78)

    unchecked = [r.metric for r in rows if r.api is None]
    failures = [r for r in rows if r.api is not None and not r.ok]
    # M11 A1 — an unpublished metric used to be printed and then dropped from
    # the exit code, so this gate returned 0 having compared a strict subset.
    # Checklist 2.9's acceptance criterion is literally the exit code, and an
    # exit code that cannot distinguish "compared all seven" from "compared
    # four" is prose, not a control (CR038). The reachable route needs nothing
    # exotic: a bad print in stored SPY drops the benchmark, three level
    # metrics come back null, the window still matches, and the old gate
    # printed PASS. Renaming a payload field (DEF210's shape, one layer out)
    # does the same with no unusual book at all.
    surprises = [m for m in unchecked if m not in allowed_unchecked]
    stale_allowances = sorted(allowed_unchecked - set(unchecked))

    if unchecked:
        print(f"  not published by the payload, so not checked: {unchecked}")
    if stale_allowances:
        print(f"  --allow-unchecked named, but PUBLISHED: {stale_allowances}")
    print(f"  tolerance       : |diff| ≤ {_TOL} in the rendered unit")
    print(f"  compared        : {len(rows) - len(unchecked)} of {len(rows)}")
    print(f"  FAILED          : {len(failures)}")

    if failures:
        print("\nFAIL — the live engine and an independent recomputation of the "
              "same stored prices disagree beyond 2 dp.")
        return 1
    if surprises:
        print(
            f"\nFAIL — {len(surprises)} metric(s) the payload did not publish "
            f"and no --allow-unchecked names: {surprises}. Nothing disagreed; "
            "nothing compared them either. Either the engine withheld them "
            "(a real finding) or the payload renamed a field this harness "
            "reads (a schema drift this gate has no pin against)."
        )
        return 1
    checked = len(rows) - len(unchecked)
    if allowed_unchecked:
        print(
            f"\nPASS — all {checked} of {len(rows)} metrics agree to 2 dp; "
            f"{len(unchecked)} expected-unpublished and waived by "
            f"--allow-unchecked: {unchecked}."
        )
    else:
        print(f"\nPASS — all {len(rows)} metrics published and agreeing to 2 dp.")
    return 0


def _pp(fraction: float | None) -> float | None:
    """Engine values are decimal fractions; the card and the Finding print
    percentage points. Comparing in the rendered unit is what makes "to 2dp"
    mean what a reader would think it means."""
    return None if fraction is None else fraction * 100.0


if __name__ == "__main__":
    sys.exit(main())
