# DEF052 — Market Analyst's technicals are 100% fabricated, prompt claims indicators that don't exist

**Status:** resolved (AT:R58) · **Filed:** AT:R58 · **Date:** 2026-07-13
**Source:** prompt — split out of CR033 (filed AT:R57, docs-only) into an individual Defect
at Saiful's request, so each of the four remaining agent-truthfulness gaps can be tackled

## Fix (AT:R58)

New `backend/app/services/technicals.py` — `compute_technicals(ticker)` (never raises),
pulling `MarketDataProvider.history(ticker, "3m")` (already-cached yfinance OHLCV, the
same feed powering the mobile Ticker Detail chart) and computing:

- **RSI(14)** — standard gain/loss average, real, hand-verified in tests.
- **Trend** — "trading" when price + 20-day SMA + 50-day SMA are directionally aligned
  (a real momentum read), "consolidating" otherwise. Same two-value vocabulary the
  scripted-fallback template's grammar already depended on, now backed by real data
  instead of a coin flip.
- **Volume tone** — last-5-day average vs. last-20-day average, real, replacing another
  coin flip.
- **Support/breakout** — the real min/max of the last 50 candles' low/high, replacing
  `base_price × 0.9` / `× 1.03`.

Wired into `room_runner.py::_profile_for_ticker()` (overlay inside the existing
`if settings.use_real_market_data:` block, alongside fundamentals/news/social) and into
`agent_runner.py`'s 1-on-1 path (Market-Analyst-gated, mirroring the News/Social
gating pattern). `room_prompts.py::_format_profile()`'s disclosure header gained a
technicals category, independent of fundamentals/news/social.

**MACD/Bollinger Bands scope decision:** dropped from the prompt rather than
half-implemented. `content/agents/market_analyst.md` rewritten to describe only what's
actually computed — RSI, a real moving-average trend read, real volume, real recent-range
support/breakout — and explicitly states MACD/moving-average-crossover/Bollinger Bands
are not computed anywhere in the app.

**Also fixed in passing:** the scripted (non-LLM) fallback template
(`_TEMPLATES[AgentId.MARKET_ANALYST]`) claimed `support` came from "the 200-day [MA]"
— a claim the real computation never backs (it's a 50-day recent-range low). Reworded to
"recent support" to match reality — same class of fix as CR024's scripted-fallback
correction for Social.

22 new tests: `test_technicals.py` (13 — RSI/trend/volume/support-breakout hand-verified
against deterministic OHLCV fixtures, graceful degradation on missing/short/erroring
history), `test_room_runner.py` extensions (5 — profile overlay, independence from
fundamentals, disclosure header live/synthetic), `test_one_on_one_market_injection.py`
(4 — Market-Analyst-only gating, mirroring CR023's News-only test). Backend suite
675 → 697, all green. Full submission + adversarial evidence:
[`audit/handshake/cr/DEF052.architect.md`](../../../audit/handshake/cr/DEF052.architect.md).
and closed one at a time instead of as one bundled CR.

## Problem

`content/agents/market_analyst.md` claims: "Indicators: MACD, RSI, moving averages,
Bollinger Bands," "Volume profile," "Support and resistance levels," "Trend
identification." None of it is real, regardless of `use_real_market_data`:

- `room_runner.py::_profile_for_ticker()` (`rsi`, line 242): `rng.randint(35, 75)` —
  always fabricated, never computed from real price history.
- `trend` (line 240, "trading" vs "consolidating"): a coin flip (`rng.random() > 0.5`).
- `volume_tone` (lines 247-248): a coin flip between two hardcoded strings — one of
  which literally says "above 20-day average — **real participation**" while being
  entirely fake.
- MACD, moving averages, and Bollinger Bands don't exist as profile fields **at all** —
  not even a synthetic placeholder. The prompt names three specific indicators the
  pipeline has never had any representation of.
- `support`/`breakout` (lines 241, 246) become price-derived once `fetch_live_fundamentals()`
  overlays a real `base_price`, but the formula is a naive `price × 0.9` / `price × 1.03` —
  not a real support/resistance level from volume profile or price history, even when
  the underlying price is real.

## Root cause

The Room's synthetic profile builder (`_profile_for_ticker()`) predates
`MarketDataProvider.history()` (real OHLCV, added AT:R41 Bundle 2 for the mobile Ticker
Detail chart) and was never revisited to wire a technical-analysis layer over it for
agent consumption. `fetch_live_fundamentals()` (CR007/CR023-adjacent) overlays price/
valuation/earnings fields but was never extended to cover technicals — a different data
shape (time-series OHLCV, not point-in-time scalars) that nobody built the indicator math
for.

**Provider note (from CR033, unchanged):** `yfinance` (already a dependency, already used
for fundamentals/news/earnings, already wired for the chart endpoint via
`MarketDataProvider.history()`) can compute real RSI/MACD/moving averages/Bollinger Bands
from its own OHLCV data. No new external API needed — the raw price series is already
flowing; this is a computation layer, not a new integration.

## Fix

New `backend/app/services/technicals.py` (never-raises contract, matching
`fetch_live_fundamentals()`/`fetch_live_news()`/`fetch_live_sentiment()`'s pattern):

```python
def compute_technicals(ticker: str, period: str = "3m") -> Technicals | None:
    """Real RSI/trend/volume/support-resistance from yfinance OHLCV. Never raises."""
```

Pulls `MarketDataProvider.history(ticker, period)` (already exists, already cached) and
computes:
- **RSI** (standard 14-period, Wilder's smoothing or simple average of gains/losses).
- **Trend** from a real moving-average relationship (e.g., price vs. 20/50-day SMA), not
  a coin flip.
- **Volume tone** from real recent volume vs. a real trailing average, not a coin flip.
- **Support/breakout** from the actual recent price range in the fetched history, not
  `base_price × fixed_multiplier`.

Wire into `room_runner.py::_profile_for_ticker()`: when `use_real_market_data` is on and
`compute_technicals()` succeeds, overlay `rsi`/`trend`/`volume_tone`/`support`/`breakout`
with the real computed values; fall back to today's synthetic block on any failure
(missing data, insufficient history, API error) — never error the Room/1-on-1 turn.
`room_prompts.py::_format_profile()`'s disclosure header gains a technicals category
(alongside fundamentals/news/social) so a profile can honestly say technicals are live
independently of the other three.

**MACD/Bollinger Bands — explicit scope decision needed:** implement them too (both are
standard, computable from the same OHLCV series — MACD from 12/26/9-period EMAs,
Bollinger from a rolling mean ± 2 standard deviations), or drop those two specific claims
from `content/agents/market_analyst.md` if out of scope for this pass. Whichever is
chosen, the prompt's claims must match runtime capability exactly — no claiming an
indicator that isn't computed.

`content/agents/market_analyst.md` rewritten to describe the real computed indicators
delivered, dropping any claim not actually implemented.

## Acceptance

- [x] RSI computed from real OHLCV via yfinance when `use_real_market_data` is on and
      history fetch succeeds.
- [x] Trend signal derived from a real moving-average relationship, not a coin flip.
- [x] Volume tone derived from real volume vs. a real trailing average, not a coin flip.
- [x] Support/breakout derived from the real recent price range, not
      `base_price × fixed_multiplier`.
- [x] Explicit scope decision recorded on MACD/Bollinger Bands — dropped from the prompt
      (not implemented); `content/agents/market_analyst.md` explicitly says so.
- [x] Graceful degradation: history fetch failure/insufficient data/timeout falls back to
      the synthetic block, never errors the Room/1-on-1 turn (`compute_technicals`
      never raises, returns `None`, callers check before overlaying).
- [x] `content/agents/market_analyst.md` claims match actual runtime capability exactly.
- [x] Disclosure header (`_format_profile()`) gains a technicals live/synthetic label,
      independent of fundamentals/news/social.
- [x] Regression tests: real values used when history available; synthetic fallback used
      when not; disclosure header correctly labels technicals as live vs synthetic.
