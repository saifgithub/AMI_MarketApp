# C05 — RESULTS — The "99% win rate" scalping recipe

**Verdict: `PARTLY HOLDS`** — by the letter of our pre-registration, and we publish it as such.
The headline claim — an 80% win rate, 90–99% with the confirmation — **fails in all 12 cells: the
highest win rate measured is 43.6%.** What holds is the weaker condition we wrote down in advance:
the recipe's net expectancy beat random entries' in 3 of 4 primary variants and their daily
counterparts. §5 explains why we now think that condition was badly built by us — and why we do not
get to un-write it.

Pre-registration: commit `3ac320eb` (2026-09-17), before any test code existed. Run: 2026-09-17 ·
12 cells · 7 instruments · 500 placebo replications per cell · `code/` 40 tests green (30 for the
pre-registered run, 10 for the post-hoc diagnostic). Every pre-registered figure is in
[`out/results.json`](out/results.json); every post-hoc figure in
[`out/posthoc_diagnostic.json`](out/posthoc_diagnostic.json), which opens with the word
EXPLORATORY.

One of our three predictions was met. Two were wrong.

---

## 1. Deviations and disclosed assumptions

No parameter, instrument, timeframe, metric or threshold was changed. Full list in
[`out/DEVIATIONS.md`](out/DEVIATIONS.md):

| # | Choice |
|:--|:--|
| 1 | STC "rising" / "falling" = higher / lower than the previous bar. The videos give no lookback. |
| 2 | The STC filter is read on the same bar as the UT Bot cross, at its close; entry is the next bar's open. |
| 3 | Daily "full history" = each instrument's first available bar → 2026-08-31. Intraday samples cannot be pinned to that date: the data vendor serves only the most recent bars, so they end on the fetch date, 2026-09-17 — 60-minute from 2023-10-19 (equities) and 2024-09-18 (crypto); 5-minute from 2026-06-24 (equities) and 2026-07-20 (crypto). |
| 4 | If a long and a short signal fire on the same bar, the long is kept. |
| 5 | Tests are run per claim from the RES008 root (two claims share a test-file name). |
| — | **Added after the run, not pre-registered:** `code/posthoc_placebo.py`, `code/posthoc_diagnostic.py` and their outputs. Written because the pre-registered comparison in §3 produced a result whose cause we could see was partly mechanical. They change no pre-registered number — a test proves the extended placebo reproduces the original exactly when its extra option is off — and they do not change the verdict. |
| — | The post-hoc run counts 773 trades in `V2_loose_daily` against 774 in the pre-registered run. One trade in 774; cause not traced. |
| — | **A misstatement corrected:** the first draft of the run notes said the recipe's intraday win rates fell *below* the placebo band. They are *above* it (e.g. 43.0% against 35.4–40.9%). No file in `out/` carried the error. |

## 2. The headline claim — win rate

UT Bot alert confirmed by STC, swing-low/high stop (10 bars), fixed R target, next-open fills,
costs included. Two variants (V1: 1.5 R target · V2: 2 R) × two readings of the filter × three
timeframes, each pooled over BTC-USD, ETH-USD, SPY, QQQ, AAPL, NVDA, TSLA.

| Cell | Trades | **Win rate** (95% interval) | Random entries, same rules (5th–95th pct) |
|:--|--:|:--|:--|
| V1 strict · 60-minute | 798 | **43.0%** (39.6 – 46.4) | 35.4 – 40.9 |
| V1 loose · 60-minute | 975 | **43.6%** (40.5 – 46.7) | 35.7 – 40.5 |
| V2 strict · 60-minute | 759 | **37.3%** (33.9 – 40.8) | 30.5 – 36.1 |
| V2 loose · 60-minute | 900 | **37.3%** (34.2 – 40.5) | 30.5 – 35.8 |
| V1 strict · 5-minute | 696 | 40.1% (36.5 – 43.8) | 23.6 – 28.9 |
| V1 loose · 5-minute | 871 | 39.4% (36.2 – 42.7) | 24.6 – 29.2 |
| V2 strict · 5-minute | 668 | 36.5% (33.0 – 40.2) | 21.9 – 27.6 |
| V2 loose · 5-minute | 828 | 33.2% (30.1 – 36.5) | 22.5 – 27.5 |
| V1 strict · daily | 659 | 38.2% (34.6 – 42.0) | 35.6 – 42.0 |
| V1 loose · daily | 834 | 38.7% (35.5 – 42.1) | 35.4 – 40.9 |
| V2 strict · daily | 601 | 33.6% (29.9 – 37.5) | 31.6 – 38.1 |
| V2 loose · daily | 774 | 33.2% (30.0 – 36.6) | 29.9 – 35.6 |

**No cell reaches 44%. The upper end of the widest interval is 46.7%.** The claim is 80% to 99%.

Arithmetic, not a finding: with a target of 1.5 times the stop, a trader breaks even before costs
at 40% wins; with 2 times, at 33.3%. The recipe's win rates sit within about four points of those
two numbers in every cell (largest gap: 4.0). A win rate near `1 / (1 + target)` is what the
target-to-stop geometry gives an entry with no information in it.

Figure: `out/win_rate_vs_claim.png`.

## 3. Expectancy — the pre-registered comparison

| Cell | Net expectancy per trade, in R (95% interval) | Random entries' 95th pct | Gross, in R (95% interval) | Cost per trade, in R |
|:--|:--|--:|:--|--:|
| V1 strict · 60m | −0.050 (−0.126 … +0.027) | −0.452 | +0.043 (−0.032 … +0.121) | 0.094 |
| V1 loose · 60m | −0.053 (−0.128 … +0.017) | −0.459 | +0.041 (−0.033 … +0.110) | 0.094 |
| V2 strict · 60m | −0.019 (−0.112 … +0.075) | −0.420 | +0.076 (−0.017 … +0.169) | 0.095 |
| V2 loose · 60m | −0.039 (−0.135 … +0.059) | −0.457 | +0.056 (−0.038 … +0.151) | 0.095 |
| V1 strict · 5m | −0.522 (−0.651 … −0.396) | −2.210 | −0.012 (−0.102 … +0.080) | 0.510 |
| V1 loose · 5m | −0.535 (−0.658 … −0.422) | −2.215 | −0.019 (−0.106 … +0.068) | 0.515 |
| V2 strict · 5m | −0.454 (−0.576 … −0.333) | −2.164 | +0.073 (−0.037 … +0.193) | 0.527 |
| V2 loose · 5m | −0.538 (−0.660 … −0.419) | −2.203 | −0.021 (−0.116 … +0.080) | 0.517 |
| V1 strict · daily | −0.083 (−0.173 … +0.008) | −0.090 | −0.063 (−0.154 … +0.028) | 0.020 |
| V1 loose · daily | −0.071 (−0.152 … +0.012) | −0.123 | −0.050 (−0.131 … +0.033) | 0.021 |
| V2 strict · daily | −0.039 (−0.162 … +0.087) | −0.009 | −0.021 (−0.144 … +0.105) | 0.018 |
| V2 loose · daily | −0.047 (−0.161 … +0.073) | −0.094 | −0.028 (−0.142 … +0.092) | 0.019 |

Read against zero, which needs no placebo at all:

- **Net expectancy is negative in all 12 cells.** In the eight 60-minute and daily cells the
  interval includes zero; in the four 5-minute cells it lies entirely below zero.
- **Before costs, the interval includes zero in all 12 cells.** There is no cell in which the
  recipe demonstrably makes money even with free trading.
- **On 5-minute bars — the timeframe the recipe is taught on — costs take half of 1 R per trade**
  at 5 bps a side for equities and 10 for crypto. A gross result of about zero becomes −0.45 to
  −0.54 R a trade.

Read against random entries, as pre-registered: the recipe's net expectancy is above the placebo's
95th percentile in all four 60-minute cells, all four 5-minute cells, and three of the four daily
cells (not V2 strict · daily).

## 4. Pre-registered hypotheses — scored

| | Prediction | Result | |
|:--|:--|:--|:--|
| H1 | Win rate below 60% in all 12 cells | highest is 43.6% | **met** |
| H2 | Win rate inside the placebo's central 90% in at least 9 of 12 cells | inside in 4 of 12 (the daily cells); **above** the band in the other 8 | **not met** |
| H3 | Net expectancy not above the placebo's 95th percentile in the primary (60-minute) cells | above it in all 4 | **not met** |

What would have supported the claim:

- Win rate ≥ 80% in any 60-minute cell → headline `HOLDS`. Highest: 43.6%. **Not met.**
- Net expectancy above the placebo's 95th percentile in ≥ 3 of the 4 primary cells **and** in the
  matching daily cells → `PARTLY HOLDS`. Met by V1 strict, V1 loose and V2 loose (60-minute
  percentile 1.000 each; daily 0.954, 0.998, 0.992). V2 strict fails on daily (0.886). **Met.**

→ **`PARTLY HOLDS`**, as the rule we committed to requires
([`../PREREG_COMMON.md`](../PREREG_COMMON.md): "if (a) occurs, the verdict is `HOLDS` or
`PARTLY HOLDS` and it is published as such").

## 5. Why we distrust the condition that was met — post-hoc, exploratory

Everything in this section was computed **after** the pre-registered results were seen. It cannot
change the verdict and does not. It is here because we can see a mechanical reason for part of §4,
and hiding that would be worse than showing it.

**The flaw is ours.** We measured expectancy in R — profit divided by each trade's own stop
distance — and costs are a fixed percentage of price. So a trade with a tiny stop pays an enormous
cost in R. The recipe enters after a breakout, when the 10-bar low is far away; a random entry is
often sitting right on its 10-bar low.

| | Median stop distance, recipe | Median stop distance, random entries | Cost in R, recipe | Cost in R, random entries |
|:--|--:|--:|--:|--:|
| 60-minute | 2.0 – 2.1% | 0.9% | 0.09 | 0.52 – 0.54 |
| Daily | 7.3 – 7.8% | 3.2 – 3.6% | 0.02 | 0.11 – 0.14 |
| 5-minute | 0.39 – 0.42% | 0.21 – 0.22% | 0.51 – 0.53 | 3.2 – 4.0 |

Our placebo paid five to eight times the recipe's costs in R. "Net expectancy above the placebo's
95th percentile" was therefore easy to pass for a reason that has nothing to do with timing.

**Daily cells, re-read with measures that do not divide cost by stop distance** (recipe's
percentile among random entries; 0.50 = no different):

| Daily cell | Pre-registered: net R | Win rate *(pre-registered)* | Gross R | Net % per trade |
|:--|--:|--:|--:|--:|
| V1 strict | 0.954 | 0.354 | 0.308 | 0.058 |
| V1 loose | 0.998 | 0.642 | 0.638 | 0.470 |
| V2 strict | 0.886 | 0.256 | 0.336 | 0.114 |
| V2 loose | 0.992 | 0.586 | 0.666 | 0.108 |

On daily bars over each instrument's full history, the recipe is indistinguishable from random
entries on every measure except the one we mis-built. **The daily leg of the `PARTLY HOLDS`
condition is an artefact.**

**60-minute cells stand up better.** The recipe is at or above the 98th percentile of random
entries on win rate (0.984 – 1.000), gross R (0.988 – 0.996) and net % per trade (1.000 in all
four). Against a second placebo arm whose stops are floored at the recipe's own 10th-percentile
stop distance, it is still at 0.986 – 0.998 on win rate and 1.000 on net % and net R. Two cautions:

- The floor is imperfect. In about 20% of placements (78,422 of 399,000 in V1 strict · 60m) the
  retry budget ran out and a narrower stop was accepted; and a floor at the 10th percentile still
  leaves the placebo's stops narrower than the recipe's on average. Our resolver assumes the stop
  is hit first when a bar spans both stop and target, which penalises narrow stops. Some of the
  remaining gap may be geometry rather than timing. We have not measured how much.
- It is one sample: 60-minute bars from 2023-10 (equities) and 2024-09 (crypto) to 2026-09-17, in
  which all seven instruments rose — from +6% (ETH) to +414% (NVDA).

**Where the money came from** (descriptive, pooled over instruments, net % per trade):

| Cell | Long trades | Short trades |
|:--|:--|:--|
| V1 strict · 60m | +0.46% (n = 404) | −0.30% (n = 394) |
| V1 loose · 60m | +0.44% (472) | −0.26% (503) |
| V2 strict · 60m | +0.57% (407) | −0.39% (352) |
| V2 loose · 60m | +0.51% (450) | −0.20% (450) |
| V1 strict · daily | +1.77% (299) | −2.70% (360) |
| V1 loose · daily | +2.66% (328) | −2.19% (506) |
| V2 strict · daily | +1.80% (303) | −2.70% (298) |
| V2 loose · daily | +3.30% (308) | −3.31% (465) |

**The short side lost money in all 12 cells**, the long side made money in all eight 60-minute and
daily cells. Every instrument rose over its 60-minute and daily samples. On 60-minute bars the
two sides net to +0.08% to +0.16% a trade after costs, with intervals that include zero
(e.g. V1 strict: +0.083%, −0.20% … +0.40%).

## 6. What can and cannot be said

Can be said:

- The recipe wins **33% to 44%** of its trades, not 80% to 99%. Across 9,363 trades in 12 cells, no
  variant, reading or timeframe reaches 44%.
- Its win rate is within about four points of `1 / (1 + target)` everywhere — what the target-to-stop
  ratio gives any entry.
- Average profit per trade is not distinguishable from zero before costs in any cell, and is
  negative after costs in every cell. On 5-minute bars, costs alone are half of 1 R.
- The short half of the recipe lost money in every cell.
- By the rule we wrote before testing, the claim `PARTLY HOLDS`: the recipe's entries did better
  than random entries on 60-minute bars in this sample. We say that first, and we say why we think
  part of the rule was badly built.

Cannot be said:

- That the entry signal is worthless. On 60-minute bars it beat every random-entry arm we built.
  We could not show that the gap is timing rather than stop geometry, and we could not show the
  opposite either.
- That it is profitable. No interval in any cell excludes zero on the upside.
- Anything about discretionary use. The videos' examples are hand-picked charts; we tested the
  rules as stated, mechanically. One of the videos' own 100 manual setups came out at 55% — we did
  not reproduce 55% in any cell, and a hand count is not a test.
- That the 5-minute result is strong evidence on its own: it is about 60 days of data. The cost
  arithmetic does not depend on the sample; the win rates do.
- "Swing low" was operationalised as the 10-bar low. A discretionary swing point would differ.
- Survivorship: all seven instruments were chosen in 2026 and all rose. That flatters the long
  side and punishes the short side, for the recipe and the placebo alike.

A properly matched placebo (stop-distance distribution, not a floor), on data after 2026-08-31, is
logged as backlog item B09 in [`../TRACKER.md`](../TRACKER.md). It will be pre-registered before
it is run.

## 7. Reproduce

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python -m pytest C05_99pct_scalping_recipe -q
(cd C05_99pct_scalping_recipe/code && ../../.venv/bin/python run_c05.py)              # pre-registered
(cd C05_99pct_scalping_recipe/code && ../../.venv/bin/python posthoc_diagnostic.py)   # exploratory, ≈ 17 min
```

Intraday bars reach back only about two to three years (60-minute) and 60 days (5-minute) from the day
they are fetched; a later re-run sees a different intraday sample. The cached bars used here are in
`common/cache/` (git-ignored).
