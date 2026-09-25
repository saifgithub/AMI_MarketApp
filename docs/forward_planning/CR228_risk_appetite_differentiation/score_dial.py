"""CR228 full-dial scorer — risk_score 1..5, paired on ticker.

Scores the 2026-09-25 re-run against the success target Saiful chose that day
("Test as per recommendation"): the Room recommends more as risk appetite rises,
monotonically from R1 to R5. The criterion is fixed here BEFORE the run, and the
verdict is read by its letter — no re-pooling or re-cutting after the fact.

PASS requires both:
  1. Trend: Page's L test for an ordered alternative (R1 <= R2 <= ... <= R5) on
     per-ticker approve_votes, one-sided p < 0.05. Tickers must be judged in
     every arm (FAILSAFE/INCOMPLETE excluded, per score_pilot.py's reasons).
  2. Monotone means: mean approve_votes never falls from one arm to the next.

approve_votes and not the approve rate, for the reason score_pilot.py gives
(CR214: the binary verdict is a 12-20% coin flip). The approve rate is reported
alongside so the user-visible effect is on the page, but it does not decide.
"""

from __future__ import annotations

import sys
from math import erf, sqrt
from pathlib import Path
from statistics import mean

from score_pilot import classify, load


def page_l(rows: list[list[float]]) -> tuple[float, float]:
    """Page's L with mid-ranks for ties; normal approximation. -> (L, one-sided p)."""
    k = len(rows[0])
    n = len(rows)
    col_rank_sums = [0.0] * k
    for row in rows:
        order = sorted(range(k), key=lambda j: row[j])
        ranks = [0.0] * k
        i = 0
        while i < k:
            j = i
            while j + 1 < k and row[order[j + 1]] == row[order[i]]:
                j += 1
            for m in range(i, j + 1):
                ranks[order[m]] = (i + j) / 2 + 1
            i = j + 1
        for c in range(k):
            col_rank_sums[c] += ranks[c]
    L = sum((c + 1) * col_rank_sums[c] for c in range(k))
    mu = n * k * (k + 1) ** 2 / 4
    var = n * k**2 * (k + 1) * (k**2 - 1) / 144
    z = (L - mu) / sqrt(var)
    p = 0.5 * (1 - erf(z / sqrt(2)))
    return L, p


def main(argv: list[str]) -> int:
    if len(argv) != 6:
        print("usage: score_dial.py <runs_r1.jsonl> ... <runs_r5.jsonl>")
        return 2
    arms = [{t: classify(r) for t, r in load(Path(p)).items()} for p in argv[1:]]
    judged = [{t: c for t, c in a.items() if c[0] in ("APPROVE", "PASS", "REJECT")} for a in arms]
    for i, (a, j) in enumerate(zip(arms, judged), start=1):
        excluded = len(a) - len(j)
        print(f"R{i}: records={len(a)} judged={len(j)} excluded(failsafe/incomplete)={excluded}")

    common = sorted(set.intersection(*(set(j) for j in judged)))
    common = [t for t in common if all(j[t][1] is not None for j in judged)]
    n = len(common)
    print(f"\npaired tickers judged in all five arms: n={n}")
    if n < 2:
        print("VERDICT: CANNOT SCORE — too few paired tickers")
        return 1

    means = [mean(j[t][1] for t in common) for j in judged]
    rates = [sum(1 for t in common if j[t][0] == "APPROVE") for j in judged]
    for i in range(5):
        print(f"  R{i + 1}: mean approve_votes={means[i]:.2f}  "
              f"approve rate={rates[i]}/{n} ({100 * rates[i] / n:.1f}%)")

    L, p = page_l([[j[t][1] for j in judged] for t in common])
    monotone = all(means[i + 1] >= means[i] for i in range(4))
    print(f"\nPage's L={L:.1f}  one-sided p={p:.4f}  (criterion 1: p < 0.05)")
    print(f"means non-decreasing R1->R5: {monotone}  (criterion 2)")
    ok = p < 0.05 and monotone
    print(f"VERDICT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
