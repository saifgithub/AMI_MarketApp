# CR090 — Meter live news/social data feeds; fail loudly instead of silently degrading

**Status:** proposed
**Filed:** 2026-07-25 (AT:R64)
**Source:** Saiful, live session, following on from a paywall-axes walkthrough. First:
*"Some of the data feed that cost money can be paywalled."* Then, on the proposed
mechanic: *"We should not even include the agents in the decision. We should fail it
loudly to tell the user these agents are chargeable. We also need to start doing the
Agent credit limit as planned."*

## Problem

Two real-cost data feeds exist and ship identically to every user regardless of plan:

- **CR023 — Alpha Vantage NEWS_SENTIMENT** ($49.99/mo flat, cached per-ticker not
  per-user). Feeds the News Analyst, Room + 1-on-1. `in_progress`.
- **CR024 — Adanos Reddit sentiment** (free tier, hard-capped **250 calls/month**,
  24h cache ⇒ ~8 distinct tickers/day). Feeds the Social Media Analyst, Room + 1-on-1.
  `in_progress`.

No paywall axis covers either (`paywall_axes.md` only has axis #6, market-data
*freshness* — real-time vs. 15-min-delayed — nothing for news/social liveness).

When live data isn't available (uncached ticker, quota exhausted, no key), both
agents already fall back to an honest "illustrative" synthetic block — correctly
disclosed as illustrative (CR023/CR024's own truthfulness work), but that disclosure
never distinguishes *"no data exists"* from *"data exists, you're not entitled to it."*
A free user experiences both as the same lower-quality output with no signal that
something is being withheld.

Separately: Adanos's 250-call/month quota is a real, shared, exhaustible resource
with **zero protection today**. Any user's traffic can burn it; a bad day degrades
the Social Analyst for every user, paid or free, for the rest of the month.

## Decision

Two changes, decided live by Saiful (2026-07-25):

1. **No silent quality substitution.** When a Room/1-on-1 turn would use live
   News/Social Analyst data and the user isn't entitled (or is short on credits),
   the response must explicitly disclose *"this agent's live data feed is a paid
   feature"* — not quietly render the synthetic fallback as if that's just how the
   agent behaves. Same **degrade-loudly** principle CR040 established for config
   gaps, applied here to an entitlement gate instead.
2. **Meter through credits, not a flat tier lock.** Reuse the credit
   infrastructure CR039 already shipped (`credit_service.py`, `InsufficientCredits`,
   the 402 pattern) rather than inventing a parallel gate. A live-data-enhanced
   News/Social Analyst turn costs credits; insufficient balance triggers the loud
   message from (1) — same shape Room already uses for its own 402.

## Design decision — RESOLVED 2026-07-26 (Saiful)

**Chosen: (a) Surcharge model.** Saiful, daily-review restore session: picked
"surcharge on top" over the per-agent rework. Room/1-on-1 keep their existing flat
price; live-data News/Social Analyst turns add a small additive surcharge **only when
they actually fire with real data**. **Surcharge amount:** documented default
**+2 credits per live-data analyst turn** (News +2, Social +2 → a Basic Room with both
live = 8 + 2 + 2 = 12), set as a named constant beside `ROOM_COST_BASIC` so it's
trivially tunable; confirm the exact figure against `credits.md` before Beta. This
resolves the question below; options kept for the record.

The exact metering shape:

- **(a) Surcharge model** — Room/1-on-1 keeps its existing flat price
  (`credits.md`: 1-on-1 = 1, Basic Room = 8); live-data agents add a small credit
  surcharge only when they actually fire with real data. Additive to the existing
  spec, cheapest to ship.
- **(b) Per-agent line-item model** — replace the flat Room price with a sum of
  per-agent costs. Bigger rework, touches `credits.md`'s whole pricing table.

**Recommend (a)** unless Saiful wants the deeper pricing rework.

## Scope (once (a) vs (b) is confirmed)

- Backend: `credit_service.py` gains a live-data-turn operation cost;
  `news_context.py` / `social_context.py`'s degrade path returns an explicit
  "paid feature withheld" marker distinct from "no data available"; wired into
  `room_runner.py` / `agent_runner.py`'s response and `room_prompts.py`'s
  disclosure header (currently binary live/synthetic per CR023/CR024 — needs a
  third state).
- Mobile: surface the "upgrade to unlock live data" message wherever the marker
  fires (Room stream, 1-on-1 chat) — copy only, no new screens.
- `paywall_axes.md` gains axis #25 documenting the decision.

## Out of scope

- LunarCrush (blocked on pricing — CR024's own open item, unaffected here).
- Changing the Alpha Vantage / Adanos providers or their pricing.
- Any change to Room's existing flat 8/25-credit base price, unless (b) is chosen.
- Lessons, mandate complexity, halal screening — free-tier sanctity untouched.

## Risk class

Same class as [CR084](../CR084_revenuecat_integration/CR084_revenuecat_integration.md)
(RevenueCat) — money/entitlements logic, cross-surface (backend + mobile).
Recommend the same `GATE: independent` dispatch treatment rather than shipping
without independent audit, given it touches real credit-spend logic.

## Acceptance

- A Floor Pass user with insufficient credits triggering a live-data News/Social
  Analyst turn sees an explicit "this needs credits / upgrade" message — never a
  silent synthetic substitution presented as business-as-usual.
- Adanos's 250-call/month quota is protected by the gate — free-tier traffic can no
  longer exhaust it unpriced.
- Existing Room/1-on-1 flat pricing and free-tier sanctity items are untouched.
- `paywall_axes.md` gains axis #25 with this decision recorded.
