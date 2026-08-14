#!/usr/bin/env bash
# Build a signed AAB for Google Play Console internal testing track.
#
# Sibling of scripts/build_testflight.sh. Same monotonic build number
# is shared across iOS + Android (the `+N` in pubspec.yaml).
#
# Pipeline:
#   1. (optional) bump pubspec build number
#   2. flutter build appbundle --release --dart-define=...
#         (Gradle signs the AAB using ~/.android-keys/keystore.properties
#          when present; falls back to debug signing when absent — that
#          fallback path is OK for local smoke testing only, never for
#          Play upload.)
#   3. surface the AAB path + the manual upload reminder
#
# First upload to Play Console is mandatory-manual (Play App Signing
# enrollment on the very first build). For every release AFTER the first,
# use scripts/publish_playstore.sh — it builds (via this script) then pushes
# to the internal track with `fastlane supply` (CR048). No web UI.
#
# Usage:
#   scripts/build_playstore.sh                  # bump + build + show path
#   scripts/build_playstore.sh --no-bump        # use whatever's in pubspec
#   scripts/build_playstore.sh --no-commit      # don't auto-commit the bump
#   scripts/build_playstore.sh --no-billing     # deliberately ship WITHOUT in-app purchase
#   scripts/build_playstore.sh --internal-only  # required when the RC key is a test_… Test Store key
#
# Required env (defaults match the production alpha setup):
#   AMI_API_URL_ALPHA              - backend URL baked into the build
#   REVENUECAT_ANDROID_SDK_KEY     - public RC SDK key for Android, `goog_…`
#                                    (CR084/DEF100). Auto-sourced from
#                                    infra/alpha.env if not exported. Public by
#                                    design — safe to embed in a shipped client.
#                                    A `test_…` key is RevenueCat's Test Store:
#                                    purchases are SIMULATED, no store products
#                                    needed. Right for alpha, but restricted to
#                                    the Play INTERNAL testing track — requires
#                                    --internal-only, and blocked in prod.
#   GOOGLE_OAUTH_WEB_CLIENT_ID     - GCP OAuth 2.0 Web client_id for Google Sign-In
#                                    (the same value the backend has in
#                                     GOOGLE_AUDIENCES env var on melehost)
#   SENTRY_DSN                     - optional; left empty if unset
#
# BILLING GATE (CR084 / CR040 degrade-loudly): without the SDK key,
# `BillingConfig.isConfigured` is false and the paywall renders the info state
# with NO buy button — the app cannot take money. Correct for a dev build, a
# silent revenue outage for a store build, so this script REFUSES to build
# without the key unless you pass --no-billing.
#
# Required setup before first run (per D-057):
#   - ~/.android-keys/ami-trade-upload.keystore     (Saiful's keystore)
#   - ~/.android-keys/keystore.properties           (referenced from build.gradle.kts)
#     Format:
#       storeFile=/Users/<saiful>/.android-keys/ami-trade-upload.keystore
#       storePassword=<...>
#       keyAlias=upload
#       keyPassword=<...>

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"
# CR050 — GCP OAuth 2.0 **Web** client_id (ami-trade-web). Public config: it is
# stamped into the Google ID token's `aud` and the backend verifies it against
# GOOGLE_AUDIENCES. Baked as the default so Google Sign-In is never silently
# disabled by a forgotten export (DEF038-class). Override via env if the key rotates.
: "${GOOGLE_OAUTH_WEB_CLIENT_ID:=153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com}"
: "${SENTRY_DSN:=}"

# CR084: source the public RC SDK key from the canonical gitignored env file
# unless already exported, so there is one place to paste a key, not two.
if [[ -z "${REVENUECAT_ANDROID_SDK_KEY:-}" && -f "${PROJECT_ROOT}/infra/alpha.env" ]]; then
  REVENUECAT_ANDROID_SDK_KEY="$(grep -E '^REVENUECAT_ANDROID_SDK_KEY=' "${PROJECT_ROOT}/infra/alpha.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ' || true)"
fi
: "${REVENUECAT_ANDROID_SDK_KEY:=}"

DO_BUMP=1
DO_COMMIT=1
DO_BILLING=1
DO_PRODUCTION=0
DO_INTERNAL_ONLY=0
DO_GAMES=1
for arg in "$@"; do
  case "$arg" in
    --no-bump)    DO_BUMP=0 ;;
    --no-commit)  DO_COMMIT=0 ;;
    --no-billing) DO_BILLING=0 ;;
    --production) DO_PRODUCTION=1 ;;
    --internal-only) DO_INTERNAL_ONLY=1 ;;
    --no-games)   DO_GAMES=0 ;;
    -h|--help)
      sed -n '2,/^$/p' "$0"
      exit 0
      ;;
    *)
      echo "✗ unknown flag: $arg" >&2
      exit 2
      ;;
  esac
done

keystore_props="$HOME/.android-keys/keystore.properties"
if [[ ! -f "$keystore_props" ]]; then
  echo "⚠ no keystore at $keystore_props — Gradle will fall back to DEBUG signing"
  echo "  That AAB will NOT be accepted by Play Console. Set up the keystore"
  echo "  first (per D-057 / docs/initial_specs/10_delivery/you_do_i_do.md), then re-run."
  echo "  Continuing anyway for local smoke testing only."
  echo ""
fi

# CR084 — RevenueCat Test Store key (`test_…`). Purchases are SIMULATED by
# RevenueCat: paywall, webhook, entitlement grant and credit top-up all run for
# real, but no money moves and no store product is needed. Right for alpha; a
# giveaway if it reaches real users, so: banner-loud here, blocked in production.
# GAMES + PRODUCTION = refuse. Structural, not advisory.
#
# Play makes this sharper than iOS: the Console lets you promote an INTERNAL
# build straight to production in two clicks, so the only thing standing
# between a games binary and the store was a banner asking nicely. A banner
# is not a control (CR040).
if [[ "$DO_GAMES" -eq 1 && ( "${RELEASE_CHANNEL:-}" == "production" || "$DO_PRODUCTION" -eq 1 ) ]]; then
  echo "✗ This is a PRODUCTION build and AMI_GAMES is on." >&2
  echo "  A hidden feature in a store binary is App Review guideline 2.3.1," >&2
  echo "  and Play's own policy on undisclosed functionality says the same." >&2
  echo "  Rebuild with --no-games:" >&2
  echo "" >&2
  echo "      scripts/build_playstore.sh --production --no-games" >&2
  exit 1
fi

# DEF290 — the containment rule below applies only to a build that can actually
# transact. DEF282 removed the RevenueCat SDK from the app's code path entirely
# (`purchase_providers.dart` returns `DisabledPurchaseService`, which does not
# import `purchases_flutter`, and `BillingConfig.usableKey` blanks any `test_`
# key in a non-debug build regardless). The gate's own message — "Purchases in
# this build are SIMULATED" — was false about every build we could produce, and
# its remedy asked the operator to affirm it to proceed.
#
# With `--no-billing` there is no purchase path to contain, and the key is
# blanked below rather than compiled in, so RevenueCat's rule is satisfied
# structurally rather than by a promise. The `--production` refusal above is
# untouched and still absolute.
if [[ "$DO_BILLING" -eq 1 && "$REVENUECAT_ANDROID_SDK_KEY" == test_* ]]; then
  if [[ "${RELEASE_CHANNEL:-}" == "production" || "$DO_PRODUCTION" -eq 1 ]]; then
    echo "✗ REVENUECAT_ANDROID_SDK_KEY is a Test Store key (test_…) and this is a PRODUCTION build." >&2
    echo "  Every user would receive paid entitlements without paying. Refusing." >&2
    echo "  Use the App-specific public key (goog_…) for production." >&2
    exit 1
  fi
  if [[ "$DO_INTERNAL_ONLY" -ne 1 ]]; then
    cat >&2 <<'BANNER'
✗ REVENUECAT_ANDROID_SDK_KEY is a Test Store key (test_…) and --internal-only was not passed.

  RevenueCat's own rule: "Never submit an app to the App Store or Google Play
  that is configured with a Test Store API key." This AAB is built for upload.

  Our narrowing (CR084 "Alpha distribution constraint"): a test_… build may go
  to the Play **internal testing** track only — never closed, open or production,
  which are reviewed and reach people outside the team. Purchases in this build
  are SIMULATED: buying grants Plan + credits for real in our DB, no money moves.

  If this build is for internal testers, say so:

      scripts/build_playstore.sh --internal-only
      scripts/publish_playstore.sh --internal-only

  For anything wider, rebuild with the App-specific public key (goog_…) and real
  Play Console products (DEF100, production phase).
BANNER
    exit 1
  fi
  cat <<'BANNER'
┌──────────────────────────────────────────────────────────────────┐
│  SIMULATED PURCHASES — RevenueCat Test Store key in this build.  │
│  Buying grants Plan + credits for real in our DB. No money moves.│
│  PLAY *INTERNAL TESTING* TRACK ONLY — never closed/open/prod.    │
│  Rebuild with a goog_… key for anything beyond internal testers. │
└──────────────────────────────────────────────────────────────────┘
BANNER
fi

if [[ -z "$GOOGLE_OAUTH_WEB_CLIENT_ID" ]]; then
  echo "⚠ GOOGLE_OAUTH_WEB_CLIENT_ID is empty — Google Sign-In button will be"
  echo "  disabled in this build. Set it once the GCP OAuth Web client is created."
  echo ""
fi

# ORDER IS LOAD-BEARING (DEF279): every refusal above runs BEFORE the
# pubspec bump below. It used to run after, so a refused build had
# already bumped and COMMITTED a build number that was never uploaded —
# Apple and Google both reject a re-upload at the same +N, so the number
# was spent, and the next real build skipped it. This bit us twice: the
# 0.1.0+85/+86 double-burn (reverted in b27a08e4) and again on the first
# +86 attempt, where the Test-Store-key gate fired one line after the
# commit. A gate that costs something when it fires teaches the operator
# to route around it.

pubspec="${MOBILE_DIR}/pubspec.yaml"
current_line=$(grep -E "^version:" "$pubspec")
current_version=$(echo "$current_line" | sed -E 's/version:[[:space:]]*//')
semver="${current_version%+*}"
build_num="${current_version#*+}"

if [[ "$DO_BUMP" == "1" ]]; then
  new_build=$((build_num + 1))
  new_version="${semver}+${new_build}"
  echo "▶ bumping pubspec: ${current_version} → ${new_version}"
  sed -i '' "s/^version: ${current_version}$/version: ${new_version}/" "$pubspec"
  build_num="$new_build"
  if [[ "$DO_COMMIT" == "1" ]]; then
    (cd "$PROJECT_ROOT" && git add mobile/pubspec.yaml && \
      git commit -m "chore(mobile): bump build ${semver}+$((build_num - 1)) → ${semver}+${build_num} for Play Store" \
      > /dev/null && echo "▶ committed bump")
  fi
else
  echo "▶ using existing version ${semver}+${build_num} (--no-bump)"
fi

# CR084 billing gate — fail loudly rather than ship a paywall that cannot charge.
if [[ "$DO_BILLING" -eq 1 && -z "$REVENUECAT_ANDROID_SDK_KEY" ]]; then
  cat >&2 <<'EOF'
✗ REVENUECAT_ANDROID_SDK_KEY is empty — this build could not take a payment.

  BillingConfig.isConfigured would be false, so the paywall renders the
  info state with no buy button. Nothing crashes and nothing warns; the
  app simply never sells anything (CR084 / DEF100).

  Fix: add the Android public SDK key to infra/alpha.env —

      REVENUECAT_ANDROID_SDK_KEY=goog_xxxxxxxxxxxxxxxxxxxx

  Get it from RevenueCat → Project Settings → API keys → the *App-specific
  public* key for the Android app. It starts with `goog_`. Do NOT use the
  secret `sk_…` key here; that one is backend-only and must never ship in
  a client.

  If you genuinely want a build with purchasing disabled, re-run with
  --no-billing and this check will stand down.
EOF
  exit 1
fi
if [[ "$DO_BILLING" -eq 0 ]]; then
  echo "⚠ --no-billing: shipping WITHOUT in-app purchase (paywall = info state only)"
  # DEF290, Android half. `:307`'s dart-define is unconditional, so a build that
  # cannot sell would still compile a `test_…` key into the AAB — "an app
  # configured with a Test Store API key" by RevenueCat's own wording, which is
  # the thing their rule forbids shipping. The app already refuses to use it
  # (`BillingConfig.usableKey` blanks a test_ key in any non-debug build, and
  # DEF282 removed the SDK from the code path entirely); this makes the binary
  # not carry it either.
  REVENUECAT_ANDROID_SDK_KEY=""
fi

echo "▶ flutter build appbundle  (release, signed if keystore present)"
cd "$MOBILE_DIR"
if [[ "$DO_GAMES" -eq 1 ]]; then
cat <<'BANNER'
┌──────────────────────────────────────────────────────────────────┐
│  THIS BUILD CARRIES THE CR109 GAME (AMI_GAMES=true).             │
│                                                                  │
│  It is a VISIBLE FIFTH TAB (AmiTab.visible), reachable by tap    │
│  from launch — no gesture, nothing hidden about it. It is fine   │
│  here because publish_playstore.sh is pinned to the Play         │
│  INTERNAL testing track, which is unreviewed and team-only.      │
│                                                                  │
│  DO NOT promote this release to closed/open testing or           │
│  production from the Play Console — Play lets you promote an     │
│  internal build straight to production, and this one must not    │
│  go. Rebuild without AMI_GAMES first. Saiful's call, AT:R66:     │
│  "if anyone finds it, it will be an easter egg for them."        │
└──────────────────────────────────────────────────────────────────┘
BANNER
else
cat <<'BANNER'
┌──────────────────────────────────────────────────────────────────┐
│  --no-games: AMI_GAMES=false. No games route is compiled in, so  │
│  an accidental Console promotion to production carries nothing   │
│  undisclosed. This is the build shape a PUBLIC release needs.    │
│                                                                  │
│  Verified below against the AAB itself, not against this flag —  │
│  the check inverts, and a games string FOUND here is a hard      │
│  failure rather than a warning.                                  │
└──────────────────────────────────────────────────────────────────┘
BANNER
fi

# A release build must not compile against another build's generated code.
#
# `GeneratedPluginRegistrant.java` is generated and gitignored, and Flutter
# writes it only when it is ABSENT or the plugin set changed — it does not
# overwrite a stale one. So a debug or integration-test build (the QA lane
# runs them) leaves a registrant that registers `integration_test`, and the
# release variant excludes dev dependencies from the classpath:
#
#   error: package dev.flutter.plugins.integration_test does not exist
#
# Nothing is misconfigured — `integration_test` is correctly in
# dev_dependencies and correctly flagged `dev_dependency: true`. The file is
# simply one artefact serving two build types, last writer wins. Measured
# (AT:R66): the stale file carried 2 references and failed; deleted and
# regenerated by the same release build, 0 references and a clean APK.
#
# Same class as the native-asset clear in build_testflight.sh. Generated
# output is regenerated; deleting it costs nothing and removes the only way
# this can fail.
echo "▶ clearing the generated plugin registrant (a debug build must not leak into a release)"
# Deleting the registrant is NOT enough, which cost a failed Play publish
# (0.1.0+85). The registrant is GENERATED FROM `.flutter-plugins-dependencies`,
# so a stale resolution simply regenerates the same broken file: that cache
# was 12 days old and still listed `integration_test` under `android`, and the
# fresh registrant duly imported it again. Clearing the resolution too forces
# Flutter to re-evaluate which plugins the RELEASE variant actually has —
# same shape as build_testflight.sh's `.dart_tool` clears, and for the same
# reason: removing an output while leaving the state that produced it just
# reproduces the output.
rm -f "${MOBILE_DIR}/android/app/src/main/java/io/flutter/plugins/GeneratedPluginRegistrant.java" \
      "${MOBILE_DIR}/.flutter-plugins-dependencies"
rm -rf "${MOBILE_DIR}/.dart_tool/flutter_build"

flutter build appbundle --release \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  --dart-define=GOOGLE_OAUTH_WEB_CLIENT_ID="${GOOGLE_OAUTH_WEB_CLIENT_ID}" \
  --dart-define=SENTRY_DSN="${SENTRY_DSN}" \
  --dart-define=AMI_GAMES="$([[ "$DO_GAMES" -eq 1 ]] && echo true || echo false)" \
  --dart-define=REVENUECAT_ANDROID_SDK_KEY="${REVENUECAT_ANDROID_SDK_KEY}"

aab="${MOBILE_DIR}/build/app/outputs/bundle/release/app-release.aab"
if [[ ! -f "$aab" ]]; then
  echo "✗ no AAB produced at $aab — flutter build appbundle failed?"
  exit 1
fi
size_mb=$(du -m "$aab" | cut -f1)
echo "▶ built $(basename "$aab") (${size_mb} MB, build ${semver}+${build_num})"

# CR109 — prove the AMI_GAMES define took, don't trust the flag.
#
# `bool.fromEnvironment` accepts ONLY the literal "true"/"false"; anything
# else silently compiles to the default. `AMI_GAMES=1` once produced a
# perfectly good, game-less APK while every step printed success (AT:R66).
# Same check install_android.sh runs, on the path that reaches a real tester.
#
# Checked against a CONTROL string present in every build, so an empty result
# means the game is absent, not that the snapshot is unsearchable.
_games_in_aab() {
  local tmp; tmp=$(mktemp -d)
  unzip -q -o "$aab" -d "$tmp" 2>/dev/null || { rm -rf "$tmp"; return 1; }
  local so; so=$(find "$tmp" -name libapp.so -path "*arm64*" | head -1)
  [[ -n "$so" && -f "$so" ]] || { rm -rf "$tmp"; return 1; }
  local hits control
  # DEF301 — probe a games-only widget Key, never the disclosure heading.
  # `NO ARENA RULES` is an ARB *value* (`app_en.arb:509`, gamesDisclosureHeading),
  # so a copy edit or a re-translation would silently change what this gate
  # tests while it went on printing success — the same shape as the defect it
  # sits next to. `games_close_beat_insight` is a const Key reached only from
  # `games_close_screen.dart`; measured 1 hit in the AAB and the IPA, 0 in a
  # game-less APK, against the control's 1 in all three.
  hits=$(strings "$so" | grep -ic "games_close_beat_insight" || true)
  control=$(strings "$so" | grep -ic "EDUCATIONAL SIMULATION" || true)
  rm -rf "$tmp"
  [[ "$control" -gt 0 ]] || { echo "control-missing"; return 0; }
  [[ "$hits" -gt 0 ]] && echo "present" || echo "absent"
}

# Runs in BOTH directions; the failing direction differs. With games ON,
# "absent" means the define did not take. With --no-games, "present" means an
# undisclosed feature is one Console click from production.
_want=$([[ "$DO_GAMES" -eq 1 ]] && echo present || echo absent)
case "$(_games_in_aab || echo unreadable)" in
  present)
    if [[ "$_want" == "present" ]]; then
      echo "▶ AMI_GAMES verified present in the AAB"
    else
      echo "✗ --no-games was passed and the game is STILL in this AAB." >&2
      echo "  Play lets an internal build be promoted straight to production," >&2
      echo "  so this cannot be allowed to leave the machine. Refusing." >&2
      echo "  Most likely cause: a stale build/ directory — clean and retry." >&2
      exit 1
    fi
    ;;
  absent)
    if [[ "$_want" == "absent" ]]; then
      echo "▶ --no-games verified: no game in the AAB"
    else
      echo "✗ AMI_GAMES did NOT take — this AAB has no game in it." >&2
      echo "  bool.fromEnvironment accepts only \"true\"/\"false\"; any other" >&2
      echo "  value silently compiles to the default, false." >&2
      echo "  Refusing to publish a build that does not carry what it claims." >&2
      exit 1
    fi
    ;;
  control-missing)
    echo "⚠ games-string check inconclusive — the CONTROL string was also" >&2
    echo "  absent, so the search method no longer holds for this build." >&2
    echo "  Not blocking, but the gate is UNVERIFIED." >&2
    ;;
  *) echo "⚠ could not read the AAB to verify AMI_GAMES — gate UNVERIFIED." >&2 ;;
esac

echo ""
echo "✓ AAB ready: ${aab}"
echo ""
echo "Next step — manual upload to Play Console internal track:"
echo "  1. open  https://play.google.com/console"
echo "  2. App → Testing → Internal testing → Create new release"
echo "  3. Upload  ${aab}"
echo "  4. Fill release notes, save, review, roll out"
echo ""
echo "First upload also enrolls in Play App Signing (one-time, irreversible)."
echo "Internal testers get the build via the opt-in link once review completes."
echo ""
echo "After that first upload, ship release #2+ with one command:"
echo "  scripts/publish_playstore.sh          # build + fastlane push to internal"
