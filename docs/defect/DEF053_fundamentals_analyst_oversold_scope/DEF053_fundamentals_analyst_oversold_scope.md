# DEF053 — Fundamentals Analyst prompt oversells its real scope, one field is always fake

**Status:** resolved (AT:R58) · **Filed:** AT:R58 · **Date:** 2026-07-13
**Source:** prompt — split out of CR033 (filed AT:R57, docs-only) into an individual Defect
at Saiful's request, so each of the four remaining agent-truthfulness gaps can be tackled

## Fix (AT:R58)

**Step 1 finding — better than expected.** Checked Alpha Vantage's `OVERVIEW`/`EARNINGS`
endpoints live (confirmed against the real API, not assumed from docs) — but then also
checked yfinance's own `Ticker().info` dict, already the fetch path `fetch_live_fundamentals()`
uses, and it already carries **all of it for free, no key needed**: verified live against
AAPL/MSFT/NVDA/GME —

- `priceToSalesTrailing12Months` → real P/S
- `enterpriseToEbitda` → real EV/EBITDA
- `pegRatio` → real PEG
- `freeCashflow` + `marketCap` → real FCF yield (computed: `freeCashflow / marketCap × 100`)
- `dividendYield` → real dividend yield (None for non-payers, e.g. GME)
- `sector` / `industry` → real classification (not a numeric peer P/E — yfinance has no
  peer-basket P/E to compute one from)
- `targetMeanPrice` + `recommendationKey` → real analyst consensus (labeled as the
  Street's view, never as the company's own guidance)

So this shipped entirely via yfinance, gated only on `settings.use_real_market_data`
(no `ALPHA_VANTAGE_API_KEY` dependency) — reaches every user, not just an
Alpha-Vantage-configured deployment.

**`sector_pe` — dropped, not fixed.** The always-fake `rng.uniform(15, 25)` field is
removed entirely from the synthetic profile, `_format_profile()`, and the
Fundamentals Analyst's scripted-fallback template (which referenced it in
`"...vs sector median ~{sector_pe}x"` — reworded to drop the clause). Real
`sector`/`industry` now carries the peer-context claim honestly, as a category rather
than a fabricated number.

**Bonus, near-zero marginal cost:** `market_data.py`'s `EarningsInfo.eps_estimate` was
already fetched by the earnings overlay (CR023) but never surfaced — now flows into
the profile as `next_earnings_eps_estimate`, a genuine forward consensus EPS tied to
the real upcoming earnings date. Closes part of the "forward guidance" claim with
actual data instead of just the analyst-consensus target price.

**Still not available, explicitly disclaimed (not fabricated):** full financial
statements (income/balance/cash-flow statements) and buyback/M&A history. Neither has
a yfinance `info`-dict field; building either would mean parsing separate statement
endpoints — out of scope for this Defect, noted in `fundamentals_analyst.md` so the
agent says so rather than estimating.

`content/agents/fundamentals_analyst.md` rewritten to describe the real (now richer)
scope: real valuation multiples (P/E, P/S, EV/EBITDA, PEG, FCF yield), real
sector/industry category, real dividend yield, real analyst consensus + forward EPS
estimate — and an explicit "financial statements not available" disclaimer.

12 new tests across `test_fundamentals.py` (+4: real fields present, absent when
missing, negative FCF + no-dividend + no-rating degradation, `build_live_data_block`
formatting) and `test_room_runner.py` (+8: `sector_pe` key gone, each new
`_format_profile()` helper line present/absent, forward EPS estimate). Backend suite
697 → 709, all green. Full
submission: [`audit/handshake/cr/DEF053.architect.md`](../../../audit/handshake/cr/DEF053.architect.md).
and closed one at a time instead of as one bundled CR.

## Problem

`content/agents/fundamentals_analyst.md` claims: "Financial statements (income, balance
sheet, cash flow)," "Earnings history and forward guidance," "Valuation multiples (P/E,
P/S, EV/EBITDA, FCF yield)," "Peer comparisons," "Capital allocation history (buybacks,
dividends, M&A)."

What's actually delivered via `fetch_live_fundamentals()` (real, via yfinance, when
configured): current price, trailing P/E only (not P/S or EV/EBITDA or FCF yield —
`fcf_margin` is a profit-margin proxy, not a valuation multiple), TTM revenue growth %,
profit margin %, net cash, 52-week range, and (since CR023, AT:R57) next earnings date.
Real, but narrower than claimed.

**Always fake, regardless of settings**: `sector_pe` (`room_runner.py:231`, the one
peer-comparison figure) is `rng.uniform(15, 25)` — never real, even when
`use_real_market_data` is on and every other fundamentals field has been overlaid with
live yfinance data. No forward guidance figures exist. No capital allocation history
(buybacks/dividends/M&A) exists anywhere in the pipeline. No full financial statements —
just the handful of scalar ratios above.

## Root cause

The prompt was authored describing the Fundamentals Analyst's conceptual role (matching
the original TradingAgents framework's ambition) before the actual yfinance-backed
scalar-ratio implementation landed, and was never revised down to match what actually
shipped. `sector_pe` was left as a leftover synthetic-scaffolding field from before
`fetch_live_fundamentals()` existed, and nothing has ever overlaid it since — an
oversight, not a deliberate placeholder (every other overlappable field in the same
function does get overlaid; this one field alone was missed).

## Fix

**Step 1 — check before assuming a new provider is needed.** `ALPHA_VANTAGE_API_KEY`
(already provisioned per CR023, already live on Alpha) may expose sector/peer P/E, P/S,
EV/EBITDA, FCF yield, or forward guidance via its `OVERVIEW` or `EARNINGS` endpoints —
verify against the real live API response (same discipline CR023/CR024 used: confirm the
actual response shape before writing any client code) before concluding nothing more is
achievable without a new integration.

**Step 2 — `sector_pe`:** if Alpha Vantage (or another already-available source) can
supply a real sector/peer P/E, wire it in following the same overlay pattern as the rest
of `fetch_live_fundamentals()`. If not achievable without new infrastructure, drop the
`sector_pe` claim from the prompt/profile rather than continuing to fabricate it — a
Fundamentals Analyst comparing to a fake peer multiple is worse than one that doesn't
claim a peer comparison at all.

**Step 3 — prompt rewrite.** `content/agents/fundamentals_analyst.md` rewritten to
describe the actual scope delivered — the scalar ratios listed above, not full financial
statements, not forward guidance, not capital allocation history — unless Step 1 turns up
a real source for any of these, in which case the prompt claims exactly what's wired and
nothing more.

## Acceptance

- [x] Investigated whether Alpha Vantage (already-provisioned key) can supply P/S,
      EV/EBITDA, FCF yield, a real sector/peer P/E, or forward guidance — finding
      documented (verified against the live API), then superseded by a cheaper free
      source: yfinance's own `info` dict already has P/S, EV/EBITDA, PEG, FCF
      (computed), sector/industry, dividend yield, and analyst consensus — no
      Alpha Vantage key needed.
- [x] `sector_pe` is either wired to a real source or the claim is dropped from the
      prompt/profile — dropped entirely (no genuine peer-basket P/E exists to wire);
      real `sector`/`industry` classification carries the peer-context claim honestly.
- [x] `content/agents/fundamentals_analyst.md` rewritten to match actual delivered
      scope exactly — real valuation multiples, sector/industry, dividend yield,
      analyst consensus + forward EPS estimate now claimed; full financial statements
      and buyback/M&A history explicitly disclaimed as unavailable.
- [x] Graceful degradation preserved: all new fields use the same `_num()`/`.get()`
      None-checks as the existing fields — missing data is omitted, never fabricated
      or crashing.
- [x] Regression tests updated to reflect the corrected scope/claims and the new
      wired fields (yfinance, not Alpha Vantage).
