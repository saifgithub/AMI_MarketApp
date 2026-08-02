"""CR136 M02 fixture generator — DEV-ONLY. Independent numpy implementation that prints known-answer literals for test_cr136_estimator_core.py; also verifies the M04 scenario-episode constants against SPY (--verify-scenarios). Never imported by tests or app code.

Run by hand from the repo root:

    backend/.venv/bin/python backend/scripts/cr136_generate_fixtures.py
    backend/.venv/bin/python backend/scripts/cr136_generate_fixtures.py --verify-scenarios

Why it exists at all: Rev 4 estimator pin 7 requires the estimator's
known-answer fixtures to be generated against an **independent** implementation.
A test that checks `ewma_covariance` against a second copy of `ewma_covariance`
checks nothing, so nothing in this file may import `app.trading_math` — the
formulas below are written out from the specification, in numpy, deliberately
in a different style (explicit weight vectors and outer products) from the
stdlib loops the shipped module uses.

numpy is used HERE ONLY. It is already in the backend venv transitively via
yfinance, so this adds no dependency, and the `trading_math` package's
stdlib-only contract is untouched because this script is never imported by the
tests or the app — it prints literals, a human pastes them in.

Deterministic by construction: every input series below is a hand-written
decimal literal, no RNG anywhere, so re-running must reproduce the checked-in
values byte for byte.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

import numpy as np

LAM = 0.97

# ── Independent estimator (numpy, written from the spec — NOT from the module) ──


def ewma_weights(lam: float, t: int) -> np.ndarray:
    ages = np.arange(t - 1, -1, -1, dtype=float)   # column j has age T-1-j
    u = lam ** ages
    return u / u.sum()


def ewma_cov(returns: np.ndarray, lam: float = LAM) -> np.ndarray:
    """Weighted-demeaned, population-style. Rows = assets, cols = time."""
    r = np.asarray(returns, dtype=float)
    t = r.shape[1]
    w = ewma_weights(lam, t)
    mu = np.average(r, axis=1, weights=w)
    d = r - mu[:, None]
    cov = np.zeros((r.shape[0], r.shape[0]), dtype=float)
    for j in range(t):
        cov += w[j] * np.outer(d[:, j], d[:, j])
    return cov


def corr_from_cov(cov: np.ndarray) -> np.ndarray:
    s = np.sqrt(np.diag(cov))
    return cov / np.outer(s, s)


def sigma_p(w: np.ndarray, cov: np.ndarray) -> float:
    return float(np.sqrt(w @ cov @ w))


def euler(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    var = w @ cov @ w
    return w * (cov @ w) / var


def mcr(w: np.ndarray, cov: np.ndarray) -> np.ndarray:
    return (cov @ w) / np.sqrt(w @ cov @ w)


def dr2(w: np.ndarray, cov: np.ndarray) -> float:
    dr = float((w @ np.sqrt(np.diag(cov))) / np.sqrt(w @ cov @ w))
    return dr * dr


def beta_r2(w: np.ndarray, cov: np.ndarray, b: int) -> tuple[float, float, float, float]:
    cov_pb = float(w @ cov[:, b])
    var_b = float(cov[b][b])
    var_p = float(w @ cov @ w)
    return cov_pb / var_b, (cov_pb ** 2) / (var_p * var_b), var_p, var_b


def tracking_error(sp: float, sb: float, beta: float) -> float:
    return float(np.sqrt(sp ** 2 + sb ** 2 - 2.0 * beta * sb ** 2))


def se_beta(var_p: float, var_b: float, beta: float, t_eff: float) -> float:
    return float(np.sqrt(max(0.0, var_p - beta ** 2 * var_b) / (t_eff * var_b)))


def t_eff(lam: float, t: int) -> float:
    w = ewma_weights(lam, t)
    return float(1.0 / np.sum(w ** 2))


# ── Input series (hand-written literals, no RNG) ────────────────────────────

# (a) Three assets, eight daily observations. Nothing structural is asked of
#     this one — it exists purely as a full-precision known answer for the
#     estimator itself.
FIXTURE_A = [
    [0.0120, -0.0080, 0.0210, -0.0150, 0.0040, 0.0180, -0.0110, 0.0070],
    [0.0035, 0.0090, -0.0025, 0.0110, -0.0060, 0.0015, 0.0075, -0.0040],
    [-0.0050, 0.0020, 0.0130, 0.0060, -0.0090, 0.0045, 0.0025, 0.0100],
]

# (b) Four assets with a DELIBERATELY NON-UNIFORM correlation structure (Rev 4
#     F8): a uniform-ρ fixture passes identically even when an estimator is
#     fully degenerate, so it cannot detect the failure mode that matters. The
#     asserted structure is: one pair ρ >= +0.6, one pair ρ <= -0.3, one pair
#     |ρ| <= 0.25.
#     The series are also deliberately MODERATE rather than extreme: an earlier
#     candidate met the three bands with pairs at ±0.99, which is nearly
#     rank-deficient and would have made the fixture agree with a degenerate
#     estimator for the wrong reason. This one has condition number ~40.
FIXTURE_B = [
    [0.0120, -0.0080, 0.0210, -0.0150, 0.0040, 0.0180, -0.0110, 0.0070],
    [0.0120, -0.0030, 0.0160, -0.0050, 0.0140, 0.0100, 0.0100, 0.0150],
    [-0.0160, 0.0160, -0.0030, 0.0150, -0.0180, 0.0130, 0.0090, -0.0010],
    [0.0080, -0.0080, 0.0120, 0.0130, 0.0100, -0.0130, -0.0140, -0.0160],
]
FIXTURE_B_WEIGHTS = [0.4, 0.3, 0.2, 0.1]

# (d) Three risky legs plus a benchmark leg (the SPY stand-in, last row). The
#     benchmark carries weight exactly 0.0 — it is an estimation leg, never a
#     holding.
#     Chosen so the fixture is REPRESENTATIVE, not just valid: beta ≈ 1.23 and
#     R² ≈ 0.72, i.e. a book the market mostly but not entirely explains. A
#     fixture at R² ≈ 0.99 would leave residual variance at floating dust and
#     would exercise se_beta only on its clamp path.
FIXTURE_D = [
    [-0.0050, 0.0200, -0.0150, -0.0200, 0.0190, 0.0070, -0.0170, -0.0060],
    [0.0000, 0.0010, -0.0130, -0.0080, 0.0020, 0.0010, 0.0170, 0.0120],
    [-0.0020, 0.0190, 0.0030, -0.0090, 0.0070, 0.0170, 0.0200, 0.0070],
    [-0.0030, 0.0070, -0.0140, -0.0030, 0.0060, 0.0060, 0.0010, 0.0000],
]
FIXTURE_D_WEIGHTS = [0.5, 0.3, 0.2, 0.0]
FIXTURE_D_B_INDEX = 3
FIXTURE_D_T_EFF = 62.897   # Rev 4's T ≥ 126 floor value, so se_beta is pinned at the floor


def _fmt_matrix(m: np.ndarray) -> str:
    rows = [
        "    [" + ", ".join(repr(float(v)) for v in row) + "],"
        for row in m
    ]
    return "[\n" + "\n".join(rows) + "\n]"


def _fmt_vector(v: np.ndarray) -> str:
    return "[" + ", ".join(repr(float(x)) for x in v) + "]"


def emit() -> int:
    provenance = (
        f"# Generated by backend/scripts/cr136_generate_fixtures.py on "
        f"{date.today().isoformat()}, numpy {np.__version__}, lambda={LAM}.\n"
        f"# Independent numpy implementation — the shipped estimator is NOT "
        f"imported here (Rev 4 estimator pin 7)."
    )
    print(provenance)
    print()

    # (a)
    cov_a = ewma_cov(np.array(FIXTURE_A))
    print("# ── Fixture (a): EWMA known answer, N=3, T=8 ──")
    print("FIXTURE_A_COV = " + _fmt_matrix(cov_a))
    print()

    # (b) — assert the non-uniform structure BEFORE emitting anything.
    cov_b = ewma_cov(np.array(FIXTURE_B))
    rho = corr_from_cov(cov_b)
    n = rho.shape[0]
    pairs = [(i, j, float(rho[i][j])) for i in range(n) for j in range(i + 1, n)]
    has_high = any(r >= 0.6 for _, _, r in pairs)
    has_neg = any(r <= -0.3 for _, _, r in pairs)
    has_flat = any(abs(r) <= 0.25 for _, _, r in pairs)
    if not (has_high and has_neg and has_flat):
        print("ABORT — fixture (b) correlation structure is not non-uniform (Rev 4 F8).",
              file=sys.stderr)
        for i, j, r in pairs:
            print(f"  rho({i},{j}) = {r:+.4f}", file=sys.stderr)
        print(f"  need >= +0.6: {has_high}; need <= -0.3: {has_neg}; "
              f"need |rho| <= 0.25: {has_flat}", file=sys.stderr)
        return 1

    w_b = np.array(FIXTURE_B_WEIGHTS, dtype=float)
    print("# ── Fixture (b): non-uniform correlation structure (Rev 4 F8), N=4, T=8 ──")
    print("# Pairwise EWMA correlations of the emitted matrix:")
    for i, j, r in pairs:
        print(f"#   rho({i},{j}) = {r:+.6f}")
    print("# Structure asserted before emission: one pair >= +0.6, one <= -0.3, "
          "one |rho| <= 0.25.")
    print("FIXTURE_B_COV = " + _fmt_matrix(cov_b))
    print(f"FIXTURE_B_SIGMA = {sigma_p(w_b, cov_b)!r}")
    print(f"FIXTURE_B_DR2 = {dr2(w_b, cov_b)!r}")
    print("FIXTURE_B_CONTRIBUTIONS = " + _fmt_vector(euler(w_b, cov_b)))
    print("FIXTURE_B_MCR = " + _fmt_vector(mcr(w_b, cov_b)))
    print()

    # (d)
    cov_d = ewma_cov(np.array(FIXTURE_D))
    w_d = np.array(FIXTURE_D_WEIGHTS, dtype=float)
    beta, r2, var_p, var_b = beta_r2(w_d, cov_d, FIXTURE_D_B_INDEX)
    te = tracking_error(float(np.sqrt(var_p)), float(np.sqrt(var_b)), beta)
    seb = se_beta(var_p, var_b, beta, FIXTURE_D_T_EFF)
    print("# ── Fixture (d): joint matrix, 3 risky + benchmark leg at w=0.0, N=4, T=8 ──")
    print("FIXTURE_D_COV = " + _fmt_matrix(cov_d))
    print(f"FIXTURE_D_BETA = {beta!r}")
    print(f"FIXTURE_D_R2 = {r2!r}")
    print(f"FIXTURE_D_VAR_P = {var_p!r}")
    print(f"FIXTURE_D_VAR_B = {var_b!r}")
    print(f"FIXTURE_D_TE_DAILY = {te!r}")
    print(f"FIXTURE_D_SE_BETA = {seb!r}   # at t_eff = {FIXTURE_D_T_EFF}")
    print()

    print("# ── t_eff cross-check (direct sum, independent of the module) ──")
    for lam in (0.94, 0.97, 0.98):
        print(f"#   t_eff({lam}, 5000) = {t_eff(lam, 5000):.6f}")
    print(f"#   t_eff(0.97, 126) = {t_eff(0.97, 126):.6f}")
    print(f"#   t_eff(0.97, 252) = {t_eff(0.97, 252):.6f}")
    return 0


# ── Scenario-episode verification (dev-only network) ────────────────────────

# Rev 4 Tier-1 scenario panel. The pinned constants live in M04's constants
# module; this check exists so they are never taken on anyone's word.
_EPISODES = [
    ("covid_2020", date(2020, 2, 19), date(2020, 3, 23), -0.339),
    ("drawdown_2022", date(2022, 1, 3), date(2022, 10, 12), -0.254),
]
_TOLERANCE_PP = 0.5


def verify_scenarios() -> int:
    """Check the pinned episode returns against SPY on the PRICE basis.

    Measured 2026-08-02, and the reason this does not use the adjusted series
    the module doc first specified: on dividend-adjusted (total-return) closes
    the 2022 episode reads −24.50% against a pinned −25.40%, a 0.90pp miss that
    blows the 0.5pp tolerance — and it misses for a reason that has nothing to
    do with the pin being wrong. Rev 4's figures are S&P 500 PRICE-index
    returns; over a nine-month episode a total-return series runs ahead of a
    price series by roughly the dividend yield. The COVID episode, five weeks
    long, agrees on either basis (0.18pp adjusted).

    Price basis is also the one the product needs: the sim pays no dividends,
    so a total-return episode constant would tell the user their book would
    have lost less than a price-only book actually would. Both bases are
    printed, and only the price basis gates.
    """
    import yfinance as yf

    df = yf.Ticker("SPY").history(
        start="2020-01-01", end="2022-12-31", interval="1d", auto_adjust=False,
    )
    if df is None or df.empty:
        print("could not fetch SPY history", file=sys.stderr)
        return 2
    price = {ts.date(): float(row["Close"]) for ts, row in df.iterrows()}
    adj_col = "Adj Close" if "Adj Close" in df.columns else "Close"
    adjusted = {ts.date(): float(row[adj_col]) for ts, row in df.iterrows()}
    days = sorted(price)

    def on_or_before(target: date) -> date:
        candidates = [d for d in days if d <= target]
        if not candidates:
            raise SystemExit(f"no SPY bar on or before {target}")
        return candidates[-1]

    worst = 0.0
    for name, start, end, pinned in _EPISODES:
        d0, d1 = on_or_before(start), on_or_before(end)
        measured = price[d1] / price[d0] - 1.0
        total_return = adjusted[d1] / adjusted[d0] - 1.0
        diff_pp = abs(measured - pinned) * 100.0
        worst = max(worst, diff_pp)
        print(
            f"{name}: {d0} -> {d1}  price {measured * 100:+.2f}%  "
            f"pinned {pinned * 100:+.2f}%  diff {diff_pp:.2f}pp  "
            f"{'OK' if diff_pp <= _TOLERANCE_PP else 'OUT OF TOLERANCE'}"
            f"   (total-return basis, not gating: {total_return * 100:+.2f}%)"
        )
    if worst > _TOLERANCE_PP:
        print(
            f"FAIL — worst deviation {worst:.2f}pp exceeds {_TOLERANCE_PP}pp on "
            f"the price basis. Re-pin deliberately; do not widen the tolerance "
            f"and do not switch basis to make it pass.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-scenarios", action="store_true",
        help="fetch SPY and check the pinned episode returns (dev-only network)",
    )
    ns = parser.parse_args()
    if ns.verify_scenarios:
        return verify_scenarios()
    return emit()


if __name__ == "__main__":
    raise SystemExit(main())
