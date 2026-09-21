# R01 — Wunder Fund RNN Challenge (wundernn.io / wunder-challenge.io)

Surveyed 2026-09-20, at Saiful's request ("look at the market data machine learning site
wundernn.io and investigate the ideas that may have been used before"). **Revised 2026-09-20 same
day** after Saiful asked to actually pull the data/docs rather than rely on secondhand summaries —
the first pass below had two factual errors, both caught and corrected here (see "Correction log").
Cross-reference: `../../03_market_ml_landscape_survey.md`, `TRACKER.md` row B14. Primary-source
docs/code saved in `reference_kit/` (`METRIC.md`, `solution.py`, `utils.py` — pulled directly from a
public fork of the starter pack, `github.com/mingda19/wunderfund`).

## What it is

A recruiting competition run by Wunder Fund, a real, operating high-frequency trading firm (running
since 2014, on traditional and crypto markets). Not a product, not a claim aimed at retail — a
talent pipeline dressed as a Kaggle-style contest, currently branded **"Alpha Connectome"**
(Sept 11 – Dec 1, 2026; "Connectome" is this generation's branding, not a description of the data —
see correction log).

**No signup wall on the data itself.** The full starter pack is a public, unauthenticated URL:

```
curl -L https://files.wundernn.io/wnn_connectome_starterpack.tar.gz | tar -xz
```

(mirrors also exist at `files-alternative.wundernn.io` and a Yandex Cloud storage bucket). An
account is only needed to *submit* to the leaderboard/prizes, not to obtain the data for research.

## The data itself (verified from `docs/data_overview.md`, not a secondhand summary)

Two trading instruments, `i0` and `i1`, each represented by a full L11 order book (top 11 bid +
top 11 ask price levels, same depth for volume) plus recent trade price/volume history, plus 8
undisclosed extra columns — **112 float32 features per row, genuinely financial market
microstructure data** (order-book state, not neurobiological — see correction log).

| File | Sequences | Rows | Content |
|---|---:|---:|---|
| `train.parquet` | 10,607 | 212,140,000 | 112 features + targets `t0`, `t1` |
| `valid.parquet` | 1,873 | 37,460,000 | same + `is_scored` scoring mask |

- Each sequence is 20,000 consecutive rows for one `seq_ix` (shuffled — not chronological order
  across sequences); steps 0–98 are warm-up (no prediction required), steps 99–19,999 require two
  finite predictions every row.
- Targets `t0`/`t1` are "two anon indicators of the future price movement of instrument `i0`" —
  **their exact definition (horizon, return type, normalization) is explicitly undisclosed.** This
  is the load-bearing limitation for any reuse: there is no way to know what a prediction of `t0`
  actually corresponds to in real trading terms.
- **Metric is Weighted Pearson correlation (WP), not R²** (a first-pass error — see correction log):
  per sequence, per target, Pearson correlation between clipped `[-2,2]` target/prediction, weighted
  by `|clipped target|` (so large moves dominate the score), averaged over both targets and all
  eligible sequences. Full spec with reference implementation: `reference_kit/METRIC.md`. A block
  (sequence) is excluded entirely from scoring if either target has no sign variation on its scored
  rows.
- Baseline (`reference_kit/solution.py`, `reference_kit/utils.py`): a genuine, runnable 2-layer
  stateful GRU (128 hidden units), ONNX-exported, CPU-only single-thread inference, scoring
  **0.5896 WP** on the full validation set. This is real, inspectable code, not vaporware.
- Rules worth flagging (`docs/rules.md`, `docs/faq.md`): no external data allowed, no sharing
  solutions/models before the competition ends, 5 submissions/day, one account per person, 1 vCPU /
  16GB RAM / 60-minute inference limit / no internet access in the scoring container. Top-8 prize
  winners must hand over full training code, a technical report, and do a live code-review call, and
  **grant Wunder Fund a non-exclusive internal-research license on the winning solution** (not made
  public). Prize pool: $13,600 across 8 places ($5,000 for 1st), confirmed directly from
  `docs/prizes.md` (a first-pass version of this file sourced the figure from a YouTube recap
  instead — see correction log).

## Actual data findings (2026-09-20/21, real `train.parquet`, not docs alone)

Saiful asked to actually pull the data rather than stop at the documentation. Downloaded the full
starter pack (~31GB extracted: `train.parquet` 29GB / 10,607 sequences, `valid.parquet` 5.6GB) to an
external drive (kept, not committed — see "Reproducing this" below) and ran a read-only exploration
(`reference_kit/explore.py`) on a 50-sequence sample (~1M scored-eligible rows):

- **Schema matches `docs/data_overview.md` exactly** — no discrepancy between the documented and
  actual column layout, confirming the earlier corrected description is accurate.
- **`t0`/`t1` are skewed negative, not symmetric.** Mean `t0` ≈ −0.28, mean `t1` ≈ −0.30 (std ≈
  0.94–0.99 each); roughly 58% of rows negative vs. ~19% positive (the rest within 1e-6 of zero).
  A plain forward-return definition over a large, representative sample would be expected to sit
  much closer to symmetric around zero — this asymmetry suggests either a directional bias in the
  sampled period/instrument, or that `t0`/`t1` are constructed quantities (not a raw return) with a
  built-in sign convention. Still undisclosed which.
- **`t0` and `t1` are strongly negatively correlated (r ≈ −0.75).** They are not two independent
  forecasting targets — most of the time they move opposite each other. Consistent with them being
  two sides of one underlying quantity (e.g. a bid-side/ask-side split, or a spread decomposition)
  rather than, say, two different horizons of the same return.
- **No single feature explains much of `t0`.** Best correlation found: `i0_p3` at r ≈ 0.18; the next
  several cluster at r ≈ 0.10–0.14 (mostly `i0` price-level features); nothing else clears 0.10. This
  is consistent with — not in tension with — the public baseline's 0.5896 WP: a real, moderately hard
  prediction task with no simple linear shortcut, matching the "no measurable edge" framing rather
  than undermining it.

**Effect on the verdict below: none — reinforces it.** Having real rows in hand lets us describe
`t0`/`t1` statistically, but the load-bearing gap is unchanged: their exact definition (horizon,
instrument-return mapping, sign convention) is still undisclosed, so there remains no way to convert
a WP score, or this skew/correlation structure, into a "beats buy-and-hold" or "beats a placebo"
statement. The data is real and the task is genuinely hard; neither fact turns a forecasting
correlation contest into a trading-edge claim.

**Reproducing this**: the ~31GB dataset is intentionally *not* committed here (a public,
unauthenticated download, and not something this repo should carry) — re-fetch with the `curl`
command above, then run `python3 reference_kit/explore.py [n_sequences]` with `WUNDER_DATA_DIR` (or
the script's default path) pointed at the extracted `datasets/` folder. The local copy used for this
analysis was kept on external storage (Saiful, 2026-09-20: "keep the data") for any deeper follow-up.

## Our verdict

**NO MEASURABLE-EDGE CLAIM TO TEST — it is a forecasting-accuracy contest, not a trading-edge
claim.** Wunder Fund is not asserting "this beats the market"; it is scoring how well entrants
predict two undisclosed-definition indicators via a correlation metric. There is no backtest, no
position sizing, no cost model, no holding period, and no comparison to buy-and-hold or a placebo
anywhere in the competition's own framing. A WP score is a statement about weighted correlation
quality on autocorrelated microstructure data, not a statement about P&L — and because `t0`/`t1`
are undisclosed, there isn't even a way to translate a leaderboard score into a real-world quantity.

This is the same category error underlying our own **C01** (`NOT SUPPORTED`): a network can score
well on next-step/short-horizon prediction while still losing money after costs, because (a)
short-horizon predictability at HFT tick-level typically reflects trivial persistence rather than
genuine signal, and (b) even genuine signal requires colocated execution, sub-millisecond latency
and queue-position edge to monetize — none of which a Kaggle-style leaderboard measures. Published
2025–2026 academic work on deep LOB forecasting makes exactly this point explicitly: high
forecasting power does not necessarily correspond to actionable trading signals (see
`../../03_market_ml_landscape_survey.md` for the citation).

## Why this verdict, not a test

- Even with the (freely downloadable) data in hand, WP-on-undisclosed-targets is not a "measurable
  edge" as `PREREG_COMMON.md` defines it (beats a placebo or beats buy-and-hold, net of costs) — it
  is a different quantity entirely, one level upstream of any tradeable claim, and the target
  definition is withheld specifically to prevent reconstructing what it means in trading terms.
  Testing it would mean inventing an entire execution layer, cost model, and target interpretation
  Wunder Fund never disclosed, then testing *our own invention* — the C04/C05 mistake in reverse,
  same as the OSS-stack survey's infrastructure repos.
- Rules explicitly forbid using the data for anything beyond the competition itself while it is
  running, and are silent on reuse after — we are not treating the freely-downloadable starter pack
  as a green light for an unrelated research project on the full 250M-row dataset.
- The full dataset is ~30+ GB compressed; pulled the small, genuinely representative artifacts
  instead (`reference_kit/`, all committed) rather than the multi-gigabyte parquet files, which
  would add no research value beyond what `docs/data_overview.md`'s schema table already specifies.

## Revisit if

- Wunder Fund (or any contestant) ever publishes an actual backtested/live P&L claim built on a
  winning model, or discloses what `t0`/`t1` actually represent — either would be a new, testable
  claim, not this one.
- A future episode wants a "prediction accuracy ≠ trading edge" explainer segment — this is a clean,
  named, legitimate (non-scammy) example precisely because Wunder Fund never overclaims: it says
  "predict two indicators," not "predict profit." Good contrast case against the YouTube claims that
  do overclaim from far weaker footing (C01 in particular). The baseline GRU architecture
  (`reference_kit/solution.py`) is also a clean, real reference implementation if AMI ever needs a
  worked example of stateful sequence modeling on market microstructure data.

## Track record note (context only, not a verdict input)

Wunder Fund itself is a genuine, long-running HFT shop, not a claimed-but-unverifiable retail
product — nothing here reads as fraud or misrepresentation. The verdict is narrowly about whether
the *competition's own framing* hands RES008 a testable trading-edge claim, and it does not, by
design: Wunder Fund is buying talent, not selling a signal.

## Correction log (2026-09-20, same-day revision)

The first version of this file was built from AI-summarized `WebFetch` results on a JS-rendered SPA
that resisted direct scraping, plus secondhand GitHub-repo summaries — not primary sources. Two
errors that revision introduced, both caught when Saiful asked to actually pull the underlying data
and docs:

1. **Wrongly called the data "neurobiological/connectome."** A summarized fetch described a
   same-family challenge ("Alpha Connectome," Challenge 3) as involving "neural signal data," and
   that was repeated here without verifying against the actual data schema. Reading
   `docs/data_overview.md` directly: it is ordinary financial order-book/trade data for two
   instruments. "Connectome" is only this challenge generation's brand name.
2. **Wrongly stated the metric as "mean R² across ~200 features"** with a leaderboard figure of
   R²=0.39–0.40. That description matches a different, earlier public repo's summary (of what may be
   a distinct challenge vintage) and was not verified against this challenge's own `METRIC.md`. The
   actual metric for the current challenge is Weighted Pearson correlation on 2 targets (`t0`,
   `t1`), not R² on ~200 features; the correct public baseline score is 0.5896 WP, not an R² figure.

Lesson for future `R_market_ml_landscape/` (or any `R##`) entries: when a site is JS-rendered and
resists `WebFetch`, escalate to pulling raw docs/config directly (GitHub forks of a starter kit,
`curl` on documented asset URLs) before writing a verdict — don't let an AI-summarized fetch of a
one-line page title stand in for the primary source.
