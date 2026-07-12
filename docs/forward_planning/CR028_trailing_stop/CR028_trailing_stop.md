# CR028 — Trailing stop

**Status:** proposed · **Session:** AT:R55 · **Date:** 2026-07-12
**Source:** migrated from `Silent_Scout/15_trailing_stop/` as part of closing and
deprecating Silent_Scout.

## What

Add a trailing-stop option alongside the existing fixed stop on a `SimTrade` — the
stop price automatically rises as the position moves up, never down. Tier 3 (deferred
until users have mastered fixed stops), and **sequenced after CR027** (price alerts) —
the recompute step piggybacks on CR027's price-polling loop, which doesn't exist yet.

## Why

`SimTradeRow.stop` (fixed stop) already exists; trailing is one additive field plus a
recompute step. Genuinely low effort once CR027's polling infrastructure lands. Not
urgent under GTM (advanced feature, not a gap users will hit early) — filed to
preserve the design, not to fast-track it.

## Design (ported)

### Schema
`SimTrade` gains `trail_pct: float | None` (e.g. `5.0` = 5%). Constraint: `stop` XOR
`trail_pct` — a trade uses one or the other, never both, never neither if a stop is
set at all. No `SimHolding` change — trailing stops are per-trade.

### Recompute (runs inside CR027's price-polling loop)
```
new_stop = current_price * (1 - trail_pct / 100)
if trade.stop is None or new_stop > trade.stop:
    trade.stop = new_stop
```
Monotonically increasing only — the stop never moves down even if price dips then
recovers below the prior high.

### Trade Ticket UI
Toggle ("Use trailing stop?") alongside the existing fixed-stop input; when enabled,
reveal a "Trailing %" numeric field. Submission validates the XOR constraint
(reject if both or neither are set when a stop is requested).

### Agent hook — corrected
Original design proposed a `_risk_block()` "Risk Agent" recommendation ("your position
is up 10%, consider a trailing stop") triggered on unrealised P&L. **Same fabricated
Risk-Agent citation as CR026/CR027** — this suggestion, if built, should surface from
the Portfolio Manager or Concierge, not a nonexistent agent.

## Scope

**In:** schema field, recompute logic, Trade Ticket toggle + validation.
**Out:** the "consider a trailing stop" proactive suggestion (nice-to-have, correctly
attributed to a real agent if built); LIFO variant (not needed, FIFO-equivalent logic
doesn't apply here anyway — this is a stop mechanism, not a lot-closing method).

## Acceptance

- Sequenced after CR027 — do not start until CR027's polling loop exists.
- Trailing stop only ever moves up; fixed and trailing stop are mutually exclusive
  per trade at submission time.
- Trade Ticket UI correctly hides/shows the trailing % field.
