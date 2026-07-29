# CR122 — Ads monetization: `AdsService` facade, house-ad inventory, AdMob behind a flag

**Status:** proposed (scope locked by Saiful 2026-07-29 — see *Decision* below; awaiting a lane, not a decision)
**Depends on:** CR039 (credit gate / `effective_plan`), CR084 (RevenueCat entitlement — the upsell destination)
**Spec:** [`docs/initial_specs/06_monetization/ads.md`](../../initial_specs/06_monetization/ads.md) — policy is already locked, this CR is wiring
**Facade pattern:** [`docs/initial_specs/08_tech/platform_facade.md:98`](../../initial_specs/08_tech/platform_facade.md#L98) — `AdsService` is already a named service

---

## Decision (Saiful, 2026-07-29)

Asked which of four scopes to build. Answer: *"I need something thats easy to drop into the app that I do not need to do a lot of selling for."*

That rules **out** direct-deal inventory (the $10–25 eCPM tier in `ads.md:97` — highest yield, but it is a sales motion). It selects the two no-sales paths, both of which ride the same facade:

- **House ads** — our own upsell inventory. Zero SDK, zero consent flow, zero store dependency. Earns through the RevenueCat path wired in CR084.
- **AdMob programmatic** — automated fill, no selling. But see *Revenue timing* — it cannot pay until the app is publicly listed.

## Why now

Ads are the Floor Pass tier's entire revenue model (`tiers_and_pricing.md`), spec'd in detail since the initial specs, and **nothing has been built**: no ads CR existed before this one, no ad SDK in `mobile/pubspec.yaml`, no ad code in `mobile/lib/`. CR084 just landed real IAP, so the upsell destination a house ad points at now exists and works.

## Revenue timing — state this plainly, do not let it be discovered later

`ads.md:96-100` targets **$2–5 eCPM** programmatic and **$1–3/month ARPU** per Floor Pass MAU, capped at ≤8 impressions/user/day. Those are per-MAU targets, not totals. At stealth-alpha tester counts the programmatic total rounds to zero — ads are a MAU-leveraged lever.

Two hard gates on programmatic revenue, both outside this CR's code:

1. **Real AdMob fill requires a published app.** Test ads render pre-launch; live fill needs the app listed in the App Store / Play, an approved AdMob account, and `app-ads.txt` served from `agenticmarketintel.ai`.
2. **The compliance slice gates store submission** (see below), so shipping the SDK without it is not shippable at all.

House ads have neither gate. That is why they are built first and why the AdMob impl is flag-gated rather than assumed-on: **an unset AdMob config must fill 100% house, never render a blank slot.**

---

## Scope

### CR122-MOBILE-A — facade + house ads (`coder.mobile`)

The earning half. No third-party SDK, no new dependency.

- `AdsService` facade per `platform_facade.md:98`, with `HouseAdsService` (universal) as the first implementation. App code calls the facade only — no screen imports an ad SDK, same seam CR084 built for `purchases_flutter` (`mobile/lib/services/billing/purchase_service.dart`).
- **House inventory**, the 4 slots in `ads.md:85-88`, targeted on usage: Floor Pass out of free 1-on-1s → Trader; Floor Pass used its free Room → Trader; Trader near credit cap → Floor Manager; Trader on a halal mandate → Floor Manager. Tapping one lands in the CR084 paywall.
- **The 6 approved placements, and only those** (`ads.md:39-44`): post-lesson interstitial, Daily Challenge results, Decision Journal empty state, Sim Portfolio empty state, Academy Hub bottom, Wallet & Plan.
- **Ads off for anyone paying.** Keyed on the backend's `effective_plan` — `floor_pass` only. `trial_trader` counts as paying and sees no ads. Upgrade removes ads immediately (`ads.md:113`); downgrade restores them next session (`ads.md:115`).
- **UX rules** (`ads.md:56-65`): 5s-skippable interstitials, `AD` / `SPONSORED` label in JetBrains Mono UPPERCASE, one-tap dismiss on native cards, visually distinct from agent cards, no autoplay-with-sound. **No rewarded ads** — founder decision, `ads.md:65`.

### CR122-MOBILE-B — frequency caps, persisted (`coder.mobile`)

Split out because it is the one part with a silent-failure mode. Caps from `ads.md:59-60`: 1 interstitial per 5 lessons completed, max 4 per session, max 1 per 10 minutes, ≤8 impressions/day.

**The caps must persist across app restarts.** An in-memory counter resets on every cold start, which turns "max 4 per session" into "unlimited" for anyone who backgrounds the app — and it fails *quietly*, looking like normal ad delivery while the user gets hammered. This is the CR040 degrade-loudly question applied to a counter: *if this resets constantly and silently, what does the user experience?* Persist the counters and the last-impression timestamp; a cap that cannot be read must block the ad, not allow it.

### CR122-MOBILE-C — AdMob behind a config flag (`coder.mobile`)

- `AdMobAdsService`, the second facade impl, via `google_mobile_ads` — a **new dependency**, flagged per CLAUDE.md's lean-stack rule.
- App id + unit ids supplied at build time by `--dart-define`, never committed — the same pattern as `mobile/lib/services/billing/billing_config.dart:25-32`. Forward them in the build scripts in this lane (`scripts/build_testflight.sh`, `scripts/build_playstore.sh`, `scripts/install_iphone.sh`), because CR084 shipped a key with no build-script consumer and it sat inert — see DEF100.
- **Unset config = 100% house fill**, logged once at init. Never a blank placement, never a crash, never a silent no-op that reads as "ads are broken".
- Programmatic requests carry the `ads.md:20-31` blocklist (get-rich-quick, unregulated brokers, binary options, high-leverage CFDs, crypto pump/dump, signal services, gambling, adult, politics, religious solicitation). Brand safety over fill rate — `ads.md:33`.
- **Android-HMS (`huawei_ads`) is out of scope here** — Huawei AppGallery is v1.1 per CLAUDE.md's platform decision. The facade leaves the seam; no third impl now.

### CR122-COMPLIANCE — the store-submission gate (`coder.mobile` + Saiful liaison)

**Blocks store submission, not the build.** None of it is needed for house ads; all of it is needed before an AdMob-carrying build can be submitted.

- **App Tracking Transparency** prompt on iOS (`ads.md:106`); declining still serves ads, just non-personalised.
- **EEA consent** via AdMob's UMP SDK (`ads.md:107`).
- **CCPA "Do Not Sell" toggle** in Settings (`ads.md:108`).
- **17+ rating** to stay out of COPPA scope (`ads.md:109`).
- **Privacy policy + App Store privacy labels must change.** An ad SDK is third-party data sharing; the policy has to say so. **DEF085 was exactly a false third-party-vendor claim in this policy** — shipping AdMob without updating it repeats that defect with a bigger blast radius. Treat the policy edit as part of the code change, not paperwork that follows it.
- `app-ads.txt` published on `agenticmarketintel.ai` (the `website/` tree).

---

## Out of scope

- **Direct-deal inventory** — explicitly declined in the Decision above. The facade must not preclude it; nothing is built for it.
- **Rewarded ads** — founder decision, `ads.md:65`. Not "later", ruled out.
- **Android-HMS ads impl** — v1.1 with AppGallery.
- **IronSource / Pangle mediation** — `ads.md:71-74` lists them as backup; single-network first, mediation only if fill rate justifies it.
- **Ad-revenue analytics dashboards** — impressions are logged; reporting is AdMob's console at this stage.
- **Re-deciding placements or policy.** `ads.md` is locked. This CR wires it.

---

## Saiful-liaison dependency (BLOCKING for programmatic revenue, NOT for the build or for house ads)

Accounts and money, same class as DEF100. **Do not fabricate app ids or ad unit ids.**

- AdMob account, app registered, ad units created per placement.
- `app-ads.txt` content to publish on the website.
- Store listings live (App Store + Play) — the precondition for any real fill.
- Rating set to 17+ in both consoles.

House ads need **none** of this and can ship and earn while it is outstanding.

---

## Acceptance

- [ ] `AdsService` facade exists; no screen imports an ad SDK directly (grep-enforced in test, mirroring the CR084 seam).
- [ ] A Floor Pass user sees house ads in the 6 approved placements; each carries an `AD`/`SPONSORED` label and a one-tap dismiss.
- [ ] **A test asserts no ad widget can render in any of the 7 forbidden contexts** (`ads.md:46-54`): the honeycomb home, Concierge conversation, Convene the Room / 1-on-1 / Brief Your Agent, agent profile cards, Mandate flows, onboarding/first-run, trade ticket. Structural, not a code-review convention — per CLAUDE.md, an instruction is not a control.
- [ ] `trader` / `floor_manager` / `trial_trader` see zero ads; a completed CR084 upgrade removes ads without an app restart.
- [ ] Frequency caps hold **across a cold start** — the persistence test is the point of MOBILE-B; an unreadable cap blocks the ad.
- [ ] With AdMob config unset: 100% house fill, one init-time log line, no blank placement and no crash.
- [ ] With AdMob config set: a test ad renders in a real build, and the build scripts actually pass the dart-defines (the DEF100 failure mode does not repeat).
- [ ] Banned-category blocklist applied to programmatic requests.
- [ ] Privacy policy + App Store privacy labels updated in the same change as the SDK; no claim about third-party data sharing is left false (DEF085 class).
- [ ] Mobile suite green; no room-cluster or forbidden-path edits.
- [ ] Independent auditor `VERDICT: COMPLETE` on MOBILE-A and MOBILE-B at minimum.

---

## Lanes

- **CR122-MOBILE-A** → `coder.mobile`, `GATE: independent` — facade + house ads. Ships and earns alone.
- **CR122-MOBILE-B** → `coder.mobile`, `DEPENDS-ON: CR122-MOBILE-A` — persisted frequency caps.
- **CR122-MOBILE-C** → `coder.mobile`, `DEPENDS-ON: CR122-MOBILE-A` — AdMob impl behind the flag.
- **CR122-COMPLIANCE** → `coder.mobile` + Saiful liaison, `DEPENDS-ON: CR122-MOBILE-C` — must land before any AdMob build is submitted.
