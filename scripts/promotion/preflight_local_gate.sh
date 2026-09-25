#!/usr/bin/env bash
# Local release gate — Flutter tests + harness offline self-tests (CR235).
#
# Saiful, 2026-09-25, on the CI review: "move the Flutter tests and harness self-tests
# into the local release gate, where results are actually read." Measured that day: GitHub
# Actions on main last went green 2026-08-10; the harness job was red every run since 08-11;
# the backend job flapped 08-14->08-25 then took 5h13m on 09-17; every push cancels the
# previous run (11 consecutive cancels the day this was measured); and nothing in
# `/promote-to-alpha` ever read the CI result. A gate nobody reads is not a gate (same shape
# as DEF326/DEF405, one layer up: this time the check that never surfaced a failure isn't a
# pipe swallowing an exit code, it's a CI job nobody looks at). So the tests that must GATE
# move here, where `preflight_suite.sh`'s own VERDICT-line + exit-code + JSON-record
# discipline already applies and a human reads it every promotion.
#
# Two checks, same discipline as preflight_suite.sh:
#   1. `flutter test` — the ~620-case Flutter suite (CR162 first wired this into CI-only).
#   2. qa/appium's offline self-tests (`tests_offline/`) — locator dispatch, locale-vs-ARB,
#      crawler logic, the harness manifest check. No device needed; these are pure-logic
#      guards over the harness itself, same set CI already ran under "UAT harness (offline
#      guards)".
#
# Exit 0 both green · 1 either is not green · 2 could not run (missing Flutter, missing
# qa/appium/.venv — degrade loudly, CR040: a missing venv is a failure naming the exact
# command to fix it, never a silent skip that reads as a pass).
#
# Run bare — never through a pipe, a background task, or anything that reports its own exit
# code (DEF405). This gate also writes `.deliveryos/local_gate_verdict.json`, named after the
# commit it measured, on the same "the record survives what the wrapper swallows" logic.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT" || exit 2

GATE_SHA="$(git -C "$REPO_ROOT" rev-parse HEAD 2>/dev/null || echo unknown)"
VERDICT_FILE="$REPO_ROOT/.deliveryos/local_gate_verdict.json"
FLUTTER_VERDICT="SKIPPED"
HARNESS_VERDICT="SKIPPED"

record_verdict() {
  mkdir -p "$(dirname "$VERDICT_FILE")"
  printf '{"sha": "%s", "verdict": "%s", "flutter": "%s", "harness": "%s", "at": "%s"}\n' \
    "$GATE_SHA" "$1" "$FLUTTER_VERDICT" "$HARNESS_VERDICT" \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$VERDICT_FILE"
}

# ── 1. Flutter test ──────────────────────────────────────────────────────────

if ! command -v flutter >/dev/null 2>&1; then
  echo "VERDICT: FAIL — flutter not found on PATH, so the Flutter suite did not run."
  echo "         A suite that could not run is not a green suite."
  record_verdict COULD_NOT_RUN
  exit 2
fi

echo "▶ flutter test (mobile/) …"
( cd "$REPO_ROOT/mobile" && flutter test --reporter compact )
FLUTTER_EXIT=$?

if [ "$FLUTTER_EXIT" -ne 0 ]; then
  FLUTTER_VERDICT="FAIL"
  echo
  echo "VERDICT: FAIL — flutter test exited $FLUTTER_EXIT. Do not promote."
  record_verdict FAIL
  exit 1
fi
FLUTTER_VERDICT="PASS"
echo "  flutter test: PASS"

# ── 2. Harness offline self-tests ────────────────────────────────────────────
#
# Degrade loudly (CR040): a missing venv is not skipped, it is a named failure with the
# exact command to fix it — mirroring qa/appium/README.md's own bootstrap section.
if [ ! -x "$REPO_ROOT/qa/appium/.venv/bin/python" ]; then
  echo
  echo "VERDICT: FAIL — qa/appium/.venv not found, so the harness offline self-tests did not run."
  echo "         Create it: cd qa/appium && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  echo "         A suite that could not run is not a green suite."
  record_verdict COULD_NOT_RUN
  exit 2
fi

echo
echo "▶ qa/appium offline self-tests …"
( cd "$REPO_ROOT/qa/appium" && .venv/bin/python -m pytest tests_offline -q -p no:cacheprovider )
HARNESS_EXIT=$?

if [ "$HARNESS_EXIT" -ne 0 ]; then
  HARNESS_VERDICT="FAIL"
  echo
  echo "VERDICT: FAIL — qa/appium tests_offline exited $HARNESS_EXIT. Do not promote."
  record_verdict FAIL
  exit 1
fi
HARNESS_VERDICT="PASS"
echo "  tests_offline: PASS"

record_verdict PASS
echo
echo "VERDICT: PASS — flutter test and qa/appium tests_offline both exited 0."
exit 0
