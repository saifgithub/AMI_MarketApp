#!/usr/bin/env bash
# Build a release IPA and upload it to TestFlight in one shot — no manual
# Xcode intervention required.
#
# Pipeline (staged so signing flags can land where they apply):
#   1. bump pubspec build number (Apple rejects re-uploads at the same +N)
#   2. flutter build ios --release --no-codesign --dart-define=...
#         (Flutter framework only — produces an unsigned .app bundle)
#   3. xcodebuild -workspace ... archive  -allowProvisioningUpdates
#         -authenticationKey* (signs + refreshes provisioning profile if
#         needed via the ASC API key — the flag that flutter build ipa
#         can't accept because of its '--' pass-through bug)
#   4. xcodebuild -exportArchive  -exportOptionsPlist ios/ExportOptions.plist
#         -allowProvisioningUpdates -authenticationKey*   (App Store IPA)
#   5. xcodebuild -exportArchive  destination=upload  (TestFlight upload —
#         Xcode 26.5 broke `xcrun altool --upload-app` with error 19, so we
#         re-run exportArchive against the archive with an upload plist)
#
# History: an earlier one-shot `flutter build ipa -- -allowProvisioningUpdates`
# attempt failed because Flutter parses post-`--` tokens as Dart entrypoints,
# not as xcodebuild args. See commit 19a0617 (revert) + AT:R31 handover.
#
# Usage:
#   scripts/build_testflight.sh                  # full build + upload
#   scripts/build_testflight.sh --no-upload      # build IPA, skip the upload step
#   scripts/build_testflight.sh --no-bump        # use whatever's in pubspec
#   scripts/build_testflight.sh --no-commit      # don't auto-commit the bump
#   scripts/build_testflight.sh --no-billing     # deliberately ship WITHOUT in-app purchase
#   scripts/build_testflight.sh --internal-only  # required when the RC key is a test_… Test Store key
#
# Required env (defaults to Saiful's setup):
#   APP_STORE_API_KEY_ID   - 10-char key ID, e.g. 44VJ5WADL2
#   APP_STORE_API_ISSUER   - team issuer UUID
#   AMI_API_URL_ALPHA      - backend URL baked into the build
#   REVENUECAT_IOS_SDK_KEY - public RC SDK key for iOS (CR084/DEF100). Two shapes:
#                            `appl_…` = the real App-specific public key (production);
#                            `test_…` = a RevenueCat Test Store key — purchases are
#                            SIMULATED, no ASC product needed, and distribution is
#                            restricted to TestFlight INTERNAL groups (--internal-only).
#                            Auto-sourced from infra/alpha.env if not exported.
#                            Public by design — safe to embed in a shipped client.
#
# BILLING GATE (CR084 / CR040 degrade-loudly): without the SDK key,
# `BillingConfig.isConfigured` is false and the paywall renders the info state
# with NO buy button — the app cannot take money. That is the correct fallback
# for a dev build and a silent revenue outage for a store build, so this script
# REFUSES to build without the key unless you pass --no-billing. Every release
# from `+61` back shipped that way, unnoticed, because nothing checked.
#
# Processing in App Store Connect takes ~15-30 min after a successful
# upload before the build shows up in TestFlight.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"
IOS_DIR="${MOBILE_DIR}/ios"

: "${APP_STORE_API_KEY_ID:=44VJ5WADL2}"
: "${APP_STORE_API_ISSUER:=289e6201-8fc9-44a3-abde-59e8e278527c}"
: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"

# CR084: source the public RC SDK key from the canonical gitignored env file
# unless it is already exported. Same file the backend keys live in, so there is
# one place to paste a key rather than two.
if [[ -z "${REVENUECAT_IOS_SDK_KEY:-}" && -f "${PROJECT_ROOT}/infra/alpha.env" ]]; then
  REVENUECAT_IOS_SDK_KEY="$(grep -E '^REVENUECAT_IOS_SDK_KEY=' "${PROJECT_ROOT}/infra/alpha.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' ' || true)"
fi
: "${REVENUECAT_IOS_SDK_KEY:=}"

DO_BUMP=1
DO_UPLOAD=1
DO_COMMIT=1
DO_BILLING=1
DO_PRODUCTION=0
DO_INTERNAL_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --no-bump)    DO_BUMP=0 ;;
    --no-upload)  DO_UPLOAD=0 ;;
    --no-commit)  DO_COMMIT=0 ;;
    --no-billing) DO_BILLING=0 ;;
    --production) DO_PRODUCTION=1 ;;
    --internal-only) DO_INTERNAL_ONLY=1 ;;
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

key_file="$HOME/.appstoreconnect/private_keys/AuthKey_${APP_STORE_API_KEY_ID}.p8"
if [[ ! -f "$key_file" ]]; then
  echo "✗ API key not found at $key_file"
  echo "  Download from App Store Connect → Users and Access → Integrations,"
  echo "  then: mkdir -p ~/.appstoreconnect/private_keys && mv ~/Downloads/AuthKey_*.p8 \"\$_\" && chmod 600 \"\$_\"/AuthKey_*.p8"
  exit 1
fi

export_options="${IOS_DIR}/ExportOptions.plist"
if [[ ! -f "$export_options" ]]; then
  echo "✗ ExportOptions.plist not found at $export_options"
  exit 1
fi

pubspec="${MOBILE_DIR}/pubspec.yaml"
current_line=$(grep -E "^version:" "$pubspec")
current_version=$(echo "$current_line" | sed -E 's/version:[[:space:]]*//')
semver="${current_version%+*}"
build_num="${current_version#*+}"

if [[ "$DO_BUMP" == "1" ]]; then
  new_build=$((build_num + 1))
  new_version="${semver}+${new_build}"
  echo "▶ bumping pubspec: ${current_version} → ${new_version}"
  # Portable in-place sed (BSD on macOS needs '' arg).
  sed -i '' "s/^version: ${current_version}$/version: ${new_version}/" "$pubspec"
  build_num="$new_build"
  if [[ "$DO_COMMIT" == "1" ]]; then
    (cd "$PROJECT_ROOT" && git add mobile/pubspec.yaml && \
      git commit -m "chore(mobile): bump build ${semver}+$((build_num - 1)) → ${semver}+${build_num} for TestFlight" \
      > /dev/null && echo "▶ committed bump")
  fi
else
  echo "▶ using existing version ${semver}+${build_num} (--no-bump)"
fi

archive_path="${MOBILE_DIR}/build/Runner.xcarchive"
ipa_dir="${MOBILE_DIR}/build/ios/ipa"

# CR084 — RevenueCat Test Store key (`test_…`). Purchases are SIMULATED by
# RevenueCat: the paywall, the webhook, the entitlement grant and the credit
# top-up all run for real, but no money moves and no store product is needed.
# That is exactly what alpha wants. It is also a giveaway if it ever reaches
# real users, so it is banner-loud here and hard-blocked from production.
if [[ "$REVENUECAT_IOS_SDK_KEY" == test_* ]]; then
  if [[ "${RELEASE_CHANNEL:-}" == "production" || "$DO_PRODUCTION" -eq 1 ]]; then
    echo "✗ REVENUECAT_IOS_SDK_KEY is a Test Store key (test_…) and this is a PRODUCTION build." >&2
    echo "  Every user would receive paid entitlements without paying. Refusing." >&2
    echo "  Use the App-specific public key (appl_…) for production." >&2
    exit 1
  fi
  if [[ "$DO_INTERNAL_ONLY" -ne 1 ]]; then
    cat >&2 <<'EOF'
✗ REVENUECAT_IOS_SDK_KEY is a Test Store key (test_…) and --internal-only was not passed.

  RevenueCat's own rule: "Never submit an app to the App Store or Google Play
  that is configured with a Test Store API key." This script uploads to App
  Store Connect, so that rule applies here.

  Our narrowing (CR084 "Alpha distribution constraint"): a test_… build may be
  distributed to TestFlight **internal** groups only — never an external group,
  which is store-reviewed and reaches people outside the team. Purchases in this
  build are SIMULATED: buying grants Plan + credits for real in our DB while no
  money moves.

  If this build is for internal testers, say so:

      scripts/build_testflight.sh --internal-only

  For anything external, rebuild with the App-specific public key (appl_…) and
  real App Store Connect products (DEF100, production phase).
EOF
    exit 1
  fi
  cat <<'EOF'
┌──────────────────────────────────────────────────────────────────┐
│  SIMULATED PURCHASES — RevenueCat Test Store key in this build.  │
│  Buying grants Plan + credits for real in our DB. No money moves.│
│  INTERNAL TestFlight GROUPS ONLY — do NOT add this build to an   │
│  external group, and never promote it to the App Store. Rebuild  │
│  with an appl_… key for anything beyond internal testers.        │
└──────────────────────────────────────────────────────────────────┘
EOF
fi

# CR084 billing gate — fail loudly rather than ship a paywall that cannot charge.
if [[ "$DO_BILLING" -eq 1 && -z "$REVENUECAT_IOS_SDK_KEY" ]]; then
  cat >&2 <<'EOF'
✗ REVENUECAT_IOS_SDK_KEY is empty — this build could not take a payment.

  BillingConfig.isConfigured would be false, so the paywall renders the
  info state with no buy button. Nothing would crash and nothing would
  warn; the app would simply never sell anything (CR084 / DEF100).

  Fix: add the iOS public SDK key to infra/alpha.env —

      REVENUECAT_IOS_SDK_KEY=appl_xxxxxxxxxxxxxxxxxxxx

  Get it from RevenueCat → Project Settings → API keys → the *App-specific
  public* key for the iOS app. It starts with `appl_`. Do NOT use the
  secret `sk_…` key here; that one is backend-only and must never ship in
  a client.

  If you genuinely want a build with purchasing disabled, re-run with
  --no-billing and this check will stand down.
EOF
  exit 1
fi
if [[ "$DO_BILLING" -eq 0 ]]; then
  echo "⚠ --no-billing: shipping WITHOUT in-app purchase (paywall = info state only)"
fi

echo "▶ flutter build ios  (release, no-codesign — framework only)"
cd "$MOBILE_DIR"
flutter build ios --release --no-codesign \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  --dart-define=REVENUECAT_IOS_SDK_KEY="${REVENUECAT_IOS_SDK_KEY}"

echo "▶ xcodebuild archive  (signs + auto-refreshes provisioning profile)"
cd "$IOS_DIR"
rm -rf "$archive_path"
xcodebuild \
  -workspace Runner.xcworkspace \
  -scheme Runner \
  -configuration Release \
  -destination "generic/platform=iOS" \
  -archivePath "$archive_path" \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$key_file" \
  -authenticationKeyID "$APP_STORE_API_KEY_ID" \
  -authenticationKeyIssuerID "$APP_STORE_API_ISSUER" \
  archive

echo "▶ xcodebuild -exportArchive  (App Store IPA)"
rm -rf "$ipa_dir"
xcodebuild \
  -exportArchive \
  -archivePath "$archive_path" \
  -exportOptionsPlist "$export_options" \
  -exportPath "$ipa_dir" \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$key_file" \
  -authenticationKeyID "$APP_STORE_API_KEY_ID" \
  -authenticationKeyIssuerID "$APP_STORE_API_ISSUER"

# xcodebuild -exportArchive names the IPA after the scheme, not the Flutter
# product. Resolve whichever .ipa landed in the export dir.
ipa=$(ls "${ipa_dir}"/*.ipa 2>/dev/null | head -1)
if [[ -z "$ipa" || ! -f "$ipa" ]]; then
  echo "✗ no IPA produced in $ipa_dir — xcodebuild -exportArchive failed?"
  exit 1
fi
size_mb=$(du -m "$ipa" | cut -f1)
echo "▶ built $(basename "$ipa") (${size_mb} MB, build ${semver}+${build_num})"

if [[ "$DO_UPLOAD" != "1" ]]; then
  echo "▶ skipping upload (--no-upload)"
  echo ""
  echo "To upload manually (Xcode 26.5+ — altool is broken, use xcodebuild):"
  echo "  cp '$export_options' /tmp/ExportOptions.upload.plist"
  echo "  /usr/libexec/PlistBuddy -c 'Set :destination upload' /tmp/ExportOptions.upload.plist"
  echo "  xcodebuild -exportArchive -archivePath '$archive_path' \\"
  echo "    -exportOptionsPlist /tmp/ExportOptions.upload.plist -exportPath '${ipa_dir}/upload' \\"
  echo "    -allowProvisioningUpdates -authenticationKeyPath '$key_file' \\"
  echo "    -authenticationKeyID ${APP_STORE_API_KEY_ID} -authenticationKeyIssuerID ${APP_STORE_API_ISSUER}"
  exit 0
fi

# Xcode 26.5 broke `xcrun altool --upload-app` (error 19). Re-run exportArchive
# against the archive with an upload-destination plist — this ships straight to
# App Store Connect. The local IPA export above is left untouched (kept as the
# build artifact + for --no-upload).
echo "▶ uploading to TestFlight (xcodebuild -exportArchive destination=upload)…"
upload_plist="${MOBILE_DIR}/build/ExportOptions.upload.plist"
cp "$export_options" "$upload_plist"
/usr/libexec/PlistBuddy -c "Set :destination upload" "$upload_plist"
xcodebuild \
  -exportArchive \
  -archivePath "$archive_path" \
  -exportOptionsPlist "$upload_plist" \
  -exportPath "${ipa_dir}/upload" \
  -allowProvisioningUpdates \
  -authenticationKeyPath "$key_file" \
  -authenticationKeyID "$APP_STORE_API_KEY_ID" \
  -authenticationKeyIssuerID "$APP_STORE_API_ISSUER"

echo ""
echo "✓ uploaded ${semver}+${build_num}. Processing in App Store Connect now."
echo "  Build will appear in TestFlight in ~15-30 min."
echo "  Internal testers see it instantly once processed; External needs"
echo "  ~24h Beta App Review on the first external build per version."
