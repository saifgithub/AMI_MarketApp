<!--
DEF099 — MergeService drops RevenueCat/entitlement/credit state on anon→claimed account merge.
Spotted by the Architect during the CR084-BE (RevenueCat webhook) build/review, 2026-07-24.
Violates the anonymous-first LOCKED decision: a pre-claim anonymous purchase must survive claim.
-->

# DEF099 — account merge drops RC entitlement + credit state (anonymous-first violation)

**Filed:** 2026-07-24, by the Architect, from the CR084-BE build (`f1e7a161`). Not user-reported.
**Severity:** blocks **anonymous purchase end-to-end** (M1). NOT a blocker for CR084-BE's own scope.
**Area:** billing / auth-merge / backend.

## The defect (vs. spec)

CLAUDE.md locks **Anonymous-first** onboarding (account claim at the end of the concierge interview).
CR084 lets a **pre-claim anonymous user purchase** (RC `app_user_id` = the anon `users.id`). But
`MergeService.execute()` — which re-keys ~16 per-user tables from orphan→adopter on claim and then
DELETEs the orphan `users` row (BL16, `f7a771a`) — does **not** carry billing state. So an anonymous
user who pays, then claims/links an existing account, **silently loses what they paid for.** That
directly violates the anonymous-first promise (their pre-claim work, incl. a purchase, must survive).

## Root cause (three concrete gaps, from the CR084-BE build)

1. **`subscription_events` + new `revenuecat_events` rows are not re-keyed.** They keep the orphan
   `user_id` and dangle after the orphan `User` is deleted (no FK cascade) — the audit/dedup trail is
   orphaned.
2. **`users.plan` / `credit_balance` / `credits_period_start` / `credits_plan_at_grant` are not carried
   orphan→adopter.** The adopter keeps its own `floor_pass` + balance; the anonymous purchase's plan +
   credits are **lost**.
3. **RC `app_user_id` is the deleted orphan UUID.** RC has no signal to re-target, so post-merge
   `RENEWAL` / `EXPIRATION` webhooks arrive for a now-deleted user and CR084-BE's webhook returns a
   loud 404 — the subscription is stranded from the real (adopter) account.

## Proposed fix (fix lane decides exact shape)

- `MergeService.execute()` re-keys `subscription_events` + `revenuecat_events` orphan→adopter (add to
  the existing re-key set); and carries billing fields with a **defined conflict rule** (adopter already
  paid vs. orphan paid — pick the higher entitlement / sum credits, or target-wins per the existing
  simple merge rules — decide deliberately, don't leave it accidental).
- Transfer the RC customer alias so future webhooks target the adopter: `Purchases`/RC customer-alias
  call (or `logIn` alias) at merge time, so `app_user_id` follows the surviving account. This is the
  RC-side half — coordinate with `coder.store` / the RC dashboard config.
- Guard with a test: an anon user with a `trader` sub + credit balance, merged into a `floor_pass`
  adopter, ends up `trader` with the credits and a re-keyed audit trail; a subsequent `RENEWAL` webhook
  for that subscription resolves to the adopter, not a 404.

## Scope / dependencies

- **coder.api** (owns `MergeService`, `credit_service`, `entitlements`, the webhook). RC-alias half may
  need a `coder.store` / Saiful-liaison step (RC dashboard).
- **Gate:** independent (money/entitlements — D-5).
- **Ordering:** must land before **anonymous purchase is enabled end-to-end**. Since that enablement
  itself waits on Saiful's RC keys/products, this is not on the CR084-BE critical path — but it IS on
  the M1 "anonymous user can pay" path. Do not enable anon purchase in the paywall until this is fixed.

## Not in scope

- CR084-BE's webhook/grant logic itself (verified sound, `f1e7a161`, in independent audit).
- Claimed-user (non-anonymous) purchases — those already target a stable `users.id`, unaffected.
