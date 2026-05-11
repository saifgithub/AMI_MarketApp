# Payments

RevenueCat wraps Apple IAP, Google Play Billing, and HMS IAP. We don't write three integrations.

## Why RevenueCat

| Pain point | RevenueCat solves it |
|---|---|
| Three different IAP receipt validation systems | One unified API |
| Different subscription state semantics per platform | Unified entitlements |
| Receipt fraud detection | Built-in |
| Restore-purchase flows | One-line API call per platform |
| Webhook for server-side entitlement state | Single webhook endpoint |
| Promotional offers cross-platform | Their offer system handles it |
| Cross-device subscription state | Built-in (user-identifier mapping) |
| Analytics on revenue, churn, LTV | Their dashboard |

Without RevenueCat, we'd write each store's receipt verification, churn analysis, and cross-platform state-merging ourselves. RevenueCat is industry standard for cross-platform mobile sub apps.

## Pricing

| RevenueCat tier | Cost |
|---|---|
| Free | Up to $10K MTR (Monthly Tracked Revenue) |
| Starter | 1% of revenue above $10K MTR |
| Pro | $X/mo + features (not needed at MVP) |

At MVP scale we'll likely be on the Free tier. At growth scale, 1% of revenue is reasonable.

## SDK integration

```dart
// pubspec.yaml
dependencies:
  purchases_flutter: ^7.0.0

// main.dart — initialize on app start
await Purchases.setLogLevel(LogLevel.info);
await Purchases.configure(
  PurchasesConfiguration(revenueCatPublicKey)
    ..appUserID = user.id   // link to our user ID
);
```

## Entitlements model

We define 3 entitlements in the RevenueCat dashboard:

| Entitlement | Granted by |
|---|---|
| `trader` | "Trader" monthly or annual products |
| `floor_manager` | "Floor Manager" monthly or annual products |
| `credit_pack_60` | (one-time consumable, not an entitlement strictly — handled via webhook) |

(Same for `credit_pack_300`, `credit_pack_850`.)

```dart
// Check entitlement
final purchaserInfo = await Purchases.getCustomerInfo();
if (purchaserInfo.entitlements.active.containsKey('trader')) {
  // User has active Trader entitlement
}
```

## Backend webhook

RevenueCat sends webhooks on every subscription event:
- `INITIAL_PURCHASE`
- `RENEWAL`
- `CANCELLATION`
- `UNCANCELLATION`
- `EXPIRATION`
- `BILLING_ISSUE`
- `PRODUCT_CHANGE` (upgrade / downgrade)
- `NON_RENEWING_PURCHASE` (credit pack consumables)

We POST these to `/v1/billing/webhook/revenuecat`:

```python
@router.post("/billing/webhook/revenuecat")
async def revenuecat_webhook(payload: dict, x_revenuecat_signature: str = Header(...)):
    # 1. Verify signature
    if not verify_revenuecat_signature(payload, x_revenuecat_signature):
        raise HTTPException(401)
    
    event = payload["event"]
    user_id = event["app_user_id"]
    
    # 2. Update user state based on event
    if event["type"] == "INITIAL_PURCHASE":
        await activate_subscription(user_id, event)
    elif event["type"] == "RENEWAL":
        await refresh_credits_for_period(user_id, event)
    elif event["type"] == "NON_RENEWING_PURCHASE":
        await grant_credit_pack(user_id, event)
    elif event["type"] == "CANCELLATION":
        # Note: cancellation ≠ expiration. User retains entitlement until period end.
        await mark_pending_downgrade(user_id, event)
    elif event["type"] == "EXPIRATION":
        await downgrade_to_floor_pass(user_id, event)
    # ... other events
    
    return {"ok": True}
```

## Apple IAP setup

In **App Store Connect**:

| Product | Type | Price (US) | Reference name |
|---|---|---|---|
| `ami_trader_monthly` | Auto-renewable subscription | $14.99 | "Trader (Monthly)" |
| `ami_trader_annual` | Auto-renewable subscription | $129 | "Trader (Annual)" |
| `ami_floor_manager_monthly` | Auto-renewable subscription | $34.99 | "Floor Manager (Monthly)" |
| `ami_floor_manager_annual` | Auto-renewable subscription | $299 | "Floor Manager (Annual)" |
| `ami_credit_pack_60` | Consumable | $4.99 | "60 Credits" |
| `ami_credit_pack_300` | Consumable | $19.99 | "300 Credits" |
| `ami_credit_pack_850` | Consumable | $49.99 | "850 Credits" |

All products are configured in RevenueCat to map to the right entitlement.

## Google Play Billing setup

Same product structure in **Play Console** with matching IDs.

## HMS IAP setup (v1.1)

Same in **Huawei AppGallery Connect** with matching IDs.

RevenueCat's HMS support requires their plug-in setup; the SDK is included in `purchases_flutter`.

## Promotional offers via RevenueCat

For Founders Pricing, Launch-Country Promo, etc., we use RevenueCat's **Offer Catalog**:

- Define offers in the RevenueCat dashboard (one per promo)
- Each offer is a discounted variant of a base product
- Apple/Google offer codes generated via App Store Connect / Play Console
- Backend determines eligibility and presents the right offer code via `/v1/billing/offers`

When user accepts an offer, Mobile calls RevenueCat with that offer's ID. RevenueCat handles redemption with the platform store.

## Restore purchases

Standard pattern:

```dart
// User clicks "Restore purchases" in Wallet & Plan
await Purchases.restorePurchases();
// RevenueCat re-verifies receipts with App Store / Play / HMS
// Webhook fires for any changes
// User's entitlement state updates
```

Required by App Store guideline 3.1.1.

## Cancellation

Users **cannot cancel via our app** (Apple/Google rules — must use platform settings). Our UI provides a one-tap deep-link:

```dart
// Apple: opens Settings → Subscriptions
await Purchases.showManageSubscriptions();
// Google: opens Play Store subscription management
// HMS: similar
```

No friction. No "are you sure?" — Apple/Google prohibit dark patterns in cancellation flows now anyway.

## Refunds

We don't issue refunds directly. Apple / Google / Huawei handle refund requests through their stores. If a user demands one through us, we politely point them to the right platform.

Exception: small operational refunds in credit packs (e.g., user bought credits but Convene the Room failed midway). We can credit back via internal credit_transactions ledger without involving the store.

## Web payments (Phase 2)

When we add a marketing-site direct subscription flow:

- **Stripe** for the web direct purchase
- **2.9% + $0.30** processing fee
- RevenueCat supports Stripe via their "Web Billing" feature
- Single source of entitlement truth across mobile + web

Apple takes 30% (15% year 2). Stripe takes 3%. Direct web sub is 10× more margin than App Store. Worth Phase 2 effort.

## Cross-references

- Tier structure: [`docs/06_monetization/tiers_and_pricing.md`](../06_monetization/tiers_and_pricing.md)
- Credit system: [`docs/06_monetization/credits.md`](../06_monetization/credits.md)
- Offer mechanics: [`docs/06_monetization/offers.md`](../06_monetization/offers.md)
- Store compliance: [`docs/09_compliance/store_compliance.md`](../09_compliance/store_compliance.md)
