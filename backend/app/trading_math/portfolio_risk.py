"""EWMA portfolio risk estimator core (CR136 M02) — one weighted covariance matrix (λ=0.97, weighted-demeaned, population-style) and every second-moment metric Rev 4 pins derived from it. Stdlib-only; no app imports; callers gate sufficiency.

A new module beside `portfolio_stats.py` rather than an extension of it, because
the two obey opposite conventions and mixing them in one file is exactly the
silent-misuse class CR040 exists to prevent: `portfolio_stats` is sample-style
(n−1), rounds for BOK display, and returns `None` on invalid input; this module
is population-style weighted, returns unrounded floats, and **raises**.

Why every metric here is a second moment: for an asset at 20% annualised
volatility the standard error of the estimated *mean return* is 40pp at three
months and still 8.9pp at five years, while the SE of the estimated *volatility*
is 1.77pp and 0.40pp over the same horizons. Mean returns are not estimable at
any horizon a retail user will ever have — so Sharpe, Sortino, Treynor, alpha
and the information ratio are permanently out of scope, and everything in here
is estimable from months of data.

There is deliberately **no Ledoit–Wolf shrinkage and no shrinkage of any kind**
(Rev 4 estimator pin 1). It was removed on measurement, not taste: LW's
constant-correlation target divides by zero on a cash row, and on a twin-pair
book it suppressed the correlated-cluster alarm this feature exists to raise
(fired in 89.0% of plain windows vs 30.1% shrunk). Shrinkage is the remedy for
inverting Σ; nothing here inverts it.

Errors are raised, never returned as `None` or NaN. A structurally invalid input
is a caller bug, and CR136's whole uncertainty contract rests on `null` meaning
exactly one thing — "not enough data" — so a second null meaning "the math
broke" would make the contract unenforceable. Sufficiency gating happens in the
caller (M04), before these functions are reached.
"""

from __future__ import annotations

import math

EWMA_LAMBDA = 0.97            # Rev 4 estimator pin 1 — RiskMetrics *investing* factor; 0.94 is the 1-day-VaR trading factor and discards most of the disclosed window (ESS 32 vs 66)
TRADING_DAYS_PER_YEAR = 252   # Rev 4 estimator pin 6 — trading-day series only; calendar-day padding understates σ ~15% (√(252/365))
TRADING_DAYS_PER_MONTH = 21   # Rev 4 F13 — one month is 21 trading days
BAD_MONTH_Z = 1.645           # Rev 4 F13 — one-sided Gaussian z for a 1-in-20 month

# Symmetry tolerance for a supplied covariance matrix. Mirrors the check in
# `portfolio_stats.py`, but raises instead of returning None.
_SYMMETRY_TOL = 1e-9

# Floating dust below which a negative quadratic form is treated as zero rather
# than as a non-PSD input. Anything larger is a genuinely wrong matrix and must
# not silently produce a number.
_PSD_DUST = 1e-12


# ── Internals ───────────────────────────────────────────────────────────────


def _finite(value: float, what: str) -> float:
    """Reject NaN and the infinities at the door.

    Every guard in this module is a `<`, `>` or `<=` comparison, and every one
    of those is False against NaN — so without an explicit screen a single
    non-finite input passes validation untouched and every metric downstream
    returns a NaN that serialises to the same `null` the uncertainty contract
    uses to mean "not enough data". Two meanings for one wire value is exactly
    what makes the contract unenforceable.
    """
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{what} must be finite, got {value!r}")
    return number


def _ewma_weights(lam: float, t: int) -> list[float]:
    """Normalized truncated EWMA weights, newest last.

    Column `j` of a T-column series has age `T-1-j`, so its unnormalized weight
    is `lam ** (T-1-j)`. Normalizing over the *available* window (rather than
    against the infinite-sum denominator) is what makes the weights sum to 1 on
    a short series.
    """
    if not 0.0 < lam < 1.0:
        raise ValueError(f"lam must be in (0, 1), got {lam}")
    if t < 1:
        raise ValueError(f"t must be >= 1, got {t}")
    unnormalized = [lam ** (t - 1 - j) for j in range(t)]
    total = math.fsum(unnormalized)
    return [u / total for u in unnormalized]


def _validate(w: list[float], cov: list[list[float]]) -> int:
    """Shared shape, finiteness and symmetry guard. Returns n."""
    n = len(cov)
    if n == 0:
        raise ValueError("cov must be non-empty")
    if len(w) != n:
        raise ValueError(f"len(w)={len(w)} does not match len(cov)={n}")
    for i, row in enumerate(cov):
        if len(row) != n:
            raise ValueError(f"cov row {i} has length {len(row)}, expected {n}")
        for j, value in enumerate(row):
            _finite(value, f"cov[{i}][{j}]")
    for i, weight in enumerate(w):
        _finite(weight, f"w[{i}]")
    for i in range(n):
        for j in range(i + 1, n):
            if abs(cov[i][j] - cov[j][i]) > _SYMMETRY_TOL:
                raise ValueError(
                    f"cov is not symmetric at ({i},{j}): "
                    f"{cov[i][j]} vs {cov[j][i]}"
                )
    return n


def _sigma_w(w: list[float], cov: list[list[float]]) -> list[float]:
    """`Σw` — the vector whose i-th entry is `Σ_j cov[i][j] · w_j`."""
    return [math.fsum(cov[i][j] * w[j] for j in range(len(w))) for i in range(len(w))]


def _variance(w: list[float], cov: list[list[float]]) -> float:
    """`wᵀΣw`, with the PSD-dust clamp applied."""
    sigma_w = _sigma_w(w, cov)
    var = math.fsum(w[i] * sigma_w[i] for i in range(len(w)))
    if var < 0.0:
        if var >= -_PSD_DUST:
            return 0.0
        raise ValueError(f"wᵀΣw is negative ({var}) — cov is not positive semi-definite")
    return var


# ── Estimator ───────────────────────────────────────────────────────────────


def ewma_covariance(
    returns: list[list[float]], lam: float = EWMA_LAMBDA,
) -> list[list[float]]:
    """Weighted-demeaned, population-style EWMA covariance. Rows = assets,
    columns = time, **newest last**.

    Population-style: no degrees-of-freedom correction. There is no `1/(1−Σw²)`
    factor — the known-answer fixtures define exactness, and a dof correction
    under exponential weights has no single agreed form to be exact against.

    λ=0.97 rather than an equal-weight window because an equal-weight window
    produces a roll-off echo: measured, it drops 2.9pp discontinuously on the
    day an old shock leaves the window — 50× the median daily change — so the
    number moves for a reason that has nothing to do with the portfolio. EWMA
    responds *at* the event instead (half-life 22.8 days, exit-day change
    0.03pp). The measured cost, disclosed rather than hidden: EWMA's effective
    sample is ~66 days, which makes single-report detection of a correlated
    cluster 82.1% instead of an equal-weight window's 89.0%.

    `T = 1` returns the all-zero matrix — that is the formula's own output for a
    single observation, not a special case. The T ≥ 126 sufficiency floor is the
    caller's (M04).
    """
    if not returns:
        raise ValueError("returns must be non-empty")
    t = len(returns[0])
    if t == 0:
        raise ValueError("returns rows must be non-empty")
    for a, row in enumerate(returns):
        if len(row) != t:
            raise ValueError(
                f"returns is ragged: row {a} has length {len(row)}, expected {t}"
            )
        for j, value in enumerate(row):
            _finite(value, f"returns[{a}][{j}]")

    weights = _ewma_weights(lam, t)
    n = len(returns)
    means = [math.fsum(weights[j] * returns[a][j] for j in range(t)) for a in range(n)]
    deviations = [
        [returns[a][j] - means[a] for j in range(t)] for a in range(n)
    ]

    cov = [[0.0] * n for _ in range(n)]
    for a in range(n):
        for b in range(a, n):
            value = math.fsum(
                weights[j] * deviations[a][j] * deviations[b][j] for j in range(t)
            )
            cov[a][b] = value
            cov[b][a] = value
    return cov


def t_eff(lam: float, t: int) -> float:
    """Effective sample size of the truncated EWMA weights: `1 / Σ_j w_j²`.

    Published wherever a standard error is published. Rev 4 pins this rather
    than the raw observation count because the equal-weight SE formula
    `σ/√(2T)` understates the true sampling error under EWMA by ~27% (measured
    1.72pp true vs 1.26pp naive at σ=20%) — reporting a confidence tighter than
    the data supports is exactly the failure the uncertainty contract exists to
    prevent.

    Deliberately the direct sum, not the closed form
    `(1+λ)/(1−λ) · (1−λᵗ)/(1+λᵗ)`; the closed form is the tests' independent
    check, and a formula that checks itself checks nothing.
    """
    weights = _ewma_weights(lam, t)
    return 1.0 / math.fsum(wj * wj for wj in weights)


# ── Whole-portfolio metrics ─────────────────────────────────────────────────


def portfolio_sigma(w: list[float], cov: list[list[float]]) -> float:
    """`√(wᵀΣw)`. Daily when `cov` is daily — annualize with `annualize_vol`."""
    _validate(w, cov)
    return math.sqrt(_variance(w, cov))


def euler_contributions(w: list[float], cov: list[list[float]]) -> list[float]:
    """Each holding's share of total portfolio risk: `wᵢ(Σw)ᵢ / σₚ²`.

    The headline output of the whole feature — the number that says "NVDA is
    62% of your risk while holding 30% of your money", which is the fact naive
    weight-counting cannot see. Sums to exactly 1.0 by Euler's theorem on the
    homogeneous-degree-1 function σₚ(w); a zero row (cash, or the benchmark
    estimation leg) contributes exactly 0.0, structurally, by bilinearity.
    """
    _validate(w, cov)
    var = _variance(w, cov)
    if var == 0.0:
        raise ValueError("portfolio variance is zero — risk shares are undefined")
    sigma_w = _sigma_w(w, cov)
    return [w[i] * sigma_w[i] / var for i in range(len(w))]


def mcr(w: list[float], cov: list[list[float]]) -> list[float]:
    """Marginal contribution to risk: `(Σw)ᵢ / σₚ`.

    The honest per-dollar quantity (Rev 4 F3). It exists because the intuitive
    sentence "trim your largest risk contributor first" is mathematically false:
    on the counterexample book that motivated this, the largest *contributor*
    was 2.23× LESS effective per dollar trimmed than another holding. Risk share
    answers "who owns the risk"; MCR answers "what happens if I trim a dollar",
    and only MCR may be used for the second question.

    Identity: `Σᵢ wᵢ · mcrᵢ = σₚ`.
    """
    _validate(w, cov)
    var = _variance(w, cov)
    if var == 0.0:
        raise ValueError("portfolio variance is zero — MCR is undefined")
    sigma_p = math.sqrt(var)
    sigma_w = _sigma_w(w, cov)
    return [sw / sigma_p for sw in sigma_w]


def dr_squared(w: list[float], cov: list[list[float]]) -> float:
    """Squared diversification ratio: `((Σᵢ wᵢσᵢ) / σₚ)²` (Choueifaty &
    Coignard 2008), read as "effective independent bets".

    Replaces naive HHI as the diversification measure because HHI is
    correlation-blind and overstates diversification by up to 8.2× at N=10 and
    24.2× at N=30 — ten mega-caps at ρ=0.8 read effective-N 10.0 by weight and
    DR² 1.22 here.

    It is not a diagnosis on its own: DR² penalises volatility imbalance as well
    as correlation, so a correctly-diversified 60/40 SPY+AGG book (ρ=0.154)
    reads 1.278, almost the same as a triple-overlap SPY+QQQ+AAPL book's 1.261.
    Risk contributions are what disambiguate the cause, which is why no surface
    is allowed to present DR² alone.

    Cash-invariant with the appended zero row: both numerator and σₚ scale by
    the invested fraction.
    """
    _validate(w, cov)
    var = _variance(w, cov)
    if var == 0.0:
        raise ValueError("portfolio variance is zero — DR² is undefined")
    weighted_vol = math.fsum(
        w[i] * math.sqrt(cov[i][i]) for i in range(len(w))
    )
    dr = weighted_vol / math.sqrt(var)
    return dr * dr


def beta_r2(
    w: list[float], cov: list[list[float]], b_index: int,
) -> tuple[float, float]:
    """`(beta, r2)` against the benchmark leg held inside the same joint matrix.

    Joint-matrix form, because Rev 4 defines beta as `Cov_w(p,b)/Var_w(b)`
    *from the same Σ*: the benchmark is estimated as one more leg of the single
    EWMA matrix, so no separate portfolio return series is ever constructed and
    the two sides cannot be estimated over different windows.

    The benchmark leg must carry weight exactly 0.0 — it is an estimation leg,
    never a holding, and a non-zero weight there would fold the benchmark into
    the portfolio it is being compared with.

    R² < 0.20 is what sets `low_explanatory_power` upstream; beta on a book the
    market barely explains is a number without a meaning, and the caller is
    required to say so.
    """
    n = _validate(w, cov)
    if not 0 <= b_index < n:
        raise ValueError(f"b_index {b_index} out of range for n={n}")
    if w[b_index] != 0.0:
        raise ValueError(
            f"w[{b_index}] must be exactly 0.0 (the benchmark is an estimation "
            f"leg, not a holding), got {w[b_index]}"
        )
    var_b = cov[b_index][b_index]
    if var_b <= 0.0:
        raise ValueError("benchmark variance is zero — beta is undefined")
    var_p = _variance(w, cov)
    if var_p == 0.0:
        raise ValueError("portfolio variance is zero — beta/R² are undefined")
    cov_pb = math.fsum(w[i] * cov[i][b_index] for i in range(n))
    beta = cov_pb / var_b
    r2 = (cov_pb * cov_pb) / (var_p * var_b)
    return beta, r2


def tracking_error(sigma_p: float, sigma_b: float, beta: float) -> float:
    """`√(σₚ² + σ_b² − 2βσ_b²)` — the book's volatility *relative to* the
    benchmark, which is the number an institutional risk report leads with.

    Scale-consistent: both inputs daily gives a daily TE, both annualized gives
    an annualized one. A derived quantity, so it publishes no standard error of
    its own — its three components each carry theirs.
    """
    sigma_p = _finite(sigma_p, "sigma_p")
    sigma_b = _finite(sigma_b, "sigma_b")
    beta = _finite(beta, "beta")
    radicand = sigma_p * sigma_p + sigma_b * sigma_b - 2.0 * beta * sigma_b * sigma_b
    if radicand < 0.0:
        if radicand >= -_PSD_DUST:
            return 0.0
        raise ValueError(
            f"tracking-error radicand is negative ({radicand}) — "
            f"σₚ={sigma_p}, σ_b={sigma_b}, β={beta} are mutually inconsistent"
        )
    return math.sqrt(radicand)


def hhi_effective_n(weights: list[float]) -> float:
    """`1 / Σvᵢ²` — the weight-based effective holding count.

    Accounting, not estimation: it publishes no standard error and gates on no
    sufficiency floor. It is also correlation-blind, which is why it is shown
    beside DR² and never instead of it.

    Precondition, documented rather than enforced: `weights` are the caller's
    invested-sleeve weights summing to 1. Total-value weights are the wrong
    input — measured, total-value effective-N is non-monotone in cash (2.63 →
    3.53 → 3.37 → 2.38 across 0/20/40/60% cash, peaking at 27.5%), so a user
    adding cash would watch "diversification" rise and then fall for no reason
    connected to their holdings.
    """
    if not weights:
        raise ValueError("weights must be non-empty")
    for i, v in enumerate(weights):
        _finite(v, f"weights[{i}]")
    hhi = math.fsum(v * v for v in weights)
    if hhi <= 0.0:
        raise ValueError("weights are all zero — effective N is undefined")
    return 1.0 / hhi


def bad_month(sigma_p_ann: float) -> float:
    """`1.645 · σₚ · √(21/252)` — the plain-language "typical bad month".

    Fractions in, fraction out. Phrased downstream as historical dispersion
    ("a 1-in-20 bad month over the window measured has been about −X%"), never
    as a forecast, and always with the Gaussian tail understatement disclosed.
    """
    sigma_p_ann = _finite(sigma_p_ann, "sigma_p_ann")
    return BAD_MONTH_Z * sigma_p_ann * math.sqrt(
        TRADING_DAYS_PER_MONTH / TRADING_DAYS_PER_YEAR
    )


def scenario_replay(beta: float, episode_return: float) -> float:
    """`beta × episode_return` — what today's book would have done in a named
    past episode, given only its market sensitivity.

    A backcast what-if, never a prediction: it is rendered only when the beta
    block is sufficient, always alongside the R² share, and the episode
    constants themselves live in the caller's constants module so they can be
    re-verified against the live benchmark series.
    """
    return _finite(beta, "beta") * _finite(episode_return, "episode_return")


def se_sigma(sigma_hat: float, t_eff: float) -> float:
    """`σ̂ / √(2·T_eff)` — the sampling SE of the volatility estimate.

    Never `σ̂/√(2T)`. Under EWMA the equal-weight formula understates the true
    sampling SE by ~27%, and this function takes no raw observation count at
    all, so the wrong formula cannot be reached by passing the wrong argument.
    (The parameter deliberately shadows the module's `t_eff` function inside
    this body: the pinned signature is what M04 calls by keyword.)
    """
    sigma_hat = _finite(sigma_hat, "sigma_hat")
    t_eff = _finite(t_eff, "t_eff")
    if t_eff <= 0.0:
        raise ValueError(f"t_eff must be > 0, got {t_eff}")
    return sigma_hat / math.sqrt(2.0 * t_eff)


def se_beta(
    var_p: float, var_b: float, beta: float, t_eff: float,
) -> float:
    """`√( max(0, Var_w(p) − β²Var_w(b)) / (T_eff · Var_w(b)) )`.

    Algebraically Rev 4's WLS form `SE(β̂) = (σ_ε,w/σ_b,w)/√T_eff`, with the
    weighted residual variance written out. The `max(0, ·)` clamp covers
    floating dust as R² approaches 1 — a book that IS the benchmark has zero
    residual variance and must return 0.0, not raise on a −1e-19 radicand.

    R3's hysteresis band is ±0.6·SE(β̂), so this is load-bearing for whether the
    market-sensitivity rule fires; it is not decoration.
    """
    var_p = _finite(var_p, "var_p")
    var_b = _finite(var_b, "var_b")
    beta = _finite(beta, "beta")
    t_eff = _finite(t_eff, "t_eff")
    if var_b <= 0.0:
        raise ValueError(f"var_b must be > 0, got {var_b}")
    if t_eff <= 0.0:
        raise ValueError(f"t_eff must be > 0, got {t_eff}")
    residual_var = var_p - beta * beta * var_b
    if residual_var < 0.0:
        # Bounded like the module's two sibling clamps, not unbounded. In real
        # use var_p, var_b and beta all come from the same Σ, so the residual is
        # non-negative by Cauchy-Schwarz and only floating error can push it
        # under; a residual negative by more than dust means the caller mixed
        # inputs from different matrices, and returning a confident SE of 0.0
        # for that is precisely the silent-wrong-number path CR040 forbids.
        if residual_var >= -_PSD_DUST * max(1.0, abs(var_p)):
            residual_var = 0.0
        else:
            raise ValueError(
                f"residual variance is negative ({residual_var}) — var_p={var_p}, "
                f"var_b={var_b}, beta={beta} are mutually inconsistent"
            )
    return math.sqrt(residual_var / (t_eff * var_b))


def append_zero_row(cov: list[list[float]]) -> list[list[float]]:
    """Return a fresh `(n+1)×(n+1)` matrix with `cov` in the top-left block and
    an exact-zero last row and column — the cash leg.

    Cash is appended AFTER estimation rather than included in it because the
    estimator would otherwise have to handle a constant series, and because
    Rev 4's cash convention is exact: a zero row contributes exactly 0.0 to
    every risk share, scales σₚ and β by exactly (1−c), and leaves DR², risk
    shares and R² exactly invariant. The input is not mutated.
    """
    n = len(cov)
    if n == 0:
        raise ValueError(
            "cov must be non-empty — an empty matrix would become a one-leg "
            "riskless portfolio rather than an error"
        )
    out = [[0.0] * (n + 1) for _ in range(n + 1)]
    for i in range(n):
        row = cov[i]
        if len(row) != n:
            raise ValueError(f"cov row {i} has length {len(row)}, expected {n}")
        for j in range(n):
            out[i][j] = row[j]
    return out


def annualize_vol(sigma_daily: float) -> float:
    """`σ_daily · √252` — the one annualisation helper; everything else here
    works in daily units.

    The IID assumption behind √252 is disclosed in the report rather than
    hidden: the same serial-correlation objection that makes Sharpe inference
    hard applies to this scaling too.
    """
    return _finite(sigma_daily, "sigma_daily") * math.sqrt(TRADING_DAYS_PER_YEAR)
