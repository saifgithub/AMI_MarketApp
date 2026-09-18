# P01 chart pack — "AI predicts the stock" vs "always predict up"

Six figures for [`../SCRIPT.md`](../SCRIPT.md), drawn in the AMI style by
[`make_charts.py`](make_charts.py).

Regenerate from the RES008 root:

```
.venv/bin/python P_prior_work/P01_ml_predicts_direction/charts/make_charts.py
```

## Where the numbers come from — and why this pack is different

Every other episode's chart pack reads a machine-readable `results.json` at run time. This
claim predates that convention: its source study published its numbers only as markdown
tables, and the `results.db` behind them was never copied into this checkout.

So the numbers are transcribed once into [`source_numbers.json`](source_numbers.json), and
`make_charts.py` **verifies every entry before it draws anything**. For each entry it opens
`source_file`, reads `source_line`, and asserts the entry's `value` string appears verbatim on
that line. Any mismatch prints `SOURCE VERIFICATION FAILED` and exits 1 — no figures are
written. That check is what stands in for a results file here.

Because the check compares literal strings, values are stored exactly as the source writes
them — including the backticks around feature names. `_feature_list()` strips those for
display only.

If the source file is edited and line numbers shift, the script fails loudly rather than
drawing stale numbers. Fix `source_line`, do not loosen the check.

## The figures

| File | Beat | What it shows | Source section |
|:--|:--|:--|:--|
| `01_auc_by_horizon.png` | 1, 4 | Mean AUC climbing 0.5107 (1d) → 0.5528 (20d), against the 0.50 coin-flip line | Headline results — daily (post-fix, authoritative) |
| `02_controls.png` | 5 | The two negative controls that make the result trustworthy: shuffled labels 0.4969, the real 20-day result 0.5528, injected signal 0.9497. Bars read scrambled → real → injected, and the subtitle follows that order | Independent leakage audit · Model shootout |
| `03_accuracy_vs_baseline.png` | 5 | Model accuracy ~54% against the always-up baseline ~63%, with the "edge negative in 30 of 32 cells" callout | The central finding |
| `04_cross_sectional.png` | 6 | Single-ticker AUC 0.5528 against cross-sectional AUC 0.5055 — strip the drift, the signal goes | Cross-sectional ranking test |
| `05_top_features.png` | 6 | The 20-day model's top features, with the five that also top the cross-sectional model highlighted — all market-wide | Most important features (20-day horizon, by gain) |
| `06_intraday_noise.png` | 7 | Daily 0.5528 against the intraday mean 0.5081, with 21/42 cells positive and binomial p = 1.000 | Headline results — intraday |

## Conventions this pack follows

- No creator, channel or platform is named anywhere in a figure.
- 42 intraday cells is the source's own count, not a 4 × 6 × 3 grid — horizons shorter than the
  bar size do not exist, so the grid is ragged. Chart 06's subtitle states the ranges without
  implying a multiplication.
- "Edge" throughout means accuracy minus the always-up baseline's accuracy. It is not profit, and
  no figure or caption presents it as profit.
