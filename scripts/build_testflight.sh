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
#
# Required env (defaults to Saiful's setup):
#   APP_STORE_API_KEY_ID   - 10-char key ID, e.g. 44VJ5WADL2
#   APP_STORE_API_ISSUER   - team issuer UUID
#   AMI_API_URL_ALPHA      - backend URL baked into the build
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

DO_BUMP=1
DO_UPLOAD=1
DO_COMMIT=1
for arg in "$@"; do
  case "$arg" in
    --no-bump)   DO_BUMP=0 ;;
    --no-upload) DO_UPLOAD=0 ;;
    --no-commit) DO_COMMIT=0 ;;
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

echo "▶ flutter build ios  (release, no-codesign — framework only)"
cd "$MOBILE_DIR"
flutter build ios --release --no-codesign \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}"

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
