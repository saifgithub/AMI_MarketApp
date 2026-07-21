#!/usr/bin/env bash
# AMI Trade — nightly analytics report generation (CR051).
#
# Runs on melehost via crontab. Regenerates each analytics report into
# $AMI_REPORT_DIR (default ~/ami_trade/reports/): a stable "latest" HTML + text
# file, plus a dated snapshot under archive/ for trend/history.
#
# Extensible by design — the whole point of a "reports generation shell": to add
# a new report, drop its generator next to this script and add one line to the
# `reports` array below (name | generator | extra-args). No other change.
#
# View: open $AMI_REPORT_DIR/<name>.html (scp it, or serve behind CF Access).
# No alerting — refresh/view on demand (Saiful, 2026-07-21).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPORT_DIR="${AMI_REPORT_DIR:-$HOME/ami_trade/reports}"
STAMP="$(date -u +%Y%m%d)"
mkdir -p "$REPORT_DIR/archive"

# name | generator script (beside this file) | extra args passed before --out
reports=(
  "daily_usage|daily_report.py|--local"
)

log() { printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }

rc=0
for spec in "${reports[@]}"; do
  IFS='|' read -r name script args <<< "$spec"
  out="$REPORT_DIR/$name.html"
  txt="$REPORT_DIR/$name.txt"
  log "generating $name -> $out"
  # generator prints the text summary to stdout, writes HTML to --out.
  if python3 "$SCRIPT_DIR/$script" $args --out "$out" > "$txt" 2>>"$REPORT_DIR/generate.err"; then
    cp -f "$out" "$REPORT_DIR/archive/${name}_${STAMP}.html"
    log "  ok ($(wc -c <"$out") bytes)"
  else
    log "  FAILED — see $REPORT_DIR/generate.err"
    rc=1
  fi
done

# keep ~2 months of dated snapshots
find "$REPORT_DIR/archive" -name '*.html' -mtime +60 -delete 2>/dev/null || true
exit "$rc"
