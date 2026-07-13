# DEF053 — Fundamentals Analyst prompt oversells its real scope, one field is always fake

**Status:** open · **Filed:** AT:R58 · **Date:** 2026-07-13
**Source:** prompt — split out of CR033 (filed AT:R57, docs-only) into an individual Defect
at Saiful's request, so each of the four remaining agent-truthfulness gaps can be tackled
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

- [ ] Investigated whether Alpha Vantage (already-provisioned key) can supply P/S,
      EV/EBITDA, FCF yield, a real sector/peer P/E, or forward guidance — finding
      documented either way (source verified against the live API, not assumed from docs).
- [ ] `sector_pe` is either wired to a real source or the claim is dropped from the
      prompt/profile — no longer an always-fake `rng.uniform(15, 25)` regardless of
      `use_real_market_data`.
- [ ] `content/agents/fundamentals_analyst.md` rewritten to match actual delivered scope
      exactly — no claims of full financial statements / capital allocation history /
      forward guidance / peer comparison unless genuinely wired this session.
- [ ] Graceful degradation preserved: any newly-added source follows the same
      never-raises + synthetic-fallback contract as the rest of `fetch_live_fundamentals()`.
- [ ] Regression tests updated to reflect the corrected scope/claims (and any new
      wired field, if Step 1 turns one up).
