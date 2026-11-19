#!/usr/bin/env bash
# Release-channel resolution shared by build_testflight.sh, build_playstore.sh
# and publish_playstore.sh. CR267 WP-45. SOURCE this file; do not execute it.
#
# Why it exists: both build scripts baked only the Alpha URL, with the backend
# switcher on. The Beta programme (CR267) needs a third shape: external testers,
# talking to api-beta, unable to be pointed at Alpha, reporting to Sentry, and
# signed under the COMPANY store accounts rather than the founder's personal
# ones. Each of those is a way to ship the wrong binary silently, so each is a
# refusal here rather than a line in a runbook (CLAUDE.md: prompt/docs are not
# controls).
#
# Contract for the sourcing script:
#   * set CHANNEL (default alpha) while parsing `--channel alpha|beta`
#   * set DO_GAMES before calling ami_channel_setup
#   * export/define AMI_API_URL_ALPHA (alpha) before calling it
#   * call `ami_channel_setup ios|android` right after argument parsing and
#     before any gate that needs credentials, then honour DRY_RUN
# It leaves behind:
#   CHANNEL_API_URL  the URL this build bakes (the schema-parity gate checks it)
#   CHANNEL_DEFINES  array of --dart-define=... words for the channel; the
#                    sourcing script expands it in its single `flutter build`
#                    call, so what dry-run prints is what the build gets.
#
# Alpha is deliberately unchanged: CHANNEL_DEFINES for alpha is exactly the two
# defines the scripts passed before this file existed.
#
# Beta bakes:
#   AMI_API_URL_PROD=<beta url>   the only URL in the binary
#   ALLOW_BACKEND_SWITCH=false    explicit; the Settings > Developer section is
#                                 compiled out and BackendModeNotifier forces
#                                 the locked mode (see backend_modes.md). No
#                                 AMI_API_URL_ALPHA / _BETA define is passed,
#                                 so the Alpha hostname is not in the binary.
#   AMI_BETA=true                 CR278: English-only build
#   AMI_ENV=beta                  Sentry environment tag
#   SENTRY_DSN=<dsn>              required: WP-53's crash-free figure is Sentry
#                                 release health, so a Beta build with no DSN
#                                 would measure nothing and say nothing.
#
# The locked mode of a no-switch build is named `prod` inside the app
# (BackendUrls.lockedMode), so a Beta build's URL rides in the `_PROD` slot.
# That is a naming quirk of the existing mode plumbing, not a Prod backend.

AMI_BETA_API_URL_DEFAULT="https://api-beta.agenticmarketintel.ai"

# The founder's personal-account identifiers, as shipped today. A Beta build
# may not carry either (CR267 WP-49 / gate S7).
AMI_PERSONAL_IOS_BUNDLE_ID="ai.agenticmarketintel.amiTrade"
AMI_PERSONAL_ANDROID_APPLICATION_ID="ai.agenticmarketintel.ami_trade"

CHANNEL="${CHANNEL:-alpha}"
DRY_RUN=0

_ami_channel_die() {
  echo "$1" >&2
  exit "${2:-1}"
}

# The identifiers the project files declare right now, so the env-supplied IDs
# can be checked against what will actually be signed. Without this a build
# could pass the env check and still ship under the old IDs, because the
# project files, not the environment, decide the bundle ID.
_ami_declared_ios_ids() {
  local pbx="${PROJECT_ROOT}/mobile/ios/Runner.xcodeproj/project.pbxproj"
  [[ -f "$pbx" ]] || return 0
  grep -E 'PRODUCT_BUNDLE_IDENTIFIER = ' "$pbx" \
    | sed -E 's/.*PRODUCT_BUNDLE_IDENTIFIER = "?([^";]+)"?;.*/\1/' \
    | grep -v '\.RunnerTests$' | sort -u
}

_ami_declared_android_id() {
  local gradle="${PROJECT_ROOT}/mobile/android/app/build.gradle.kts"
  [[ -f "$gradle" ]] || return 0
  grep -E '^[[:space:]]*applicationId[[:space:]]*=' "$gradle" \
    | head -1 | sed -E 's/.*"([^"]+)".*/\1/'
}

_ami_beta_require_company_ids() {
  local platform="$1" env_name declared personal
  if [[ "$platform" == "ios" ]]; then
    env_name="AMI_BETA_IOS_BUNDLE_ID"
    personal="$AMI_PERSONAL_IOS_BUNDLE_ID"
  else
    env_name="AMI_BETA_ANDROID_APPLICATION_ID"
    personal="$AMI_PERSONAL_ANDROID_APPLICATION_ID"
  fi
  local given="${!env_name:-}"

  if [[ -z "$given" ]]; then
    _ami_channel_die "✗ --channel beta refused: ${env_name} is not set.
  A Beta build must be signed under the COMPANY store accounts, and the final
  company bundle / application IDs do not exist yet — they come from WP-49
  (company-account migration, gate S7; docs/forward_planning/CR258_company_account_migration/).
  Until then no Beta build can be made, on purpose: the only identifiers in the
  project are the founder's personal ones (${personal}), and a Beta build
  under those would have to be re-issued under new IDs.
  When WP-49 lands: change the IDs in the project files, then export
      ${env_name}=<the new id>
  (it must equal what the project declares; this script checks)."
  fi

  if [[ "$given" == "$personal" ]]; then
    _ami_channel_die "✗ --channel beta refused: ${env_name} is the personal-account ID (${personal}).
  A Beta build under the personal accounts is exactly what WP-49 / gate S7 exists to prevent."
  fi

  if [[ "$platform" == "ios" ]]; then
    declared="$(_ami_declared_ios_ids)"
  else
    declared="$(_ami_declared_android_id)"
  fi
  if [[ "$declared" != "$given" ]]; then
    _ami_channel_die "✗ --channel beta refused: ${env_name}=${given} but the project declares:
$(printf '%s\n' "${declared:-<none found>}" | sed 's/^/      /')
  The project files decide what is signed, not the environment. Finish the
  WP-49 identifier change in the project (and signing) first, then re-run."
  fi
}

# $1 = ios | android
ami_channel_setup() {
  local platform="$1"
  case "$CHANNEL" in
    alpha|beta) ;;
    *) _ami_channel_die "✗ unknown --channel '${CHANNEL}' (expected alpha or beta)" 2 ;;
  esac

  if [[ "$CHANNEL" == "alpha" ]]; then
    CHANNEL_API_URL="${AMI_API_URL_ALPHA}"
    CHANNEL_DEFINES=(
      "--dart-define=ALLOW_BACKEND_SWITCH=true"
      "--dart-define=AMI_API_URL_ALPHA=${AMI_API_URL_ALPHA}"
    )
    _ami_channel_report "$platform"
    return 0
  fi

  : "${AMI_API_URL_BETA:=${AMI_BETA_API_URL_DEFAULT}}"
  : "${SENTRY_DSN:=}"

  if [[ "${DO_GAMES:-0}" -eq 1 ]]; then
    _ami_channel_die "✗ --channel beta refused: AMI_GAMES is on.
  Beta reaches external testers and CR267 decision 10 is 'no features hidden'.
  Re-run with --no-games."
  fi

  _ami_beta_require_company_ids "$platform"

  if [[ "$platform" == "android" && -z "${AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID:-}" ]]; then
    _ami_channel_die "✗ --channel beta refused: AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID is not set.
  Google Sign-In audiences move to the company project in WP-49; the personal
  project's client ID baked as the Alpha default would sign testers in against
  the wrong audience. Export the company Web client ID."
  fi

  if [[ -z "$SENTRY_DSN" ]]; then
    _ami_channel_die "✗ --channel beta refused: SENTRY_DSN is empty.
  WP-53's crash-free figure comes from Sentry release health. A Beta build with
  no DSN would ship, run, and report nothing (CR267 WP-45). Export SENTRY_DSN."
  fi
  if [[ "$SENTRY_DSN" != https://*@* ]]; then
    _ami_channel_die "✗ --channel beta refused: SENTRY_DSN does not look like a DSN (expected https://<key>@<host>/<project>)."
  fi

  if [[ "$AMI_API_URL_BETA" != https://* ]]; then
    _ami_channel_die "✗ --channel beta refused: AMI_API_URL_BETA must be an https URL (got '${AMI_API_URL_BETA}')."
  fi

  CHANNEL_API_URL="${AMI_API_URL_BETA}"
  CHANNEL_DEFINES=(
    "--dart-define=ALLOW_BACKEND_SWITCH=false"
    "--dart-define=AMI_API_URL_PROD=${AMI_API_URL_BETA}"
    "--dart-define=AMI_BETA=true"
    "--dart-define=AMI_ENV=beta"
  )
  if [[ "$platform" == "ios" ]]; then
    # build_testflight.sh bakes no SENTRY_DSN on alpha; the Android script
    # passes its own on every channel, so only iOS needs it added here.
    CHANNEL_DEFINES+=("--dart-define=SENTRY_DSN=${SENTRY_DSN}")
  else
    GOOGLE_OAUTH_WEB_CLIENT_ID="${AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID}"
  fi
  _ami_channel_report "$platform"
}

# Prints the resolved configuration. Never prints the DSN or any key, only
# whether it is set.
_ami_channel_report() {
  local platform="$1" d shown
  echo "▶ release channel: ${CHANNEL} (${platform})"
  echo "  api url baked    : ${CHANNEL_API_URL}"
  for d in "${CHANNEL_DEFINES[@]}"; do
    case "$d" in
      --dart-define=SENTRY_DSN=*) shown="--dart-define=SENTRY_DSN=<set>" ;;
      *) shown="$d" ;;
    esac
    echo "  ${shown}"
  done
  if [[ "$CHANNEL" == "beta" ]]; then
    echo "  SENTRY_DSN       : <set>"
    if [[ "$platform" == "ios" ]]; then
      echo "  bundle id        : ${AMI_BETA_IOS_BUNDLE_ID}"
    else
      echo "  application id   : ${AMI_BETA_ANDROID_APPLICATION_ID}"
    fi
  fi
}

# Call after ami_channel_setup. --dry-run stops here: arguments parsed, channel
# refusals applied, resolved config printed, nothing built, bumped or uploaded.
ami_channel_dry_run_exit() {
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "▶ --dry-run: stopping before any gate, bump or build."
    exit 0
  fi
}
