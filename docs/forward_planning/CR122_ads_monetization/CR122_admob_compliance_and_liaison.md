# CR122 — AdMob compliance + liaison checklist (MOBILE-C / COMPLIANCE)

What the code shipped, what it deliberately did NOT fabricate, and the exact
Saiful-liaison steps between here and an AdMob-carrying store submission.
Referenced from `admob_config.dart`, `admob_real_sdk.dart`, both store build
scripts' ADS POLICY GATE, and the platform manifests.

**Nothing here blocks the build or house ads.** It blocks *store submission
of an ads-enabled build* — and the build scripts enforce that: with
`ADMOB_MODE` set they refuse to build until `ADMOB_POLICY_PUBLISHED=1`
acknowledges this checklist is done.

---

## 1. What is in the code today (no account needed)

| Piece | Where | State |
| --- | --- | --- |
| App ids (iOS + Android) | `mobile/ios/Runner/Info.plist` (`GADApplicationIdentifier`), `mobile/android/app/src/main/AndroidManifest.xml` (`com.google.android.gms.ads.APPLICATION_ID`) | **Google's PUBLISHED SAMPLE app ids** (`…~1458002511` iOS / `…~3347511713` Android). Committed because the GMA SDK crashes at launch without *some* id once the plugin is linked. They serve only Google demo inventory — harmless, never revenue. |
| Delay flags | same two files | `GADDelayAppMeasurementInit` / `DELAY_APP_MEASUREMENT_INIT` = true, so the native SDK stays dormant unless Dart calls `MobileAds.initialize()` — which never happens without `ADMOB_MODE`. |
| Test unit ids | `admob_config.dart` | Google's RESERVED test ad unit ids (sample publisher `3940256099942544`), literal-pinned in `test/services/admob_config_test.dart`. `ADMOB_MODE=test` uses them; always fill with test creatives. |
| Consent (UMP) | `admob_real_sdk.dart::RealAdMobUmpConsent` | `requestConsentInfoUpdate` → `loadAndShowConsentFormIfRequired` → `canRequestAds`; ATT ride-along on iOS; re-consent via Settings → AD PRIVACY (shown only when UMP says required). Any UMP failure = house fill, loudly. |
| CCPA | Settings → AD PRIVACY toggle → `rdp=1` extra on every request | Persisted; unreadable store fails TOWARD privacy (rdp on). |
| Content policy | `ad_content_policy.dart` | `maxAdContentRating='T'`, age treatment none (17+). The banned-category list is data here; enforcement is console-side (§3). |

## 2. Get test fill on real devices (no account needed)

1. Cable build: `ADMOB_MODE=test scripts/install_iphone.sh` — Google test
   interstitial + native fill through the full gate/caps/consent path.
2. EEA consent form from Riyadh: add
   `ADMOB_CONSENT_DEBUG_GEOGRAPHY=eea ADMOB_TEST_DEVICE_IDS=<device-id>`.
   The device id is printed by the GMA SDK in the run log on first request
   ("To get test ads on this device, set testDeviceIds…") — copy it from
   there; UMP debug geography only applies to registered test devices.
3. On-device test-plan items #1–#6 (`CR122_ads_monetization.md`) run in this
   mode. Item #1's second half (registered test device against **live** unit
   ids) needs §3 first.

## 3. Saiful — AdMob console (account material; do not fabricate)

1. Create/verify the AdMob account; register both apps (iOS + Android).
2. Swap the two sample app ids in the manifests for the real ones —
   one-line edits at the paths in §1 (commit as part of the CR122 closure).
3. Create ad units per platform: 1 interstitial + 1 native each. They ride
   into a build as
   `ADMOB_MODE=live ADMOB_INTERSTITIAL_AD_UNIT_ID=… ADMOB_NATIVE_AD_UNIT_ID=…`
   (per-platform values per pipeline run; never committed).
4. **Blocking controls** (`ads.md:20-31` — the list in
   `ad_content_policy.dart::bannedCategories`, pinned by test). AdMob has no
   per-request category parameter, so this lives in the console:
   Brand safety → Blocking controls, both apps:
   - Sensitive categories → block: *Get rich quick*, *Gambling & betting*
     (incl. lottery), *Sexually suggestive/Adult*, *Politics*, *Religion*,
     *Cryptocurrencies* (covers pump/dump), *Binary options*, *CFDs and
     forex* / *Speculative financial products* (covers unregulated brokers +
     high-leverage CFDs), *Financial newsletters/signal services* where
     offered as a category; anything not offered as a category goes in as
     advertiser-URL blocks as encountered.
   - Ad review center: enable, review weekly at first.
5. **Privacy & messaging** (UMP): create + publish the **GDPR message** (EEA)
   and the **iOS ATT explainer message** for both apps. Until a GDPR message
   is published, `loadAndShowConsentFormIfRequired` errors in the EEA — the
   app then serves house only (loud log, no blank slot), so this step is
   load-bearing for EEA programmatic revenue.
6. **US state regulations message** (optional now): our CCPA toggle already
   sends `rdp=1` independent of UMP.
7. `app-ads.txt`: console → App settings shows the exact line, shape
   `google.com, pub-<YOUR-PUB-ID>, DIRECT, f08c47fec0942fa0`. Hand it to the
   webmaster lane → publish at `https://agenticmarketintel.ai/app-ads.txt`
   (the `website/` tree), then trigger a crawl check in the console.

## 4. Saiful — store consoles

1. **17+ / adult rating** in both consoles (`ads.md:109`, COPPA posture).
2. **App Store privacy labels**: an AdMob build adds *Identifiers (Device
   ID)*, *Usage Data (Ad interactions)* under "Data Used to Track You" /
   "Third-Party Advertising" (exact taxonomy per Apple's current form +
   Google's published data-collection disclosure for GMA).
3. **Play Data safety form**: same, Google's disclosure for the GMA SDK.
4. **SKAdNetworkItems**: `Info.plist` carries Google's primary id
   (`cstr6suwn9.skadnetwork`). Before submission, paste Google's full
   current SKAdNetwork list (published in the AdMob iOS docs, ~50 entries)
   — it changes over time, so it is fetched at submission, not committed
   from memory today.

## 5. Privacy policy (DEF085 class — sequencing is the point)

The LIVE policy truthfully says "no advertising identifiers, no sharing with
advertisers" — and stays true while AdMob is dark, which is every build
without `ADMOB_MODE`. Publishing ad-sharing text *today* would be DEF085
mirrored (claiming data sharing that does not happen). So:

- The full v2.1 clause-level draft is ready in
  [`CR122_privacy_policy_v2.1_draft.md`](CR122_privacy_policy_v2.1_draft.md).
- Publish sequence (webmaster lane executes, Saiful approves wording):
  archive current → `/privacy/v2/`, publish v2.1 at `/privacy/`, give the
  clause-16 **14-day notice** (in-app banner / email), and only after the
  labels (§4) are also live, build with
  `ADMOB_MODE=live … ADMOB_POLICY_PUBLISHED=1`.
- The build scripts' ADS POLICY GATE makes this ordering structural, not a
  convention.

## 6. What remains explicitly unverifiable pre-listing

Fill rate, eCPM, revenue (CR122 doc, *Explicitly NOT claimed*). A green
suite + test fill is "the subsystem works", never "ads are earning".
