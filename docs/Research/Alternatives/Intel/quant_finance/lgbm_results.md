# LightGBM Price-Movement Prediction — Test Results

**Tested 2026-08-15.** Real data (yfinance), real walk-forward validation, 13 tickers daily + 3 tickers intraday.
Scripts: [`scripts/lgbm_baseline.py`](../scripts/lgbm_baseline.py) (daily), [`scripts/lgbm_intraday.py`](../scripts/lgbm_intraday.py) (intraday).

## Method

- **Model:** LightGBM classifier (400 trees, lr 0.03, 15 leaves, depth 5, subsample+colsample regularised).
- **Label:** direction of forward return, close[t] → close[t+h].
- **Validation:** 5-fold expanding-window walk-forward, strictly chronological, with a **purge gap of `h` bars** between train and test so training labels cannot overlap the test window.
- **Features (~45):** lagged returns, MA relationships, realised vol, volume, RSI/stochastic/Bollinger, 52-week position, calendar; plus cross-asset SPY/VIX/BTC (reindexed + forward-filled only — never back-filled).
- **Baseline:** majority class computed on **train only** (stocks drift up, so this is usually "up").

## Independent leakage audit (and one real bug found)

A separate agent audited both scripts for lookahead bias, including an **injected-signal sanity check**: a synthetic series where the next bar's direction follows the current bar's with 95% probability, pushed through the unmodified `build_features` / `make_label` / `walk_forward` functions.

- **Sanity check PASSED** — daily h=1 recovered **AUC 0.9497**, intraday h=1 bar **AUC 0.9485**, with correct session-boundary resets. This rules out a shift-direction flip, dropna misalignment, or leaky/shuffled splits: *when real signal exists, this pipeline finds it at AUC ~0.95*. The near-0.50 results on real market data are therefore mechanically trustworthy.
- `make_label`, the dropna interaction, the walk-forward purge, and the intraday `groupby`/`transform`/`shift` pattern were all confirmed correct. SPY and VIX are clean (both close 20:00 UTC, contemporaneous with the ticker).

**Confirmed bug — BTC timezone leak** (`lgbm_baseline.py`, cross-asset block): a 24/7 asset's daily bar is *not* contemporaneous with a US equity's on the same calendar date. BTC-USD's date-D close aggregates through end-of-UTC-day (~21:00–23:00 UTC), **4–8 hours after** the 20:00 UTC NYSE close — verified by matching BTC's 2026-08-10 daily close (63910.59) to its 21:00 UTC hourly bar (63910.42). So unlagged `btc_*` features at row D encoded part of the overnight window the h=1 label predicts. **Fixed** by lagging BTC one day; SPY/VIX need no lag.

**Effect of the fix (measured, not assumed):**

| Horizon | AUC pre-fix | AUC post-fix | Δ |
|---|---|---|---|
| 1 day | 0.5162 | 0.5107 | **−0.0055** (p weakened 0.0015 → 0.0490) |
| 5 days | 0.5186 | 0.5190 | +0.0004 |
| 10 days | 0.5332 | 0.5345 | +0.0013 |
| 20 days | 0.5485 | 0.5528 | +0.0044 |

The leak bit precisely where theory predicts — the 1-day horizon — and its significance nearly collapsed there. Other horizons moved within noise (paired t-test on the change: t=0.10, **p=0.920**). **The bug was real but does not explain the headline result**; the 20-day signal is unchanged and still strong.

## Headline results — daily (post-fix, authoritative)

| Horizon | Mean AUC | p vs 0.50 | Mean edge vs baseline | Cells with negative edge |
|---|---|---|---|---|
| 1 day | 0.5107 | 0.0490 | −0.0198 | 7/8 |
| 5 days | 0.5190 | 0.0066 | −0.0466 | 8/8 |
| 10 days | 0.5345 | 0.0026 | −0.0563 | 8/8 |
| 20 days | **0.5528** | **0.0005** | −0.0448 | 7/8 |

(8-ticker batch: MSFT, GOOGL, AMZN, META, TSLA, WMT, JNJ, KO. A separate 5-ticker batch — AAPL, NVDA, JPM, XOM, SPY — was weaker, AUC 0.483–0.537, all edges negative.)

**Overall: AUC 0.5292, t=6.83, p<0.0001 — but edge negative in 30/32 cells.**

## The central finding: real ranking signal, no usable classification edge

These two facts are both true and are not contradictory:

1. **AUC is significantly above 0.50.** The model has genuine, statistically detectable ability to *rank* which periods are more likely to be up. This is not noise — p=0.0005 at the 20-day horizon, and it survives both the BTC-leak fix and an independent leakage audit.
2. **Accuracy is consistently WORSE than "always predict up".** Because stocks rise ~59–63% of 20-day windows, the naive baseline scores ~0.63 while the model's accuracy is ~0.54.

The model knows something, but not enough to beat the market's upward drift as a binary classifier. A weak ranking signal (AUC 0.55) is only monetisable through mechanisms that exploit *ordering* — relative position sizing, long/short spreads, ranking a cross-section of tickers — not through "will this go up, yes/no".

**Controls:** the effect survives (a) removing cross-asset features entirely (AMZN 20d: 0.576 → 0.553), and (b) fixing the confirmed BTC timezone leak (see audit section — 20d AUC actually *rose* to 0.5528). It is not a forward-fill artifact.

## Headline results — intraday

42 cells across 1m / 5m / 15m / 30m bars, horizons 1 min → 120 min, on AAPL / NVDA / SPY.
Overnight gaps excluded from labels; rolling windows computed within-session and auto-scaled to session length.

| Horizon | Mean AUC | Mean edge |
|---|---|---|
| 1 min | 0.5108 | +0.0026 |
| 5 min | 0.5006 | −0.0050 |
| 15 min | 0.4994 | −0.0037 |
| 30 min | 0.5135 | +0.0036 |
| 60 min | 0.5129 | +0.0077 |
| 120 min | 0.5106 | +0.0019 |

**Intraday is indistinguishable from noise:**
- Positive edge in **21/42** cells — binomial p = **1.000** vs a coin flip. Exactly chance.
- Mean AUC 0.5081, t-test vs 0.50: **p = 0.069** (not significant).
- Cells with AUC > 0.55: **4 observed vs ~6–10 expected by chance** across 42 tests — *fewer* than multiple-testing alone predicts.
- Best cell (NVDA 1m bars / 30 min horizon, AUC 0.5721) is a **multiple-testing artifact**, not a finding.

## Answer: what time horizon?

**Longer is better, and the trend is monotonic.** Daily AUC rises 0.511 (1d) → 0.519 (5d) → 0.535 (10d) → **0.553 (20d)**, while everything below one day collapses to noise.

Ranked:
1. **20 trading days (~1 month)** — best and most statistically robust (p=0.0005). *Recommended horizon.*
2. **10 days** — second best (p=0.0026).
3. **5 days** — weak (p=0.0066). **1 day is marginal** (p=0.049) and was the horizon most contaminated by the BTC leak — treat with suspicion.
4. **Minutes to hours — dead.** No signal survives; at these horizons price movement is dominated by microstructure noise and the bid-ask spread would consume any theoretical edge many times over.

Intuition for why: short-horizon moves are near-random microstructure; longer horizons let slower, genuinely predictable effects (volatility regimes, mean reversion from 52-week extremes, momentum) accumulate above the noise floor.

**Note the tradeoff:** longer horizons also mean fewer independent observations and slower feedback — a 20-day model produces ~12 non-overlapping predictions per year per ticker.

## Most important features (20-day horizon, by gain)

`vol_60d`, `pct_off_52w_low`, `month`, `px_over_ma200`, `btc_vol20`, `spy_vol20`, `vix_vol20`, `ma20_over_ma50`

Volatility and position-relative-to-range dominate — *not* short-term price momentum. Cross-asset volatility (BTC/SPY/VIX) ranks highly, consistent with the regime-aware LightGBM literature. `month` ranking 3rd is a mild overfitting smell worth watching.

## Honest caveats

- **No transaction costs, slippage, or borrow costs** are modelled anywhere. Any apparent intraday edge would be erased several times over by spread alone.
- **AUC ≠ profit.** Ranking ability must be converted into position sizing to be worth anything, and that conversion is where most of the difficulty actually lives.
- **Survivorship bias:** all 13 tickers are current large-caps that demonstrably survived 2015–2026. Companies that went to zero aren't in the sample.
- **Single hyperparameter set**, no tuning — tuning against these same folds would inflate results.
- 5-fold walk-forward on 13 tickers is a modest sample; the two ticker batches disagreed noticeably (0.483–0.537 vs 0.510–0.577), so per-ticker variance is large.

## Model shootout — does combining tools help? (No.)

20-day horizon, 8 tickers, 5 folds, 40 matched cells per model. Script: [`scripts/model_shootout.py`](../scripts/model_shootout.py).

| Model | AUC | Accuracy | p vs LightGBM |
|---|---|---|---|
| Ens: GBM+linear | 0.5556 | 0.5411 | 0.51 |
| Ens: 3×GBM avg | 0.5541 | 0.5412 | 0.46 |
| CatBoost | 0.5533 | 0.5485 | 0.85 |
| **LightGBM** | **0.5523** | 0.5404 | — |
| Ens: 5×Tree avg | 0.5514 | 0.5495 | 0.76 |
| XGBoost | 0.5499 | 0.5427 | 0.45 |
| RandomForest | 0.5412 | 0.5605 | 0.14 |
| ExtraTrees | 0.5356 | 0.5913 | 0.10 |
| **Logistic (linear)** | **0.5308** | 0.5392 | **0.12** |
| Dummy (majority) | 0.5000 | 0.5870 | 0.0005 |
| **CONTROL: shuffled y** | **0.4969** | 0.5698 | 0.002 |

1. **Negative control passed** — shuffled labels → 0.4969. Harness is clean.
2. **Ensembling adds +0.003 AUC — nothing** (p=0.51). No model differs significantly from LightGBM.
3. **Logistic regression ties LightGBM** (0.531 vs 0.552, p=0.12). The available signal is **essentially linear**; boosting/stacking buys nothing.

This is a **data ceiling, not a model ceiling.** Adding model classes (AutoGluon, TFT, N-BEATS, LSTM) cannot fix it — when a linear model already ties the best GBM, there is no complex structure left to extract.

## Cross-sectional ranking test — the decisive experiment

Single-ticker models failed because upward drift makes "always up" a ~60/40 baseline. The standard fix is to predict **relative** performance: *does ticker i beat the cross-sectional median over the next 20 days?* That label is 50/50 by construction, so the baseline is a true 0.500 and market beta is stripped out.

Panel: 32 large-caps × 2,891 dates = **92,512 rows**, walk-forward by date. Script: [`scripts/cross_sectional.py`](../scripts/cross_sectional.py).

| Fold | AUC | Q5−Q1 spread | Top quintile | Bottom quintile | Universe |
|---|---|---|---|---|---|
| 1 | 0.4707 | **−0.61%** | +1.33% | +1.94% | +1.46% |
| 2 | 0.5335 | +2.20% | +3.42% | +1.22% | +1.70% |
| 3 | 0.4980 | −0.06% | +1.59% | +1.65% | +1.62% |
| 4 | 0.5116 | +0.24% | +2.50% | +2.27% | +2.34% |
| 5 | 0.5139 | +1.38% | +2.51% | +1.14% | +1.71% |

- **Mean AUC 0.5055, p = 0.6231** — indistinguishable from random against a true 0.500 baseline.
- **Mean spread +0.63% per 20 days, p = 0.2849** — not significant. Positive in only 3/5 folds, with fold 1 actively negative and a fold-to-fold std of 1.14pp against a 0.63pp mean.
- Cost sensitivity: at 10bp/leg plus short borrow, the spread drops to ~+0.15%/period — inside the noise band.

### Why this matters most

**The single-ticker AUC of 0.5528 did not survive beta removal.** The same features top both models — `vol_60d`, `pct_off_52w_low`, `px_over_ma200`, `btc_vol20`, `vix_vol20` — and these are **market-regime indicators, not stock-specific ones**. They describe what the whole market is doing, so they cannot discriminate *between* stocks.

The honest reading: the measured 0.55 AUC was mostly **market-regime/beta timing**, not stock-selection skill. And beta timing is precisely what the always-up baseline already captures for free — which is exactly why edge was negative in 30/32 single-ticker cells. The two results are the same fact viewed twice.

Both routes are therefore blocked:
- **Predict absolute direction** → real AUC, but upward drift beats you.
- **Predict relative direction** → drift removed, but the signal vanishes with it.

## Fundamentals: blocked by data, not code

The original plan included P/E, ROE, FCF, D/E features. Not feasible here:
- yfinance's free tier returns only **5–7 quarters** of fundamentals (back to ~2025-03), not the 2015–2026 span the walk-forward needs.
- yfinance serves **restated** figures. Using them at historical dates is severe lookahead bias.

Proper fundamentals backtesting requires a **point-in-time** database (Sharadar, Compustat, SimFin, FMP). That is a paid-data problem, and no amount of modelling works around it.

## Verdict

LightGBM works as a tool and the pipeline is sound (validated by an injected-signal test recovering AUC 0.95, and a shuffled-label control landing at 0.497), but **no configuration tested produces a usable edge**:

- **Best horizon is 20 trading days** — AUC 0.5528, p=0.0005. Sub-daily is pure noise (binomial p=1.000).
- **Model choice is irrelevant.** Logistic regression ties LightGBM; ensembling adds +0.003 AUC. Data ceiling, not model ceiling — so deep models (TFT/N-BEATS/LSTM/AutoGluon) cannot rescue it.
- **The apparent signal is market-regime timing, not stock selection.** It vanishes (AUC 0.5055, p=0.62) once beta is stripped via cross-sectional ranking, and the top features are market-wide volatility/range indicators in both setups.
- **Fundamentals are blocked** by the absence of point-in-time data.

This is what the efficient-market prior predicts, and it is consistent with AlphaPy's own tutorial reporting ~0.61 AUC on an easier target. The productive next step is **better data** (point-in-time fundamentals, alternative data, higher-quality intraday) — not better models.
