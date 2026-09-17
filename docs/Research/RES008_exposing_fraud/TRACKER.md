# RES008 — Tracker

**The register. Check here before starting anything.** A row marked `closed` is not revisited
unless new *data* exists (not new enthusiasm). IDs are never reused.

- `C##` — a claim taken from the YouTube landscape and tested under RES008. Folder `C##_<slug>/`.
- `P##` — a claim already tested in prior work ([`01_prior_work.md`](01_prior_work.md)). No folder; reused as-is.
- `B##` — backlog: seen in the landscape, not yet tested. Promote to `C##` when picked up.

Status: `prereg` (pre-registration committed, not yet run) · `running` · `closed` · `parked` (blocked, reason given).
Verdicts: see the vocabulary in [`README.md`](README.md).

Last updated: 2026-09-17.

---

## C — claims tested under RES008

| ID | Claim (as a class — no channels) | Reach measured 2026-09-17 | Status | Verdict | Prereg commit | Results | Video brief |
|:--|:--|:--|:--|:--|:--|:--|:--|
| C01 | A neural network (LSTM) predicts tomorrow's stock price | 2 videos · 1.95M | prereg | — | `3ac320eb` | — | — |
| C02 | A chatbot wrote me a profitable strategy | 3 videos · 3.28M | prereg | — | `3ac320eb` | — | — |
| C03 | Keep tweaking until the backtest is spectacular (+10× margin) | within C02's videos + 2 more | closed 2026-09-17 | `DISPROVED` (selection without a holdout) — best of 420 lands at the 54.5th percentile afterwards (41.8–66.3); below buy-and-hold on 21 of 23; best of 420 *random* strategies out-backtests the tuned winner on 23 of 23; 10× BTC winner liquidated 26 times in its own tuning window | `3ac320eb` | [RESULTS](C03_tune_until_spectacular/RESULTS.md) | [brief](C03_tune_until_spectacular/VIDEO_BRIEF.md) |
| C04 | A 90% win rate proves the strategy works | 4 videos · 2.99M | prereg | — | `3ac320eb` | — | — |
| C05 | The "99% win rate" scalping recipe (ATR trailing stop + Schaff trend cycle) | 2 videos · 2.17M | prereg | — | `3ac320eb` | — | — |
| C06 | An "AI" grid / band robot earns passive income in any market | 3 videos · 0.92M | closed 2026-09-17 | `NOT SUPPORTED` — dashboard "grid profit" positive in 99.65% of runs, account down in 36.80%; 5× liquidated in 32.54%; grid ties buy-and-hold (51.09%) — two of our four predictions wrong | `3ac320eb` | [RESULTS](C06_ai_grid_bot_passive_income/RESULTS.md) | [brief](C06_ai_grid_bot_passive_income/VIDEO_BRIEF.md) |
| C07 | "I gave an AI bot real money" and it beat the market in a week / month | 2 videos · 6.12M | closed 2026-09-17 | `DISPROVED` — a zero-skill bot beats SPY in 50.6% of weeks (by ≥ 3 pts in 14.8%); the disclosed RSI rule sits at the 57th–58th placebo percentile and trails buy-and-hold on 19–20 of 22 while winning ~8 trades in 10; a +5 pt/yr edge needs ~87 years of weekly results to show | `3ac320eb` | [RESULTS](C07_gave_ai_bot_real_money/RESULTS.md) | [brief](C07_gave_ai_bot_real_money/VIDEO_BRIEF.md) |
| C08 | A chatbot's ten stock picks beat the index | 2 videos · 2.76M | closed 2026-09-17 | `NOT SUPPORTED` — luck alone spans 28 points in a typical year; 19 of 30 asks declined; back-dated picks at the 94th percentile (hindsight, stated by all 30 replies); one of our spread thresholds missed (28 vs > 30) | `3ac320eb` | [RESULTS](C08_chatbot_stock_picks/RESULTS.md) | [brief](C08_chatbot_stock_picks/VIDEO_BRIEF.md) |

## P — prior work, reused (not re-tested)

| ID | Claim | Verdict as recorded | Evidence | Episode-ready? |
|:--|:--|:--|:--|:--|
| P01 | ML predicts stock direction | DISPROVED — edge negative in 30/32 cells vs always-up; AUC 0.5055 once beta removed | `docs/Research/Alternatives/Intel/quant_finance/lgbm_results.md` | yes — evidence is in this repo · [brief](P_prior_work/P01_ml_predicts_direction/VIDEO_BRIEF.md) |
| P02 | A volatility/gamma "flip" predicts downside | NOT SUPPORTED — 0 of 18 | RES001 part 04 | yes |
| P03 | Volatility regime predicts direction | NOT SUPPORTED — sign flips across windows | RES001 part 03 | yes |
| P04 | Stop after k losses improves results | DISPROVED mechanically (below placebo 10/12); behavioural value only | RES001 part 06 | yes · [brief](P_prior_work/P04_stop_after_k_losses/VIDEO_BRIEF.md) |
| P05 | Volume-without-progress predicts reversal | NOT SUPPORTED on a daily proxy — cannot speak to tick data | RES001 part 06 | yes, with the resolution caveat |
| P06 | A contest-winning return proves skill | NOT SUPPORTED — it is the expected maximum of zero-skill entrants | RES001 part 03 §E | yes · [brief](P_prior_work/P06_contest_win_proves_skill/VIDEO_BRIEF.md) |
| P07 | Pre-FOMC drift is tradeable | DISPROVED in 2015–2026; real before | Aegis edge-hunt P1 (private repo) | needs evidence re-hosted |
| P08 | FX fix / month-end continuation | PARTLY HOLDS — real gross, killed net of costs on a true holdout | Aegis edge-hunt P3/P3b (private) | needs evidence re-hosted |
| P09 | Regime timing beats buy-and-hold | DISPROVED — 0 of 207 pass | Aegis cemetery T-005, Tier-1 report (private) | verify primary first |
| P10 | HMM regime labels predict direction | DISPROVED — ≈ 0.50 | cemetery T-001 (private) | verify primary first |
| P11 | Opening-range breakout | DISPROVED — 0 of 82 | cemetery T-006 (private) | verify primary first |
| P12 | Breakout-combo sweep (gold) | DISPROVED — best in-sample = worst holdout | cemetery T-020 (private) | verify primary first |
| P13 | Meta-labelling adds edge | DISPROVED | cemetery T-021 (private) | verify primary first |
| P14 | Neural-SDE daily edge | DISPROVED — smoothing artifact | Aegis CR033 stage 3 (private) | verify primary first |
| P15 | Gold S/R + RSI reversal | DISPROVED — worse than random entry, IS and OOS | `AMI_FOREX` R-rev-1 (private) | needs evidence re-hosted |
| P16–P19 | Weak / unfinished items | — | see `01_prior_work.md` §B | no |
| P20 | Vol is forecastable; regime sizing homogenises risk | HOLDS — as a risk method that costs return | RES001 part 03 | yes — "what is real" episode |
| P21 | Dispersion rotates with regime | HOLDS — public stylised fact | RES001 part 04 | yes, same episode |
| P22 | Conditioned VIX-futures carry | PARTLY HOLDS — marginal, thin post-2020 | Aegis edge-hunt P2 (private) | no — not for a retail audience |
| P23 | Crypto funding carry | PARTLY HOLDS — decaying toward kill line | Aegis edge-hunt P4 (private) | no |
| P24 | Gold overnight drift | UNCONFIRMED here — positive in private work, single instrument | `Forex/research/` (private) | no — needs an RES008-standard re-run |

## B — backlog (seen, not tested)

| ID | Claim | Why not yet |
|:--|:--|:--|
| B01 | ML "AI indicator" (nearest-neighbour classifier on RSI/WaveTrend/CCI/ADX; k-means SuperTrend) has a 57–95% win rate — 5 videos · 1.04M | Open-source core is re-implementable but a faithful port is a sizeable job; P01 already covers "ML on technical features predicts direction". Next batch. |
| B02 | Reinforcement-learning agent learns a profitable policy — 1 video · 0.30M | The creator shows it failing out-of-sample himself; RES001 part 01 reviewed the main RL framework. Low value. |
| B03 | Chatbot reads headlines → "beat analysts by 512%" — 2 videos · 0.10M, heavily re-cited | Needs a timestamped headline feed we do not have. Desk review possible: the study's own cost sensitivity. `Forex/news_validator/` is a ready harness. |
| B04 | Upload a chart screenshot, get the trade — 0.02M read, a 0.9M video unread | No P&L claim to test; the right test is call *consistency* across near-identical screenshots. Needs a vision model. |
| B05 | Chatbot-vs-chatbot live trading contests — 0.29M spotted, captions unavailable | Desk review of public leaderboards; P06 (expected maximum of zero-skill entrants) is the argument. |
| B06 | Chatbot gives qualitative day-trading rules, a human executes — 2 videos · 0.41M | Discretionary; not mechanisable. The most-viewed creator says on camera the skill was his, not the chatbot's. |
| B07 | Undisclosed-logic bots sold as "AI arbitrage" / forex robots ($249–$4,500) — 2 videos · 0.64M | `UNTESTABLE` as presented. Candidate "why you can't check this, and what that tells you" episode. |
| B08 | Unread high-reach candidates: chatbot-built bots wired to a broker API (0.76M, 0.21M), "real money to chatbot X" series, AI candlestick tool (0.91M) | Second discovery pass. IDs in `_internal/`. |
