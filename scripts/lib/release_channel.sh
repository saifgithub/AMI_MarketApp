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
#   ONESIGNAL_APP_ID=<beta app>   WP-49: the Beta OneSignal app (APNs key is team-bound)
#   SENTRY_DSN=<dsn>              required: WP-53's crash-free figure is Sentry
#                                 release health, so a Beta build with no DSN
#                                 would measure nothing and say nothing.
#
# The locked mode of a no-switch build is named `prod` inside the app
# (BackendUrls.lockedMode), so a Beta build's URL rides in the `_PROD` slot.
# That is a naming quirk of the existing mode plumbing, not a Prod backend.

# CR267 WP-49 (prep): every company-account value comes from a gitignored env
# file, never from a default baked into a script. mobile/beta_accounts.env.example
# lists every key. A key already exported in the environment wins over the file
# (so tests and one-off overrides work). The file is PARSED, not sourced: only
# KEY=VALUE lines for the known keys below are read; nothing in it is executed.
# Alpha never reads this file and never sees these variables.
AMI_BETA_ACCOUNTS_ENV="${AMI_BETA_ACCOUNTS_ENV:-${PROJECT_ROOT}/mobile/beta_accounts.env}"

AMI_BETA_API_URL_DEFAULT="https://api-beta.agenticmarketintel.ai"

# The founder's personal-account identifiers, as shipped today. A Beta build
# may not carry any of them (CR267 WP-49 / gate S7): each is a copy-paste away
# from shipping a "company" build that is really wired to the personal account.
AMI_PERSONAL_IOS_BUNDLE_ID="ai.agenticmarketintel.amiTrade"
AMI_PERSONAL_ANDROID_APPLICATION_ID="ai.agenticmarketintel.ami_trade"
AMI_PERSONAL_APPLE_TEAM_ID="S7RBWM4879"
AMI_PERSONAL_ASC_KEY_ID="44VJ5WADL2"
AMI_PERSONAL_ASC_ISSUER="289e6201-8fc9-44a3-abde-59e8e278527c"
AMI_PERSONAL_ONESIGNAL_APP_ID="3c2020b6-d8b0-493f-b0e3-5d6ede868d7b"
AMI_PERSONAL_GOOGLE_WEB_CLIENT_ID="153141744056-03d6sabmvita0a2civs6e0ngjoac54v7.apps.googleusercontent.com"
AMI_PERSONAL_KEYSTORE_PROPERTIES="${HOME}/.android-keys/keystore.properties"
AMI_PERSONAL_PLAY_SERVICE_ACCOUNT="${HOME}/.android-keys/play-service-account.json"

# Keys the env file may set. Anything else in the file is ignored.
AMI_BETA_ACCOUNT_KEYS=(
  AMI_BETA_IOS_BUNDLE_ID AMI_BETA_APPLE_TEAM_ID
  AMI_BETA_APP_STORE_API_KEY_ID AMI_BETA_APP_STORE_API_ISSUER
  AMI_BETA_ANDROID_APPLICATION_ID AMI_BETA_ANDROID_KEYSTORE_PROPERTIES
  AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID
  AMI_BETA_ONESIGNAL_APP_ID AMI_BETA_REVENUECAT_IOS_SDK_KEY
  AMI_BETA_REVENUECAT_ANDROID_SDK_KEY AMI_API_URL_BETA SENTRY_DSN
)

_ami_beta_load_accounts_env() {
  [[ -f "$AMI_BETA_ACCOUNTS_ENV" ]] || return 0
  local line key val k
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*([A-Z0-9_]+)=(.*)$ ]] || continue
    key="${BASH_REMATCH[1]}"
    val="${BASH_REMATCH[2]}"
    val="${val%"${val##*[![:space:]]}"}"
    if [[ "$val" == \"*\" || "$val" == \'*\' ]]; then val="${val:1:${#val}-2}"; fi
    for k in "${AMI_BETA_ACCOUNT_KEYS[@]}"; do
      if [[ "$k" == "$key" && -z "${!key:-}" && -n "$val" ]]; then
        export "$key=$val"
      fi
    done
  done < "$AMI_BETA_ACCOUNTS_ENV"
}

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

# One-line description per key, used in the refusal message.
_ami_beta_key_desc() {
  case "$1" in
    AMI_BETA_IOS_BUNDLE_ID) echo "company iOS bundle ID" ;;
    AMI_BETA_APPLE_TEAM_ID) echo "company Apple Developer Team ID (10 chars)" ;;
    AMI_BETA_APP_STORE_API_KEY_ID) echo "company App Store Connect API key ID (10 chars)" ;;
    AMI_BETA_APP_STORE_API_ISSUER) echo "company App Store Connect issuer UUID" ;;
    AMI_BETA_ANDROID_APPLICATION_ID) echo "company Play package name / applicationId" ;;
    AMI_BETA_ANDROID_KEYSTORE_PROPERTIES) echo "path to the company upload keystore.properties" ;;
    AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON) echo "path to the company Play service-account JSON" ;;
    AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID) echo "company Google OAuth Web client ID" ;;
    AMI_BETA_ONESIGNAL_APP_ID) echo "the Beta OneSignal app ID (APNs key is team-bound)" ;;
    *) echo "" ;;
  esac
}

_ami_chk_personal() { # $1 key, $2 personal value; appends to $personal in caller
  local v="${!1:-}"
  if [[ -n "$v" && "$v" == "$2" ]]; then
    personal+=("$1=$v")
  fi
  return 0
}

# Refuses ONCE, naming every missing or personal-account key, so the founder
# fixes the env file in one pass rather than one refusal at a time.
_ami_beta_require_company_ids() {
  local platform="$1" k missing=() personal=() bad=() keys=()
  if [[ "$platform" == "ios" ]]; then
    keys=(AMI_BETA_IOS_BUNDLE_ID AMI_BETA_APPLE_TEAM_ID AMI_BETA_APP_STORE_API_KEY_ID
          AMI_BETA_APP_STORE_API_ISSUER AMI_BETA_ONESIGNAL_APP_ID)
  else
    keys=(AMI_BETA_ANDROID_APPLICATION_ID AMI_BETA_ANDROID_KEYSTORE_PROPERTIES
          AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID AMI_BETA_ONESIGNAL_APP_ID)
    if [[ "${AMI_CHANNEL_NEEDS_PLAY_UPLOAD:-0}" -eq 1 ]]; then
      keys+=(AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON)
    fi
  fi

  for k in "${keys[@]}"; do
    [[ -n "${!k:-}" ]] || missing+=("$k")
  done

  _ami_chk_personal AMI_BETA_IOS_BUNDLE_ID "$AMI_PERSONAL_IOS_BUNDLE_ID"
  _ami_chk_personal AMI_BETA_ANDROID_APPLICATION_ID "$AMI_PERSONAL_ANDROID_APPLICATION_ID"
  _ami_chk_personal AMI_BETA_APPLE_TEAM_ID "$AMI_PERSONAL_APPLE_TEAM_ID"
  _ami_chk_personal AMI_BETA_APP_STORE_API_KEY_ID "$AMI_PERSONAL_ASC_KEY_ID"
  _ami_chk_personal AMI_BETA_APP_STORE_API_ISSUER "$AMI_PERSONAL_ASC_ISSUER"
  _ami_chk_personal AMI_BETA_ONESIGNAL_APP_ID "$AMI_PERSONAL_ONESIGNAL_APP_ID"
  _ami_chk_personal AMI_BETA_GOOGLE_OAUTH_WEB_CLIENT_ID "$AMI_PERSONAL_GOOGLE_WEB_CLIENT_ID"
  _ami_chk_personal AMI_BETA_ANDROID_KEYSTORE_PROPERTIES "$AMI_PERSONAL_KEYSTORE_PROPERTIES"
  _ami_chk_personal AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON "$AMI_PERSONAL_PLAY_SERVICE_ACCOUNT"

  if [[ -n "${AMI_BETA_APPLE_TEAM_ID:-}" && ! "$AMI_BETA_APPLE_TEAM_ID" =~ ^[A-Z0-9]{10}$ ]]; then
    bad+=("AMI_BETA_APPLE_TEAM_ID must be 10 upper-case letters/digits")
  fi
  for k in AMI_BETA_IOS_BUNDLE_ID AMI_BETA_ANDROID_APPLICATION_ID; do
    if [[ -n "${!k:-}" && ! "${!k}" =~ ^[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z][A-Za-z0-9_-]*)+$ ]]; then
      bad+=("${k} is not a valid reverse-DNS id (${!k})")
    fi
  done

  if (( ${#missing[@]} + ${#personal[@]} + ${#bad[@]} == 0 )); then
    return 0
  fi

  {
    echo "✗ --channel beta refused: the company-account configuration is incomplete."
    echo "  A Beta build must be signed and wired under the COMPANY store accounts"
    echo "  (CR267 WP-49 / gate S7; docs/forward_planning/CR258_company_account_migration/)."
    echo "  Fill ${AMI_BETA_ACCOUNTS_ENV} (template: mobile/beta_accounts.env.example)"
    echo "  or export the keys. Alpha builds are unaffected."
    if (( ${#missing[@]} )); then
      echo "  Missing:"
      for k in "${missing[@]}"; do echo "    - ${k}: $(_ami_beta_key_desc "$k")"; done
    fi
    if (( ${#personal[@]} )); then
      echo "  Set to the founder's PERSONAL-account value (a Beta build under it is what WP-49 prevents):"
      for k in "${personal[@]}"; do echo "    - ${k}"; done
    fi
    if (( ${#bad[@]} )); then
      echo "  Malformed:"
      for k in "${bad[@]}"; do echo "    - ${k}"; done
    fi
  } >&2
  exit 1
}

# ── Beta account wiring (CR267 WP-49 prep) ──────────────────────────────────
# Called by the scripts AFTER --dry-run exits, so dry-run never touches a file
# or needs a credential. They change what the BETA build is signed/wired with;
# for alpha they do nothing beyond clearing the Gradle/fastlane variables they own.

_AMI_BETA_PBX_BACKUP=""

_ami_beta_restore_project() {
  local pbx="${PROJECT_ROOT}/mobile/ios/Runner.xcodeproj/project.pbxproj"
  if [[ -n "$_AMI_BETA_PBX_BACKUP" && -f "$_AMI_BETA_PBX_BACKUP" ]]; then
    cp "$_AMI_BETA_PBX_BACKUP" "$pbx"
    rm -f "$_AMI_BETA_PBX_BACKUP"
    _AMI_BETA_PBX_BACKUP=""
    echo "▶ restored the Xcode project to the personal (Alpha) settings"
  fi
}

# iOS: credentials, export options, RevenueCat key. Sets BETA_EXPORT_OPTIONS for
# the script to use instead of ios/ExportOptions.plist.
ami_beta_ios_prepare() {
  [[ "$CHANNEL" == "beta" ]] || return 0
  APP_STORE_API_KEY_ID="$AMI_BETA_APP_STORE_API_KEY_ID"
  APP_STORE_API_ISSUER="$AMI_BETA_APP_STORE_API_ISSUER"
  # Never inherit Alpha's RevenueCat key: it belongs to the personal app and
  # bundle ID. Empty makes the script's own "no key" gate demand --no-billing.
  REVENUECAT_IOS_SDK_KEY="${AMI_BETA_REVENUECAT_IOS_SDK_KEY:-}"

  local src="${PROJECT_ROOT}/mobile/ios/ExportOptions.plist"
  local out="${PROJECT_ROOT}/mobile/build/ExportOptions.beta.plist"
  [[ -f "$src" ]] || _ami_channel_die "✗ ${src} not found"
  mkdir -p "$(dirname "$out")"
  sed "s|<string>${AMI_PERSONAL_APPLE_TEAM_ID}</string>|<string>${AMI_BETA_APPLE_TEAM_ID}</string>|" \
    "$src" > "$out"
  if ! grep -q "<string>${AMI_BETA_APPLE_TEAM_ID}</string>" "$out" \
     || grep -q "$AMI_PERSONAL_APPLE_TEAM_ID" "$out"; then
    _ami_channel_die "✗ could not set the company teamID in the Beta export options (ExportOptions.plist no longer carries ${AMI_PERSONAL_APPLE_TEAM_ID}?)"
  fi
  BETA_EXPORT_OPTIONS="$out"
}

# iOS: the Xcode project, not the environment, decides the bundle ID and team.
# Patch the Runner target (and RunnerTests' id suffix) for the duration of the
# build and restore on any exit. Alpha never calls the patch, so the committed
# project file stays byte-identical for it.
ami_beta_ios_patch_project() {
  [[ "$CHANNEL" == "beta" ]] || return 0
  local pbx="${PROJECT_ROOT}/mobile/ios/Runner.xcodeproj/project.pbxproj"
  [[ -f "$pbx" ]] || _ami_channel_die "✗ ${pbx} not found"
  if ! grep -q "PRODUCT_BUNDLE_IDENTIFIER = ${AMI_PERSONAL_IOS_BUNDLE_ID};" "$pbx" \
     || ! grep -q "DEVELOPMENT_TEAM = ${AMI_PERSONAL_APPLE_TEAM_ID};" "$pbx"; then
    _ami_channel_die "✗ the Xcode project is not in its pristine personal-account state (a previous Beta build died mid-run?).
  Restore it with: git checkout -- mobile/ios/Runner.xcodeproj/project.pbxproj"
  fi
  _AMI_BETA_PBX_BACKUP="$(mktemp "${TMPDIR:-/tmp}/ami_pbx_backup.XXXXXX")"
  cp "$pbx" "$_AMI_BETA_PBX_BACKUP"
  trap _ami_beta_restore_project EXIT
  sed -i.betabak \
    -e "s|PRODUCT_BUNDLE_IDENTIFIER = ${AMI_PERSONAL_IOS_BUNDLE_ID};|PRODUCT_BUNDLE_IDENTIFIER = ${AMI_BETA_IOS_BUNDLE_ID};|" \
    -e "s|PRODUCT_BUNDLE_IDENTIFIER = ${AMI_PERSONAL_IOS_BUNDLE_ID}\.RunnerTests;|PRODUCT_BUNDLE_IDENTIFIER = ${AMI_BETA_IOS_BUNDLE_ID}.RunnerTests;|" \
    -e "s|DEVELOPMENT_TEAM = ${AMI_PERSONAL_APPLE_TEAM_ID};|DEVELOPMENT_TEAM = ${AMI_BETA_APPLE_TEAM_ID};|" \
    "$pbx"
  rm -f "${pbx}.betabak"
  local declared
  declared="$(_ami_declared_ios_ids)"
  if [[ "$declared" != "$AMI_BETA_IOS_BUNDLE_ID" ]] \
     || grep -q "$AMI_PERSONAL_APPLE_TEAM_ID" "$pbx"; then
    _ami_beta_restore_project
    _ami_channel_die "✗ patching the Xcode project for Beta did not produce ${AMI_BETA_IOS_BUNDLE_ID} / ${AMI_BETA_APPLE_TEAM_ID} (found: ${declared:-none})"
  fi
  echo "▶ Xcode project patched for this Beta build: ${AMI_BETA_IOS_BUNDLE_ID}, team ${AMI_BETA_APPLE_TEAM_ID} (restored on exit)"
}

# Android: Gradle reads AMI_GRADLE_APPLICATION_ID / AMI_GRADLE_KEYSTORE_PROPERTIES
# and fastlane reads AMI_PLAY_PACKAGE_NAME; unset, they fall back to the personal
# values, which is exactly Alpha's behaviour. This function owns those three
# variables: it clears them for alpha (a stray export in the shell cannot
# re-point an Alpha build) and sets them for beta.
ami_beta_android_prepare() {
  unset AMI_GRADLE_APPLICATION_ID AMI_GRADLE_KEYSTORE_PROPERTIES AMI_PLAY_PACKAGE_NAME
  [[ "$CHANNEL" == "beta" ]] || return 0

  local props="$AMI_BETA_ANDROID_KEYSTORE_PROPERTIES"
  if [[ ! -f "$props" ]] || ! grep -q '^storeFile=' "$props"; then
    _ami_channel_die "✗ --channel beta refused: AMI_BETA_ANDROID_KEYSTORE_PROPERTIES (${props}) is missing or has no storeFile=.
  Gradle would fall back to DEBUG signing and Play would reject the AAB; the Beta
  upload key must be the company one. Create it first (see the WP-49 prep doc)."
  fi
  export AMI_GRADLE_APPLICATION_ID="$AMI_BETA_ANDROID_APPLICATION_ID"
  export AMI_GRADLE_KEYSTORE_PROPERTIES="$props"
  export AMI_PLAY_PACKAGE_NAME="$AMI_BETA_ANDROID_APPLICATION_ID"
  BETA_KEYSTORE_PROPS="$props"
  REVENUECAT_ANDROID_SDK_KEY="${AMI_BETA_REVENUECAT_ANDROID_SDK_KEY:-}"
  if [[ "${AMI_CHANNEL_NEEDS_PLAY_UPLOAD:-0}" -eq 1 ]]; then
    export SUPPLY_JSON_KEY="$AMI_BETA_PLAY_SERVICE_ACCOUNT_JSON"
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

  _ami_beta_load_accounts_env
  : "${AMI_API_URL_BETA:=${AMI_BETA_API_URL_DEFAULT}}"
  : "${SENTRY_DSN:=}"

  if [[ "${DO_GAMES:-0}" -eq 1 ]]; then
    _ami_channel_die "✗ --channel beta refused: AMI_GAMES is on.
  Beta reaches external testers and CR267 decision 10 is 'no features hidden'.
  Re-run with --no-games."
  fi

  _ami_beta_require_company_ids "$platform"

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
    "--dart-define=ONESIGNAL_APP_ID=${AMI_BETA_ONESIGNAL_APP_ID}"
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
    echo "  accounts env     : ${AMI_BETA_ACCOUNTS_ENV}"
    if [[ "$platform" == "ios" ]]; then
      echo "  bundle id        : ${AMI_BETA_IOS_BUNDLE_ID}"
      echo "  apple team id    : ${AMI_BETA_APPLE_TEAM_ID}"
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
