# CR198 — "Share a Premium" two-stage referral funnel (Plan 2 of CR045)

**Filed 2026-08-20 (AT:R73), on Saiful's direction** during the open-CR review: asked whether
"close CR045" and "file Plan 2 now" were mutually exclusive — they are not, so this CR is the
filing and CR045 closes on it (its own acceptance: *"closes once Saiful has picked and named
the plans he wants built"*).

## What

The two-stage referral program Saiful designed and parameterized inside CR045
(`docs/forward_planning/CR045_paywall_funnel_tactics/CR045_paywall_funnel_tactics.md`, "Plan 2"
section — that section is the spec of record; this doc does not restate it, it binds it):

- **Stage 1 (signup):** referred friend claims an account + completes onboarding → referrer
  gets **7 days Trader** (the DEF060/CR039 temporary-grant mechanic).
- **Stage 2 (conversion):** that friend becomes a *paying* subscriber → referrer topped up
  **+23 days Trader** (30 total).
- Tier: **Trader only, never Floor Manager.** Eligibility: **every user incl. Floor Pass.**
- Stacking: days stack across referrals, **capped at 90 banked days**. Friend-side reward:
  30 bonus credits (unchanged from §5). Abuse bar: claim + completed onboarding.

Parameters were **locked by Saiful 2026-07-21** — build to them; do not re-open.

## Gate

**Blocked on CR084 (RevenueCat / real payments).** Stage 2 is structurally unbuildable until a
"friend became a paying subscriber" event exists, and shipping stage 1 alone changes the offer
economics Saiful locked as a pair. Do not lane this CR before CR084 is live on at least one
store track.

## Scope (when unblocked)

1. Referral code/link issue + attribution on account claim (the DEF060 claim event is the hook).
2. Grant mechanics: reuse the CR039 credit/entitlement grant path — no parallel grant system.
3. Banked-days ledger with the 90-day cap enforced at write.
4. Conversion webhook from RevenueCat → stage 2 top-up, idempotent per referred user.
5. Client surface: share sheet + "your banked days" row (front-end proposal + sign-off first).

## Acceptance

- Both stages grant correctly and idempotently (double webhook ≠ double grant).
- Cap holds: 91st banked day is refused at write, loudly.
- Floor Pass user can refer and receive; Floor Manager tier is never granted by referral.
- Anonymous-stays-anonymous friend grants nothing.
- All grants visible in the existing entitlement/credit audit surfaces.
