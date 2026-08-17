# Verification — the AAPL debt/cash "cross-source conflict" claim

**Audited 2026-08-17**, in response to a direct challenge: *"are you sure OpenBB is the same as yfinance?"*

Answer: **half right, half wrong.** OpenBB's `provider="yfinance"` genuinely is built on the `yfinance`
PyPI package — confirmed, not an independent vendor. But the flagship example used throughout this
research (and repeated in our own comparison doc) to demonstrate what dual-sourcing catches — AAPL's
totalDebt $84.34B vs $98.66B, cash $62.40B vs $35.93B — is **not a cross-source data conflict**. It's an
annual-vs-quarter period mismatch, verified live against the same numbers the research originally cited.

---

## What was claimed, where

| Location | Claim |
|---|---|
| [`README.md:101`](README.md) | "Using both enables automatic cross-verification — on AAPL it flags 2 real conflicts (debt $84.34B vs $98.66B; cash $62.40B vs $35.93B) across 12 checked metrics." |
| [`README.md:133`](README.md) | "Nemotron quantified it: the conflict obscures net debt by ~$40B ($21.9B vs $62.7B depending on source)." |
| [`fundamentals_llm.md:52`](fundamentals_llm.md) | "It caught a real data inconsistency unprompted. On AAPL it noticed `totalDebt` from the summary endpoint ($84.34B) disagreed with the balance sheet ($98.66B)..." |
| [`fundamentals_llm.md:107`](fundamentals_llm.md) | "...it resolved the cash conflict by checking that `$98.66B debt − $35.93B cash = $62.72B` matches the filed net-debt line..." |
| [`vs_ami_fundamentals_analyst.md`](vs_ami_fundamentals_analyst.md) (as originally written) | "genuine parsing/schema divergence between two code paths over the same underlying data" |

Note the `fundamentals_llm.md:52` instance is under the **v1** pipeline (`fundamentals_llm.py`,
yfinance-only, no OpenBB at all) — so this discrepancy predates OpenBB entirely.

## What was actually verified

**1. OpenBB genuinely wraps the `yfinance` package — confirmed by dependency chain and source.**
- `pip show openbb-yfinance` (venv on `ami-host`) → `Requires: openbb-core, yfinance`.
- `openbb_yfinance/models/{balance_sheet,income_statement,cash_flow,key_metrics}.py` — every one of the
  four calls `fundamentals_llm2.py` makes does `from yfinance import Ticker` and calls a real `yfinance`
  method: `get_balance_sheet(freq=period)`, `get_income_stmt(freq=period)`, `get_cash_flow(freq=period)`,
  `get_info()`. Same installed package, same Python objects — no independent HTTP scraping.

**2. The debt discrepancy is an annual-vs-quarter default-period artifact, not vendor disagreement.**
- `fundamentals_llm2.py` calls `obb.equity.fundamental.balance(ticker, provider="yfinance")` with
  **no `period` argument**, so it silently gets OpenBB's default: `period="annual"`.
- The raw-`yfinance` comparison side reads `.info`, which reflects the **most recent quarter**.
- Live re-test, same process, 2026-08-17:

  | Source | Period | Total debt |
  |---|---|---|
  | `yf.Ticker("AAPL").info["totalDebt"]` | current quarter (2026-06-30) | $84.34B |
  | `yf.Ticker("AAPL").quarterly_balance_sheet` | 2026-06-30 | $84.34B |
  | `yf.Ticker("AAPL").quarterly_balance_sheet` | 2026-03-31 | $84.71B |
  | `yf.Ticker("AAPL").balance_sheet` (annual) | FY2025 (ended 2025-09-30) | **$98.66B** |
  | `obb.equity.fundamental.balance("AAPL", provider="yfinance")` (default `period="annual"`) | FY2025 | **$98.66B** |

  Matched-period figures agree almost exactly ($84.34B vs $84.71B on adjacent quarters — normal
  quarter-to-quarter movement). The $84.34B-vs-$98.66B "conflict" is comparing a fresh quarter against an
  11-month-old fiscal year-end, not two sources disagreeing about the same fact.
- **Secondary factor, real but minor:** `.info` and the statement calls do hit two different Yahoo Finance
  endpoints inside `yfinance` itself (`quoteSummary` vs `fundamentals-timeseries`) — so even at matched
  periods, small drift is possible. In this live test the same-quarter figures matched within $400K on an
  $84B number — negligible.

**3. Cash figure — not independently re-verified.** $62.40B vs $35.93B was not re-checked in this pass.
Given the debt figure's mechanism, the same annual/quarter default mismatch is the likely explanation, but
that is not confirmed — don't cite it as fixed or as still-a-real-conflict without checking.

## What remains correct and unaffected

- The OpenBB column-name bug (`total_equity`/`total_liabilities` don't exist; real names
  `common_stock_equity`/`total_liabilities_net_minority_interest`) — a separately-verified, real bug, unrelated
  to this correction.
- The `debtToEquity` ×100 unit handling (yfinance reports it as a percent-like number) — unrelated finding,
  still valid.
- The core "OpenBB is not an independent vendor" conclusion in `vs_ami_fundamentals_analyst.md` — correct,
  just for a different reason than originally stated (see correction below).

## Correction made as a result

`vs_ami_fundamentals_analyst.md`'s "Provider reality check" section originally attributed the AAPL numbers
to "genuine parsing/schema divergence between two code paths." Corrected in place to the verified mechanism
(period-default mismatch) — see that file for the current text; this note is the record of why it changed.
