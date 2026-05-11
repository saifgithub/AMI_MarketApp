#!/usr/bin/env bash
# Bootstrap the Flutter project — runs once on a fresh machine after Flutter is installed.
#
# Generates the iOS + Android platform folders, downloads fonts via the GitHub
# Releases API (so URLs don't go stale), copies AMI design assets, fetches deps,
# and verifies the build is sane.
#
# Idempotent: safe to re-run.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"
AMI_DS="/Volumes/Extreme Pro/AMI AI Design System"

cd "${MOBILE_DIR}"

echo "▶ Verifying Flutter is installed…"
flutter --version >/dev/null 2>&1 || { echo "ERROR: Flutter not on PATH. Install: brew install --cask flutter"; exit 1; }
flutter --version | head -1

echo ""
echo "▶ Generating iOS + Android platform folders (--no-overwrite preserves lib/ + pubspec.yaml)…"
flutter create \
  --project-name=ami_trade \
  --org=ai.agenticmarketintel \
  --platforms=ios,android \
  --no-overwrite \
  . 2>&1 | tail -3

echo ""
echo "▶ Copying AMI design assets…"
mkdir -p assets/icons assets/fonts/Inter assets/fonts/JetBrainsMono
cp "${AMI_DS}/assets/hex_mesh.svg" assets/hex_mesh.svg
cp "${AMI_DS}/assets/logo_hex.svg" assets/logo_hex.svg
echo "  ✓ hex_mesh.svg, logo_hex.svg"

# ─────────────────────────────────────────────────────────────────────────
# Inter — https://github.com/rsms/inter
# ─────────────────────────────────────────────────────────────────────────
echo ""
echo "▶ Inter font…"
if ls assets/fonts/Inter/Inter-{Regular,Medium,SemiBold,Bold}.ttf >/dev/null 2>&1; then
  echo "  ✓ already installed (skipping)"
else
  INTER_URL=$(curl -sL "https://api.github.com/repos/rsms/inter/releases/latest" \
    | grep '"browser_download_url"' | grep '.zip' | head -1 | cut -d'"' -f4)
  echo "  Latest: $INTER_URL"
  TMP="$(mktemp -d)"
  curl -sL --fail "$INTER_URL" -o "${TMP}/inter.zip"
  unzip -q "${TMP}/inter.zip" -d "${TMP}/inter"
  for w in Regular Medium SemiBold Bold; do
    cp "${TMP}/inter/extras/ttf/Inter-${w}.ttf" "assets/fonts/Inter/Inter-${w}.ttf"
    echo "  ✓ Inter-${w}.ttf"
  done
  rm -rf "$TMP"
fi

# ─────────────────────────────────────────────────────────────────────────
# JetBrains Mono — https://github.com/JetBrains/JetBrainsMono
# Their release zip has a version-tagged filename so we fetch latest tag.
# ─────────────────────────────────────────────────────────────────────────
echo ""
echo "▶ JetBrains Mono font…"
if ls assets/fonts/JetBrainsMono/JetBrainsMono-{Regular,Medium,Bold}.ttf >/dev/null 2>&1; then
  echo "  ✓ already installed (skipping)"
else
  JBM_URL=$(curl -sL "https://api.github.com/repos/JetBrains/JetBrainsMono/releases/latest" \
    | grep '"browser_download_url"' | grep '.zip' | head -1 | cut -d'"' -f4)
  echo "  Latest: $JBM_URL"
  TMP="$(mktemp -d)"
  curl -sL --fail "$JBM_URL" -o "${TMP}/jbm.zip"
  unzip -q "${TMP}/jbm.zip" -d "${TMP}/jbm"
  for w in Regular Medium Bold; do
    FOUND=$(find "${TMP}/jbm" -name "JetBrainsMono-${w}.ttf" -not -path "*Italic*" 2>/dev/null | head -1)
    [[ -n "$FOUND" ]] && cp "$FOUND" "assets/fonts/JetBrainsMono/JetBrainsMono-${w}.ttf" \
                     && echo "  ✓ JetBrainsMono-${w}.ttf"
  done
  rm -rf "$TMP"
fi

echo ""
echo "▶ flutter pub get…"
flutter pub get 2>&1 | tail -3

echo ""
echo "▶ flutter analyze…"
flutter analyze 2>&1 | tail -3

echo ""
echo "✓ Mobile project ready."
echo ""
echo "Next:"
echo "  cd ${MOBILE_DIR}"
echo "  flutter run -d ios     # iOS simulator"
echo "  flutter run            # device picker"
