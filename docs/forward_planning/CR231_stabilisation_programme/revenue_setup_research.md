# Revenue setup — founder checklist

Source: `/private/tmp/claude-501/-Volumes-Extreme-Pro-AMI-MarketApp/3b407fa5-.../scratchpad/revenue-setup.html`
(claude.ai artifact + `/tmp` scratchpad, at risk of loss). Date: 2026-09-22.
**Internal research, not user-facing.** Converted to markdown and preserved here under
[CR231](CR231_stabilisation_programme.md) / [D-073](../../initial_specs/11_decisions/decision_log.md#d-073--build-on-the-personal-developer-accounts-migrate-to-the-company-account-at-the-end)
so it survives outside a temp directory and a private artifact link.

Production release entity: **Agentic Market Intelligence (Malaysia)**. Personal
developer accounts: **testing only**.

## How payments are collected

You never pay Apple or Google revenue — **they pay you**. Commission is deducted
before money reaches your account; nothing is invoiced or transferred out. The only
payments you make are two fixed setup fees, on a card, unrelated to revenue.

**Subscriptions & credit packs:** User → Apple/Google → your bank, net of commission.
RevenueCat sits beside this flow, not in it — receipt validation and entitlements
only, it never touches the money.

**Ad revenue:** Advertiser → Google Ads → your bank, net, as a separate payout. This
is a **separate payments profile from Play Console** — different bank details,
different threshold, its own payout run.

## What lands in your account, per dollar of gross

| Source | Standard rate | Reduced rate | Condition |
|---|---|---|---|
| Apple IAP | 30% | 15% | Small Business Program, applied for, <$1M proceeds/yr |
| Apple IAP (any account) | 30% | 15% | Same subscriber's 13th+ month, automatic |
| Google Play | 15–30% | ~10% | Subscriptions, phasing in — verify in-console for MY |
| RevenueCat | 1% of gross | $0 | Below $2,500/mo tracked revenue |
| AdMob | — | — | Google's cut is pre-netted into what advertisers pay; no separate line |

## Company vs. personal account — Phase 0 (decided, deferred to end of development)

Development has been happening under the **personal** Apple/Google developer
accounts. Decided 2026-09-22: **finish full development first, migrate to the
company account once** — not mid-development, not incrementally. This matches the
project plan's own M6 milestone ("production APNs cert — dev cert was used in Alpha,
cut over to production"), so it's not a bespoke plan, it's the pattern this project
already uses. Personal stays the **testing-only** account throughout; the **company
account is the only production release** — no permanent dual-listing.

### Phase 0 steps

1. **Accept: this is a re-platform, not a transfer.** Apple's account "Organization
   Transfer" only moves an app between two *existing organization* accounts — it does
   not apply to an individual account moving to a brand-new company account. There is
   no button that carries the app across. Both platforms effectively require standing
   the app up fresh under the company identity.
2. **Decide the production bundle ID / package name.** Current:
   `ai.agenticmarketintel.amiTrade` (iOS) / `ai.agenticmarketintel.ami_trade`
   (Android) — already the company's domain, not a personal placeholder, which
   helps. Apple discourages reusing a bundle ID across separate developer accounts;
   confirm whether it can carry cleanly to the company Team ID or whether a new one
   is needed before anything downstream is built on it.
3. **Smoke-test the cutover on a throwaway build, once the company account exists.**
   *De-risks launch.* Doesn't change the develop-first sequencing — it's cheap
   insurance, not early migration. Sign-in and push both silently break on a Team ID
   change; verifying them once, early, on a disposable build means the real cutover
   at the end isn't the first time either has been tested under the company
   identity. Skip this and both are untested until launch week, which is the worst
   time to discover a StoreKit or APNs quirk.
4. **Re-register Sign in with Apple under the new Team ID.** A Team ID change breaks
   the existing Services ID + key. This has to be recreated against the company
   account before the production build can offer Apple sign-in.
5. **Re-issue APNs push certs/keys under the new Team ID.** Same reason as Sign in
   with Apple — push credentials are tied to the Team ID that created them.
   OneSignal (or whatever's wired server-side) needs the new ones before production
   push works. Project plan milestone M6.
6. **Keep developing on the personal account until development is complete.** *No
   blocker.* Nothing in Phases 1–5 below blocks day-to-day development or testing.
   The 105 existing TestFlight builds and their history stay on personal and are not
   carried over — that's fine, they did their job. Migration is a single pass, done
   once, **after** features are done — not incremental, not started early beyond the
   smoke test above.

## Phase 1 — entity credentials (longest lead time)

Start here regardless of anything else. The D-U-N-S number is the one step that can
quietly cost two weeks if it isn't first in the queue.

- **Get a D-U-N-S number for Agentic Market Intelligence.** Free, 5 days–2 weeks.
  Required for an Apple *Organization* account — an individual account doesn't need
  one, but this is a company. Sdn Bhd entities qualify. Apply via Apple's enrolment
  flow or directly at `dnb.com`.
- **Confirm the company bank account name matches exactly.** Both App Store Connect
  and Play Console payouts get rejected on name mismatches more than any other
  cause. The account name must read `Agentic Market Intelligence` (or its registered
  SSM/company variant) — not a personal name, not a trading name.

## Phase 2 — Apple (company account)

The first three steps here are the ones that actually matter for testing — they
unblock the product screens in App Store Connect. Small Business Program only
matters for real revenue and doesn't block sandbox purchases.

- **Enrol in Apple Developer Program — Organization.** $99/yr. Needs the D-U-N-S
  number from Phase 1. Same fee as an individual account — cost isn't the reason to
  incorporate, credibility of the displayed seller name is.
- **Sign the Paid Apps Agreement.** *Unblocks testing.* In App Store Connect.
  Nothing accrues until this is signed — not a formality, a hard gate on every
  dollar. Also the gate on creating the seven product IDs at all — no products, no
  sandbox purchase to test.
- **Add banking details + tax form (App Store Connect).** *Unblocks testing.* Tax
  form is W-8BEN-E for a company (not the individual W-8BEN). Bank details go with
  the payout — see the name-match step above.
- **Apply to the Small Business Program.** Free, but not automatic. Drops
  commission from 30% to 15% while proceeds stay under $1M/yr. Must be actively
  applied for — it doesn't switch on by itself. Do this the same session as
  enrolment so no revenue accrues at the higher rate first.

## Phase 3 — Google (company account)

Both steps here unblock testing, not just production — Play won't let you create the
four subscription IDs or three one-time products until the payments profile exists.

- **Register a Play Console account.** $25 once — no annual renewal, unlike Apple.
- **Set up the Play payments profile + verification.** *Unblocks testing.* Company
  identity verification, banking, and a US tax form — this profile is **separate
  from AdMob's** (Phase 4). Completing this one does not carry over.

## Phase 4 — AdMob

Depends on CR225 re-linking the SDK before ads can actually serve — but the
account/payment side can be set up in parallel.

- **Create the AdMob account, register both apps.** iOS and Android each get
  registered separately inside the one AdMob account.
- **Add AdMob banking details + tax form.** Easy to forget because it feels like a
  duplicate of the Play step — it isn't. Skipping this withholds tax on every dollar
  of ad revenue, not just the portion that would normally be withheld.
- **Publish `app-ads.txt` on the website.** AdMob console shows the exact line once
  the account exists (`google.com, pub-<ID>, DIRECT, f08c47fec0942fa0`). Publish at
  `agenticmarketintel.ai/app-ads.txt`, then trigger a crawl check in console.
  Without it, your inventory is unauthorized and fill/eCPM drop.

## Phase 5 — RevenueCat product config

Code-side, unblocked by nothing above — but currently unconfigured. Probing the SDK
key today returns RevenueCat's stock template; none of the seven real products exist
yet.

- **Create the seven products + two entitlements in the RC dashboard.** Free below
  $2,500/mo. `trader_monthly` $14.99 · `trader_annual` $129 · `floor_manager_monthly`
  $34.99 · `floor_manager_annual` $299 · `credits_starter` $4.99 ·
  `credits_standard` $19.99 · `credits_power` $49.99 — mapped to entitlements
  `trader` / `floor_manager`.

## Parked deliberately, out of scope

Tax treatment (US withholding, Malaysian sourcing, SST), and whether/when to
formalize accounting for this revenue. Address those separately when the numbers are
real — this checklist is the mechanical path to a working payout, nothing more.
