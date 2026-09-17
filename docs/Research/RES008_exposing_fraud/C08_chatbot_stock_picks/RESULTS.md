# C08 — RESULTS — "A chatbot's ten stock picks beat the index"

**Verdict: `NOT SUPPORTED`.** Pre-registration: commit `3ac320eb` (2026-09-17), written before any
chatbot was asked anything. Run: 2026-09-17 · 2.36M random portfolios, 60 chatbot replies ·
pipeline 233 s · `code/` 11 tests green. Every figure is in [`out/results.json`](out/results.json)
or the derived [`out/gap_table.json`](out/gap_table.json).

Sub-claim (c) — "you can validate a chatbot's picks by back-testing them" — met its pre-registered
kill criterion cleanly. One clause of H1 did not, so the overall verdict stays `NOT SUPPORTED`.

---

## 1. Deviations

| # | What | Why it matters |
|:--|:--|:--|
| 1 | **First collection pass discarded (60 replies).** A developer-tool plugin injected its own context into the calls; 8 of 60 replies visibly answered "as a development assistant". All 60 were moved to `out/_discarded_pass1/` (kept, with a README) and re-collected with the CLI in safe mode. No figure uses the discarded pass. | The test needs what a retail user would see, not what a coding tool says. |
| 2 | **Claude models, not the chatbots in the videos** (pre-registered). Haiku 4.5, Sonnet 5, Opus 5. | Every Part 2–3 number describes these three models only. |
| 3 | The safe-mode CLI still tells the model today's date. | A consumer chatbot knows the date too. Replies state their own knowledge cut-offs (early to mid 2026). |
| 4 | `BK` returns no data from Yahoo → universe is 99 names, not 100. No substitute added. | Frozen list respected. |
| 5 | Part 3 control pool is 98 names: `BK` again, and `PLTR`, which was not public on 2019-01-02. | The pre-registered rule ("names with data at the window start"), applied. |
| 6 | **H1's "5th–95th spread exceeds 30 points" did not say pooled or per-window.** Both are reported; they disagree (§2). | The ambiguity is ours, so H1 is scored "not cleanly met". |
| 7 | `out/gap_table.json` is derived after the run from per-window values already in `results.json` (`code/06_gap_table.py`); no new simulation. | The pre-registered gap frequencies were stored per window but not pooled. |

## 2. Part 1 — what luck alone does

10,000 random equal-weight ten-stock portfolios from `U-LARGE100`, for each of 236 twelve-month
windows starting monthly 2006-01 → 2025-08. No chatbot involved.

| | |
|:--|--:|
| Random portfolios that beat the universe's own equal-weight mean | **45.2%** |
| Random portfolios that beat SPY | **68.3%** |
| Excess over the universe mean: 5th / 50th / 95th percentile, pooled | −14.6 / −1.0 / +17.5 points |
| 5th–95th spread, pooled over all windows | 32.1 points |
| 5th–95th spread **within** one window: median (min – max) | **28.1** (16.2 – 113.5) points; above 30 in 44% of windows |

How often a *random* ten-stock portfolio produced the gaps shown in the videos (mean over 236 windows):

| One-year result | vs SPY | vs the universe mean |
|:--|--:|--:|
| ahead by ≥ 3 points | 54.3% | 31.8% |
| ahead by ≥ 13 points | 17.0% | 8.3% |
| ahead by ≥ 22 points | 6.2% | 3.2% |
| behind by ≥ 8 points | 8.2% | 19.0% |

"Three of four portfolios beat the index": 31.3% if each is a coin flip; **62.2%** using the
measured 68.3% chance that a random draw from this list beats SPY.

**Why 68% beat SPY — read this before quoting it.** `U-LARGE100` was chosen in 2026, so every
name in it survived and grew to be large. Any ten of them, back-tested, is drawn from winners. That
is not a finding about stock picking; it is survivorship, and it is exactly the trap in back-testing
a list of companies you have heard of today. The fair benchmark is the universe's own mean: 45.2%.

## 3. Part 2 — what the chatbots actually pick ("now" prompt, 3 models × 10 fresh runs)

| Model | Replies naming stocks | Declined |
|:--|--:|--:|
| Haiku 4.5 | 0 / 10 | 10 |
| Sonnet 5 | 1 / 10 | 9 |
| Opus 5 | 10 / 10 | 0 |

**19 of 30 replies declined to name any stock.** Everything below rests on 11 replies — ten from one
model.

- **Stability:** mean pairwise Jaccard overlap 0.535 over all 11; 0.603 within Opus; 0.229 between
  Opus and the single Sonnet reply.
- **What it picks:** AVGO, LLY and TSM in 11 of 11 replies; AMZN, GEV and JPM in 10; GOOGL in 9.
- **Tilt:** in-universe picks sit at the **73.9th** percentile of trailing 36-month return (95%
  interval 71.6–76.5) and the 59.4th on 12 months (56.5–62.6), as of 2026-08-28. 50 = no tilt.
- 32.7% of picks (36 of 110) fall outside the universe (TSM, GEV, MELI, VRT …) and are excluded
  from the tilt measure.

All 11 replies that named stocks also said, unprompted, that most professional managers fail to
beat the index.

## 4. Part 3 — hindsight ("It is January 2, 2019 …", 3 models × 10 runs)

Haiku declined 10 of 10. Sonnet and Opus answered 20 of 20 — and **all 30 replies said, in their
own words, that they know what happened after 2019** and cannot give a blind answer.

The 20 sets of picks, held 2019-01-02 → 2023-12-29, against 10,000 random portfolios of the same
size from the 98 names available that day:

| | Mean percentile | 95% interval | n |
|:--|--:|:--|--:|
| Pooled | **94.3** | 91.2 – 97.1 | 20 |
| Opus 5 | 93.2 | 87.7 – 98.6 | 10 |
| Sonnet 5 | 95.4 | 92.7 – 97.9 | 10 |

Fifteen of the 20 land above the 96th percentile. A typical list: MSFT, AMZN, AAPL, GOOGL, V, MA,
NVDA, ADBE, NFLX, CRM.

## 5. Pre-registered hypotheses — scored

| | Prediction | Result | |
|:--|:--|:--|:--|
| H1 | Random portfolio beats the universe mean in 40–55% of draws | 45.2% | met |
| | 5th–95th spread of one-year excess return exceeds 30 points | 32.1 pooled · **28.1 median within-window** | **not cleanly met** — the pre-registration did not say which; the per-window figure is the fairer reading of "one draw, one year", and it falls short |
| | "3 of 4 beat the index" ≈ 31% by coin flip | 31.3% analytic; 62.2% at the measured rate vs SPY | met (and understated) |
| H2 | Mean Jaccard ≥ 0.4 and picks at or above the 65th percentile on trailing 36-month return | 0.535 and 73.9 | met — **on 11 replies, 10 from one model** |
| H3 | Back-dated picks average at or above the 90th percentile of random portfolios | 94.3 (91.2–97.1) | **met** |

What would have supported the claim: spread under 10 points — measured 28–32, **not met**;
Jaccard < 0.2 and tilt within 45–55 — **not met**; back-dated picks within the 35th–65th
percentile — **not met**.

None of the claim-supporting conditions is met; one clause of ours is not cleanly met →
**`NOT SUPPORTED`**.

## 6. What can and cannot be said

Can be said:

- One ten-stock portfolio, one year: the middle 90% of pure-luck outcomes spans about 28 points in
  a typical year. Finishing 13 points ahead of the index happens to a random portfolio about one
  time in six (17.0% vs SPY). One run per chatbot cannot separate skill from that.
- Asked the video's exact prompt 30 times, these chatbots declined 19 times. When one did answer,
  it named largely the same recent winners every time (73.9th percentile on three-year return).
- Asked to pick "as of 2019", the chatbots landed at the 94th percentile — and every one of the 30
  replies said it could not un-know the future. Back-testing a chatbot's picks over any period
  inside its training data measures memory.
- Back-testing any list of *today's* well-known companies flatters it: random draws from such a
  list "beat SPY" 68% of the time.

Cannot be said:

- That chatbot picks will underperform. **No forward performance was measured — it cannot be;
  the year has not happened.** That is the content of sub-claim (c), not a gap in the test.
- Anything about other vendors' chatbots. Refusal rates, overlap and tilt are for three Claude
  models in September 2026.
- That the picks are *bad*. A momentum tilt toward large recent winners has been a reasonable
  portfolio at times. It is a well-known factor, available without a chatbot; it is not an
  independent forecast.
- H2's stability figure is one model's consistency with itself plus one reply from another.

## 7. Reproduce

```bash
cd docs/Research/RES008_exposing_fraud
.venv/bin/python -m pytest C08_chatbot_stock_picks/code -q
for s in 02_random_portfolios 03_parse_picks 04_analyse_picks 05_build_results 06_gap_table; do
  .venv/bin/python C08_chatbot_stock_picks/code/$s.py; done       # ≈ 4 min
```

`01_ask_chatbots.py` re-asks the chatbots; replies are not deterministic, so the 60 collected
replies are committed under `out/responses/` and the analysis runs from those.
Figures: `out/random_portfolio_spread.png`, `out/hindsight_percentiles.png`.
