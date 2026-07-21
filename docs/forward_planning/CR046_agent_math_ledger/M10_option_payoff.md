# M10 — Option payoff & break-even

**Origin:** CR054 §4.5 (BOK Wave-1 numbers) · **Status:** done (library + guards; Wave-1 lessons are the consumer)

## What
The expiry arithmetic of a call or put — intrinsic value, long per-share P&L, and break-even — so
every payoff-diagram point in the BOK's M15 ("Options & derivatives literacy") lessons is computed,
never authored by hand.

## Why opened
CR054 Wave 1 authors ~7 options lessons whose core artefact is the payoff diagram: a table of
"stock at 80/100/120 → P&L −5/−5/+15" numbers plus a break-even. Hand-authoring those invites the
exact wrong-number class CR046 exists to remove, and an options mistake is worse than most — the
lessons explicitly teach "why retail options lose", so a wrong payoff number would undercut the
whole module's credibility.

## Formula
All long-side, per share, 2 dp; a short side is the exact negation (the lesson states it, never
re-derives it). `kind` is `"call"`/`"put"`, case-insensitive; anything else → None so a template
typo can't print a call's numbers for a put.
- `option_intrinsic_value(kind, strike, underlying)` — call `max(0, S−K)`, put `max(0, K−S)`.
  `underlying` may be 0 (the bankruptcy case a put lesson teaches); negative → None.
- `option_payoff(kind, strike, price_at_expiry, premium)` — intrinsic − premium. At/below the
  worthless point this is exactly −premium (max loss = what you paid).
- `option_break_even(kind, strike, premium)` — call `K + premium`; put `K − premium`, None when the
  premium swallows the whole strike (a put can't break even at or below a zero stock price).

## Source data
Lesson-authored example parameters (strike, premium, expiry prices) — pedagogical inputs, not
market data.

## Consumed by
**No production caller yet — by design.** Wave-1 lesson authoring (M15 lessons + their quizzes)
routes every payoff/break-even figure through these. Simulation-only constraint unchanged: options
are taught as literacy, never tradable in-app.

## Computed in
`app/trading_math/option.py::option_intrinsic_value` / `option_payoff` / `option_break_even`.

## Guard test
`tests/unit/test_trading_math_bok.py` — call and put payoff points (ITM profit, max-loss=premium),
both break-evens, the bankruptcy-put intrinsic (underlying 0 → K), case-insensitive kind + unknown
kind rejection, and the None-on-nonsense guards (no strike, negative underlying/premium, put
premium ≥ strike).

## Changelog
- 2026-07-21 (CR054-W0d, AT:coder.math): created — opened ahead of Wave-1 lesson authoring.
