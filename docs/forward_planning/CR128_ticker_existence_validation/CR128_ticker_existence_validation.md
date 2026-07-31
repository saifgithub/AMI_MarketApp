# CR128 — Ticker existence validation + closest-match suggestion

**Status:** proposed · **Session:** AT:architect · **Date:** 2026-07-30 · **HIGH PRIORITY (Saiful, 2026-07-31)**
**Source:** in-app bug report `ab1d5664` (Platinum Anchor, `8f1e288a`, `0.1.0+58`) —
*"when we convene a room, start a trade or adding to a watch list, we need to check
that the ticker actually exist. otherwise we need to suggest the closest one."*
Steps: *"if it is not exact, we should display a bit about the company and get
confirmation."*

## Problem

None of the three ticker-entry points (Convene the Room, Start Trade, Add to
Watchlist) validate that a typed ticker actually exists before proceeding. Checked
`market_data.py` and the trade/watchlist/Room-convene code paths — no fuzzy-match or
existence check exists anywhere today. A mistyped or nonexistent ticker likely either
fails deep in the flow with a raw error, or silently produces a no-data run — neither
is a good user experience, and this is a real gap, not a regression.

## Scope (not yet designed)

1. **Existence check** — validate the typed ticker against a reference universe.
   Candidates already in the codebase: the Sharia-universe download (CR075), the
   `yfinance`/Yahoo market-data layer, or a dedicated symbol list — which one (or a
   new one) is the right source needs a decision, not an assumption.
2. **Closest-match suggestion** — when the ticker doesn't exist, suggest the nearest
   valid one (edit-distance / prefix match against the same reference).
3. **Confirmation UI** — when the match isn't exact, show basic company info (name,
   maybe sector/exchange) and require explicit confirmation before proceeding.
4. **Consistency** — the same check/suggestion/confirmation UX should gate all three
   entry points identically, not diverge per screen.

## Acceptance

Not yet defined — depends on the reference-source decision above. At minimum: typing
a nonexistent ticker into any of the three flows never silently proceeds or raw-fails;
it offers a specific, named alternative with enough context to confirm or reject.
