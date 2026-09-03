#!/usr/bin/env bash
# Publish a release APK to melehost's shared folder — the input our automated
# tester consumes. Single source of truth for "get the current APK onto the
# tester", called by BOTH the device-install path (install_android.sh) and the
# store-release path (publish_playstore.sh) so the rig is refreshed on EVERY
# build, never just when someone remembers.
#
# Why this exists as its own script (CR079, superseding CR078's "only
# install_android produces an APK" scope): the melehost folder is not a
# convenience hand-out — it feeds an automated test rig. A stale APK there means
# the rig silently tests code that has moved, and reports pass/fail against the
# wrong build. That is worse than a missing copy, and it is the CR040
# "degrade loudly" class: the failure must be impossible to miss.
#
# Usage:
#   scripts/share_apk_to_tester.sh                 # build a fresh release APK, then scp
#   scripts/share_apk_to_tester.sh <path-to-apk>   # scp an APK the caller already built
#
# Env:
#   AMI_APK_SHARE_DEST            scp destination (default: melehost tester folder)
#   AMI_API_URL_ALPHA            backend URL baked into a freshly-built APK
#   GOOGLE_OAUTH_WEB_CLIENT_ID   Google Sign-In web client_id (same as the other build scripts)
#   SENTRY_DSN                   optional
#
# Exit status: 0 iff the shared copy was replaced. Non-zero on scp failure so a
# caller can react — but callers MUST invoke this guarded (inside `if`, or with
# `|| true`) if they run `set -e` and a LAN hiccup must not abort them. The loud
# STALE message is printed here regardless, so the warning is never lost.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MOBILE_DIR="${PROJECT_ROOT}/mobile"

# Melehost addresses: LAN-direct (fast) and Tailscale fallback (VPN, ~500ms latency).
# Same user and path on both. Caller may override AMI_APK_SHARE_DEST completely
# (full scp destination string), in which case no fallback probe runs.
: "${MELEHOST_LAN_IP:=192.168.20.59}"
: "${MELEHOST_TAILSCALE_IP:=100.110.14.31}"
: "${MELEHOST_USER:=saiful}"
: "${MELEHOST_APK_PATH:=/home/saiful/hermes_folder/project/AMI_MarketApps/apk/}"

# Only set AMI_APK_SHARE_DEST if not already set by caller. This allows the
# fallback probe to run: we detect which host is reachable and build the
# destination dynamically. If caller sets AMI_APK_SHARE_DEST (full scp-style
# string), that overrides any probe — we use it as-is.
if [[ -z "${AMI_APK_SHARE_DEST:-}" ]]; then
  # Probe reachability of the primary (LAN) address first. Use nc on port 22
  # (SSH) instead of ICMP ping — more networks allow TCP to a known service
  # than allow ICMP, and scp will use SSH anyway.
  PRIMARY_HOST="${MELEHOST_USER}@${MELEHOST_LAN_IP}:${MELEHOST_APK_PATH}"
  FALLBACK_HOST="${MELEHOST_USER}@${MELEHOST_TAILSCALE_IP}:${MELEHOST_APK_PATH}"

  if nc -z -w 3 "${MELEHOST_LAN_IP}" 22 2>/dev/null; then
    # Primary is reachable; use it.
    AMI_APK_SHARE_DEST="${PRIMARY_HOST}"
    CHOSEN_ROUTE="LAN"
  else
    # Primary is not responding; fall back to Tailscale. Try it once to confirm
    # it's reachable before committing to it.
    if nc -z -w 3 "${MELEHOST_TAILSCALE_IP}" 22 2>/dev/null; then
      AMI_APK_SHARE_DEST="${FALLBACK_HOST}"
      CHOSEN_ROUTE="Tailscale fallback"
    else
      # Neither reachable. Log the problem and let scp try anyway — the error
      # will be loud and clear. Use the primary so the error message names the
      # expected host (not a fallback that also failed).
      AMI_APK_SHARE_DEST="${PRIMARY_HOST}"
      CHOSEN_ROUTE="LAN (unreachable; Tailscale also failed)"
    fi
  fi
else
  # Caller set AMI_APK_SHARE_DEST explicitly. Honor it, no probe.
  CHOSEN_ROUTE="(caller-specified override)"
fi
: "${AMI_API_URL_ALPHA:=https://api-alpha.agenticmarketintel.ai}"
# CR050 — GCP OAuth 2.0 **Web** client_id (ami-trade-web). Public config; baked as
# the default so Google Sign-In is never silently disabled by a forgotten export.
: "${GOOGLE_OAUTH_WEB_CLIENT_ID:=153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com}"
: "${SENTRY_DSN:=}"

# DEF301 — the rig must run the app the release ships, not a near-miss of it.
#
# This helper used to build with four dart-defines and no AMI_GAMES, so
# `bool.fromEnvironment('AMI_GAMES', defaultValue: false)` resolved FALSE and the
# whole games tree shook out: every `publish_playstore.sh` run produced a 5-tab
# AAB for Play and a 4-tab APK for melehost, in the same run, under one version
# string. `strings libapp.so` at 0.1.0+91: AAB 1 hit, IPA 1 hit, APK 0 —
# control string present in all three, so absent meant absent.
#
# Two artifacts with the same version and different features make a bug report
# untraceable, and the automated tester was exercising a tab users do not have
# (or rather, missing one they do).
#
# Defaults to FALSE, deliberately: run standalone this stays the safe direction,
# and only a caller that KNOWS the release carries the game turns it on.
# `publish_playstore.sh` exports its own DO_GAMES choice, so the APK matches the
# AAB it was built beside rather than guessing.
: "${AMI_GAMES:=false}"

APK="${1:-}"

if [[ -z "$APK" ]]; then
  APK="${MOBILE_DIR}/build/app/outputs/flutter-apk/app-release.apk"
  echo "▶ flutter build apk --release  (for the automated tester)"
  ( cd "$MOBILE_DIR" && flutter build apk --release \
      --dart-define=ALLOW_BACKEND_SWITCH=true \
      --dart-define=AMI_API_URL_ALPHA="${AMI_API_URL_ALPHA}" \
      --dart-define=GOOGLE_OAUTH_WEB_CLIENT_ID="${GOOGLE_OAUTH_WEB_CLIENT_ID}" \
      --dart-define=SENTRY_DSN="${SENTRY_DSN}" \
      --dart-define=AMI_GAMES="${AMI_GAMES}" )
fi

if [[ ! -f "$APK" ]]; then
  echo "✗ no APK at $APK — flutter build apk failed?" >&2
  echo "✗ automated-tester APK is STALE — ${AMI_APK_SHARE_DEST} still holds the previous build." >&2
  exit 1
fi

# DEF306 — say what this artifact IS, in the run log, every time.
#
# The destination filename is deliberately NOT suffixed: the melehost rig reads
# a fixed path and renaming it would leave the old APK in place beside a new
# one, which is a worse version of the same confusion. So the identity is
# stated here instead, and the installed app states its own gates under
# Settings — the copy that survives being installed.
echo "▶ artifact feature set: AMI_GAMES=${AMI_GAMES}$([[ "$AMI_GAMES" == "true" ]] || echo '  (no GAME tab in this APK)')"
echo "▶ publishing APK → ${AMI_APK_SHARE_DEST}  (via ${CHOSEN_ROUTE})"
if scp -o ConnectTimeout=10 "$APK" "$AMI_APK_SHARE_DEST"; then
  echo "✓ automated-tester APK is current: ${AMI_APK_SHARE_DEST}"
  exit 0
fi

echo "✗ scp FAILED — automated-tester APK is STALE at ${AMI_APK_SHARE_DEST}." >&2
echo "  The rig is now testing the PREVIOUS build. Re-run, or copy by hand:" >&2
echo "  scp \"${APK}\" \"${AMI_APK_SHARE_DEST}\"" >&2
exit 1
