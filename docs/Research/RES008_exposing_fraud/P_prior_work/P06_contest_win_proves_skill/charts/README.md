# P06 chart pack — what a contest win can and cannot tell you

Two figures for [`../SCRIPT.md`](../SCRIPT.md), drawn in the AMI style by
[`make_charts.py`](make_charts.py).

Regenerate from the RES008 root:

```
.venv/bin/python P_prior_work/P06_contest_win_proves_skill/charts/make_charts.py
```

Both figures read `RES001_finding_the_edge/03_volatility_regime_sizing/out/results.json` at run
time. That file is git-ignored, so the script prints `skipped …` and exits 0 when it is absent
rather than drawing stale numbers.

## The figures

| File | Beat | What it shows | Source keys |
|:--|:--|:--|:--|
| `01_crowd_of_dots.png` | 1, 4 | 300 zero-skill entrants, one month each — the maximum ringed. Illustrative mechanism only: one random seed, spread set by the test's own required volatility for 300 entrants | `E.by_n["300"].required_monthly_vol` (spread only) |
| `02_entrant_count_vs_volatility.png` | 5 | The monthly volatility at which +100% is the *expected maximum* under zero skill: 50 → 32.7% (5.98× SPY), 100 → 29.0% (5.30×), 300 → 25.0% (4.58×), 500 → 23.6% (4.32×), against SPY's own 5.5% | `E.spy_monthly_vol`, `E.by_n[N].required_monthly_vol`, `E.by_n[N].leverage_vs_spy` |

## What these figures must not be made to say

The source section is a **conditional** whose antecedents were never verified: it assumes a field of
a given size and a given entrant volatility, neither of which was measured against any real contest.

- Chart 01 is a mechanism illustration and carries the stamp `ILLUSTRATIVE DRAW — MECHANISM ONLY,
  NOT A MEASURED RESULT`. Do not remove it, and do not relabel the ringed dot as anyone real.
- Neither figure names a contest, a person, an organiser or a year, and neither may be edited to.
- The four volatility multiples hold for those four entrant counts as computed. Do not interpolate
  a figure for another field size, and do not annualise anything.
- Nothing here shows a win *was* luck — only that a headline return does not *require* skill to
  explain. Any caption added later must preserve that distinction.
