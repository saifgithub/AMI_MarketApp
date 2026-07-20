# CR048 — Play Store internal testing distribution + fastlane automation

**Status:** in_progress
**Filed:** 2026-07-20 (AT:R64)
**Builds on:** [D-057](../../initial_specs/11_decisions/decision_log.md) (Android-GMS pulled into Alpha; internal-track distribution + Play App Signing locked) and `scripts/build_playstore.sh` (already builds a signed AAB). Ownership per [`you_do_i_do.md`](../../initial_specs/10_delivery/you_do_i_do.md).

---

## Why

Testers get Android builds as raw APKs today — USB sideload via `scripts/install_android.sh` onto two Galaxy devices, plus WhatsApp APK sharing. Saiful's ask: *"I don't want to keep sending APKs to my testers. I want them to be able to download a new test version from the Play Store."*

The Play Console **Internal testing track** is exactly the TestFlight-equivalent for that: up to 100 testers, no review, live in minutes; testers install once from an opt-in link and every future build arrives as a normal Play Store update. D-057 already chose this track — this CR closes the last mile.

The build/signing half already exists. What's new: (1) the one-time bootstrap to actually get the app onto the internal track, and (2) **fastlane supply** so every release after the first is a single command, no web UI. Saiful chose the automated path over manual per-release uploads (2026-07-20).

## What already existed (reused, not rebuilt)

- `scripts/build_playstore.sh` — builds a signed `--release` AAB, auto-bumps the shared `+N` build number, prints manual-upload steps.
- Gradle release signing in `mobile/android/app/build.gradle.kts` (reads `~/.android-keys/keystore.properties`).
- Upload keystore **present and valid** — `~/.android-keys/ami-trade-upload.keystore` + `keystore.properties` both exist (verified R64). The earlier handover note calling this unwritten was stale; corrected in `HANDOVER_R.md`.
- Play Console account registered (individual, D-057). `applicationId = ai.agenticmarketintel.ami_trade`, `minSdk 28` / `targetSdk 35`.

## Scope

### Code (Claude — landed this CR)

- **`mobile/android/fastlane/Fastfile`** — `internal` lane (`upload_to_play_store` → track `internal`, `release_status: completed`, metadata/screenshots/changelogs skipped) + `validate` lane (`validate_only: true`, dry run). Uploads only; does not build.
- **`mobile/android/fastlane/Appfile`** — `package_name` + `json_key_file` read from `SUPPLY_JSON_KEY` (default `~/.android-keys/play-service-account.json`, outside the repo).
- **`mobile/android/Gemfile`** — pins fastlane; `bundle install` once.
- **`scripts/publish_playstore.sh`** — release #2+ one-liner: runs `build_playstore.sh` (bump + signed AAB), then `bundle exec fastlane internal`. Flags pass through (`--no-bump`, `--no-commit`); `--validate` for a dry run. **Fails loudly** if the service-account key is missing (CR040 degrade-loudly) rather than silently skipping the upload.
- **`.gitignore`** — fastlane generated artifacts (`report.xml`, generated `README.md`, `.bundle/`, `vendor/bundle/`). `Fastfile`/`Appfile`/`Gemfile`/`Gemfile.lock` are tracked. Service-account JSON never enters the repo.
- **`scripts/build_playstore.sh`** — header cross-reference to the new publish script.

### One-time operations (Saiful — Part-C checklist)

**1. Play Console API service account (enables fastlane)**
- Play Console → **Setup → API access** → link or create a Google Cloud project.
- Create a service account (opens GCP IAM) → back in Play Console, grant it app access under **Users & permissions**: *"Release to testing tracks, excluding production"* + *"Manage testing track releases"*.
- In GCP, create a **JSON key** for that service account → save it to `~/.android-keys/play-service-account.json` (never commit it).

**2. First manual upload (enrolls Play App Signing — one-time, irreversible)**
- Build a fresh AAB (Claude does this in R64, or run `scripts/build_playstore.sh`).
- Play Console → create the app entry if it doesn't exist → **Testing → Internal testing → Create new release** → upload the AAB → accept Play App Signing enrollment.
- Complete the required **App content** declarations: privacy policy URL, Data safety, Content rating, Target audience, Ads, News/Financial-features declarations as prompted → review → **Roll out to internal testing**.

**3. Testers + opt-in link**
- Internal testing → **Testers** tab → create an email list of testers' Google-account emails → **Save**.
- Copy the **opt-in URL** → send to testers. Each opens it → *"Become a tester"* → installs from the Play Store. The two existing Galaxy devices switch from sideload to this link.

### Steady state (release #2 onward)

`scripts/publish_playstore.sh` → builds + pushes to the internal track. Testers get it as a Play Store auto-update. No APKs, no web UI.

## Constraints / notes

- **First upload cannot be automated.** Google requires the initial submission via the web UI to enroll Play App Signing; `supply` handles release #2 onward only. Sequenced accordingly above.
- **Individual-account production gate** (14-day / 12-tester closed testing before production) does **not** apply to the internal track (D-057) — internal testers get builds immediately.
- Testers must each have a Google account and accept the opt-in link on-device — a one-time change from the current sideload flow.
- The test build keeps `ALLOW_BACKEND_SWITCH=true` + Alpha URL (unchanged from today's APKs) — testers stay on the Alpha cohort, no behaviour change.

## Acceptance

- [x] fastlane scaffolding + `publish_playstore.sh` land; `bundle exec fastlane lanes` lists `internal` + `validate`.
- [x] Fresh release-signed AAB builds (no debug-signing fallback warning).
- [ ] Saiful: service account created + JSON key at `~/.android-keys/play-service-account.json`.
- [ ] Saiful: first AAB manually uploaded to internal testing; Play App Signing enrolled; testers added; opt-in link shared.
- [ ] Verified: `scripts/publish_playstore.sh` pushes a release #2 that appears in Play Console → Internal testing and lands on a tester's device as a Play Store update.

CR closes when a tester installs a build from the Play Store and a subsequent `publish_playstore.sh` release reaches them as an auto-update.
