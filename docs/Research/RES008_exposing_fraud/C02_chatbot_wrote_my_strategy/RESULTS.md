# C02 — RESULTS — "A chatbot wrote me a profitable trading strategy"

**Verdict: `DISPROVED`** — for the claim as pre-registered: that the chatbot supplies the edge.
Pre-registration: commit `3ac320eb` (2026-09-17), before any code existed and before any strategy
was generated. Run: 2026-09-17 · 30 strategies generated, 29 scored · 22 stocks and ETFs (2
cryptocurrencies for the Bitcoin prompt) × 2 windows × 500 placebo replications · scoring 8,183 s.
Every figure is in [`out/results.json`](out/results.json); the headline counts were recomputed
independently from its per-ticker cells and match, and one strategy (hold above the 50-day
average, AAPL, 2019–2026) was re-implemented from scratch and reproduces the stored return to five
significant figures.

All three pre-registered predictions were met; neither claim-supporting condition was.

---

## 1. Deviations and disclosed assumptions

No prompt, universe, window, metric or threshold was changed.

| # | Choice | Effect |
|:--|:--|:--|
| 1 | **First generation pass discarded.** A developer-tool plugin injected its own context into the chatbot calls (the same fault as [C08](../C08_chatbot_stock_picks/RESULTS.md) deviation 1). The partial pass — 23 replies — was moved to `out/_discarded_pass1/` with a README and all 30 were generated again with the CLI in safe mode. No figure uses the discarded pass. | The test needs what a retail user would see. The discarded replies were never scored, so the choice could not have been made on results. |
| 2 | **The chatbots are Claude models (Haiku 4.5, Sonnet 5, Opus 5); the videos use a different vendor's chatbot.** Pre-registered. | The claim class is "a chatbot wrote it". Ours are named. |
| 3 | The chatbot turned its own prose into code (second turn, fixed instruction in `code/01_generate_strategies.py`), so the rules scored are its reading of its answer, not ours. | — |
| 4 | **Look-ahead gate:** 26 strategies passed first time, 3 passed after the one permitted repair (two had a missing import, one a read-only array bug), 1 was excluded after failing twice (`p04_haiku` — the same missing import survived its repair). No strategy failed for look-ahead. | 29 of 30 scored; every share below is "of 29". The three import failures are trivial ones that a friendlier harness would have patched silently; we followed the pre-registered rule instead. It cost the claim one strategy of 30 and cannot change a 0-of-29 result. |
| 5 | Truncation-test dates: five, at the 20th/40th/60th/80th/95th percentile of SPY's history. | Spec said "spread through the sample". |
| 6 | `p10_haiku` never trades: its three conditions are never true together on any of the 22 tickers. It is scored as written — always flat. | It "beats" buy-and-hold on the two tickers that fell, like every other low-exposure strategy (§2). It has no placebo percentile and is left out of the S2 median (28 values). |
| 7 | After the run we removed 58 truncated text fragments (`replicates`) that a serialisation slip had written into `results.json`. They were unreadable stubs of the bootstrap draws, not results. No number changed. | — |
| — | **Contamination runs in the claim's favour.** The chatbots have read about every year of this data. Nothing is out-of-sample for them. | If anything this flatters the strategies. |
| — | **29 strategies are not 29 independent ideas.** All three models answered prompt 2 with the same rule; one model answered four different prompts (1, 4, 5, 8) with the same RSI(2) pullback. | Counts "of 29" overstate the number of independent trials. The result is unanimous, so this does not matter to the verdict. |

## 2. S1 — is it worth doing? (net, next-open fills, costs included)

| | 2005–2018 | **2019 → 2026-08 (holdout)** |
|:--|--:|--:|
| Strategies that beat buy-and-hold on more than half their tickers | 3 of 29 *(the three Bitcoin strategies, 2 coins each)* | **0 of 29** |
| Strategy × ticker cells that beat buy-and-hold | — | **38 of 578 (6.6%)** |
| …and which tickers those were | — | BA 15 · DIS 12 · PFE 10 · ETH 1 |
| Strategies whose pooled daily return minus buy-and-hold has an interval entirely below zero | — | 26 of 29 *(the other three are the Bitcoin strategies; their intervals include zero)* |

In the holdout BA fell 32%, PFE fell 1% and DIS rose 4%. **A strategy "beat the market" only
where the market went nowhere or down** — and there, being out of the market is enough; the
strategy that never trades did it too. On the other 19 stocks and ETFs, and on Bitcoin, no chatbot
strategy beat holding in a single case.

The median strategy is in the market 26% of the time in the holdout (range: 0% for the one that
never trades, to 100%). These are mostly long-or-flat rules in a period when the median ticker
returned +248%.

## 3. S2 — is there any skill? (against 500 matched random-entry placebos per ticker)

Percentile 50 = the strategy's entries did as well as random entries with the same number of
trades and the same holding periods.

| | 2005–2018 | **2019 → 2026-08 (holdout)** |
|:--|--:|--:|
| Median strategy's mean placebo percentile | 51.5 | **49.7** |
| Range across strategies | 31.0 – 75.0 | 25.1 – 85.5 |
| Strategies at or above the 95th percentile | 0 | **0** |
| In both windows | — | **0** |
| Strategy × ticker cells at or above the 95th percentile | — | 18 of 556 (3.2%) — 5% is what chance gives |

The highest holdout figure is 85.5 (`p09_opus`: hold Bitcoin above its 200-day average; two coins,
27 trades a coin). Nothing clears 95 in either window, so there is no individual follow-up
candidate to name.

Figure: `out/placebo_percentiles.png`.

## 4. The as-shown arm — the screenshot

Each strategy on its single best ticker of 2005–2018, no costs, fills at the signal bar's close —
what a strategy-tester screenshot shows.

- **28 of 29 show a profit** (the 29th is the strategy that never trades). Best-ticker returns run
  from +34% to +2,398%; the three Bitcoin strategies show +1,715% to +1,793%.
- Only **10 of those 28** beat simply holding that same best ticker. A typical case: a pullback
  strategy shows +253% on AMZN, which itself returned +3,274% over the same window.
- The same 29 strategies in the holdout, all tickers, after costs: §2.

`out/as_shown_vs_holdout.png` plots both arms **relative to buy-and-hold**, which is why most
"as-shown" bars point left; a screenshot shows the absolute figure and no benchmark. The video
figure must be redrawn in absolute terms (brief, chart pack).

## 5. What the chatbots said (descriptive; [`out/catalogue.md`](out/catalogue.md))

- 25 of 30 replies promised no win rate or return. Several opened by refusing to promise
  profitability; one called win rate alone misleading; one rejected the premise of prompt 8.
- Four replies cited "published backtests" with win rates of 65–80% (or "70%+") for an RSI(2)
  pullback. Measured here, in the holdout, the two versions given for prompt 8 won **66.0%**
  (795 of 1,204 trades) and **63.5%** (2,234 of 3,519) — close to what was cited — and returned a
  median **+18%** and **+41%** per ticker over the window, against +248% for holding. High win
  rate, a fraction of the return: [C04](../C04_win_rate_proves_edge/RESULTS.md).
- One Bitcoin reply volunteered that its strategy would have made "~500–800%" against
  "~10,000%+" for buy-and-hold.

The chatbots were, on the whole, more careful than the claim made about them.

## 6. Pre-registered hypotheses — scored

| | Prediction | Result | |
|:--|:--|:--|:--|
| H1 | At most 6 of 30 beat buy-and-hold net in the holdout on more than half their tickers | 0 of 29 | **met** |
| H2 | Median S2 in [35, 65]; at most 3 of 30 at or above the 95th placebo percentile in the holdout | 49.7; 0 of 29 | **met** |
| H3 | The as-shown arm looks profitable for ≥ 80% of strategies | 28 of 29 (96.6%) | **met** |

What would have supported the claim: ≥ 15 of 30 beating buy-and-hold on most tickers in the
holdout — 0, **not met**; or ≥ 8 of 30 at or above the 95th placebo percentile in both windows —
0, **not met**.

→ **`DISPROVED`**.

## 7. What can and cannot be said

Can be said:

- Thirty one-line prompts to three chatbots produced textbook rules: moving-average filters,
  RSI pullbacks, breakouts, MACD, SuperTrend. None beat buy-and-hold across its universe in
  2019–2026, and none timed its entries better than random entries with the same trade count.
  The median sits at the 50th percentile.
- A flattering screenshot was available for every strategy that traded at all. Picking the best
  ticker, dropping costs and leaving out the benchmark is sufficient.
- Where a strategy "beat the market", the market had fallen and the strategy was mostly in cash.
- The chatbots mostly did not claim an edge. The claim is made about them, not by them.

Cannot be said:

- That a chatbot is no use for *coding* a strategy a trader already has. 26 of 30 functions ran
  correctly first time and none looked ahead. The test is of the claim that the chatbot supplies
  the edge.
- That these rules lose money. Most made money in a rising market; they made less than holding,
  because they were in the market a quarter of the time.
- Anything about risk-adjusted performance. Lower exposure also means smaller drawdowns; we
  report max drawdown per cell in `results.json` and draw no conclusion from it. The claim tested
  is "profitable strategy", and the evidence offered for it is total return.
- Anything about the other vendor's chatbot specifically.
- Daily bars, 22 large US stocks and ETFs chosen in 2026 (survivorship flatters buy-and-hold and
  the strategies alike), long/short or long/flat at full size.

## 8. Reproduce

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python C02_chatbot_wrote_my_strategy/code/02_extract_and_gate.py   # re-gates the stored replies
.venv/bin/python C02_chatbot_wrote_my_strategy/code/03_score.py              # ≈ 2 h 15 min
.venv/bin/python C02_chatbot_wrote_my_strategy/code/04_catalogue.py
.venv/bin/python C02_chatbot_wrote_my_strategy/code/05_outputs.py
```

`01_generate_strategies.py` calls the chatbots and will not return the same text twice; the 30
replies scored here are stored verbatim in `out/generated/`. The gate executes model-written code:
it is statically checked for imports and calls other than numpy and pandas before it runs.
