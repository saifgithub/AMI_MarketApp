# Research Primer: Tabular GBM & Time-Series Transformers for Financial ML

**Status:** Research only — no setup/install has been done yet. This captures groundwork from 2026-08-14/15 before any actual implementation.

## Background

Started from a description of two candidate approaches for a financial-analysis project:
1. **Tabular Fundamentals & Ratios** — Gradient Boosted Trees (LightGBM/XGBoost/CatBoost) on structured data (P/E, D/E, FCF, ROE).
2. **Time-Series & Macro Trends** — Temporal Transformers (TFT/N-BEATS/LSTM-GRU) on price sequences + macro indicators.

Confirmed via full recursive search that **neither exists anywhere in `/opt/saiful/llm_research` or `/opt/saiful/vllm-gb10-sm121`** — this workspace is entirely local-LLM/VLM serving infra (Gemma, Qwen, DeepSeek, Nemotron, etc.). Any work here would be a from-scratch project.

Two concrete public options were identified and researched in depth:
- **[AlphaPy](https://github.com/ScottfreeLLC/AlphaPy)** — pip-installable AutoML framework with a built-in `MarketFlow` pipeline for GBM models on stock data.
- **[mveen3/TFT_Model_For_Stock_Price_Prediction](https://huggingface.co/mveen3/TFT_Model_For_Stock_Price_Prediction)** — a Hugging Face repo with a Temporal Fusion Transformer trained for next-day Nifty50 return forecasting.

---

## 1. Concept primer — what kind of "training" are we even talking about

| | Gradient-Boosted Trees (AlphaPy) | Temporal Fusion Transformer | LLM (Nemotron/Qwen/Gemma) |
|---|---|---|---|
| **What it is** | Ensemble of decision trees | Neural net w/ attention, built for numeric sequences | Neural net w/ attention, built for text tokens |
| **Input** | One row of numbers per prediction (P/E, RSI, volume ratio...) | A sequence of numbers over time (30-90 days of prices/indicators) | A sequence of text tokens |
| **Output** | One number/class (e.g. "up >2% in 5 days: yes/no") | A forecast trajectory (e.g. next N days' returns) | The next token, repeated into a whole response |
| **Size** | KBs–MBs (hundreds to low-thousands of small trees) | Low millions of parameters | Billions of parameters |
| **How "training" works** | Fit fresh, from scratch, on your labeled dataset — minutes on CPU | Trained (mostly) from scratch per problem domain — no internet-scale pretraining step exists for TFT the way it does for LLMs | Pretrained once on huge text corpora (the expensive part), then optionally fine-tuned/prompted |
| **Transfer learning?** | Basically none — a tree model trained on AAPL doesn't help predict TSLA | Weak/limited — can try applying a checkpoint to new data, but not designed to generalize the way an LLM does | Strong — that's the entire point of a foundation model |
| **Hardware** | CPU is fine | Small GPU helpful, not required | Needs the GB10/vLLM fleet |

**Key takeaway:** AlphaPy and TFT don't have a "pretrained then fine-tune" relationship with anything in the LLM fleet — you're not adapting Nemotron or any other model. You're fitting a small model directly to your data every time. "Training" here means the whole thing, not a fine-tune step. These would be fully separate, independent projects with zero interaction with the vLLM/Nemotron/Qwen fleet.

---

## 2. AlphaPy deep-dive

Legacy AlphaPy (`pip install alphapy`) vs **AlphaPy Pro** (`alphapy-pro`, actively developed): as of the Pro v4.0 restructuring, **MarketFlow/SportFlow were moved into a private repo (`alphapy-finance`)**. Pro's public repo is a generic domain-agnostic ML pipeline core — it does **not** include the stock-market pipeline out of the box. **For actual stock/finance work today, legacy AlphaPy (`pip install alphapy`) is the correct choice.**

### Real example from AlphaPy's official Market Prediction Tutorial

`market.yml`:
```yaml
target_group: test
groups:
  test: ['aapl', 'amzn', 'goog', 'fb', 'nvda', 'tsla']
forecast_period: 1      # predict 1 day ahead
data_history: 500       # 500 days of history
data_fractal: 1d        # daily bars
leaders: ['gap', 'gapbadown', 'gapbaup', 'gapdown', 'gapup']
features: [moving averages, RSI, ADX, volatility, volume ratios, doji/hook patterns...]
```

`model.yml`:
```yaml
target: rrover           # the label column to predict
target_value: True
algorithms: ['RF']       # Random Forest here; swap in XGB/LGBM/CATB
type: classification
cv_folds: 3
estimators: 501
scoring_function: roc_auc
```

Run with: `mflow --pdate 2017-10-01`

Result from AlphaPy's own tutorial run: **~0.61 AUC** on "will today be a larger-than-average range day" — barely-better-than-coin-flip. That's a realistic baseline for short-horizon price prediction with off-the-shelf technical features, not a red flag specific to AlphaPy. Fundamentals (P/E, ROE, FCF) are **not** in the default feature set — would need to be pulled separately (e.g. via `yfinance`) and merged in as extra columns.

Source: [Market Prediction Tutorial](https://alphapy.readthedocs.io/en/latest/tutorials/market.html)

### Install notes — TESTED 2026-08-15, verdict: not practically runnable

Actually attempted install + `mflow --help` in `quant_finance/venv` (Python 3.11, aarch64). xgboost/lightgbm/catboost themselves installed cleanly (that risk is resolved). AlphaPy itself hit **6 sequential, unrelated compatibility breaks**, each only discovered after patching the previous one — clear signature of abandoned software (last release 2020, no updates since):

| # | Blocker | Root cause |
|---|---|---|
| 1 | `configparser.SafeConfigParser` missing | Removed in Python 3.12 (via `pyfolio` dep) — required downgrading to Python 3.11 |
| 2 | `scipy==1.4.1` build fails | Hard-pinned by AlphaPy itself; no aarch64 wheel, fails building from source on modern toolchain — required `--no-deps` install + manually installing modern equivalents |
| 3 | `import parser` fails | Python stdlib `parser` module removed in 3.10+; used non-trivially in `variables.py`/`market_variables.py` for expression validation — patched to `ast.parse(expr, mode='eval')` |
| 4 | `iexfinance` missing | Live paid market-data API dependency, hard-imported at module load regardless of whether it's used |
| 5 | `keras`/`tensorflow` missing | Hard-imported at module load even though the default tutorial config only uses Random Forest |
| 6 | `keras.wrappers.scikit_learn.KerasClassifier`/`KerasRegressor` missing | That API moved to `scikeras` years ago, then changed again under Keras 3 — patch worked for `KerasClassifier` but the identical error recurred immediately on the next line for `KerasRegressor`, with likely more of the same (and probably stale sklearn/matplotlib API usage) still ahead |

Stopped after #6 — an unbounded chase, not a couple of quick fixes. **Conclusion: legacy AlphaPy (2.5.0) is unmaintained and not worth pursuing further.** Use AutoGluon or PyCaret instead (§4) for the tabular-GBM use case — both actively maintained, no equivalent bit-rot risk.

Venv left in place at `quant_finance/venv` (Python 3.11) with the patched AlphaPy for reference if anyone wants to pick the thread back up, but it is **not recommended** as a foundation to build on.

---

## 3. TFT / time-series deep-dive

A Temporal Fusion Transformer uses the same *attention* mechanism idea as an LLM transformer, but applied very differently:
- **LLM attention**: which earlier *words* matter for predicting the next word.
- **TFT attention**: which earlier *time steps* and which *input variables* (price? volume? sentiment?) matter most for the forecast — and it separates **static** context (e.g. "this is a large-cap tech stock") from **time-varying** inputs (daily price/sentiment), a concept vanilla LLMs don't have.

Outputs quantile forecasts (e.g. 10th/50th/90th percentile of next-day return) rather than a single number — useful for expressing uncertainty, unlike classic GBM classifiers.

### The `mveen3/TFT_Model_For_Stock_Price_Prediction` checkpoint specifically
Inspected the actual repo contents (not just the model card) — **it is not a plug-and-play inference model**:
- Contents: `tft_hpt_train_test.py` (101 KB training/hyperparameter-tuning script) + one `window_15/` folder with `checkpoints/`, `metrics.csv`, `state.json`. No inference script, no requirements.txt, no usage example in the README.
- Trained on a narrow feature set: Nifty50 OHLCV-derived technical indicators **plus 3-channel news sentiment (direct/sectoral/global)** across 7/10/15/30-day windows. We don't have their sentiment data source, so the shipped checkpoint can't produce meaningful predictions without reconstructing that exact pipeline.
- MIT licensed. Explicitly "research/educational use... not financial advice."
- **Realistic value:** a reference architecture/implementation to learn from and adapt, not a drop-in forecaster.

**Recommended real path if pursued later:** use `pytorch-forecasting`'s own `TemporalFusionTransformer` class (same one this repo likely wraps) to train a **fresh** TFT on data we can actually source — `yfinance` OHLCV + a macro series (e.g. FRED via `pandas-datareader`) — rather than depending on the un-reproducible sentiment pipeline.

Source: [mveen3/TFT_Model_For_Stock_Price_Prediction](https://huggingface.co/mveen3/TFT_Model_For_Stock_Price_Prediction)

---

## 4. Alternatives worth knowing about before committing

- **[AutoGluon](https://auto.gluon.ai/)** / **[PyCaret](https://pycaret.org/)** — lower-effort than AlphaPy for tabular ML generally (few lines of code vs YAML files), broader community, not finance-specific but easy to point at fundamentals data.
- **[Prophet](https://facebook.github.io/prophet/)** (Meta) — easiest entry point for time-series with trend/seasonality; much simpler mental model than TFT, good first step before deep learning.
- **[Darts](https://unit8co.github.io/darts/)** — one unified API across classical stats models *and* deep models (including TFT, N-BEATS) — lets you start simple (ARIMA) and move to deep learning later without rewriting the pipeline. Probably the best learning vehicle for understanding the TFT approach without depending on someone else's unreproducible checkpoint.
- **[Nixtla statsforecast/mlforecast](https://github.com/Nixtla/statsforecast)** — fastest, most production-oriented, less beginner hand-holding.
- General 2026 guidance: **for small/simple problems, classical stats (ARIMA) still beats deep learning** — deep models like TFT only pull ahead with many series, high-frequency data, or complex seasonality. Worth calibrating expectations accordingly.

Sources: [PyCaret time-series guide](https://mushtaqmsit.substack.com/p/time-series-forecasting-with-pycaret), [Darts vs sktime vs mlforecast](https://piotrpomorski.substack.com/p/darts-vs-sktime-vs-mlforecast-a-no), [2026 time-series tools roundup](https://www.analyticsvidhya.com/blog/2026/06/time-series-forecasting-tools/)

---

## Next steps (not started)
If/when ready to actually build:
- **Part A (AlphaPy):** venv → `pip install alphapy xgboost lightgbm catboost yfinance` → verify aarch64 wheels → follow Market Prediction Tutorial → add fundamentals via `yfinance` → run `mflow`.
- **Part B (TFT):** likely skip the `mveen3` checkpoint itself; use `pytorch-forecasting`'s `TemporalFusionTransformer` fresh on `yfinance` + FRED macro data instead.
- Standard project skeleton (`Model/`, `scripts/`, `tmp/`) to be added at that point, per the `/opt/saiful/llm_research/<name>/{Docs,Model,scripts,tmp}/` convention.
