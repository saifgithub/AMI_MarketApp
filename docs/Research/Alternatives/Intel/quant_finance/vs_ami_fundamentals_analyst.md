# Fundamentals data: quant_finance research vs AMI Trade's Fundamentals Analyst

Both pipelines send fundamentals to an LLM. This compares what actually goes into the prompt.

**Sources:** their side — [`scripts/fundamentals_llm2.py`](scripts/fundamentals_llm2.py) (`build_brief`, `from_yfinance`, `from_openbb`).
Our side — `backend/app/services/fundamentals.py` (`fetch_live_fundamentals`, `fetch_statement_facts`) +
`backend/app/services/room_prompts.py` (`_format_profile`, fundamentals lane) +
`content/agents/fundamentals_analyst.md`.

---

## Provider reality check

**Verified 2026-08-17** (challenged, then checked against source and a live test — see
[`VERIFICATION.md`](VERIFICATION.md) for full evidence). Their script calls OpenBB with
**`provider="yfinance"`** on every endpoint (`metrics`/`income`/`balance`/`cash`). This is confirmed to
genuinely be the `yfinance` PyPI package, not an independent vendor: `openbb-yfinance`'s own dependency
list requires `yfinance`, and every fetcher in `openbb_yfinance/models/*.py` does `from yfinance import
Ticker` and calls a real `yfinance.Ticker` method — same installed package, same session.

The AAPL numbers originally cited as evidence of "materially different numbers for nominally the same
source" (`totalDebt` $84.34B vs $98.66B, cash $62.40B vs $35.93B) are **not parsing/schema divergence**.
The debt figure is an annual-vs-quarter default-period mismatch: their script calls OpenBB's `balance()`
with no `period` argument, silently defaulting to `period="annual"` (FY2025), while the raw-`yfinance` side
reads `.info` (current quarter). Live re-test confirmed same-period figures agree almost exactly
($84.34B/$84.71B on adjacent quarters vs $98.66B annual FY2025 — matching OpenBB's default output). The
cash figure was not independently re-checked and shouldn't be cited either way without doing so.

Our side is single-source: raw `yfinance` only (`.info` snapshot + `quarterly_income_stmt`/`quarterly_cashflow`).
No OpenBB, no Alpha Vantage, no internal fundamentals DB in the live path (confirmed in code comment,
`fundamentals.py:363–369`).

---

## What we send that they don't

| Field | Where |
|---|---|
| Analyst consensus — rating, target mean/median/high/low, opinion count | `analyst_consensus_line` |
| Next earnings date + quarter + consensus EPS estimate | `room_runner.py` via `market_data.py::YfinanceProvider.earnings()` |
| Ownership — institutional %, insider %, shares out, float | `ownership_line` |
| Margin trend YoY (bps), gross/operating/net | `margin_trend_line`, from `quarterly_income_stmt` |
| Buybacks TTM + yield | `buyback_line`, from `quarterly_cashflow` |
| Per-field live/not-available provenance gate (CR104) | `field_state` in `room_runner.py` — a missing field renders as "not available," never fabricated |
| Point-in-time backtest path (SEC EDGAR facts) | `edgar_pit.py::fetch_pit_fundamentals()` |
| Lane separation — fundamentals vs market/news/social split across 4 specialist agents | `_AGENT_LANES`, `room_prompts.py:1133` |

The EDGAR point-in-time path is worth flagging specifically: their `README.md` §Blocked calls fundamentals
backtesting **"impossible with free data... needs a point-in-time database (Sharadar/Compustat/SimFin)"**.
We already have a working point-in-time source for the backtest/as-of path — it just isn't wired into their
research script, which only uses live `yfinance`/OpenBB.

## What they send that we don't

| Field | Where |
|---|---|
| Full filed statements — 5 periods × 40/70/54 fields, income/balance/cash | `render_statements()`, OpenBB |
| Explicit cross-source verification block — 12 ratio checks + 2 balance-sheet checks, tolerance-based, disagreements surfaced to the model | `cross_verify()`, `CHECKS`/`BALANCE_CHECKS` |
| Market context bundled into the same brief — 1M/3M/12M returns, annualized vol, 52w high/low position, price vs 200d MA | `market_context()` |
| Price/Book | `priceToBook` in `build_brief` |

We only extract two narrow *derived deltas* from quarterly statements (margin trend, buyback TTM) — no raw
line items ever reach the prompt. `fundamentals_analyst.md:54–59` makes this a stated, deliberate scope
limit: the persona is told to say "not available" if asked for a statement line item or multi-period trend,
rather than estimate one. Their script sends the actual statement rows.

Our market-context equivalent (52-week range) is intentionally lane-gated to the Fundamentals Analyst; the
rest (RSI, trend, volume, ranges) is explicitly **out of lane** for this agent — see the persona's own
"Not in your lane this call" line — and lives with the Market Analyst instead. Theirs bundles everything
into one brief because it's a single-agent script, not a 12-agent room with lane firewalls.

## Convergent finding

Both projects independently hit the same `yfinance` quirk: `debtToEquity` is reported as a percent-like
number (needs /100). We fix it with a documented divide (`fundamentals.py`, comment: `# divided by 100
(yfinance reports it *100)`). They handle it structurally — `cross_verify()` explicitly tolerates "a pure
100x unit difference (fraction vs percent)" before flagging a real conflict. Independent confirmation the
quirk is real, not a one-off parsing bug on either side.

## Worth considering

1. **Cross-verification has no equivalent here — as a structural point, not because of the AAPL example.**
   CR104's live/not-available gate catches *missing* data, not *disagreeing* data — that distinction still
   holds. But the AAPL debt/cash figures don't demonstrate it: per the correction above, that specific case
   was a period-basis artifact in their own comparison code (annual vs quarter), not a genuine cross-source
   disagreement a single-source pipeline would miss. A real example of cross-verification catching something
   ours can't — one where the two sources are on the same basis and still disagree — hasn't been shown yet.
2. **Full filed statements would close a stated gap.** The Fundamentals Analyst is currently instructed to
   refuse multi-period/line-item questions. OpenBB's `metrics`/`income`/`balance`/`cash` endpoints work
   key-free with the yfinance provider (no FMP/Intrinio key needed) and would answer them.

Neither is proposed as a CR — flagging for a call, not filing one.
