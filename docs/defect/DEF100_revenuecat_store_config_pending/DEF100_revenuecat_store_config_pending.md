<!--
DEF100 — RevenueCat + store billing config not yet provisioned (Saiful-liaison dependency).
Filed at Saiful's explicit request 2026-07-24 ("log it as a defect so it remains in my sight")
so the CR084 external dependency is tracked in the defect register, not just in prose.
This is a CEO/board (Tier-1) task, not a code task — kept OPEN until Saiful provisions it.
-->

# DEF100 — RevenueCat + store billing config pending (blocks live purchases / M1 end-to-end)

**Filed:** 2026-07-24, by the Architect at Saiful's request. **Owner: Saiful** (CEO/board Tier-1 —
accounts, money, store identity), executed via the `coder.store` liaison. NOT a code defect — a
provisioning dependency logged for visibility.

**Severity:** blocks **M1 end-to-end** (a real user paying). Does NOT block the code — CR084-BE is
integrated (`f6f4cfd`) and CR084-MOBILE can be built against a stub offering.

## What's missing

CR084 wired the RevenueCat integration in code (backend webhook + entitlement/credit grants landed;
mobile SDK + paywall next). None of it can take a real payment until the RevenueCat dashboard + the two
app stores are provisioned. Required from Saiful:

1. **RevenueCat dashboard:** project created; **public SDK keys** (iOS + Android) for the mobile SDK;
   **webhook auth secret** (the value the backend checks — set as `REVENUECAT_WEBHOOK_SECRET` in
   melehost's `.env`).
2. **App Store Connect + Google Play Console:** the **7 products** created and mapped to RC offerings +
   the two entitlements (`trader`, `floor_manager`):
   - subs: `trader_monthly` $14.99, `trader_annual` $129, `floor_manager_monthly` $34.99,
     `floor_manager_annual` $299
   - consumables: `credits_starter` $4.99, `credits_standard` $19.99, `credits_power` $49.99
3. **Apple + Google paid-app agreements + banking/tax** (the M1 blocker noted in `project_plan.md:182`).

## Current safe behavior until provisioned (degrade loudly — CR040)

- Backend webhook **fails closed**: an unset `revenuecat_webhook_secret` → HTTP 503 + logged error
  (never silent-accept). No dark path.
- Mobile paywall (CR084-MOBILE) MUST NOT offer a purchase button until the RC offering resolves — show
  the existing cooldown/upgrade-info state, not a dead buy button.

## Definition of done (Saiful's checklist)

- [ ] RC public SDK keys (iOS, Android) provided → into the Flutter build config.
- [ ] RC webhook secret provided → `REVENUECAT_WEBHOOK_SECRET` in melehost `.env` + verified the
      webhook accepts a real RC test event (503 clears).
- [ ] 7 products live in App Store Connect + Play Console, mapped to RC offerings + entitlements.
- [ ] Apple/Google paid agreements active.
- [ ] One live-device test purchase of `trader_monthly` grants `Plan.TRADER` + 150 credits end-to-end
      (the CR084 acceptance smoke).

## Related

- CR084 (RevenueCat integration) — the code this unblocks. CR084-BE integrated; CR084-MOBILE pending.
- DEF099 (anon-merge billing carry-over) — must ALSO land before anonymous purchase is enabled.
