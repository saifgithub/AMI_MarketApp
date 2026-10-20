#!/usr/bin/env bash
# Nightly full UAT run (CR263) — launched at 03:00 local by launchd
# (scripts/uat/install_nightly.sh). Saiful, 2026-10-19: "a full test run using
# the simulator daily, say at 3am automatically".
#
# Full, not --changed-only: the nightly is the run that catches drift nobody
# touched — Alpha config, market data, the LLM serve. Runs the live-Alpha API
# layer and the iOS Simulator layer, records both in the ledger (so a green
# night also satisfies the release gate for the current code), posts a macOS
# notification with the verdict, and prunes runs older than 14 days.

set -uo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
RUNS="${PROJECT_ROOT}/qa/uat/_runs"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH}"

mkdir -p "$RUNS"
echo "=== nightly UAT $(date -u +%FT%TZ) @ $(git -C "$PROJECT_ROOT" rev-parse --short HEAD)"

"${PROJECT_ROOT}/scripts/uat/run_uat.sh" --all
rc=$?

latest="$(ls -1d "${RUNS}"/20*/ 2>/dev/null | sort | tail -1)"
summary="$(grep -E '^[0-9]+\. \*\*' "${latest}report.md" 2>/dev/null | sed 's/\*\*//g' | tr '\n' ' ')"
if (( rc == 0 )); then title="AMI UAT nightly: PASS"; else title="AMI UAT nightly: FAIL"; fi
osascript -e "display notification \"${summary:-no results} — ${latest}report.md\" with title \"${title}\"" 2>/dev/null || true
echo "${title} — ${summary} — ${latest}report.md"

# CR264 every-control crawl — reported, not counted in the nightly verdict
# while UAT-CTRL-001 is parked (Saiful, 2026-10-20).
AMI_CRAWL_CAP=7200 "${PROJECT_ROOT}/scripts/uat/run_uat.sh" --device ios --no-build --exhaustive || true

find "$RUNS" -mindepth 1 -maxdepth 1 -type d -name '20*' -mtime +14 -exec rm -rf {} + 2>/dev/null
exit "$rc"
