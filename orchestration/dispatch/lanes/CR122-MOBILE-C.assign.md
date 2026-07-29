<!-- dispatch assign lane — Architect-owned. CR052. -->
# CR122-MOBILE-C — assign (AdMob impl behind a config flag + build-script wiring)

KIND: code
INSTANCE: coder.mobile
ACCEPTANCE: docs/forward_planning/CR122_ads_monetization/CR122_ads_monetization.md (§Scope CR122-MOBILE-C, §Test plan "AdMob unset" + "Blocklist" + on-device slice, §Acceptance)
DEPENDS-ON: CR122-MOBILE-A (second impl of the facade A defines; integrate A first)
GATE: independent
HOT-FILES: mobile/lib/services/ads/** (coder.mobile), mobile/pubspec.yaml (NEW dependency — flagged), scripts/build_testflight.sh + scripts/build_playstore.sh + scripts/install_iphone.sh (coordinate with coder.store before touching)

**What:** `AdMobAdsService` — the second `AdsService` impl, via `google_mobile_ads` (iOS + Android-GMS). **Android-HMS `huawei_ads` is OUT of scope** — Huawei AppGallery is v1.1 per CLAUDE.md's platform decision. Leave the seam, do not add a third impl.

**New dependency — flag it.** `google_mobile_ads` is the first ad SDK in the tree. CLAUDE.md requires flagging new deps; `platform_facade.md:98` already names it as the intended one, so this is the sanctioned choice, not a free pick.

**1. Config via `--dart-define`, never committed.** Mirror `mobile/lib/services/billing/billing_config.dart:25-32` exactly — `String.fromEnvironment` with an empty default, per-platform app id + per-placement unit ids.

**2. Unset config = 100% house fill.** Log once at init, render no blank placement, throw nothing. This is the CR040 degrade-loudly requirement and it is testable without any AdMob account.

**3. Wire the build scripts IN THIS LANE.** `scripts/build_testflight.sh:108-109`, `scripts/build_playstore.sh:111-114` and `scripts/install_iphone.sh:97-98` pass `AMI_API_URL_ALPHA` / `GOOGLE_OAUTH_WEB_CLIENT_ID` / `SENTRY_DSN` and must also pass the AdMob defines, with the same empty-value warning pattern as `build_playstore.sh:102`. **This is not optional tidy-up: CR084 shipped a RevenueCat public SDK key that no build script consumed, so it sat inert in `infra/alpha.env` while every build shipped with an empty key — that is DEF100, still open.** Same trap, same lane, closed here.

**4. Banned categories on every programmatic request** — the `ads.md:20-31` blocklist: get-rich-quick, unregulated brokers, binary options, high-leverage CFDs, crypto pump/dump, signal services/pump newsletters, lottery/gambling, adult, politics, religious solicitation. `ads.md:33` is explicit that brand safety outranks fill rate. Assert the blocklist is attached in a test — an unenforced policy list is decoration.

**Testability — read this before claiming you cannot verify it.** No AdMob account and no store listing are required to prove this lane works: Google publishes reserved **test ad unit ids** per format and platform, and registering a **test device** forces test fill against real unit ids. Verify both paths. What genuinely cannot be verified pre-listing is fill rate and eCPM — revenue properties, not correctness ones. Do not report a green suite as evidence that ads earn.

**Constraints:** no screen imports `google_mobile_ads` — it lives only in `admob_ads_service.dart`, and MOBILE-A's facade-seam test must stay green. Do not weaken the forbidden-context tests. Consent/ATT/privacy work is CR122-COMPLIANCE, not this lane — but note the SDK must not be *initialised* ahead of consent where the platform requires it, so leave that ordering hook clean for COMPLIANCE.

**Self-test:** `cd mobile && flutter analyze` clean + `flutter test` green including the unset-config house-fill case and the blocklist assertion. Report counts + the exact dart-define names you added so the build docs can be updated.

**Hand-off:** write `orchestration/dispatch/lanes/CR122-MOBILE-C.coder.mobile.md` `STATUS: READY_FOR_AUDIT (round 1)` + `audit/handshake/cr/CR122-MOBILE-C.architect.md` + `SUBMITTED: round 1`. ONE commit, tag `(AT:coder.mobile CR122)`, push origin main.

<!-- Intentionally NOT assigned yet: DEPENDS-ON CR122-MOBILE-A. -->
