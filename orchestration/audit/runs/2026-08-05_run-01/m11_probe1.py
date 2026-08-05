"""M11 r1 audit probe 1 — (a) reproduce the builder's numpy-vs-trading_math
calibration claim, (b) measure the _joined_returns vs engine _join order gap."""
import math
import random
import sys
from datetime import date, timedelta

import numpy as np

sys.path.insert(0, ".")

from scripts.cr136_live_crosscheck import (  # noqa: E402
    ewma_covariance as np_cov,
    _joined_returns,
    _MAX_RETURNS,
)
from app.trading_math.portfolio_risk import ewma_covariance as engine_cov  # noqa: E402

# ── (a) calibration: 4 assets × 300 returns ────────────────────────────────
rng = random.Random(20260805)
R = [[rng.gauss(0.0004, 0.012) for _ in range(300)] for _ in range(4)]
A = np_cov(np.array(R))
B = np.array(engine_cov(R))
print("=== (a) harness numpy vs app.trading_math, 4x300 ===")
print(f"max |cov diff|            : {np.abs(A - B).max():.3e}")
print(f"max relative diff         : {(np.abs(A - B) / np.abs(B)).max():.3e}")

w = np.array([0.4, 0.3, 0.2, 0.1])
sa = math.sqrt(float(w @ A @ w)) * math.sqrt(252)
sb = math.sqrt(float(w @ B @ w)) * math.sqrt(252)
print(f"sigma_ann harness/engine  : {sa:.12f} / {sb:.12f}  diff {abs(sa-sb):.3e}")

# ── (b) join-order divergence ──────────────────────────────────────────────
# A trades every weekday for 3y; B trades every OTHER weekday over the same span.
start = date(2023, 8, 7)
weekdays = []
d = start
while len(weekdays) < 780:
    if d.weekday() < 5:
        weekdays.append(d)
    d += timedelta(days=1)

closes = {
    "A": {d: 100.0 + i * 0.01 for i, d in enumerate(weekdays)},
    "B": {d: 50.0 + i * 0.01 for i, d in enumerate(weekdays[::2])},
}


def engine_join(sets_source, tickers):
    sets = [set(sets_source[t]) for t in tickers]
    common = set.intersection(*sets)
    return sorted(common)[-(_MAX_RETURNS + 1):]


harness_returns, harness_days = _joined_returns(closes, ["A", "B"])
engine_days = engine_join(closes, ["A", "B"])

print()
print("=== (b) join order: engine intersects FULL sets, harness trims first ===")
print(f"A has {len(closes['A'])} dates, B has {len(closes['B'])} dates")
print(f"engine  _join  -> {len(engine_days)} dates, {len(engine_days)-1} returns"
      f"  [{engine_days[0]}..{engine_days[-1]}]")
print(f"harness _joined-> {len(harness_days)} dates, {harness_returns.shape[1]} returns"
      f"  [{harness_days[0]}..{harness_days[-1]}]")
print(f"payload n_observations would be {len(engine_days)-1}; "
      f"harness computes {harness_returns.shape[1]} -> "
      f"{'MISMATCH -> exit 2' if len(engine_days)-1 != harness_returns.shape[1] else 'agree'}")

# ── (b2) the nastier corner: counts coincide, date sets differ ─────────────
# A: full weekdays. B: same weekdays but missing 3 days that are OLDER than
# A's 505-day cutoff, plus 3 extra-old days A lacks -> equal counts, different sets.
closesC = {
    "A": {d: 100.0 + i * 0.01 for i, d in enumerate(weekdays)},
    "B": {d: 50.0 + i * 0.01 for i, d in enumerate(weekdays)},
}
for d in weekdays[:3]:
    del closesC["B"][d]
hr, hd = _joined_returns(closesC, ["A", "B"])
ed = engine_join(closesC, ["A", "B"])
print()
print("=== (b2) same span, B missing 3 of the OLDEST days ===")
print(f"engine  -> {len(ed)-1} returns   harness -> {hr.shape[1]} returns   "
      f"same dates: {sorted(ed) == sorted(hd)}")
