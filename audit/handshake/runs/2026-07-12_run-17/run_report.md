<!--
Auditor run report — run-17 (2026-07-12, session AT:U1). Round-1 audit of DEF052
(Market Analyst real technicals). Fixed in f367e26. Verdict: AWAITING_FIXES — one
MAJOR (F1: NaN close raises, fails the Room Convene). Owner: AUDITOR.
-->

# run-17 (round 1) — DEF052 (Market Analyst real technicals) → AWAITING_FIXES

- **Auditor session:** AT:U1 (track U), 2026-07-12
- **Audited SHA:** `f367e26`. `git diff f367e26..HEAD -- backend/ content/` empty (only
  a later docs/audit commit between), so the main checkout == the committed fix — full
  suite run there (py 3.13.13, sqlite tempfile) → **697 passed**.
- **Verdict:** AWAITING_FIXES — one MAJOR, zero BLOCKER.

---

## F1 (MAJOR, reproduced) — NaN close → `ValueError` → whole Room Convene fails

`compute_technicals` (technicals.py) promises "Never raises" and callers rely on it to
degrade to the synthetic block. It wraps only `history()` in try/except, not the math.

- **Reproduced (my own probe):** a candle list of 60 clean bars + one NaN close →
  `compute_technicals('AAPL')` raises `ValueError: cannot convert float NaN to integer`
  (at `round(rsi)`, technicals.py:132; `round(support)`/`round(breakout)` :136-137 same
  exposure). A NaN *low* alone doesn't reliably raise (min skips it) but silently yields
  a wrong support; the NaN *close* is the definitive raise.
- **The provider passes NaN through.** `YfinanceProvider.history()` (market_data.py:485-499)
  builds each `Candle` guarded only by `except (KeyError, TypeError, ValueError)`, but
  `float(nan)` returns `nan` without raising and there is no `df.dropna()`. NaN is
  pandas/yfinance's missing-value sentinel; `Candle(c=nan)` is a type-valid `list[Candle]`
  element. Reachable via user-selectable tickers (thin / recent-IPO / halted) on the live
  `use_real_market_data` path.
- **Blast radius = the entire Convene.** `if technicals:` catches only `None`, not a raise.
  The `_profile_for_ticker(ticker)` call (room_runner.py:1078) is **before** `run()`'s own
  try (opens :1118), so the `RoomStatus.FAILED` handler (:1233) doesn't catch it either —
  it propagates to `_pump()` (:939), which emits a client error event with **no verdict**.
  The whole 12-agent Room Convene fails, not just the Market Analyst's block.
- **Contract falsified.** Defeats the module's "Never raises" docstring and DoD
  acceptance #6 ("history fetch failure/insufficient data/timeout falls back to the
  synthetic block, never errors the Room/1-on-1 turn"). All three sibling modules
  (fundamentals/news/social) wrap the full computation and return `None` here — DEF052 is
  the outlier.

**Minimal remedy (round 2):** wrap the `compute_technicals` body in
`try/except Exception: return None` (match the siblings), or drop NaN candles / guard
`round()` with `math.isfinite`. Add a NaN-close regression asserting `is None`.

## Everything else — verified correct

- **697 passed** at the SHA (reproduced).
- **RSI(14)**: simple gain/loss average; hand-logic matches the alternating-delta test
  (RS 2.0 → 67); `avg_loss==0 → 100`.
- **Trend**: `trading` iff price/20-SMA/50-SMA aligned, else `consolidating`.
- **Volume**: 5-day vs 20-day average, ±10% buckets, `baseline<=0` guarded.
- **Support/breakout**: `min(lows[-50:])`/`max(highs[-50:])`; **windowing test genuine** —
  10.0/500.0 extremes planted in the first 15 of 65 candles, asserts 90.0/110.0.
- **Candle attrs** `.c/.h/.low/.v` match the real `Candle` NamedTuple.
- **Gating**: overlay inside `use_real_market_data`; 1-on-1 Market-Analyst-only; independent
  of fundamentals.
- **Disclosure**: `technicals_source="live"` set only on real compute; header labels
  technicals live/synthetic and disclaims MACD/MA-crossover/Bollinger.
- **Prompt truthfulness**: `market_analyst.md` drops MACD/Bollinger, no-intraday, say-so-
  when-no-data; scripted `_TEMPLATES` "the 200-day [MA]" → "recent support"; Voice example
  de-MACD'd.
- **Register**: `def_list.md` DEF052 = `resolved` — should reopen on this bounce.

## Live
Backend-only; needs `/promote-to-alpha` to run live. F1's empirical NaN frequency wasn't
measured against live yfinance from the Mac (pure editor), but the raise is reproduced at
the unit level and the provider pass-through is confirmed in source — a "never raises"
module must not raise on a type-valid `Candle`.

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| DEF052 | `f367e26` | **AWAITING_FIXES (round 1)** — F1 MAJOR (reproduced): NaN close raises `ValueError`, failing the whole Room Convene; defeats the never-raises contract + DoD acceptance #6. Everything else verified correct (697; RSI/trend/volume/support windowing; gating; disclosure; prompt truthfulness). |

No OUT-OF-SCOPE findings.
