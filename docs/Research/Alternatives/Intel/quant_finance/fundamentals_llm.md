# Fundamentals Analysis → LLM Interpretation

**Built and tested 2026-08-15.** Working pipeline: [`scripts/fundamentals_llm.py`](../scripts/fundamentals_llm.py)

This is the actual goal: **gather fundamental data and have an LLM interpret it.** Not prediction. The earlier prediction experiments ([lgbm_results.md](lgbm_results.md)) established that forecasting price from this data does not work — but *interpreting the financial condition of a business* is a different and far more tractable task, and it works well.

**Key unblock:** the point-in-time data problem that killed the backtesting effort **does not apply here**. Point-in-time data is only needed to avoid lookahead bias when backtesting. For "analyse this company as it stands today," current fundamentals are exactly right.

## Recommendation

| | Use it when | Reality |
|---|---|---|
| **yfinance** (recommended now) | Today, for this use case | Free, no API key, **24/24 key ratios available**, 4 periods of statements. Already working. |
| **OpenBB Platform 4.7.2** | When you outgrow the above | Free core, **richer**: income 40 fields × 5 periods, balance 70 × 5, cash 54 × 5, metrics 35. Normalised schema, provider-swappable. |

**Verdict: start with yfinance, keep OpenBB as the upgrade path.**

The deciding factor for OpenBB is *later*, not now: its `equity.fundamental.ratios` endpoint requires an `fmp` or `intrinio` API key (verified — the `yfinance` provider is rejected there). But `metrics`, `income`, `balance`, `cash`, and `profile` all work key-free with the yfinance provider, returning **more fields and more periods** than raw yfinance. So if you later pay for FMP, the same OpenBB code silently gets better data — including the point-in-time history that would reopen backtesting.

Both are installed in `quant_finance/venv` (Python 3.11).

## What the pipeline does

```
yfinance  ->  structured analyst brief  ->  Qwen3.6-35B on :8000  ->  analysis
```

1. **Fetch** — ratios grouped into valuation / profitability / growth / leverage+liquidity / cash flow / scale, plus business description and sector.
2. **Trend context** — the 4 most recent periods of income, balance, and cash flow statements, so the model sees *direction*, not just a snapshot.
3. **Format** — a readable brief (~4.8K chars for one company). Qwen3.6 has a 262K context, so this is comfortable even for large peer sets.
4. **Interpret** — sent to the local fleet with an analyst system prompt that requires grounding every claim in the given figures and flagging missing/anomalous ones instead of inventing them.

Runs `/no_think` by default (Qwen3.6 is markedly faster and still accurate for structured analytical work in this mode); `--think` enables reasoning.

## Usage

```bash
cd /opt/saiful/llm_research/quant_finance && source venv/bin/activate

python3 scripts/fundamentals_llm.py AAPL              # single-company analysis
python3 scripts/fundamentals_llm.py AAPL MSFT NVDA    # peer comparison
python3 scripts/fundamentals_llm.py AAPL --raw        # data only, no LLM
python3 scripts/fundamentals_llm.py AAPL --think      # enable reasoning mode
```

**Measured performance:** 45s single company, 65s for a 3-company peer comparison, against `ami-llm` (Qwen3.6-35B-A3B-NVFP4) on port 8000. No fleet changes required — it uses the existing production endpoint read-only.

## Verified output quality

Two things from the live test runs are worth recording, because they show the guardrails working:

1. **It caught a real data inconsistency unprompted.** On AAPL it noticed `totalDebt` from the summary endpoint ($84.34B) disagreed with the balance sheet ($98.66B), flagged the discrepancy explicitly, and reasoned about which source to trust — rather than silently picking one. That is the "flag anomalies rather than invent" instruction working as intended.

   > **Correction, 2026-08-17:** this is yfinance's own current-quarter `.info` vs its own annual
   > `.balance_sheet` — an annual-vs-quarter basis gap, not a genuine inconsistency. Same-period figures
   > agree. The model's instinct to flag it and reason about trust was sound; "inconsistency" is the wrong
   > label for the underlying cause. Evidence: [`VERIFICATION.md`](VERIFICATION.md).
2. **Peer mode produced genuine cross-company reasoning**, not parallel summaries — e.g. surfacing Microsoft's capex jump from $28.11B (2023) to $115.95B, and NVIDIA's implied hyperscaler concentration risk, then ranking the three separately on *quality* vs *growth-adjusted valuation* with the tension between those rankings made explicit.

The system prompt deliberately forbids price prediction and investment advice — it assesses financial condition and business quality only. That is both the honest scope and, per the prediction experiments, the only scope the data actually supports.

## Limitations

- **yfinance data quality is "good enough", not institutional.** The debt discrepancy above is a real example. For anything consequential, verify against filings.
- **No point-in-time history** — this analyses the company *as of now*. Fine for interpretation, unusable for backtesting.
- **Restated figures**: historical statements reflect current restatements, not what was reported at the time.
- **The LLM can still be wrong.** It is interpreting, not auditing. The prompt reduces hallucination by demanding figure citations, but does not eliminate it — spot-check the numbers it quotes.
- Free yfinance endpoints are rate-limited and occasionally flaky; expect intermittent fetch failures on large batches (seen during testing).

---

# v2: Both sources + both models

Scripts: [`scripts/fundamentals_llm2.py`](../scripts/fundamentals_llm2.py) (collector), [`scripts/dual_model_analysis.py`](../scripts/dual_model_analysis.py) (dual-model runner).

The either/or framing above was wrong — yfinance and OpenBB are **complementary**, and using both enables something neither gives alone: **automatic cross-verification**.

- **yfinance** → business summary, sector, employees, beta, FCF, dividend yield, price/book (TTM/MRQ basis)
- **OpenBB** → 4–5 periods of filed income/balance/cash statements, plus `ebitda_margin` which yfinance lacks (annual basis)
- **Both** → the same quantity from two independent sources, so disagreements are surfaced instead of silently trusted

## Dual-model setup

| Model | Port | Context | Mode |
|---|---|---|---|
| Qwen3.6-35B-A3B-NVFP4 (`ami-llm`) | 8000 | 262K | `/no_think` |
| Nemotron-3.5-Lightning-30B-A3B | 8030 | 65K | reasoning on |

Identical brief, identical prompt, temperature 0.3, queried in parallel — so any difference is the *model*, not the input. Where two independent models agree on a reading, confidence is higher; where they diverge, that's a flag to inspect.

```bash
python3 scripts/dual_model_analysis.py AAPL --out report.md
python3 scripts/dual_model_analysis.py AAPL MSFT NVDA
```

**Measured:** Qwen 84s / 1,805 completion tokens. Nemotron 148s / 7,681 tokens. Both ~7K-char answers.

## Three real bugs this process exposed

Running two models against the same data turned out to be an effective *debugging* tool — disagreement between them pointed at defects in the data layer, not just the models.

1. **Wrong OpenBB column names → missing equity.** The collector requested `total_equity` and `total_liabilities`, which **do not exist** in OpenBB's yfinance schema (the real names are `common_stock_equity` and `total_liabilities_net_minority_interest`). They silently rendered as nothing. With equity absent, *both* models tried to derive it as `assets − debt` (wrong — that's `assets − liabilities`), and Qwen concluded the D/E ratio was "mathematically impossible." Fixed; equity, net debt, and liabilities now appear.

2. **Unlabelled mixed bases.** Summary metrics are TTM/most-recent-quarter; filed statements are annual. Nothing said so, so the models read a legitimate basis difference as a data error. yfinance's `debtToEquity` of 78.44 (MRQ) vs the annual 1.34x (133.8%) is a **period mismatch, not a contradiction** — and neither model got this right before the fix. Now every section carries an explicit `[basis: ...]` label, plus a `DERIVED FROM FILED BALANCE SHEET` block computing annual ratios directly.

3. **Nemotron returned an empty answer.** Its reasoning trace is charged against the *same* completion budget as the answer. On the richer v2 brief it consumed all 5,000 tokens thinking and emitted **zero characters** — while still reporting HTTP 200. Fixed with a per-model `token_mult` (3× for Nemotron) *and* an explicit empty-answer check, since a blank success is worse than a visible failure.

## Model comparison

Post-fix, both handle the data correctly, with different characters:

- **Qwen3.6** — faster (84s), more concise. Strong at *internal-consistency adjudication*: it resolved the cash conflict by checking that `$98.66B debt − $35.93B cash = $62.72B` matches the filed net-debt line, concluding OpenBB's cash figure is right and yfinance's `$62.40B` must use a broader definition.
- **Nemotron 3.5 Lightning** — slower (148s), more thorough and better sourced. It correctly attributed the 148.75% ROE to buyback-driven equity compression, traced equity across all four periods ($62.15B → $56.95B → $73.73B), and explained *why* the sources differ (yfinance aggregates marketable securities with cash; OpenBB follows the filed GAAP taxonomy).

> **Correction, 2026-08-17:** the $98.66B debt figure feeding this calculation is OpenBB's default annual
> balance sheet (see the debt correction above) — the "$62.40B must use a broader definition" and
> "sources differ" reasoning is built on a comparison that mixes annual and quarterly figures rather than
> two disagreeing definitions. Both models' reasoning *process* still held up (internally consistent,
> correctly traced) — it's the framing of *why* the numbers differed that needs revising. The cash figure
> itself was not independently re-verified. See [`VERIFICATION.md`](VERIFICATION.md).

**Recommendation:** Qwen for routine/batch runs, Nemotron when the analysis matters, both when you want cross-model agreement as a confidence signal.

## Possible next steps

- Add sector/industry median comparisons so ratios are judged against peers automatically rather than in isolation.
- Swap in OpenBB as the fetch layer for the richer 5-period, 40–70-field statements.
- Add an FMP API key to unlock OpenBB's true `ratios` endpoint and point-in-time history.
- Batch mode: run a watchlist and emit a ranked digest.
- Feed 10-K/10-Q filing text alongside the numbers (the 262K context has ample room).
