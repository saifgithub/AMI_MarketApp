# C07 — RESULTS — "I gave an AI bot real money and it beat the market"

**Verdict: `DISPROVED`** — for both separable claims as pre-registered: (a) the disclosed
RSI rule has an edge; (b) a one-week or one-month result can show that a bot has one.
Pre-registration: commit `3ac320eb` (2026-09-17), before any test code existed. Run: 2026-09-17 ·
Part 1 780 s, Part 2 700 s · `code/` 11 tests green. Figures are in
[`out/results_part1.json`](out/results_part1.json) and [`out/results_part2.json`](out/results_part2.json);
the Part 2 shares were recomputed independently from the stored per-bot arrays and match.

All four pre-registered predictions were met (H3 narrowly — see §4); neither claim-supporting
condition was.

---

## 1. Deviations and disclosed assumptions

No parameter, universe, window, metric or threshold was changed. Eight literal-reading choices are
listed in [`out/DEVIATIONS.md`](out/DEVIATIONS.md). Those a reader might question:

| # | Choice |
|:--|:--|
| 1 | The RSI rule "as a portfolio" = equal-weight, daily-rebalanced mean of the 22 tickers' net returns, 2005 → 2026-08-31 (both windows joined) so it spans the same dates as the zero-skill bots. |
| 2 | Zero-skill bot: each position is 1/3 of **current** equity when opened. |
| 4 | The trending-month basket holds whichever of the 10 names are listed (9 before TSLA's 2010 listing). |
| 5 | A trade counts as "inside a trending window" by its entry bar. |
| 7 | "+5 points a year" = 0.05/52 per week, 0.05/12 per month. |
| 8 | Results are split into `results_part1.json` and `results_part2.json`. `out/part2_arrays.npz` (161 MB of per-bot window returns) is git-ignored; `run_part2.py` regenerates it. |
| — | **Added by us after the run:** [`out/derived_extras.json`](out/derived_extras.json) (`code/derived_extras.py`) — three descriptive read-outs of the same 2,000 bots. Not pre-registered; not part of the verdict. |
| — | **Precision caveat we add:** the Wilson intervals on trade win rates treat 1.4–16 million trades as independent. They are not — 2,000 bots trade the same ten stocks on the same days. The printed intervals are far too narrow; read the point estimates, and treat H3's margin (60.88 vs 60) as inside real uncertainty. |

## 2. Part 1 — the disclosed rule: RSI(14), long below 30, flat above 70

22 tickers (`U-EQ`), next-open fills, 5 bps a side, 500 matched-random-entry placebos per ticker.

| Window | Tickers where the rule beats buy-and-hold, net | Rule minus buy-and-hold, mean daily net return (95% interval) | Mean placebo percentile (95% interval) |
|:--|--:|:--|:--|
| DEFINE 2005–2018 | **3 of 22** | −0.035% (−0.045% … −0.026%) | 57 (48 – 68) |
| HOLDOUT 2019 → 2026-08 | **2 of 22** | −0.058% (−0.075% … −0.041%) | 58 (50 – 66) |
| 60-minute, ≈ 730 days | 3 of 22 | −0.008% per bar (−0.011% … −0.005%) | 57 (50 – 65) |

Placebo percentile 50 = the rule's entries do as well as random entries with the same number of
trades and the same holding periods. The rule sits at 57–58 with intervals that reach 50: **no
timing skill detectable**, and it gives up return to buy-and-hold on 19–20 tickers of 22 — it is
in the market 37% of the time, in a period when the market rose.

*Derived from the per-ticker rows (`out/derived_extras.json`):* the rule **wins most of its
trades** — 227 of 284 (79.9%) in 2005–2018, 118 of 155 (76.1%) in 2019–2026 — because it buys dips
in stocks that went on rising. On AAPL in the holdout it won **9 trades out of 9** and returned
+247%; holding AAPL returned +836%. On TSLA in 2005–2018, 9 of 9 and +398% against +1,190%. A high
win rate, no timing skill against random entries, and a fraction of the buy-and-hold return, all
at once — C04 is about exactly this.

## 3. Part 2 — what a week or a month can show

**The zero-skill bot:** up to three long positions picked at random from ten large stocks, held
1–3 days, costs included. 2,000 of them, 2005 → 2026-08-31, every 5-day and 21-day window —
10.9 million bot-weeks.

| A bot with **no skill at all**… | One week | One month (21 days) |
|:--|--:|--:|
| beats SPY | **50.6%** | 51.1% |
| beats SPY by ≥ 1 point | 35.9% | 44.1% |
| beats SPY by ≥ 3 points | 14.8% | 31.1% |
| beats SPY by ≥ 10 points *(derived)* | — | 6.5% |
| middle 90% of excess return | −4.98% … +5.27% | −9.69% … +11.11% |

*Derived, descriptive:* four winning weeks in a row happen to a zero-skill bot 6.2% of the time.
Over 21 years the luckiest of the 2,000 bots beat SPY in 54.1% of its weeks, the unluckiest in
47.3% — skill-free bots differ by that much.

The Part 1 RSI rule as a 22-stock portfolio does *worse* than the random bot on this measure:
it beats SPY in 43.3% of weeks and 39.6% of months.

**Trending months** (the ten-stock basket up ≥ 8% over 21 days — 479 of 5,427 windows, 8.8%): the
zero-skill bot wins **60.9%** of its trades, against 52.7% in all conditions. A long-only bot in a
rising month wins most of its trades whatever it does.

**How long a track record would need to be.** Measured volatility of the excess return: 3.24% a
week, 6.48% a month. For a genuine +5-points-a-year edge to stand two standard errors clear of
zero: **4,549 weeks (87 years)** of weekly results, or 966 months (80 years).

Figures: `out/one_week_vs_spy.png`, `out/trending_month_winrate.png`.

## 4. Pre-registered hypotheses — scored

| | Prediction | Result | |
|:--|:--|:--|:--|
| H1 | RSI rule does not beat buy-and-hold in the majority of tickers in either window; pooled placebo percentile in [30, 70] | 3/22 and 2/22; 57 and 58 | **met** |
| H2 | Zero-skill bot beats SPY in 40–60% of one-week windows | 50.6% | **met** |
| H3 | In trending months the zero-skill bot wins ≥ 60% of its trades | 60.9% | **met, narrowly** — under a point of margin, and the true uncertainty is wider than the printed interval (§1) |
| H4 | Track record needed for a +5 pt/yr edge exceeds 3 years | 80–87 years | **met** |

What would have supported the claim: RSI rule at or above the 95th placebo percentile in both
windows — 57 and 58, **not met**; zero-skill bot beats SPY in under 25% of weeks — 50.6%,
**not met**.

→ **`DISPROVED`**. If H3 is set aside as marginal, H1, H2 and H4 carry the verdict on their own:
H3 is an illustration of H2, not an independent leg.

## 5. What can and cannot be said

Can be said:

- A bot with no skill beats the index in one week out of two, by three points or more in one week
  out of seven, and four weeks running about one time in sixteen. A winning week or month is what
  chance looks like.
- In a strongly rising month a long-only bot wins about six trades in ten with random entries.
- The one rule that was disclosed — buy RSI below 30, sell above 70 — timed its entries no better
  than random ones and earned less than buy-and-hold on 19 of 22 stocks (2005–2018) and 20 of 22
  (2019–2026).
- To see a real five-points-a-year edge in weekly results at this volatility takes decades, not
  weeks. That cuts both ways: a *losing* week says nothing either.

Cannot be said:

- Anything about the bots in the videos whose logic was not disclosed. They are untested here and
  may be good, bad or lucky; one week cannot tell us, which is the finding.
- That the creators misreported their results. We assume the weeks happened exactly as shown.
- That RSI "doesn't work" in every form. One rule, long/flat, daily and hourly bars, 22 large
  stocks.
- The zero-skill bot's exact shares depend on its design (three positions, ten volatile large
  caps). A more diversified random bot would hug the index more closely and its gaps would be
  smaller; the coin-flip share would not change.
- Survivorship: all tickers were chosen in 2026. It lifts the random bot and the RSI rule alike.

## 6. Reproduce

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python -m pytest C07_gave_ai_bot_real_money/code -q
.venv/bin/python C07_gave_ai_bot_real_money/code/run_part1.py     # ≈ 13 min
.venv/bin/python C07_gave_ai_bot_real_money/code/run_part2.py     # ≈ 12 min, writes the .npz
.venv/bin/python C07_gave_ai_bot_real_money/code/make_summary.py
.venv/bin/python C07_gave_ai_bot_real_money/code/make_figures.py
.venv/bin/python C07_gave_ai_bot_real_money/code/derived_extras.py
```
