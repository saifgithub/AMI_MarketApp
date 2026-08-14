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
DO_GAMES=1
for arg in "$@"; do
  case "$arg" in
    --no-bump)    DO_BUMP=0 ;;
    --no-upload)  DO_UPLOAD=0 ;;
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

# CR084 — RevenueCat Test Store key (`test_…`). Purchases are SIMULATED by
# RevenueCat: the paywall, the webhook, the entitlement grant and the credit
# top-up all run for real, but no money moves and no store product is needed.
# That is exactly what alpha wants. It is also a giveaway if it ever reaches
# real users, so it is banner-loud here and hard-blocked from production.
# GAMES + PRODUCTION = refuse. Structural, not advisory.
#
# Until --no-games existed, this hole was masked rather than closed: a test_…
# RevenueCat key forced --internal-only, so a games build could not reach an
# external group by accident. But the key is the thing a public rollout
# CHANGES — swap in a real appl_… key and nothing here would have stopped
# `--production` shipping a binary with an unreachable-by-design game route
# compiled into it, which is precisely what App Review guideline 2.3.1 names.
# The banner said "do not"; a banner is not a control (CR040).
if [[ "$DO_GAMES" -eq 1 && ( "${RELEASE_CHANNEL:-}" == "production" || "$DO_PRODUCTION" -eq 1 ) ]]; then
  echo "✗ This is a PRODUCTION build and AMI_GAMES is on." >&2
  echo "  A hidden feature in a store binary is App Review guideline 2.3.1." >&2
  echo "  Rebuild with --no-games:" >&2
  echo "" >&2
  echo "      scripts/build_testflight.sh --production --no-games" >&2
  exit 1
fi

# DEF296 — the games build's containment, as a control instead of a citation.
#
# The banner below used to say a games build was safe "because a test_…
# RevenueCat key forces --internal-only". That forcing lives in the billing
# block further down, guarded on `DO_BILLING -eq 1`. `--no-billing` sets
# DO_BILLING=0 *and* blanks the key (DEF290, correctly), so the gate
# short-circuits on its first condition, --internal-only is never demanded, and
# the banner's entire stated basis is absent while the banner still prints.
#
# That is not an exotic path. DEF282 removed the purchase SDK from the app's
# code path entirely and both RevenueCat keys in infra/alpha.env are test_…, so
# --no-billing is the only honest flag for every build we can currently produce
# — 0.1.0+90 and +91 both shipped exactly this way.
#
# So the demand is attached to what it is actually about. A games build needs
# --internal-only whatever the billing flags say, because the thing being
# contained is the game, not the purchase path. Android has had the real
# version of this all along (publish_playstore.sh:69 refuses a test_ key on any
# non-internal track, reading the key from infra/alpha.env rather than from the
# build's own flags); iOS had a banner where Android had a check.
#
# What this does NOT claim: that the combination is impossible. Group
# assignment happens in App Store Connect, after and outside this script, so no
# build flag can reach it. What it does is make the operator state the intent
# for the risky combination on every path — which is what the banner was
# already asserting had happened, and had not.
if [[ "$DO_GAMES" -eq 1 && "$DO_INTERNAL_ONLY" -ne 1 ]]; then
  cat >&2 <<'EOF'
✗ AMI_GAMES is on and --internal-only was not passed.

  This build carries the CR109 games tab. TestFlight INTERNAL groups skip Beta
  App Review; EXTERNAL groups do not, and an undocumented feature in a
  store-reviewed binary is App Store Review guideline 2.3.1.

  Nothing downstream of this script can tell the two apart — group assignment
  is a manual step in App Store Connect — so the intent is stated here.

      scripts/build_testflight.sh --internal-only     (games, internal only)
      scripts/build_testflight.sh --no-games          (no games route at all)
EOF
  exit 1
fi

# DEF290 — the containment rule below applies only to a build that can actually
# transact. DEF282 removed the RevenueCat SDK from the app's code path entirely
# (`purchase_providers.dart` returns `DisabledPurchaseService`, which does not
# import `purchases_flutter`, and `BillingConfig.usableKey` blanks any `test_`
# key in a non-debug build regardless). So the gate's own message — "Purchases
# in this build are SIMULATED: buying grants Plan + credits for real in our DB"
# — was false about every build we could produce, and its remedy asked the
# operator to affirm it to proceed. A gate whose stated reason is untrue is how
# an operator learns that firing does not mean stop; that is DEF277 again, one
# script over.
#
# With `--no-billing` there is no purchase path to contain, and the key is
# blanked below rather than compiled in — so RevenueCat's "never submit an app
# configured with a Test Store API key" is satisfied structurally instead of by
# a promise.
if [[ "$DO_BILLING" -eq 1 && "$REVENUECAT_IOS_SDK_KEY" == test_* ]]; then
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

archive_path="${MOBILE_DIR}/build/Runner.xcarchive"
ipa_dir="${MOBILE_DIR}/build/ios/ipa"

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
  # DEF290 — blank it rather than merely not using it. Passing a `test_…` key
  # as a dart-define compiles it into the IPA, so a build that cannot sell
  # would still be "an app configured with a Test Store API key" by
  # RevenueCat's own wording. The app already refuses to use it
  # (`BillingConfig.usableKey`); this makes the binary not carry it.
  REVENUECAT_IOS_SDK_KEY=""
fi

echo "▶ flutter build ios  (release, no-codesign — framework only)"
cd "$MOBILE_DIR"
if [[ "$DO_GAMES" -eq 1 ]]; then
cat <<'BANNER'
┌──────────────────────────────────────────────────────────────────┐
│  THIS BUILD CARRIES THE CR109 GAME (AMI_GAMES=true).             │
│                                                                  │
│  It is a VISIBLE FIFTH TAB (AmiTab.visible), reachable by tap    │
│  from launch — no gesture, nothing hidden about it. It is still  │
│  undocumented in the store listing, which is what App Review     │
│  guideline 2.3.1 names.                                          │
│                                                                  │
│  The basis for shipping it: --internal-only was passed (DEF296   │
│  refuses this build without it), and TestFlight INTERNAL groups  │
│  skip Beta App Review.                                           │
│                                                                  │
│  DO NOT promote this build to an external group or the App       │
│  Store — that step is in App Store Connect, where nothing here   │
│  can stop you. Rebuild with --no-games first. Saiful's call,     │
│  AT:R66: "if anyone finds it, it will be an easter egg for them."│
└──────────────────────────────────────────────────────────────────┘
BANNER
else
cat <<'BANNER'
┌──────────────────────────────────────────────────────────────────┐
│  --no-games: AMI_GAMES=false. No games route is compiled in, so  │
│  there is nothing for App Review guideline 2.3.1 to find. This   │
│  is the build shape a PUBLIC release needs.                      │
│                                                                  │
│  Verified below against the IPA itself, not against this flag —  │
│  the check inverts, and a games string FOUND here is a hard      │
│  failure rather than a warning.                                  │
└──────────────────────────────────────────────────────────────────┘
BANNER
fi

# A release archive must not inherit another build's native assets.
#
# Flutter writes them to ONE path per OS — `build/native_assets/ios/` — with
# no device/simulator split, so an iOS *simulator* build (the QA lane runs
# them) leaves a simulator-platform framework there and the next device
# archive copies it straight into Runner.app. App Store Connect then refuses
# the upload: "references an unsupported platform in the x86_64 slice", after
# a twelve-minute build (AT:R66, 0.1.0+76).
#
# The two `.dart_tool` entries are the load-bearing ones, and BOTH are
# needed. Clearing the output directory alone leaves the build system
# believing native assets are already built, so it writes a manifest that
# references `objective_c` and never regenerates the framework — every
# rebuild then dies on "references objective_c, which was not found in
# build/native_assets/ios/". `hooks_runner` is the native-assets hook cache;
# `flutter_build` is the build-system state that decides whether the hook
# runs at all. Dropping only `hooks_runner` reproduces the same failure,
# which is how this list got its fifth entry.
#
# Every path is pure build output; the next build regenerates them. On a
# shared checkout with several lanes live, "the last build here was mine" is
# not an assumption a release script may make.
echo "▶ clearing native-asset caches (a simulator build must not leak into a release archive)"
rm -rf "${MOBILE_DIR}/build/native_assets" \
       "${MOBILE_DIR}/build/ios/Release-iphoneos" \
       "${MOBILE_DIR}/build/ios/iphoneos" \
       "${MOBILE_DIR}/.dart_tool/hooks_runner" \
       "${MOBILE_DIR}/.dart_tool/flutter_build"

flutter build ios --release --no-codesign \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
  --dart-define=AMI_GAMES="$([[ "$DO_GAMES" -eq 1 ]] && echo true || echo false)" \
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

# CR109 — prove the AMI_GAMES define took, don't trust the flag.
#
# `bool.fromEnvironment` accepts ONLY the literal "true"/"false"; anything
# else silently compiles to the default. `AMI_GAMES=1` once produced a
# perfectly good, game-less APK while every step printed success (AT:R66).
# install_android.sh has verified its artefact since; this is the same check
# on the path that reaches a REAL TESTER, which is the one that matters more.
#
# A games-only string must be present in the AOT snapshot, and it is checked
# against a CONTROL string that exists in every build — so an empty result
# means the game is absent, not that `strings` cannot see into this binary.
_games_in_ipa() {
  local tmp; tmp=$(mktemp -d)
  unzip -q -o "$ipa" -d "$tmp" 2>/dev/null || { rm -rf "$tmp"; return 1; }
  local fw; fw=$(find "$tmp" -path "*App.framework/App" -type f | head -1)
  [[ -n "$fw" && -f "$fw" ]] || { rm -rf "$tmp"; return 1; }
  local hits control
  # DEF301 — a games-only widget Key, not the ARB disclosure heading, which a
  # copy edit would change without anyone noticing this gate stopped testing.
  hits=$(strings "$fw" | grep -ic "games_close_beat_insight" || true)
  control=$(strings "$fw" | grep -ic "EDUCATIONAL SIMULATION" || true)
  rm -rf "$tmp"
  [[ "$control" -gt 0 ]] || { echo "control-missing"; return 0; }
  [[ "$hits" -gt 0 ]] && echo "present" || echo "absent"
}

# The check runs in BOTH directions, and the failing direction is the one
# that matters in each case. With games ON, "absent" means the define did not
# take. With --no-games, "present" means a hidden feature is about to reach
# App Review — the more expensive mistake of the two, and the whole reason
# the flag exists.
_want=$([[ "$DO_GAMES" -eq 1 ]] && echo present || echo absent)
case "$(_games_in_ipa || echo unreadable)" in
  present)
    if [[ "$_want" == "present" ]]; then
      echo "▶ AMI_GAMES verified present in the IPA"
    else
      echo "✗ --no-games was passed and the game is STILL in this IPA." >&2
      echo "  A hidden, unreachable-by-design feature in a store binary is" >&2
      echo "  exactly what App Review guideline 2.3.1 names. Refusing." >&2
      echo "  Most likely cause: a stale build/ directory — clean and retry." >&2
      exit 1
    fi
    ;;
  absent)
    if [[ "$_want" == "absent" ]]; then
      echo "▶ --no-games verified: no game in the IPA"
    else
      echo "✗ AMI_GAMES did NOT take — this IPA has no game in it." >&2
      echo "  bool.fromEnvironment accepts only \"true\"/\"false\"; any other" >&2
      echo "  value silently compiles to the default, false." >&2
      echo "  Refusing to upload a build that does not carry what it claims." >&2
      exit 1
    fi
    ;;
  control-missing)
    echo "⚠ games-string check inconclusive — the CONTROL string was also" >&2
    echo "  absent, so the search method no longer holds for this build." >&2
    echo "  Not blocking the upload, but the gate is UNVERIFIED." >&2
    ;;
  *) echo "⚠ could not read the IPA to verify AMI_GAMES — gate UNVERIFIED." >&2 ;;
esac
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
