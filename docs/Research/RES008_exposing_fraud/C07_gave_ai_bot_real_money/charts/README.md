# C07 chart pack

All figures are rendered by `make_charts.py` from files in `../out/`. Every number on
every chart is read from those files at run time — nothing is typed in. Run from the
RES008 root:

```bash
.venv/bin/python C07_gave_ai_bot_real_money/charts/make_charts.py
```

| File | Brief beat(s) | Chart-pack row | JSON / data keys used |
|:--|:--|:--|:--|
| `01_zero_skill_week_vs_spy.png` | 1, 5 | `one_week_vs_spy.png` (restyled) | `out/results_part2.json` → `zero_skill_bot.week_vs_spy.{share_beats_spy, share_beats_spy_by_3pt, n_pairs}`, `zero_skill_bot.week_excess_percentiles.{p5,p95}`; histogram values from `out/part2_arrays.npz` → `week_excess_bot` |
| `02_trending_month_winrate.png` | 7 | `trending_month_winrate.png` (restyled) | `out/results_part2.json` → `trending_month_conditional.{unconditional_trade_win_rate, trend_trade_win_rate, n_all_trades, n_trend_trades, share_of_windows_trending}` |
| `03_rule_vs_buy_hold_define.png` | 5 | "Rule vs buy-and-hold, 22 tickers x 2 windows" (to draw) — DEFINE window | `out/results_part1.json` → `DEFINE.per_ticker[].{ticker, net_total_return, buy_hold_total_return}`, `DEFINE.pooled.{n_tickers_beat_buy_hold_net, n_tickers}` |
| `04_rule_vs_buy_hold_holdout.png` | 5 | "Rule vs buy-and-hold, 22 tickers x 2 windows" (to draw) — HOLDOUT window | `out/results_part1.json` → `HOLDOUT.per_ticker[].{ticker, net_total_return, buy_hold_total_return}`, `HOLDOUT.pooled.{n_tickers_beat_buy_hold_net, n_tickers}` |
| `05_placebo_percentile.png` | 5 | "Placebo distribution with marker" (to draw) | `out/results_part1.json` → `DEFINE.pooled.mean_placebo_percentile.{estimate,lower,upper}`, `HOLDOUT.pooled.mean_placebo_percentile.{estimate,lower,upper}` |

## Notes on sourcing decisions

- **The brief's "2,000 bot lines" figure is not in the pack.** Per-bot equity paths were
  never written to `out/`; only the per-(bot, week) excess-return array is saved. A running
  sum of that array was tried and cut in review: random picks from ten large-cap survivors
  drift upward against SPY, so the wall of lines reads as "random bots win", which is not
  the finding (50.6% of weeks). The cold open uses `01_zero_skill_week_vs_spy.png` instead.
- **`01_zero_skill_week_vs_spy.png` reproduces without the raw array.** `out/part2_arrays.npz`
  is git-ignored for size (161 MB). When it is present the script bins it and rewrites
  `01_week_excess_hist.json` (150 bins, −25 to +25 points); when it is absent the script
  draws from that cached file. The two big numbers on the chart come from
  `out/results_part2.json`, not from the bins.
- **No figure plots the RSI rule's 227/284 and 118/155 trade counts or the AAPL/TSLA
  9-of-9 rows** (`out/derived_extras.json` → `rsi_rule_pooled_trades`). The brief's chart
  pack table does not list a figure for these; they appear only in the beat sheet's
  "source of every number" column for beat 4, which the voice-over and on-screen trade
  list (not a chart) carry per the beat sheet.
- Four of the five chart-pack rows in `VIDEO_BRIEF.md` are covered (the two "restyle" rows and
  two of the three "to draw" rows — the per-ticker comparison is split into two figures, one
  per window, for legibility at 1920x1080 with 22 tickers each).
- `02_trending_month_winrate.png` is stamped "prediction met narrowly". H3 **was**
  pre-registered (≥ 60%); it came in at 60.9%, and `RESULTS.md` §1 says the printed interval
  is too narrow because 2,000 bots trade the same ten stocks. The chart draws our 60% bar and
  shows point estimates only, matching the brief's "must not say" list.
