# CR258 — Migrate AMI Trade to the company developer accounts

Executes D-073 (`docs/initial_specs/11_decisions/decision_log.md`): re-platform from Saiful's personal Apple/Google identity to **Agentic Market Intelligence Sdn Bhd**, then connect RevenueCat and AdMob under the company. Prior research: `docs/forward_planning/CR231_stabilisation_programme/revenue_setup_research.md`.

**Status: proposed → in progress (Phase A).** Requested by Saiful 2026-10-13.

## Company identities (no secrets in this repo)

| Purpose | Identity | State |
|---|---|---|
| Apple Developer (Organization) | Apple-Developer@AgenticMarketIntel.ai | mailbox created 2026-10-13; enrolment not started |
| Google Play Console (Organization) | Android-developer@AgenticMarketIntel.ai | mailbox created 2026-10-13; enrolment not started |
| Legal entity | Agentic Market Intelligence Sdn Bhd | D-U-N-S: **pending** |

Passwords, recovery codes, 2FA seeds, `.p8`/keystore/service-account files: never in the repo. Keep in the company password manager; local key files stay under `~/.android-keys/` and `~/.appstoreconnect/`.

## Current (personal) values to be replaced

1. iOS bundle `ai.agenticmarketintel.amiTrade`; Apple team `S7RBWM4879` (`mobile/ios/Runner.xcodeproj/project.pbxproj`, `ExportOptions.plist`; `APPLE_AUDIENCES` in `docker-compose.yml`).
2. Android `ai.agenticmarketintel.ami_trade` (`mobile/android/app/build.gradle.kts`, `fastlane/Appfile`); upload keystore via `~/.android-keys/keystore.properties`.
3. ASC API key/issuer defaults in `scripts/build_testflight.sh`; Play service account in `scripts/publish_playstore.sh`.
4. Google OAuth Web client (`serverClientId`, `sign_in_screen.dart`; backend `GOOGLE_AUDIENCES`) — see DEF076.
5. RevenueCat: `REVENUECAT_IOS_SDK_KEY`, `REVENUECAT_ANDROID_SDK_KEY`, `REVENUECAT_SECRET_API_KEY`, `REVENUECAT_WEBHOOK_SECRET` — see DEF100.
6. AdMob: Google test IDs in `Info.plist` / `AndroidManifest.xml`; real unit IDs not yet created.
7. OneSignal APNs key (tied to Apple team); `ONESIGNAL_APP_ID`, `ONESIGNAL_REST_KEY`.
8. Not used / no change: Firebase (none), universal links (none), legal URLs (already company domain).

## Phases

**A — Company foundations (Saiful).** 1. D-U-N-S for the Sdn Bhd (5–14 days; name/address match SSM). 2. ✅ Role mailboxes created. 3. Business phone for Apple verification call. 4. Company bank, tax, SSM and director ID.

**B — Store accounts.** Apple Organization (US$99/yr): Apple ID → enrol with D-U-N-S → Paid Apps Agreement + bank/tax → App ID, Sign in with Apple, APNs key, ASC API key. Google Play Organization (US$25): register → identity verification → payments profile → app + Play App Signing → service-account JSON. New org accounts need a closed test (12+ testers, 14 days) before production — start early.

**C — Services.** RevenueCat (org, iOS+Android apps, ASC/Play connections, products `trader_*`/`floor_manager_*`/credit packs, entitlements, offerings, webhook). AdMob (company account, apps, real ad units; `ad_policy.md`). Google Cloud project (OAuth Web/Android/iOS clients, new package + SHA-1). OneSignal (new APNs key).

**D — Repo/backend (Claude).** Update the files in the table above, melehost `.env` + `docker-compose.yml` forwarding (config-compose parity test), then `build_testflight.sh` → `publish_playstore.sh --no-bump`. Sandbox-test purchases, restore, ads, push, Apple/Google sign-in.

**E — Cutover.** Testers move to company TestFlight/Play internal track; retire personal-team artefacts (`Apple_Store/`, old keys) only after stable; update D-073, `hosting.md`, `payments.md`.

## Open decisions

1. **Bundle ID:** keep (requires personal account to release it; TestFlight-only apps may not be transferable) or take new IDs (testers re-invited, Apple-linked user `sub` migration check).
2. Whether the existing OneSignal app is reused or a new one is created.

## Claude-in-Chrome split

Claude drives console configuration (RevenueCat, AdMob, GCP, ASC/Play app, IAP products, API keys) and copies IDs into the repo. Saiful does D-U-N-S/KYC, SMS/2FA/verification calls, CAPTCHAs, bank/payment details and legal agreements.

## Acceptance

1. Release build installs from company TestFlight and Play internal track.
2. Sandbox purchase → RevenueCat webhook → entitlement visible on backend.
3. Real AdMob unit serves on a test device; Apple + Google sign-in succeed.
4. `pytest backend/tests/unit/test_config_compose_parity.py` passes.
