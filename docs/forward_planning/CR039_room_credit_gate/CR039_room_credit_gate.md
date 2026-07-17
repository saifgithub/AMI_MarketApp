# CR039 — Meter Convene the Room on credits: the first real paywall, and the trial's first cliff

**Status:** in progress · **Session:** AT:R60 · **Date:** 2026-07-17
**Source:** Saiful, reviewing DEF060: *"the idea here is to onboard the user so we can start
charging fee. what can we do?"* — investigated the whole funnel, found the blocker is not
onboarding.

## Problem

DEF060 fixed the top of the funnel (account claim is offered; the mandate persists on claim).
But nothing below it exists. Ground-truthing the anon → claim → trial → paywall → purchase
chain against the code found four things:

1. **No way to take money.** No `purchases_flutter` / `in_app_purchase` in `mobile/pubspec.yaml`,
   no paywall or subscription screen anywhere in `mobile/lib`, no RevenueCat / webhook /
   checkout route in the backend.
2. **Nothing to sell.** Grepping `backend/app` for `402` / `PAYMENT_REQUIRED` /
   `upgrade_required` returns **nothing** — no route ever refuses anyone on plan grounds.
   `entitlements.effective_plan` is consumed only by `pick_tier` callers
   (`brief_engine.py:255`, `agent_runner.py:53`) and the admin panel. Of the 24 axes in
   [`paywall_axes.md`](../../initial_specs/06_monetization/paywall_axes.md), only **#1 (Smarter
   AI)** is enforced — and it is *invisible* to the user. From the user's seat, Floor Pass and
   Floor Manager are the same product. (`room.py:3`'s docstring claims the endpoint "validates
   plan + access"; no such check exists.)
3. **The trial has no cliff.** It fires correctly — 7 days, atomically on claim
   (`auth_service.py:479`) — and `entitlements.py:42` correctly virtual-downgrades
   `TRIAL_TRADER` → `FLOOR_PASS` at expiry. But because plan only moves the LLM tier, expiry is
   a *silent model downgrade*. Nothing visibly ends. There is no moment that creates a reason
   to pay.
4. **Credits are earn-only.** `reputation_service.py:326-327` adds them; **nothing anywhere
   decrements them**. Credit packs would have nothing to spend on.

None of this is a defect. It is the intended alpha state —
[`project_plan.md:113`](../../initial_specs/10_delivery/project_plan.md): *"No payments. No
RevenueCat. Floor Pass for everyone during alpha."* Charging is **M1**
(`project_plan.md:182`, `◯ unstarted`), which already names the routes to gate: *"entitlement
checks on premium routes (1-on-1 with PM, Convene the Room)."*

## Decision

**Build the cliff, not the checkout.** Pull M1's entitlement half forward; leave RevenueCat
alone.

The two halves are separable, and this half has **zero dependency on Saiful's external work**
(Apple/Google dev accounts, RevenueCat product config). It is also what makes the checkout
worth building later: today there would be nothing to buy. Charging stays **off** —
`project_plan.md:113` is unamended by this CR.

## Scope

### Currency: credits, not a room counter

The spec's currency is credits, not room counts:
[`tiers_and_pricing.md:12`](../../initial_specs/06_monetization/tiers_and_pricing.md) — 13
credits/mo (Floor Pass = 1 Room + 5 one-on-ones) / 150 (Trader) / 500 (Floor Manager);
[`credits.md:19`](../../initial_specs/06_monetization/credits.md) — a Basic Room costs **8**.
A raw room counter would contradict the spec and be rewritten at M1. Credits are also already
half-built: `room_runs.credit_cost` exists (`models.py:385`, defaulted 0 and never set).

### Ledger: reuse `SubscriptionEventRow`, no new table

`models.py:543-548` already states *"Every admin write and every app-side credit consumption
produces a row"* and anticipates `revenuecat_purchase` rows at M1. `reputation_service.py:326-336`
already writes `event_type="credits_added"` rows with `from_value`/`to_value` balance deltas.
`users.credit_balance` is the denormalized running total; `subscription_events` is the ledger
behind it — the same pattern as `users.reputation` / `reputation_events`. This CR adds only the
mirror: `credits_spent`, `credits_refunded`, `credits_reset`.

### Re-grant on effective-plan *change*, not only month rollover

This is what makes the cliff bite. A 7-day trial usually lapses mid-month; keying the allowance
purely to the calendar would delay the visible drop by up to three weeks and destroy the
conversion moment. Allowance is re-granted when the calendar month rolls **or** when
`effective_plan` differs from the plan the current balance was granted under.

### Changes

| Area | Change |
|---|---|
| `services/credit_service.py` (new) | `ALLOWANCE` by plan, `ROOM_BASIC_COST = 8`, `_ensure_period`, `balance_for`, `spend`, `refund`, `InsufficientCredits` |
| `db/models.py` + migration | `users.credits_period_start`, `users.credits_plan_at_grant` (both nullable — existing rows re-grant on first touch, no backfill) |
| `api/room.py::stream_room` | Spend after the ownership 403, before the run spawns → `402` with `{balance, cost, plan, resets_at}`. Set `credit_cost` on the run row. Fix the stale docstring. |
| `services/room_runner.py` | Refund on the terminal error path — a crashed run must not bill the user |
| `schemas/mandate.py` | `credits_resets_at` + `credit_allowance` (client already receives `plan`, `trial_expires_at`, `credit_balance` at `mandate.py:120-122`) |
| Mobile | Typed `InsufficientCreditsException` (today `streamRoom` throws a generic `Exception('HTTP 402…')`), balance shown at Room entry, upgrade sheet on 402, EN l10n |

## Out of scope

- **RevenueCat / checkout / purchase** — M1. Needs Saiful's dev accounts + RC product config.
  The upgrade sheet this CR ships is the surface M1 later attaches the buy button to.
- **1-on-1 metering** (axis #4) — same service, trivial follow-on once this lands.
- **Credit packs** — nothing to buy until M1.
- **DEF060's skip-path mandate gap** — still open, tracked on DEF060.

## Open question

[`credits.md:46`](../../initial_specs/06_monetization/credits.md) says credits **reset monthly,
do not accumulate** — but `reputation_service` grants streak/earned credits into the same
`credit_balance`. A hard reset to allowance **evaporates earned credits**, cheapening the
reputation loop. Shipping per spec (reset to allowance; earned credits are within-month only);
revisit if it feels wrong on device. Tracking earned separately is real extra scope and isn't
worth it before there's a paywall.

## Acceptance

- A Floor Pass user (13 credits) converges one Room (→ 5 left) and is refused the second with a
  402 carrying `balance`/`cost`/`resets_at`; no `room_runs` row is created and no LLM call fires.
- An active-trial user (150) converges freely.
- **The cliff:** when the trial lapses, the allowance re-grants to 13 *immediately* — not at
  month rollover — and a convene that previously succeeded now 402s.
- A failed run refunds; the ledger shows spend + refund.
- Free-tier sanctity holds: the gate touches **only** Convene the Room. Lessons, daily
  challenges, mandate complexity, and halal screening stay free
  (`paywall_axes.md` §"Free-tier sanctity").
