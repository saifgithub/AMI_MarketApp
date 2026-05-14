#!/usr/bin/env bash
# Build a release IPA and upload it to TestFlight in one shot.
#
# Auto-bumps the build number in pubspec.yaml so Apple accepts the upload
# (App Store Connect rejects re-uploads at the same version+build combo),
# then `flutter build ipa --release --export-method=app-store`, then
# `xcrun altool --upload-app` with the App Store Connect API key stored
# at ~/.appstoreconnect/private_keys/AuthKey_<APP_STORE_API_KEY_ID>.p8.
#
# Usage:
#   scripts/build_testflight.sh                  # full build + upload
#   scripts/build_testflight.sh --no-upload      # build IPA, skip upload
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

echo "▶ flutter build ipa  (release, app-store)"
cd "$MOBILE_DIR"
flutter build ipa --release \
  --export-method=app-store \
  --dart-define=ALLOW_BACKEND_SWITCH=true \
  --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}"

ipa="${MOBILE_DIR}/build/ios/ipa/ami_trade.ipa"
if [[ ! -f "$ipa" ]]; then
  echo "✗ expected IPA at $ipa — flutter build failed?"
  exit 1
fi
size_mb=$(du -m "$ipa" | cut -f1)
echo "▶ built ${ipa} (${size_mb} MB, build ${semver}+${build_num})"

if [[ "$DO_UPLOAD" != "1" ]]; then
  echo "▶ skipping upload (--no-upload)"
  echo ""
  echo "To upload manually:"
  echo "  xcrun altool --upload-app --type ios -f '$ipa' \\"
  echo "    --apiKey ${APP_STORE_API_KEY_ID} --apiIssuer ${APP_STORE_API_ISSUER}"
  exit 0
fi

echo "▶ uploading to TestFlight…"
xcrun altool --upload-app --type ios -f "$ipa" \
  --apiKey "${APP_STORE_API_KEY_ID}" \
  --apiIssuer "${APP_STORE_API_ISSUER}"

echo ""
echo "✓ uploaded ${semver}+${build_num}. Processing in App Store Connect now."
echo "  Build will appear in TestFlight in ~15-30 min."
echo "  Internal testers see it instantly once processed; External needs"
echo "  ~24h Beta App Review on the first external build per version."
